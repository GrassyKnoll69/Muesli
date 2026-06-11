"""Health-check helpers for the Muesli engine.

Every function in this module NEVER raises — on any error it degrades to
``False`` (or ``None`` for platform-not-applicable).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------


def check_ollama(host: str) -> bool:
    """Return True if the Ollama server at *host* is reachable."""
    try:
        from muesli_engine.enhance import llm  # noqa: PLC0415

        result = llm.list_ollama_models(host)
        return isinstance(result, list)
    except Exception:
        return False


def check_webview2() -> bool | None:
    """Check for the Evergreen WebView2 runtime on Windows.

    Returns:
        ``None`` on non-Windows.
        ``True`` if WebView2 is installed.
        ``False`` on Windows if not installed or on any error.
    """
    if not sys.platform.startswith("win"):
        return None

    try:
        import winreg  # noqa: PLC0415 — Windows only

        _WV2_KEY = r"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"
        _WV2_KEY_NATIVE = r"SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"

        for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            for key_path in (_WV2_KEY, _WV2_KEY_NATIVE):
                try:
                    with winreg.OpenKey(hive, key_path) as k:
                        value, _ = winreg.QueryValueEx(k, "pv")
                        if value:
                            return True
                except OSError:
                    continue
        return False
    except Exception:
        return False


def check_diarization_models() -> bool:
    """Return True if both diarization ONNX models are present."""
    try:
        from muesli_engine import models_store  # noqa: PLC0415

        return models_store.diarization_models_present()
    except Exception:
        return False


def check_whisper_model(settings) -> bool:
    """Best-effort check that the faster-whisper model is cached locally.

    Looks under the HuggingFace hub cache directory for a folder whose name
    contains ``faster-whisper-{settings.whisper_model}``.  Any error returns
    ``False``.
    """
    try:
        model_name: str = settings.whisper_model
        # Honour the standard HF cache env overrides.
        hf_cache = os.environ.get("HF_HUB_CACHE") or os.environ.get(
            "HUGGINGFACE_HUB_CACHE"
        )
        if hf_cache:
            cache_dir = Path(hf_cache)
        else:
            cache_dir = Path.home() / ".cache" / "huggingface" / "hub"

        if not cache_dir.exists():
            return False

        needle = f"faster-whisper-{model_name}"
        return any(
            needle in entry.name
            for entry in cache_dir.iterdir()
            if entry.is_dir()
        )
    except Exception:
        return False


def check_gpu() -> bool:
    """Return True if at least one CUDA device is visible to CTranslate2."""
    try:
        import ctranslate2  # noqa: PLC0415

        return ctranslate2.get_cuda_device_count() > 0
    except Exception:
        return False


def check_cuda_libraries() -> bool:
    """Return True if CUDA DLLs have been downloaded into CUDA_DIR."""
    try:
        from muesli_engine import models_store  # noqa: PLC0415

        return models_store.cuda_libraries_present()
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Aggregate payload
# ---------------------------------------------------------------------------


def health_payload(settings) -> dict:
    """Assemble a dict describing the health of all external dependencies."""
    return {
        "ollama": check_ollama(settings.ollama_host),
        "webview2": check_webview2(),
        "diarization_models": check_diarization_models(),
        "whisper_model": check_whisper_model(settings),
        "gpu_present": check_gpu(),
        "cuda_libraries": check_cuda_libraries(),
    }
