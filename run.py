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


def main():
    threading.Thread(target=_serve, daemon=True).start()
    webview.create_window("Muesli", f"http://127.0.0.1:{PORT}", width=1000, height=720)
    webview.start()


if __name__ == "__main__":
    main()
