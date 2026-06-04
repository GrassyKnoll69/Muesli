from __future__ import annotations

from muesli_engine.config import Settings, resolve_whisper_device

_model_cache: dict[tuple[str, str, str], object] = {}


def _get_model(settings: Settings):
    device, compute_type = resolve_whisper_device(settings.whisper_device)
    key = (settings.whisper_model, device, compute_type)
    if key not in _model_cache:
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
