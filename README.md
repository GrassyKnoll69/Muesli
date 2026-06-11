# Muesli

Muesli is a local-first, open-source AI meeting notetaker — a free alternative to Granola. Record your meeting audio, jot rough notes, then let Muesli transcribe the audio and enhance your notes into clean structured markdown using a local Ollama model. Everything runs on your machine; no data leaves your network. Optionally opt in to a cloud LLM (OpenAI or Anthropic) for enhancement — configured entirely from the in-app Settings screen.

## Features

- **Manual recording** — start/stop capture from the desktop UI, recording your **microphone** and **system audio** (WASAPI loopback) as separate time-aligned streams.
- **Speaker diarization** — transcripts are attributed per speaker: your mic is labeled **You**, and remote participants are split into **Speaker 1/2/…** via local ONNX clustering (sherpa-onnx, no PyTorch, no cloud). Rename speakers inline; the enhanced notes and search use the attributed transcript.
- **Template-driven AI enhancement** — choose from built-in templates (General, 1:1, Standup, Sales Call) or create your own; the LLM shapes the notes to the template.
- **Template editor** — create, edit, duplicate, and delete templates in-app, and preview the exact prompt a template produces before using it.
- **Searchable library** — full-text search over transcripts and enhanced notes via SQLite FTS5.
- **Formatted notes** — enhanced notes render as proper markdown (headings, lists, emphasis).
- **Markdown export** — download any meeting's enhanced notes (with a title/date header) as a `.md` file.
- **100% free on local models** — runs entirely on Ollama + faster-whisper; no API keys required.
- **In-app Settings** — switch Whisper model/device, the Ollama model/host, and the enhancement backend without editing files.
- **Optional cloud LLM** — enter an OpenAI or Anthropic key in Settings, pick a model, and **Test connection**. The key is stored in your OS keyring (Windows Credential Manager), never in the database or in plaintext.
- **Pywebview desktop shell** — the app opens as a native window (no browser tab needed).

## Prerequisites

| Requirement | Notes |
|---|---|
| Python 3.11+ | `python --version` |
| Node.js 18+ | Required to build the React UI |
| [Ollama](https://ollama.com) | Install, then `ollama pull qwen2.5:14b` |
| NVIDIA CUDA (optional) | GPU-accelerated Whisper; CPU fallback works automatically |

Pull the default model before running:

```bash
ollama pull qwen2.5:14b
```

## Setup

```bash
# 1. Clone the repo
git clone https://github.com/GrassyKnoll69/Muesli.git
cd Muesli

# 2. Create a Python virtual environment and install engine dependencies
python -m venv engine/.venv
engine/.venv/Scripts/python -m pip install -r engine/requirements.txt   # Windows
# source engine/.venv/bin/activate && pip install -r engine/requirements.txt  # macOS/Linux

# 3. Build the React UI
cd ui
npm install   # if peer-dep resolution fails, use: npm install --legacy-peer-deps
npm run build
cd ..
```

> The engine install pulls in `keyring` (for secure cloud-key storage) and the UI pulls in `react-markdown` (for note rendering).

## Run

```bash
# From the repo root, with the engine venv active:
PYTHONPATH=engine engine/.venv/Scripts/python run.py
```

A native window opens at `http://127.0.0.1:8731`. The FastAPI engine is also accessible directly in a browser or via curl for scripting.

On macOS/Linux:

```bash
PYTHONPATH=engine engine/.venv/bin/python run.py
```

## Windows installer

Muesli ships as a per-user Windows installer (no admin required) built with
PyInstaller + Inno Setup. From a developer checkout with the engine venv (plus
`pyinstaller`), Node.js, and [Inno Setup 6](https://jrsoftware.org/isinfo.php)
(`winget install JRSoftware.InnoSetup`) installed, build everything with one
command:

```powershell
.\build_installer.ps1
```

This builds the UI, freezes the app, and produces
`packaging\Output\MuesliSetup-<version>.exe`. See [`packaging/README.md`](packaging/README.md)
for details.

Notes:

- **Unsigned** — Windows SmartScreen warns on first launch ("More info" →
  "Run anyway"). Code signing is not done yet.
- **Detected at runtime, not bundled** — on first run the app checks for the
  **Ollama** service and the **WebView2** runtime and guides you to install them
  if missing. The Whisper and speaker models download on first use; the optional
  **NVIDIA CUDA** libraries can be downloaded during install (a checkbox in the
  setup wizard) or later from the app's onboarding panel.
- Uninstalling removes the program files but leaves your data in `~/.muesli`.

## Configuration

Muesli stores its database and recordings in `~/.muesli/` by default. Override with:

```bash
set MUESLI_HOME=D:\my-notes   # Windows
export MUESLI_HOME=~/my-notes  # macOS/Linux
```

Most settings (Whisper model/device, Ollama model/host, enhancement backend, cloud provider/model) are editable at runtime from the in-app **Settings** screen and persist in the local SQLite database; `engine/muesli_engine/config.py` holds the defaults. Cloud API keys are entered in Settings and stored in your OS keyring (Windows Credential Manager) — they are never written to the database.

## Development

Run the engine test suite (no audio/GPU/Ollama required):

```bash
cd engine
.venv/Scripts/python -m pytest -q   # Windows
# python -m pytest -q               # macOS/Linux (with venv active)
```

Run the Vite dev server (with the engine running separately):

```bash
cd ui && npm run dev
```

The Vite proxy forwards `/meetings`, `/recordings`, `/templates`, `/settings`, and `/ollama` to `http://localhost:8731`.

## License

MIT
