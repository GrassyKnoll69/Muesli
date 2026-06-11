# Muesli M3: Speaker Diarization + Packaging

> Design spec - 2026-06-09. Scoped to two M3 features: speaker diarization and a
> Windows installer. Live transcript and calendar auto-detect are deferred.

## Context

Muesli's MVP through M2.5 captures system audio (WASAPI loopback), transcribes
it with faster-whisper into a single flat string, enhances it with an LLM, and
presents everything in a polished pywebview desktop UI. Two gaps remain before
the app feels like a finished product:

1. Notes have no idea **who said what**. The transcript is one undifferentiated
   block, so the LLM cannot reliably attribute action items to owners.
2. There is **no way to ship it**. The app runs from a developer checkout
   (`python run.py` with a venv and a separate `npm run build`). A normal user
   cannot install it.

This milestone closes both. The two features are coupled: the diarization stack
adds heavy native dependencies that the installer must bundle, so they are
designed and sequenced together.

## Goals

- Capture the local user's microphone as a **separate stream** from system
  loopback, time-aligned with it.
- Produce a **speaker-attributed transcript**: deterministic "You" vs. remote
  via channel origin, plus ML clustering to split multiple remote speakers.
- Persist transcript **segments** (start, end, speaker, text) and let the user
  **rename** speakers; feed the attributed transcript into enhancement.
- Display the diarized transcript clearly in Meeting Detail.
- Produce a **one-file Windows installer** (PyInstaller + Inno Setup) that
  installs Muesli with a Start Menu shortcut and an uninstaller.
- On first run, **detect and guide** the user through external prerequisites
  (Ollama, WebView2 runtime, model downloads) instead of failing silently.

## Non-Goals

- No live/streaming transcript during recording (still a later M3 surface).
- No calendar auto-detect.
- No macOS/Linux packaging. Loopback capture is WASAPI-only; this is a Windows
  installer.
- No code-signing certificate. The installer ships unsigned for now; SmartScreen
  warnings are a known limitation, documented, not solved here.
- No bundling of Ollama or the Whisper/diarization model weights into the
  installer. Those are detected/downloaded, not shipped.
- No diarization of overlapping speech beyond what channel separation already
  gives. Cross-talk on the remote channel is best-effort.

---

## Part A: Speaker Diarization

### A.1 Dual-stream capture

`Recorder` today opens one loopback stream and writes one WAV. M3 captures two
concurrent streams per meeting:

- **Mic stream** — default input device. This is the local user. Written to
  `{id}-mic.wav`.
- **Loopback stream** — default output device (existing logic). This is every
  remote participant, mixed. Written to `{id}-loopback.wav`.

Decisions:

- Both streams start as close together as possible and record their wall-clock
  start time. Stored start offsets let downstream merging align segment
  timestamps even if the two streams begin a few milliseconds apart.
- Streams keep native rates while recording; resampling to 16 kHz mono (what
  Whisper and the embedding model want) happens at transcription time, not in
  the capture loop.
- If no input (mic) device is available, recording continues loopback-only and
  the meeting is flagged so diarization degrades gracefully to "remote speakers
  only" rather than failing.
- `audio_path` on the meeting becomes insufficient for two files. Store a
  loopback path and a mic path (see schema).

### A.2 Channel-origin + ML diarization pipeline

Transcription stops discarding segments. The new flow, per meeting:

1. **Transcribe the mic stream** with faster-whisper, preserving per-segment
   `(start, end, text)`. Every segment is labeled `You`.
2. **Transcribe the loopback stream** the same way, preserving segments.
3. **Cluster the loopback segments by speaker.** For each loopback segment,
   compute a speaker embedding over its audio, then run threshold-based
   agglomerative clustering to assign `Speaker 1`, `Speaker 2`, ... A single
   remote participant collapses to one cluster.
4. **Merge** mic segments and labeled loopback segments into one list ordered by
   start time. This merge is a pure function and is the primary unit-tested
   surface of the feature.
5. Store the merged, labeled segments. Also write a flat speaker-attributed
   string (`You: ...\nSpeaker 1: ...`) into the existing `transcript` column so
   FTS search and the enhancement prompt keep working.

Because channel origin already separates "you" from "them" deterministically,
the ML model is only responsible for splitting the remote side. This keeps the
clustering problem easy (no need to distinguish the local mic from remote audio)
and means a 1:1 call needs no reliable multi-speaker ML at all.

### A.3 Embedding model choice (sub-decision, recommendation below)

"Channels + local ML" requires a speaker-embedding model. The candidates and the
tradeoff that matters most — **installer size**:

- **ONNX speaker embeddings (recommended)** — a small pretrained embedding model
  (e.g. a WeSpeaker/3D-Speaker ECAPA export) run via `onnxruntime`, plus
  `scikit-learn`/`scipy` for clustering. No PyTorch, no HuggingFace gating, adds
  tens of MB to the bundle. Best fit for a lean installer and local-first.
- **resemblyzer** — simple API, no HF token, but pulls **PyTorch** (~hundreds of
  MB to ~2 GB in a PyInstaller bundle).
- **pyannote.audio pipeline** — highest quality, but PyTorch **and** a gated
  HuggingFace token the user must obtain, plus larger model downloads. Friction
  conflicts with the "detect & guide" onboarding goal.

Recommendation: ONNX embeddings + agglomerative clustering. It keeps the
installer small enough that Part B stays manageable and avoids the token
friction. The planning phase should confirm a concrete, redistributable ONNX
model before committing.

### A.4 Speaker renaming

Auto labels (`Speaker 1`) are placeholders. Users need to rename them ("Alice").
Store a per-meeting label map (`speaker_labels`: meeting_id, key, display_name)
rather than rewriting every segment, so renames are one row each and segment rows
stay stable. Display resolves a segment's raw key through the map.

### A.5 Schema changes

- `meetings`: replace single `audio_path` usage with `loopback_path` and
  `mic_path` (keep `audio_path` as a deprecated alias or migrate). Add
  `diarized` boolean / status nuance so the UI can show "transcribed but not
  diarized" if mic was absent.
- New `transcript_segments`: `id, meeting_id, start REAL, end REAL,
  speaker_key TEXT, source TEXT('mic'|'loopback'), text TEXT`.
- New `speaker_labels`: `meeting_id, speaker_key, display_name`, unique on
  `(meeting_id, speaker_key)`.
- `transcript` column stays, repopulated as the attributed flat string for FTS.

### A.6 API + UI changes

- `transcribe` endpoint now also diarizes and persists segments; response
  includes segments or the client fetches `GET /meetings/{id}/segments`.
- New `PUT /meetings/{id}/speakers` to rename a speaker label.
- Enhancement reads the attributed transcript so the LLM can assign owners; the
  prompt builder gains a speaker-aware transcript section.
- Meeting Detail transcript tab renders segments as speaker-tagged turns (color
  chip per speaker) instead of a flat `<pre>`, with inline rename on the chip.
- Settings gains: enable/disable diarization, optional mic device selection.

### A.7 Diarization testing

- Unit: the segment-merge/ordering function, the speaker-label resolution
  through the rename map, and the attributed-transcript string builder. All pure.
- Unit: clustering label assignment with injected/stub embeddings (no model).
- Manual: real two-stream capture with a multi-speaker clip, verify "You" vs.
  split remote speakers and rename flow.

---

## Part B: Packaging + Installer

### B.1 Build pipeline

A repeatable Windows build, driven by one script (`build_installer.ps1`):

1. `npm --prefix ui run build` → `ui/dist`.
2. **PyInstaller** (onedir, not onefile) bundles `run.py` + the `muesli_engine`
   package + `ui/dist` (as data) + native libs (ctranslate2, PyAudioWPatch,
   pywebview's WebView2 loader, onnxruntime). onedir is chosen over onefile for
   faster startup and fewer native-DLL extraction problems with ctranslate2.
3. **Inno Setup** (`iscc`) wraps the onedir output into `MuesliSetup.exe`:
   per-user install under `%LOCALAPPDATA%` (no admin prompt), Start Menu +
   optional desktop shortcut, and an uninstaller.

A PyInstaller `.spec` file is committed so hidden imports (faster_whisper,
ctranslate2, uvicorn workers, onnxruntime) and data files are reproducible.

### B.2 What is and isn't bundled

- **Bundled:** Python runtime, all pip deps, the built UI, native audio/inference
  libs.
- **Not bundled (downloaded on first use):** Whisper model and the ONNX speaker
  model. They land in `%LOCALAPPDATA%\Muesli` (alongside the existing
  `~/.muesli` data dir). First run shows a one-time download with progress.
- **Not bundled (external):** Ollama and the WebView2 runtime — see B.3.

### B.3 Detect & guide onboarding

On startup the app runs health checks and surfaces a first-run / Settings panel:

- **WebView2 runtime** present? pywebview needs it (usually on Win11). If absent,
  link to Microsoft's Evergreen installer.
- **Ollama** installed and reachable at `localhost:11434`? If not, show a card
  with the install link and the `ollama pull <model>` command, and offer to
  switch to the cloud backend (already supported) as an alternative.
- **Models** present? If not, trigger/explain the first-run download.

Health checks are a small engine endpoint (`GET /health`) the UI renders, so the
same panel works in dev and in the packaged app.

### B.4 Versioning + metadata

- Single source of version in `engine/pyproject.toml`, surfaced in the UI footer
  and stamped into the Inno Setup output filename and the .exe metadata.

### B.5 Packaging testing

- Build runs clean from the script on a Windows machine.
- Install the produced `.exe` on a machine without the dev venv; launch from the
  Start Menu shortcut.
- Full E2E in the installed app: record (mic + loopback) → transcribe + diarize →
  enhance, exercising first-run model download and Ollama detection.
- Uninstall removes program files and shortcut (leaves user data in `~/.muesli`).

---

## Sequencing

Part A lands before Part B: diarization finalizes the dependency set (onnxruntime
+ clustering libs) that the installer must bundle, so packaging captures the real
footprint rather than being redone.

## Planning Assumptions

- The plan must inspect the working tree first and base changes on what exists
  (current `Recorder`, `transcribe_wav`, `Database` schema, `build_prompt`,
  `create_app`, settings/health surfaces from M2/M2.5).
- The ONNX embedding model must be a concrete, redistributable choice confirmed
  during planning; if none is viable, fall back to resemblyzer and accept the
  PyTorch install-size cost (documented), without changing the rest of the
  design.
- Dual-stream capture must degrade to loopback-only when no mic device exists,
  rather than blocking recording.
- Schema changes need a forward migration for existing `~/.muesli` databases;
  old meetings without segments still open (transcript tab falls back to the
  flat string).

## Open Decisions For Planning

1. **Embedding model**: confirm a specific redistributable ONNX speaker model
   (recommended) vs. accepting PyTorch via resemblyzer.
2. **Speaker count**: pure distance-threshold clustering vs. an estimated
   speaker count (silhouette). Start with a tuned threshold; revisit if remote
   over/under-splitting shows up in verification.
3. **Install location**: per-user `%LOCALAPPDATA%` (no admin, recommended) vs.
   `Program Files` (admin, machine-wide).
4. **CI**: add a tag-triggered GitHub Actions Windows job to publish the
   installer artifact, or keep the build local-only for now.
