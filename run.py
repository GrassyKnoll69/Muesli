from __future__ import annotations

import sys
import threading
from pathlib import Path

import uvicorn
import webview

# Make the engine package importable when launching from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent / "engine"))

from muesli_engine.app import create_app  # noqa: E402

PORT = 8731


def _serve():
    uvicorn.run(create_app(), host="127.0.0.1", port=PORT, log_level="info")


def _safe_print(msg: str) -> None:
    # In a windowed/frozen build sys.stdout may be None; never crash on output.
    try:
        if sys.stdout is not None:
            print(msg, flush=True)
    except Exception:
        pass


def _progress(*args) -> None:
    try:
        name = args[0] if args else ""
        done = args[1] if len(args) > 1 else 0
        total = args[2] if len(args) > 2 else None
        if total:
            _safe_print(f"  {name}: {done * 100 // total}%")
        else:
            _safe_print(f"  {name}: {done} bytes")
    except Exception:
        pass


def _run_downloads(args: list[str]) -> None:
    """Headless first-run downloads, used by the installer's optional steps."""
    from muesli_engine.config import ensure_dirs

    ensure_dirs()
    if "--download-models" in args:
        from muesli_engine import models_store

        _safe_print("Downloading speaker diarization models...")
        models_store.ensure_diarization_models(progress=_progress)
        _safe_print("Diarization models ready.")
    if "--download-cuda" in args:
        from muesli_engine import models_store

        _safe_print("Downloading NVIDIA CUDA libraries (this can take several minutes)...")
        models_store.ensure_cuda_libraries(progress=_progress)
        _safe_print("CUDA libraries ready.")


def main():
    args = sys.argv[1:]
    if "--download-models" in args or "--download-cuda" in args:
        _run_downloads(args)
        return

    threading.Thread(target=_serve, daemon=True).start()
    webview.create_window("Muesli", f"http://127.0.0.1:{PORT}", width=1000, height=720)
    webview.start()


if __name__ == "__main__":
    main()
