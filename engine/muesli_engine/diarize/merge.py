"""Pure functions for merging and labeling transcription segments with speaker info.

No model imports here — this module is safe to use without faster-whisper or
sherpa-onnx installed.
"""
from __future__ import annotations

import re
from typing import Any


def _overlap(a_start: float, a_end: float, b_start: float, b_end: float) -> float:
    """Return the temporal overlap (in seconds) between two intervals."""
    return max(0.0, min(a_end, b_end) - max(a_start, b_start))


def assign_speakers(
    loopback_segments: list[dict[str, Any]],
    diar_turns: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Label each loopback segment with the maximally-overlapping speaker key.

    Args:
        loopback_segments: List of ``{"start", "end", "text"}`` dicts.
        diar_turns: List of ``{"start", "end", "speaker": int}`` dicts where
            *speaker* is a 0-based cluster index as returned by sherpa-onnx.

    Returns:
        New list of dicts — one per input segment — each containing the original
        ``start``, ``end``, ``text`` plus a ``speaker_key`` such as ``"spk1"``.
        A segment that overlaps no turn receives ``"spk1"``.  Inputs are never
        mutated.

    Tie-break: when two speakers accumulate equal overlap for a segment, the
    lowest speaker index (i.e. lowest *n* in ``spk<n>``) wins.
    """
    result = []
    for seg in loopback_segments:
        s_start = seg["start"]
        s_end = seg["end"]

        # Accumulate overlap per speaker (index → total overlap seconds).
        speaker_overlap: dict[int, float] = {}
        for turn in diar_turns:
            ov = _overlap(s_start, s_end, turn["start"], turn["end"])
            if ov > 0.0:
                spk = turn["speaker"]
                speaker_overlap[spk] = speaker_overlap.get(spk, 0.0) + ov

        if speaker_overlap:
            # Max overlap; tie-break by lowest index (min key).
            best = max(speaker_overlap, key=lambda k: (speaker_overlap[k], -k))
        else:
            best = 0  # default → spk1

        new_seg = {
            "start": s_start,
            "end": s_end,
            "text": seg["text"],
            "speaker_key": f"spk{best + 1}",
        }
        result.append(new_seg)
    return result


def merge_streams(
    mic_segments: list[dict[str, Any]],
    loopback_segments: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Merge mic and loopback segment lists into a single timeline-ordered list.

    Args:
        mic_segments: ``[{"start","end","text"}, ...]`` already in the loopback
            timeline (caller is responsible for applying any offset).
        loopback_segments: ``[{"start","end","text","speaker_key"}, ...]`` as
            returned by :func:`assign_speakers`.

    Returns:
        One list of ``{"start","end","speaker_key","source","text"}`` dicts,
        ordered by *start*.  Tie-break: mic segments come before loopback
        segments that share the same *start* time (stable, deterministic).
    """
    tagged: list[tuple[float, int, dict[str, Any]]] = []

    for seg in mic_segments:
        tagged.append((
            seg["start"],
            0,  # sort key: mic before loopback on equal start
            {
                "start": seg["start"],
                "end": seg["end"],
                "speaker_key": "you",
                "source": "mic",
                "text": seg["text"],
            },
        ))

    for seg in loopback_segments:
        tagged.append((
            seg["start"],
            1,  # sort key: loopback after mic on equal start
            {
                "start": seg["start"],
                "end": seg["end"],
                "speaker_key": seg["speaker_key"],
                "source": "loopback",
                "text": seg["text"],
            },
        ))

    tagged.sort(key=lambda t: (t[0], t[1]))
    return [item for _, _, item in tagged]


def humanize_key(key: str) -> str:
    """Convert an internal speaker key to a display name.

    Examples:
        ``"you"`` → ``"You"``
        ``"spk1"`` → ``"Speaker 1"``
        ``"spk12"`` → ``"Speaker 12"``
        Any other key → ``key.capitalize()``
    """
    if key == "you":
        return "You"
    m = re.fullmatch(r"spk(\d+)", key)
    if m:
        return f"Speaker {int(m.group(1))}"
    return key.capitalize()


def attributed_transcript(
    segments: list[dict[str, Any]],
    name_map: dict[str, str],
) -> str:
    """Render a multi-speaker transcript as a human-readable string.

    Args:
        segments: Ordered list of segment dicts, each containing at least
            ``"speaker_key"`` and ``"text"``.
        name_map: Mapping of ``speaker_key`` → display name.  Missing keys fall
            back to :func:`humanize_key`.

    Returns:
        One ``"Display: text"`` line per segment joined by ``"\\n"``.  Returns
        ``""`` when *segments* is empty.
    """
    if not segments:
        return ""

    lines = []
    for seg in segments:
        spk_key = seg["speaker_key"]
        display = name_map.get(spk_key, humanize_key(spk_key))
        lines.append(f"{display}: {seg['text']}")
    return "\n".join(lines)
