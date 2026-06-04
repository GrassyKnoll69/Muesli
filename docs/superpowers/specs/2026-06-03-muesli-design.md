# Muesli — Open-Source Local AI Notetaker (Granola Clone)

> Design spec — 2026-06-03. Approved by Michael during brainstorming.

## Context

Muesli is a local-first, open-source **Granola clone**: a desktop app that
quietly captures meeting audio, transcribes it, lets you take rough notes, and
uses an LLM to rewrite those notes into clean structured notes — runnable
**100% free on local models** (no API costs), with an optional paid cloud LLM as
an opt-in upgrade.

### Confirmed decisions

- **Priority:** build-for-me-first → learn → open-source later (in that order).
- **Platform:** Windows desktop first (WASAPI loopback for system audio).
- **LLM strategy:** local-first (Ollama + local Whisper), optional cloud key.
- **Stack:** Python engine + React web UI, wrapped in a **pywebview** desktop
  window. A hard split between a testable backend "engine" and a swappable UI is
  the core architecture lesson.
- **Bias:** maximize shipping; lean on free batteries-included libraries.
- **Hardware:** gaming PC, NVIDIA GPU 8GB+ VRAM → default to high-quality models
  (`faster-whisper large-v3` on GPU; Ollama `qwen2.5:14b`, configurable).
- **v1 features:** AI note enhancement, templates, search past meetings.
  (No live-transcript view, no auto-detect, no diarization in v1.)
- **In-meeting UX:** Granola-style — a clean notepad; audio captures silently in
  the background; transcript hidden until after.
- **Recording trigger:** manual Start/Stop button.
- **v1 pipeline control:** Stop just saves; user clicks **Transcribe** then
  **Enhance** manually (better visibility while building/debugging).

**Cost note:** every required component is free/open-source (pywebview,
pyaudiowpatch, faster-whisper + Whisper weights, Ollama + open LLM weights,
FastAPI, React, SQLite). The only thing that ever costs money is the *optional*
cloud LLM path, which is off by default.

## Architecture

```
Muesli/
  engine/                         # Python backend ("the engine")
    muesli_engine/
      config.py                   # paths, model names, optional cloud keys, settings
      audio/capture.py            # pyaudiowpatch: system loopback + mic -> mixed WAV
      transcribe/whisper.py       # faster-whisper wrapper (GPU, CPU fallback)
      enhance/llm.py              # Ollama client; optional cloud adapter behind same interface
      enhance/templates.py        # load/render templates (prompt + output structure)
      storage/db.py               # SQLite schema + FTS5 search + queries
      storage/models.py           # pydantic models (Meeting, Note, Template, ...)
      api/routes.py               # FastAPI endpoints
      app.py                      # builds FastAPI app, serves built UI + API
    tests/                        # pytest: per-module unit tests with fixtures
    requirements.txt
  ui/                             # React + Vite + TypeScript frontend ("the view")
    src/pages/{Library,ActiveMeeting,MeetingDetail,Templates}.tsx
    src/api/client.ts             # typed fetch wrapper to the engine API
    src/components/...
    package.json, vite.config.ts
  run.py                          # entrypoint: start uvicorn + open pywebview window
  README.md
```

**Engine/UI boundary:** the React app only ever talks to the FastAPI engine over
HTTP. The engine has no knowledge of the UI. This makes the engine unit-testable
in isolation and lets the UI be replaced later (e.g. Tauri for OSS release).

### Components

1. **Audio Capture** (`audio/capture.py`, `pyaudiowpatch`) — on Start, opens a
   WASAPI loopback stream (system audio) + the default mic, mixes both into one
   WAV on disk under a per-meeting folder. On Stop, closes streams and finalizes
   the file. If loopback is unavailable, fall back to mic-only with a warning.

2. **Transcription** (`transcribe/whisper.py`, `faster-whisper`) — after Stop,
   loads the WAV and produces a timestamped transcript. Default `large-v3` on
   CUDA; auto-fallback to a smaller CPU `int8` model if no GPU. Chunk long audio
   to bound memory. First run downloads the model with progress.

3. **Enhancement** (`enhance/llm.py` + `templates.py`) — given *(rough notes +
   transcript + selected template)*, builds a prompt and calls the local Ollama
   model (default `qwen2.5:14b`), returning structured markdown. The same
   `enhance(notes, transcript, template) -> markdown` interface has two
   implementations: `OllamaBackend` (default) and `CloudBackend` (opt-in, reads a
   user-provided OpenAI/Anthropic key). Detect Ollama-not-running / model-missing
   and surface the exact `ollama pull <model>` command.

4. **Storage** (`storage/db.py`, SQLite stdlib) — tables: `meetings`, `notes`
   (rough + enhanced), `templates`, `settings`. A FTS5 virtual table indexes
   enhanced notes + transcripts for full-text search. WAVs live on disk; DB stores
   their paths.

5. **API** (`api/routes.py`, FastAPI) — endpoints:
   `POST /recordings/start`, `POST /recordings/{id}/stop`,
   `PUT /meetings/{id}/notes` (autosave), `POST /meetings/{id}/transcribe`,
   `POST /meetings/{id}/enhance`, `GET /meetings` + `GET /meetings/search?q=`,
   `GET /meetings/{id}`, CRUD `/templates`, `GET/PUT /settings`.

6. **Frontend** (React/Vite/TS) — three screens:
   - **Library:** list of past meetings + search box (FTS).
   - **Active Meeting:** clean notepad (autosaves via `PUT notes`), recording
     indicator, template picker, Stop button.
   - **Meeting Detail:** tabs — Enhanced / My Notes / Transcript — with manual
     **Transcribe** and **Enhance** buttons.
   - Plus a small **Templates** manager (create/edit named prompt templates).

7. **Shell** (`run.py`, pywebview) — launches uvicorn (serving API + built React
   static files) and opens a native pywebview window pointed at the local URL.
   Pure-Python runtime: no Node/Electron needed to *run* the shipped app.

### Data flow (v1)

`Start` → background capture begins → user types notes (autosaved to DB) →
`Stop` → WAV finalized → user clicks **Transcribe** (faster-whisper → transcript
saved) → user clicks **Enhance** (Ollama + template → enhanced notes saved) →
meeting appears in Library and is full-text searchable.

## Default models & config

- Whisper: `large-v3` (CUDA, float16); CPU fallback `base`/`small` int8.
- LLM: Ollama `qwen2.5:14b` default; user-switchable (e.g. `llama3.1:8b`).
- All model names + the optional cloud key live in `config.py` / `settings`.

## Build order (M1 = MVP)

1. **Scaffold** repo: `engine/` Python package + `ui/` Vite app + `run.py`.
   `requirements.txt`, `.gitignore`, basic README run steps.
2. **Storage** first (`storage/`): SQLite schema, models, FTS5, CRUD — fully
   unit-tested with an in-memory DB.
3. **API skeleton** (`api/routes.py` + `app.py`): wire endpoints to storage with
   stubbed capture/transcribe/enhance; serve a placeholder UI.
4. **Audio capture** (`audio/capture.py`): WASAPI loopback + mic → WAV; verify
   with a short manual recording.
5. **Transcription** (`transcribe/whisper.py`): WAV → transcript on GPU.
6. **Enhancement** (`enhance/`): templates + Ollama backend; seed 2-3 default
   templates (1:1, standup, sales call).
7. **Frontend**: Library, Active Meeting (notepad + Stop), Meeting Detail
   (tabs + Transcribe/Enhance buttons), Templates manager.
8. **Shell**: `run.py` ties uvicorn + pywebview together.
9. **End-to-end pass** + README polish.

### Later milestones (out of scope here)

- **M2:** optional cloud LLM UI, settings screen, markdown export, template
  editor polish.
- **M3:** live transcript, speaker diarization, calendar auto-detect, packaged
  installer for OSS release.

## Dependencies (all free)

- Python: `fastapi`, `uvicorn`, `pywebview`, `pyaudiowpatch`, `faster-whisper`,
  `ollama`, `pydantic`. (`sqlite3` is stdlib.) GPU Whisper pulls in CTranslate2 +
  CUDA runtime libs.
- JS: `react`, `react-dom`, `vite`, `typescript`, a router, optional Tailwind.
- External: **Ollama** installed locally with a model pulled
  (`ollama pull qwen2.5:14b`); NVIDIA CUDA for GPU Whisper.

## Verification

- **Unit (pytest):** storage CRUD + FTS search returns expected rows; transcribe
  module returns non-empty text from a short sample WAV fixture; enhancement
  returns structured markdown using a mocked/stubbed Ollama response; template
  rendering produces the expected prompt.
- **Manual E2E (M1 done):** install + `ollama pull`, run `python run.py`, Start a
  recording, play/speak a short clip, Stop, click Transcribe (transcript appears),
  click Enhance (clean notes appear), confirm the meeting shows in Library and
  that searching a keyword finds it.
- **Loopback check:** confirm system audio (e.g. a YouTube clip) is captured, not
  just the mic.
