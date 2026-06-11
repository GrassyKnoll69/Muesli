"""Model-backed diarization pipeline.

Combines faster-whisper transcription (via :mod:`muesli_engine.transcribe.whisper`)
with sherpa-onnx speaker diarization to produce a merged, speaker-attributed
segment list.

sherpa-onnx is imported **lazily** inside :func:`_run_sherpa_diarization` so that
the module can be imported without sherpa-onnx installed (e.g. during unit tests).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from muesli_engine.config import APP_DIR, Settings
from muesli_engine.diarize.merge import assign_speakers, merge_streams
from muesli_engine.transcribe.whisper import transcribe_segments

# Paths under APP_DIR / "models" — imported by Task B2 for download logic.
SEGMENTATION_MODEL = "sherpa-onnx-pyannote-segmentation-3-0.onnx"
EMBEDDING_MODEL = "wespeaker_en_voxceleb_resnet34.onnx"


def _load_wav_mono(path: str, target_rate: int) -> Any:
    """Load a WAV file as a mono float32 numpy array at *target_rate*.

    The capture layer always writes 16-bit PCM WAVs (``paInt16``) at the
    device's native rate (often 48 kHz). sherpa-onnx diarization requires the
    audio at the model's own sample rate, so we downmix to mono and resample
    with linear interpolation (best-effort; adequate for speaker embeddings).
    """
    import wave

    import numpy as np

    with wave.open(path, "rb") as wf:
        n_channels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        rate = wf.getframerate()
        raw = wf.readframes(wf.getnframes())

    if sampwidth != 2:
        raise ValueError(f"expected 16-bit PCM WAV, got sample width {sampwidth}")

    data = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    if n_channels > 1:
        data = data.reshape(-1, n_channels).mean(axis=1)

    if rate != target_rate and data.size:
        duration = data.size / rate
        tgt_len = int(round(duration * target_rate))
        x_old = np.linspace(0.0, duration, num=data.size, endpoint=False)
        x_new = np.linspace(0.0, duration, num=tgt_len, endpoint=False)
        data = np.interp(x_new, x_old, data).astype(np.float32)

    return data


def _run_sherpa_diarization(
    loopback_path: str,
    settings: Settings,
) -> list[dict[str, Any]]:
    """Run sherpa-onnx OfflineSpeakerDiarization on *loopback_path*.

    The import of ``sherpa_onnx`` is deferred to this function so that the
    module loads without the library present (tests run without it).

    Args:
        loopback_path: Path to the loopback WAV file.
        settings: Application settings; ``diarization_threshold`` is read via
            ``getattr`` with a default of 0.5 (field added in Task A4).

    Returns:
        List of ``{"start": float, "end": float, "speaker": int}`` dicts,
        ordered by start time.
    """
    import sherpa_onnx  # noqa: PLC0415 — intentional lazy import

    models_dir = APP_DIR / "models"
    segmentation_path = str(models_dir / SEGMENTATION_MODEL)
    embedding_path = str(models_dir / EMBEDDING_MODEL)
    threshold = getattr(settings, "diarization_threshold", 0.5)

    config = sherpa_onnx.OfflineSpeakerDiarizationConfig(
        segmentation=sherpa_onnx.OfflineSpeakerSegmentationModelConfig(
            pyannote=sherpa_onnx.OfflineSpeakerSegmentationPyannoteModelConfig(
                model=segmentation_path,
            ),
        ),
        embedding=sherpa_onnx.SpeakerEmbeddingExtractorConfig(model=embedding_path),
        # num_clusters=-1 selects threshold-based clustering (unknown speaker
        # count); the threshold tunes how readily remote speakers are split.
        clustering=sherpa_onnx.FastClusteringConfig(
            num_clusters=-1, threshold=threshold
        ),
        min_duration_on=0.3,
        min_duration_off=0.5,
    )
    if not config.validate():
        raise RuntimeError(
            "Invalid sherpa-onnx diarization config; check that the segmentation "
            f"and embedding models exist under {models_dir}."
        )

    diarizer = sherpa_onnx.OfflineSpeakerDiarization(config)
    samples = _load_wav_mono(loopback_path, getattr(diarizer, "sample_rate", 16000))
    result = diarizer.process(samples).sort_by_start_time()
    return [
        {"start": float(r.start), "end": float(r.end), "speaker": int(r.speaker)}
        for r in result
    ]


def diarize_meeting(
    loopback_path: str,
    mic_path: str | None,
    mic_offset: float,
    settings: Settings,
) -> list[dict[str, Any]]:
    """Transcribe and diarize a meeting from two audio streams.

    Steps:
        1. Transcribe the mic stream (if provided) and shift timestamps by
           *mic_offset* so they align with the loopback timeline.
        2. Transcribe the loopback stream.
        3. Run sherpa-onnx speaker diarization on the loopback stream.
        4. Assign speaker labels to loopback segments.
        5. Merge mic and loopback segments into a single timeline-ordered list.

    Args:
        loopback_path: Path to the loopback (system audio) WAV file.
        mic_path: Path to the microphone WAV file, or ``None`` to skip mic
            transcription.
        mic_offset: Seconds by which to shift mic segment timestamps into the
            loopback timeline.
        settings: Application settings.

    Returns:
        List of ``{"start","end","speaker_key","source","text"}`` dicts ordered
        by *start*, as returned by :func:`~muesli_engine.diarize.merge.merge_streams`.
    """
    # Step 1: mic transcription + timestamp shift.
    if mic_path:
        raw_mic = transcribe_segments(mic_path, settings)
        mic_segments = [
            {
                "start": seg["start"] + mic_offset,
                "end": seg["end"] + mic_offset,
                "text": seg["text"],
            }
            for seg in raw_mic
        ]
    else:
        mic_segments = []

    # Step 2: loopback transcription.
    loopback_segments = transcribe_segments(loopback_path, settings)

    # Step 3: diarization turns from the loopback audio.
    diar_turns = _run_sherpa_diarization(loopback_path, settings)

    # Step 4: assign speaker labels to loopback segments.
    labeled_loopback = assign_speakers(loopback_segments, diar_turns)

    # Step 5: merge both streams.
    return merge_streams(mic_segments, labeled_loopback)
