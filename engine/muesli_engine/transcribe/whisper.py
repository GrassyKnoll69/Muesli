from __future__ import annotations

import os
import sys
from importlib import util as _import_util

from muesli_engine.config import Settings, resolve_whisper_device

_model_cache: dict[tuple[str, str, str], object] = {}
_cuda_dll_dirs_added = False


def _ensure_cuda_dll_path() -> None:
    """Make the pip-installed NVIDIA CUDA libraries discoverable on Windows.

    CTranslate2 loads cuBLAS/cuDNN by name at runtime. The ``nvidia-*-cu12``
    wheels ship the DLLs under ``site-packages/nvidia/*/bin``, but that folder
    is not on the search path, so the load fails with
    ``Library cublas64_12.dll is not found``.

    CTranslate2's native loader calls ``LoadLibrary`` without the user-dirs
    search flag, so ``os.add_dll_directory`` (which only the legacy/ctypes
    loader honors) is not enough on its own -- the bin dirs must be prepended
    to ``PATH``, which the standard DLL search order reads. We do both.
    """
    global _cuda_dll_dirs_added
    if _cuda_dll_dirs_added or not sys.platform.startswith("win"):
        return
    spec = _import_util.find_spec("nvidia")
    bin_dirs = []
    for base in spec.submodule_search_locations if spec else []:
        for sub in ("cublas", "cudnn", "cuda_nvrtc", "cuda_runtime"):
            bin_dir = os.path.join(base, sub, "bin")
            if os.path.isdir(bin_dir):
                bin_dirs.append(bin_dir)
                os.add_dll_directory(bin_dir)
    if bin_dirs:
        os.environ["PATH"] = os.pathsep.join(bin_dirs) + os.pathsep + os.environ.get("PATH", "")
    _cuda_dll_dirs_added = True


def _get_model(settings: Settings):
    device, compute_type = resolve_whisper_device(settings.whisper_device)
    key = (settings.whisper_model, device, compute_type)
    if key not in _model_cache:
        if device == "cuda":
            _ensure_cuda_dll_path()
        from faster_whisper import WhisperModel

        _model_cache[key] = WhisperModel(
            settings.whisper_model, device=device, compute_type=compute_type
        )
    return _model_cache[key]


def transcribe_wav(path: str, settings: Settings) -> str:
    """Transcribe a WAV file into a single plain-text transcript."""
    model = _get_model(settings)
    segments, _info = model.transcribe(path, vad_filter=True)
    return " ".join(seg.text.strip() for seg in segments).strip()
