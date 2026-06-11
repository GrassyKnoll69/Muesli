"""Tests for the pure diarization merge functions (no models needed)."""
from __future__ import annotations

import pytest

from muesli_engine.diarize.merge import (
    assign_speakers,
    attributed_transcript,
    humanize_key,
    merge_streams,
)


# ---------------------------------------------------------------------------
# humanize_key
# ---------------------------------------------------------------------------


class TestHumanizeKey:
    def test_you(self):
        assert humanize_key("you") == "You"

    def test_spk1(self):
        assert humanize_key("spk1") == "Speaker 1"

    def test_spk2(self):
        assert humanize_key("spk2") == "Speaker 2"

    def test_spk10(self):
        assert humanize_key("spk10") == "Speaker 10"

    def test_unknown_key_falls_back(self):
        # Unknown keys: capitalize the key unchanged
        result = humanize_key("alice")
        assert isinstance(result, str)
        assert len(result) > 0


# ---------------------------------------------------------------------------
# assign_speakers
# ---------------------------------------------------------------------------


class TestAssignSpeakers:
    def _seg(self, start, end, text="hello"):
        return {"start": start, "end": end, "text": text}

    def _turn(self, start, end, speaker):
        return {"start": start, "end": end, "speaker": speaker}

    def test_simple_overlap_assigns_speaker(self):
        segs = [self._seg(0.0, 2.0)]
        turns = [self._turn(0.0, 2.0, 0)]
        result = assign_speakers(segs, turns)
        assert result[0]["speaker_key"] == "spk1"

    def test_max_overlap_wins(self):
        # Segment 0-4s; speaker 0 covers 0-1 (1s), speaker 1 covers 1-4 (3s)
        segs = [self._seg(0.0, 4.0)]
        turns = [
            self._turn(0.0, 1.0, 0),
            self._turn(1.0, 4.0, 1),
        ]
        result = assign_speakers(segs, turns)
        assert result[0]["speaker_key"] == "spk2"

    def test_tiebreak_by_lowest_speaker_index(self):
        # Each speaker overlaps equally (1s each)
        segs = [self._seg(0.0, 2.0)]
        turns = [
            self._turn(0.0, 1.0, 1),  # spk2, 1s overlap
            self._turn(1.0, 2.0, 0),  # spk1, 1s overlap
        ]
        result = assign_speakers(segs, turns)
        # Tie-break: lowest speaker index (0 = spk1) wins
        assert result[0]["speaker_key"] == "spk1"

    def test_no_overlap_defaults_to_spk1(self):
        segs = [self._seg(5.0, 7.0)]
        turns = [self._turn(0.0, 3.0, 0)]
        result = assign_speakers(segs, turns)
        assert result[0]["speaker_key"] == "spk1"

    def test_empty_turns_defaults_to_spk1(self):
        segs = [self._seg(0.0, 2.0)]
        result = assign_speakers(segs, [])
        assert result[0]["speaker_key"] == "spk1"

    def test_empty_segments_returns_empty(self):
        result = assign_speakers([], [self._turn(0.0, 1.0, 0)])
        assert result == []

    def test_both_empty(self):
        assert assign_speakers([], []) == []

    def test_output_preserves_start_end_text(self):
        segs = [self._seg(1.0, 3.0, "hello world")]
        turns = [self._turn(1.0, 3.0, 2)]
        result = assign_speakers(segs, turns)
        assert result[0]["start"] == 1.0
        assert result[0]["end"] == 3.0
        assert result[0]["text"] == "hello world"
        assert result[0]["speaker_key"] == "spk3"

    def test_does_not_mutate_inputs(self):
        segs = [self._seg(0.0, 2.0, "hi")]
        turns = [self._turn(0.0, 2.0, 0)]
        original_seg_keys = set(segs[0].keys())
        assign_speakers(segs, turns)
        assert set(segs[0].keys()) == original_seg_keys

    def test_multiple_segments_each_labeled(self):
        segs = [
            self._seg(0.0, 2.0, "first"),
            self._seg(3.0, 5.0, "second"),
        ]
        turns = [
            self._turn(0.0, 2.0, 0),
            self._turn(3.0, 5.0, 1),
        ]
        result = assign_speakers(segs, turns)
        assert result[0]["speaker_key"] == "spk1"
        assert result[1]["speaker_key"] == "spk2"

    def test_partial_overlap_assigns_correct_speaker(self):
        # Segment 0-4; turn 0: 0-1 (overlap 1s), turn 1: 2-4 (overlap 2s)
        segs = [self._seg(0.0, 4.0)]
        turns = [
            self._turn(0.0, 1.0, 0),
            self._turn(2.0, 4.0, 1),
        ]
        result = assign_speakers(segs, turns)
        assert result[0]["speaker_key"] == "spk2"


# ---------------------------------------------------------------------------
# merge_streams
# ---------------------------------------------------------------------------


class TestMergeStreams:
    def _mic(self, start, end, text="mic text"):
        return {"start": start, "end": end, "text": text}

    def _loopback(self, start, end, speaker_key, text="lb text"):
        return {"start": start, "end": end, "text": text, "speaker_key": speaker_key}

    def test_ordering_by_start(self):
        mic = [self._mic(3.0, 4.0)]
        loopback = [self._loopback(1.0, 2.0, "spk1"), self._loopback(5.0, 6.0, "spk2")]
        result = merge_streams(mic, loopback)
        starts = [s["start"] for s in result]
        assert starts == [1.0, 3.0, 5.0]

    def test_mic_segments_labeled_you(self):
        mic = [self._mic(0.0, 2.0, "I said this")]
        loopback = []
        result = merge_streams(mic, loopback)
        assert result[0]["speaker_key"] == "you"
        assert result[0]["source"] == "mic"

    def test_loopback_keeps_speaker_key(self):
        mic = []
        loopback = [self._loopback(0.0, 2.0, "spk1", "they said")]
        result = merge_streams(mic, loopback)
        assert result[0]["speaker_key"] == "spk1"
        assert result[0]["source"] == "loopback"

    def test_output_keys(self):
        mic = [self._mic(0.0, 1.0)]
        result = merge_streams(mic, [])
        assert set(result[0].keys()) == {"start", "end", "speaker_key", "source", "text"}

    def test_empty_mic(self):
        loopback = [self._loopback(0.0, 2.0, "spk1")]
        result = merge_streams([], loopback)
        assert len(result) == 1
        assert result[0]["source"] == "loopback"

    def test_empty_loopback(self):
        mic = [self._mic(0.0, 2.0)]
        result = merge_streams(mic, [])
        assert len(result) == 1
        assert result[0]["source"] == "mic"

    def test_both_empty(self):
        assert merge_streams([], []) == []

    def test_interleave_correct(self):
        # Mic at 0, lb at 1, mic at 2, lb at 3
        mic = [self._mic(0.0, 0.5, "a"), self._mic(2.0, 2.5, "c")]
        loopback = [
            self._loopback(1.0, 1.5, "spk1", "b"),
            self._loopback(3.0, 3.5, "spk1", "d"),
        ]
        result = merge_streams(mic, loopback)
        assert [s["text"] for s in result] == ["a", "b", "c", "d"]

    def test_equal_start_mic_before_loopback(self):
        # On equal start, mic should come before loopback (deterministic)
        mic = [self._mic(1.0, 2.0, "mic")]
        loopback = [self._loopback(1.0, 2.0, "spk1", "lb")]
        result = merge_streams(mic, loopback)
        assert result[0]["source"] == "mic"
        assert result[1]["source"] == "loopback"


# ---------------------------------------------------------------------------
# attributed_transcript
# ---------------------------------------------------------------------------


class TestAttributedTranscript:
    def _seg(self, speaker_key, text):
        return {"start": 0.0, "end": 1.0, "speaker_key": speaker_key, "source": "loopback", "text": text}

    def test_basic_rendering(self):
        segs = [
            self._seg("spk1", "Hello there"),
            self._seg("you", "Hi"),
        ]
        result = attributed_transcript(segs, {})
        assert result == "Speaker 1: Hello there\nYou: Hi"

    def test_name_map_resolution(self):
        segs = [self._seg("spk1", "Hello")]
        result = attributed_transcript(segs, {"spk1": "Alice"})
        assert result == "Alice: Hello"

    def test_name_map_partial(self):
        segs = [
            self._seg("spk1", "one"),
            self._seg("spk2", "two"),
        ]
        result = attributed_transcript(segs, {"spk1": "Alice"})
        lines = result.split("\n")
        assert lines[0] == "Alice: one"
        assert lines[1] == "Speaker 2: two"

    def test_empty_segments_returns_empty_string(self):
        assert attributed_transcript([], {}) == ""

    def test_you_humanized_without_map(self):
        segs = [self._seg("you", "hello")]
        result = attributed_transcript(segs, {})
        assert result == "You: hello"

    def test_name_map_overrides_you(self):
        segs = [self._seg("you", "hello")]
        result = attributed_transcript(segs, {"you": "Bob"})
        assert result == "Bob: hello"

    def test_multiple_segments_joined_with_newline(self):
        segs = [
            self._seg("spk1", "line 1"),
            self._seg("spk1", "line 2"),
            self._seg("spk2", "line 3"),
        ]
        result = attributed_transcript(segs, {"spk2": "Carol"})
        assert result == "Speaker 1: line 1\nSpeaker 1: line 2\nCarol: line 3"
