# Muesli M3 Implementation Plan: Speaker Diarization + Packaging

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add speaker-attributed transcripts (deterministic "You" from a separate mic stream + ONNX ML clustering to split remote speakers) and ship Muesli as a Windows installer (PyInstaller + Inno Setup) with detect-and-guide onboarding for Ollama/WebView2/models.

**Architecture:** Keep the engine/UI boundary. Capture mic and loopback as two time-aligned WAVs. Transcription preserves segments; a new `diarize/` module runs `sherpa-onnx` (onnxruntime-based, no PyTorch) on the loopback stream to split remote speakers, then pure merge/label functions produce an ordered, speaker-tagged transcript stored as segments. Packaging bundles the final dependency set; models and external tools are detected, not bundled.

**Tech Stack:** Python 3.11+, FastAPI, faster-whisper, **sherpa-onnx** (+ bundled onnxruntime) for speaker diarization, SQLite/FTS5; React/TS/Vite UI; PyInstaller + Inno Setup for the installer.

**Design spec:** `docs/superpowers/specs/2026-06-09-muesli-m3-diarization-packaging-design.md`

---

## Scope Check

Two bounded features from M3: speaker diarization and a Windows installer. Live transcript and calendar auto-detect remain out of scope. Part A lands before Part B so the installer captures the real dependency footprint.

## Confirmed external components

- **Library:** `sherpa-onnx` (pip; ships onnxruntime, no torch). Provides `OfflineSpeakerDiarization` = pyannote segmentation ONNX + a speaker-embedding ONNX + built-in clustering.
- **Segmentation model:** `sherpa-onnx-pyannote-segmentation-3-0` (from the sherpa-onnx model releases).
- **Embedding model:** a WeSpeaker English ONNX export, e.g. `wespeaker_en_voxceleb_resnet34.onnx` (Apache-2.0), from `https://github.com/k2-fsa/sherpa-onnx/releases/tag/speaker-recongition-models`.
- Models are **downloaded on first use** to `APP_DIR/models`, never bundled.

---

# Part A: Speaker Diarization

## Task A1: Storage — segments, speaker labels, dual audio paths (TDD)

**Files:**
- Modify: `engine/muesli_engine/storage/models.py`
- Modify: `engine/muesli_engine/storage/db.py`
- Modify: `engine/tests/test_storage.py`

- [ ] **Step 1: Extend models**

In `models.py` add a `Segment` model and extend `Meeting`:

```python
class Segment(BaseModel):
    id: int | None = None
    meeting_id: int
    start: float
    end: float
    speaker_key: str          # "you" | "spk1" | "spk2" ...
    source: str               # "mic" | "loopback"
    text: str


class Meeting(BaseModel):
    id: int | None = None
    title: str
    created_at: datetime
    audio_path: str | None = None        # deprecated alias of loopback_path
    loopback_path: str | None = None
    mic_path: str | None = None
    rough_notes: str = ""
    transcript: str = ""
    enhanced_notes: str = ""
    template_id: int | None = None
    status: str = "recording"
    diarized: bool = False
```

- [ ] **Step 2: Write failing storage tests**

Add to `tests/test_storage.py` tests covering: storing/reading segments for a meeting (ordered by start), upserting a speaker display name and resolving it, and a forward migration that opens a pre-M3 DB (no new columns/tables) without error. Use the existing `make_db()` helper.

- [ ] **Step 3: Schema + migration in `db.py`**

Add to `SCHEMA` (all `IF NOT EXISTS`):

```sql
CREATE TABLE IF NOT EXISTS transcript_segments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    meeting_id INTEGER NOT NULL,
    start REAL NOT NULL,
    end REAL NOT NULL,
    speaker_key TEXT NOT NULL,
    source TEXT NOT NULL,
    text TEXT NOT NULL,
    FOREIGN KEY(meeting_id) REFERENCES meetings(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS speaker_labels (
    meeting_id INTEGER NOT NULL,
    speaker_key TEXT NOT NULL,
    display_name TEXT NOT NULL,
    PRIMARY KEY (meeting_id, speaker_key)
);
```

Add an idempotent `_migrate()` (called from `init_schema` after `executescript`) that `ALTER TABLE meetings ADD COLUMN` for `loopback_path`, `mic_path`, and `diarized` when absent (read `PRAGMA table_info(meetings)` first). Keep `audio_path` for back-compat; `set_audio_path` should also set `loopback_path`.

Add methods: `replace_segments(meeting_id, list[Segment])` (delete then bulk insert in one transaction), `list_segments(meeting_id) -> list[Segment]` (ordered by `start, id`), `set_speaker_name(meeting_id, key, name)` (upsert), `get_speaker_names(meeting_id) -> dict[str,str]`, `set_audio_paths(meeting_id, loopback, mic)`, `set_diarized(meeting_id, bool)`. Update `_row_to_meeting` for the new columns.

- [ ] **Step 4: Run tests + commit**

`cd engine && .venv/Scripts/python -m pytest tests/test_storage.py -v` → green.
Commit: `feat: store transcript segments and speaker labels`.

## Task A2: Dual-stream recorder

**Files:**
- Modify: `engine/muesli_engine/audio/capture.py`

- [ ] **Step 1: Add a mic stream alongside loopback**

Generalize `Recorder` to capture two streams concurrently. Keep the existing loopback device discovery; add a default-input (mic) stream. Each stream runs its own read loop/thread and frame buffer. Record `time.monotonic()` at the moment each stream's first frame is read so downstream code can align them.

`stop()` returns a `dict` (not a single path): `{"loopback": <path>, "mic": <path|None>, "mic_offset": <float>}`. Write `{id}-loopback.wav` and `{id}-mic.wav`. If no input device is available, log it, skip the mic stream, and return `mic=None` (graceful degradation to loopback-only). Keep a thin back-compat: if a caller passes a single `out_path`, derive the two sibling paths from it.

> Not unit-tested (needs real devices). Verified in Task A6.

- [ ] **Step 2: Commit** — `feat: capture mic and loopback as separate streams`.

## Task A3: Segment-preserving transcription + diarization pipeline (TDD the pure parts)

**Files:**
- Modify: `engine/muesli_engine/transcribe/whisper.py`
- Create: `engine/muesli_engine/diarize/__init__.py`
- Create: `engine/muesli_engine/diarize/pipeline.py`
- Create: `engine/muesli_engine/diarize/merge.py`
- Create: `engine/tests/test_diarize.py`
- Modify: `engine/requirements.txt`

- [ ] **Step 1: Preserve segments in transcription**

Add `transcribe_segments(path, settings) -> list[dict]` returning `[{"start", "end", "text"}, ...]` from faster-whisper (keep the existing `transcribe_wav` as a thin join wrapper for any flat-string callers). Empty/missing path → `[]`.

- [ ] **Step 2: Add `sherpa-onnx` to requirements**

Append to `engine/requirements.txt`:

```
sherpa-onnx==1.*
scipy==1.*   # only if clustering helpers are needed outside sherpa
```

- [ ] **Step 3: Write failing tests for the pure merge/label functions**

`tests/test_diarize.py` covers `merge.py` only (no models):

- `assign_speakers(loopback_segments, diar_turns)` labels each whisper segment with the speaker of the maximally-overlapping diarization turn; a segment overlapping nothing gets `spk1`.
- `merge_streams(mic_segments, loopback_segments)` returns one list ordered by `start`, mic segments labeled `you`, interleaved correctly with loopback labels.
- `attributed_transcript(segments, name_map)` renders `"You: ...\nAlice: ..."`, resolving `speaker_key` through `name_map` and falling back to a humanized key (`spk1` → `Speaker 1`).

- [ ] **Step 4: Implement `merge.py` (pure)**

Implement the three functions above. `assign_speakers` uses interval-overlap max; deterministic tie-break by lowest speaker index. `humanize_key("spk1") -> "Speaker 1"`, `humanize_key("you") -> "You"`.

- [ ] **Step 5: Implement `pipeline.py` (model-backed, not unit-tested)**

```python
def diarize_meeting(loopback_path, mic_path, mic_offset, settings) -> list[Segment-dicts]:
    # 1. transcribe_segments(mic_path)  -> label "you", shift by mic_offset
    # 2. transcribe_segments(loopback_path)
    # 3. diar_turns = _run_sherpa_diarization(loopback_path, settings)  # OfflineSpeakerDiarization
    # 4. assign_speakers(loopback_segments, diar_turns)
    # 5. return merge_streams(mic_segments, loopback_segments)
```

`_run_sherpa_diarization` lazily builds `sherpa_onnx.OfflineSpeakerDiarization` from the segmentation + embedding ONNX paths under `APP_DIR/models` (downloaded in Part B Task B2 / first-run). Use a clustering threshold from settings; when `mic_path is None`, still diarize loopback but skip step 1.

- [ ] **Step 6: Run tests + commit**

`pytest tests/test_diarize.py -v` → green.
Commit: `feat: add diarization pipeline and segment merge`.

## Task A4: Wire diarization into the API + enhancement

**Files:**
- Modify: `engine/muesli_engine/app.py`
- Modify: `engine/muesli_engine/api/routes.py`
- Modify: `engine/muesli_engine/config.py`
- Modify: `engine/tests/test_api.py`

- [ ] **Step 1: Settings for diarization**

In `config.py` add to `Settings`: `enable_diarization: bool = True`, `diarization_threshold: float = 0.5`, `mic_device: str | None = None`. Surface them in `SettingsUpdate` and `settings_payload()` in `routes.py`.

- [ ] **Step 2: Dual-path recording + diarize seam in `EngineContext`**

In `app.py`: `start_recording` keeps using one `Recorder` but now consumes its dict result on stop. Add a `diarize_fn` seam (default → `diarize.pipeline.diarize_meeting`, overridable in tests with a stub). `stop_recording` returns the paths dict; the stop route persists both via `db.set_audio_paths(...)`.

- [ ] **Step 3: Transcribe route diarizes when enabled**

Rewrite the `/meetings/{id}/transcribe` handler: if `settings.enable_diarization` and a loopback path exists, call `ctx.diarize_fn(...)`, `db.replace_segments(...)`, set `diarized=True`, and write the **attributed** flat transcript (via `attributed_transcript`) into the `transcript` column (keeps FTS working). Otherwise fall back to the existing flat `transcribe_fn` path. Return the meeting.

- [ ] **Step 4: New endpoints**

- `GET /meetings/{id}/segments` → `db.list_segments` joined with `get_speaker_names` for display names.
- `PUT /meetings/{id}/speakers` body `{speaker_key, display_name}` → `db.set_speaker_name`; rebuild and re-store the attributed `transcript` string so search/enhance reflect the rename.

- [ ] **Step 5: Attributed transcript into enhancement**

The enhance route already passes `meeting.transcript`; since that column now holds the attributed string, the LLM sees `You:/Speaker N:` turns and can assign owners. No prompt change required, but update `build_prompt`'s transcript heading comment to note speaker attribution.

- [ ] **Step 6: Update `test_api.py`**

Construct the app with a stub `diarize_fn` returning canned segments (no models). Assert: transcribe persists segments, `GET /segments` returns them ordered, renaming a speaker updates the attributed transcript, and `enable_diarization=False` still works via the flat path. Keep existing lifecycle tests green.

- [ ] **Step 7: Run full engine suite + commit**

`cd engine && .venv/Scripts/python -m pytest -q` → green.
Commit: `feat: diarized transcribe, segments and speaker rename API`.

## Task A5: Frontend — segmented transcript, rename, settings

**Files:**
- Modify: `ui/src/api/client.ts`
- Modify: `ui/src/pages/MeetingDetail.tsx`
- Modify: `ui/src/pages/Settings.tsx`
- Create: `ui/src/components/SpeakerTranscript.tsx`
- Modify: `ui/src/styles.css`

- [ ] **Step 1: API client**

Add `Segment` type (`start, end, speaker_key, display_name, source, text`), extend `Meeting` with `loopback_path/mic_path/diarized`, and add `getSegments(id)`, `renameSpeaker(id, key, name)`. Add the new settings fields to the settings client calls.

- [ ] **Step 2: `SpeakerTranscript` component**

Render segments as speaker-tagged turns: a colored chip per distinct `speaker_key` (stable color hash), the display name (inline-editable → `renameSpeaker`, then refetch), and the turn text. Group consecutive same-speaker segments. Empty → existing "Nothing here yet."

- [ ] **Step 3: MeetingDetail transcript tab**

When `meeting.diarized` and segments exist, render `<SpeakerTranscript>`; otherwise fall back to the current flat `<pre>` (pre-M3 meetings still open). Fetch segments alongside the meeting.

- [ ] **Step 4: Settings**

Add a "Transcription & speakers" section: toggle `enable_diarization`, a clustering-sensitivity (threshold) control, and an optional mic-device note/field. Wire to the settings API.

- [ ] **Step 5: Build + commit**

`npm --prefix ui run build` → succeeds. Commit: `feat: speaker-attributed transcript UI`.

## Task A6: Diarization verification

- [ ] Run engine + UI test suites and build.
- [ ] Manual E2E with a multi-speaker clip + speaking into the mic: Start → talk → Stop → Transcribe. Confirm: "You" turns come from the mic, remote speakers split into Speaker 1/2, rename persists and updates enhanced-note attribution, and a 1:1 collapses remote to a single speaker.
- [ ] Confirm loopback-only (no mic) still produces a usable diarized transcript.
- [ ] Commit any focused fixes: `fix: polish diarization verification`.

---

# Part B: Packaging + Installer

## Task B1: PyInstaller bundle (onedir)

**Files:**
- Create: `packaging/muesli.spec`
- Create: `packaging/README.md`
- Modify: `.gitignore` (add `build/`, `dist/`, `*.spec` exceptions as needed)

- [ ] **Step 1: Author `muesli.spec`**

onedir bundle of `run.py`. `datas` includes `ui/dist`. `hiddenimports` includes `faster_whisper`, `ctranslate2`, `sherpa_onnx`, `onnxruntime`, uvicorn protocol/loop modules, `pyaudiowpatch`. Collect native binaries for ctranslate2/onnxruntime/sherpa-onnx/pywebview. Do **not** bundle model weights.

- [ ] **Step 2: Build + smoke test**

`pyinstaller packaging/muesli.spec` → `dist/Muesli/Muesli.exe` launches, serves UI, window opens. Record any missing hidden imports and add them. Commit: `build: add PyInstaller bundle spec`.

## Task B2: First-run, model download, health endpoint

**Files:**
- Create: `engine/muesli_engine/models_store.py`
- Modify: `engine/muesli_engine/config.py` (add `MODELS_DIR = APP_DIR / "models"`, ensure in `ensure_dirs`)
- Modify: `engine/muesli_engine/api/routes.py`
- Modify: `engine/tests/test_api.py`

- [ ] **Step 1: Model resolver/downloader**

`models_store.py`: `ensure_diarization_models()` downloads the segmentation + embedding ONNX into `MODELS_DIR` if absent (checksum-verified), returning their paths; the diarization pipeline reads from here. Whisper models continue to resolve through faster-whisper's own cache (point it at `MODELS_DIR` via env if convenient).

- [ ] **Step 2: `GET /health`**

Return JSON: `ollama` reachable at `settings.ollama_host` (reuse `llm.list_ollama_models` with a short timeout), `webview2` present (registry check on Windows, else `null`), `diarization_models` present, `whisper_model` present. No exceptions escape — each check degrades to `false`/`null`.

- [ ] **Step 3: Tests + commit**

Unit-test the health payload shape with stubbed checkers. Commit: `feat: health checks and first-run model download`.

## Task B3: Onboarding UI

**Files:**
- Create: `ui/src/pages/Onboarding.tsx` (or a dismissible banner component)
- Modify: `ui/src/App.tsx`, `ui/src/api/client.ts`

- [ ] **Step 1: Health-driven onboarding**

`getHealth()` client call. On app load, if any prerequisite is missing, show a card: Ollama missing → install link + `ollama pull <model>` + "switch to cloud backend" shortcut; WebView2 missing → Evergreen installer link; models missing → "downloading…" / trigger. Dismissible once healthy.

- [ ] **Step 2: Build + commit** — `feat: first-run onboarding for prerequisites`.

## Task B4: Inno Setup installer + build script

**Files:**
- Create: `packaging/muesli.iss`
- Create: `build_installer.ps1`
- Modify: `README.md`

- [ ] **Step 1: Inno Setup script**

`muesli.iss` packages `dist/Muesli/` into `MuesliSetup-<version>.exe`: per-user install to `{localappdata}\Muesli` (no admin), Start Menu shortcut, optional desktop shortcut, uninstaller. Uninstall removes program files; **leaves** `~/.muesli` user data. Stamp version + `.exe` metadata.

- [ ] **Step 2: One-command build**

`build_installer.ps1`: `npm --prefix ui run build` → `pyinstaller packaging/muesli.spec` → `iscc packaging/muesli.iss`. Read version from `engine/pyproject.toml`. Fail fast on any step.

- [ ] **Step 3: README packaging section**

Document prerequisites to build (PyInstaller, Inno Setup `iscc` on PATH), the one command, the unsigned/SmartScreen caveat, and that Ollama + WebView2 are detected at runtime. Commit: `build: Inno Setup installer and build script`.

## Task B5: Install + E2E verification

- [ ] Run `build_installer.ps1` clean; produces `MuesliSetup-<version>.exe`.
- [ ] Install on a machine without the dev venv; launch from Start Menu.
- [ ] First-run: onboarding correctly flags missing Ollama/models; model download completes; WebView2 detection correct.
- [ ] Full E2E in the installed app: record (mic+loopback) → transcribe+diarize → rename speaker → enhance → search.
- [ ] Uninstall removes program files + shortcut, preserves `~/.muesli`.
- [ ] Commit fixes: `fix: polish installer verification`.

---

## Self-Review Notes

- **Spec coverage:** dual-stream capture (A2), channel-origin + ONNX ML split (A3), segments + rename + attributed enhancement (A1/A4/A5), PyInstaller+Inno installer (B1/B4), detect-and-guide health/onboarding (B2/B3), first-run model download not bundled (B2). All covered.
- **Lean-installer goal honored:** `sherpa-onnx` + onnxruntime, no PyTorch, no HuggingFace token; models downloaded, not bundled.
- **Back-compat:** additive migration; pre-M3 meetings open via the flat-transcript fallback; `audio_path` retained as an alias.
- **Sequencing:** Part A finalizes dependencies before Part B bundles them.
- **Testable seams:** pure merge/label functions (A3) and stubbed `diarize_fn`/health checkers (A4/B2) keep model-free unit tests meaningful; model-backed paths are manually verified.
- **Known limitations:** unsigned installer (SmartScreen); overlapping remote cross-talk is best-effort; Windows-only (WASAPI).

## Open Decisions Carried Into Execution

1. Confirm the exact WeSpeaker English embedding ONNX filename/checksum and the segmentation model URL from the sherpa-onnx releases at build time.
2. Clustering by fixed threshold vs. estimated speaker count — start with `diarization_threshold`, revisit in A6 if remote speakers over/under-split.
3. Optional: tag-triggered GitHub Actions Windows job to publish the installer artifact (deferred unless wanted).
