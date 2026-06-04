# Muesli

Muesli is a local-first, open-source AI meeting notetaker — a free alternative to Granola. Record your meeting audio, jot rough notes, then let Muesli transcribe the audio and enhance your notes into clean structured markdown using a local Ollama model. Everything runs on your machine; no data leaves your network. Optionally opt in to a cloud LLM (OpenAI) for enhancement if you prefer.

## Features (v1)

- **Manual recording** — start/stop system-audio capture (WASAPI loopback) from the desktop UI.
- **Template-driven AI enhancement** — choose from built-in templates (General, 1:1, Standup, Sales Call) or create your own; the LLM shapes the notes to the template.
- **Searchable library** — full-text search over transcripts and enhanced notes via SQLite FTS5.
- **100% free on local models** — runs entirely on Ollama + faster-whisper; no API keys required.
- **Optional cloud LLM** — configure `enhancement_backend = "cloud"` with an OpenAI key to use GPT-4o-mini instead.
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
npm install
npm run build
cd ..
```

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

## Configuration

Muesli stores its database and recordings in `~/.muesli/` by default. Override with:

```bash
set MUESLI_HOME=D:\my-notes   # Windows
export MUESLI_HOME=~/my-notes  # macOS/Linux
```

Settings (Whisper model, Ollama model, cloud backend) are in `engine/muesli_engine/config.py`.

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

The Vite proxy forwards `/meetings`, `/recordings`, and `/templates` to `http://localhost:8731`.

## License

MIT
