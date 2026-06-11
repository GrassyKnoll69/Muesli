from __future__ import annotations

import os

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


def transcribe_segments(path: str, settings: Settings) -> list[dict]:
    """Transcribe a WAV file, returning one dict per segment with timing.

    Args:
        path: Path to the WAV file.  If falsy or the file does not exist,
            returns ``[]`` without loading any model.
        settings: Application settings used to resolve the Whisper model.

    Returns:
        ``[{"start": float, "end": float, "text": str}, ...]``, with *text*
        stripped of leading/trailing whitespace.
    """
    if not path or not os.path.exists(path):
        return []
    model = _get_model(settings)
    segments, _info = model.transcribe(path, vad_filter=True)
    return [
        {"start": seg.start, "end": seg.end, "text": seg.text.strip()}
        for seg in segments
    ]


def transcribe_wav(path: str, settings: Settings) -> str:
    """Transcribe a WAV file into a single plain-text transcript.

    Thin wrapper around :func:`transcribe_segments` that joins all segment
    texts into one string.  Behavior for empty/missing *path* is unchanged
    (returns ``""``).
    """
    return " ".join(s["text"] for s in transcribe_segments(path, settings)).strip()
