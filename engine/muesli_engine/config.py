from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel

APP_DIR = Path(os.environ.get("MUESLI_HOME", str(Path.home() / ".muesli")))
DB_PATH = APP_DIR / "muesli.db"
RECORDINGS_DIR = APP_DIR / "recordings"


class Settings(BaseModel):
    whisper_model: str = "large-v3"
    whisper_device: str = "auto"            # "auto" | "cuda" | "cpu"
    whisper_compute_type: str = "float16"   # "int8" recommended on CPU
    ollama_model: str = "qwen2.5:14b"
    ollama_host: str = "http://localhost:11434"
    enhancement_backend: str = "ollama"     # "ollama" | "cloud"
    cloud_provider: str | None = None       # "openai" | "anthropic"
    cloud_model: str | None = None          # resolved to a provider default when unset
    cloud_api_key: str | None = None        # test-injection seam only; never persisted
    enable_diarization: bool = True
    diarization_threshold: float = 0.5
    # Selects the loopback endpoint by name substring; blank = default output.
    capture_device: str | None = None
    mic_device: str | None = None


def ensure_dirs() -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)


def resolve_whisper_device(device: str) -> tuple[str, str]:
    """Return (device, compute_type), auto-detecting CUDA when device='auto'."""
    if device != "auto":
        return device, ("float16" if device == "cuda" else "int8")
    try:
        import ctranslate2  # bundled with faster-whisper

        if ctranslate2.get_cuda_device_count() > 0:
            return "cuda", "float16"
    except Exception:
        pass
    return "cpu", "int8"
