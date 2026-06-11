from __future__ import annotations

import logging
import os
import time
import wave
from pathlib import Path

import pyaudiowpatch as pyaudio

_CHUNK = 1024
_log = logging.getLogger(__name__)


def list_devices() -> dict[str, list[str]]:
    """Enumerate selectable WASAPI capture endpoints by display name.

    Returns ``{"loopback": [...], "input": [...]}`` (deduped, preserving order).
    Degrades to empty lists on any failure (e.g. no audio subsystem) — never
    raises, so the API endpoint is safe to call anywhere.
    """
    loopback: list[str] = []
    input_: list[str] = []
    loopback_seen: set[str] = set()
    input_seen: set[str] = set()
    pa = None
    try:
        pa = pyaudio.PyAudio()
        for i in range(pa.get_device_count()):
            dev = pa.get_device_info_by_index(i)
            name: str = dev["name"]
            if dev.get("isLoopbackDevice"):
                if name not in loopback_seen:
                    loopback.append(name)
                    loopback_seen.add(name)
            elif int(dev.get("maxInputChannels", 0)) > 0:
                if name not in input_seen:
                    input_.append(name)
                    input_seen.add(name)
    except Exception:
        return {"loopback": [], "input": []}
    finally:
        if pa is not None:
            try:
                pa.terminate()
            except Exception:
                pass
    return {"loopback": loopback, "input": input_}


def _derive_paths(out_path: str | Path) -> tuple[str, str]:
    """Derive sibling loopback/mic paths from a single base WAV path.

    ``<dir>/<stem>.wav``  →  loopback: ``<dir>/<stem>-loopback.wav``
                              mic:      ``<dir>/<stem>-mic.wav``
    """
    p = Path(out_path)
    stem = p.stem
    parent = p.parent
    loopback_path = str(parent / f"{stem}-loopback.wav")
    mic_path = str(parent / f"{stem}-mic.wav")
    return loopback_path, mic_path


class Recorder:
    """Records WASAPI loopback (system audio) and the mic to separate WAV files.

    Captures two concurrent streams:

    - **Loopback** — what plays through the chosen output device (every remote
      participant, mixed).
    - **Mic** — the chosen input device (the local user).

    Uses PortAudio **callback mode** for both streams: PortAudio drives its own
    audio thread and hands us each buffer via a callback. This avoids a manual
    read loop, whose blocking ``stream.read()`` either hangs on ``stop`` (when
    no audio is playing) or crashes natively if the stream is closed mid-read
    from another thread. ``stop_stream``/``close`` are thread-safe in callback
    mode, so ``stop()`` returns promptly.

    Device selection (both optional) chooses the capture endpoints by
    case-insensitive name substring:

    - ``capture_device`` selects the loopback endpoint. Falls back to the
      ``MUESLI_CAPTURE_DEVICE`` environment variable, then to the default
      output. Useful when the default output is a virtual device (e.g.
      SteelSeries Sonar / VoiceMeeter) that splits audio into multiple streams;
      capturing the physical endpoint records everything the user hears.
    - ``mic_device`` selects the input endpoint. Falls back to the default
      WASAPI input device.

    If no mic device is available, or opening the mic stream fails, the recorder
    degrades gracefully to loopback-only and ``stop()`` returns ``mic=None``.

    ``stop()`` returns::

        {
            "loopback": "<path>",
            "mic": "<path or None>",
            "mic_offset": <float>,  # seconds; positive = mic started later
        }
    """

    def __init__(
        self,
        out_path: str | Path,
        capture_device: str | None = None,
        mic_device: str | None = None,
    ):
        self.out_path = str(out_path)
        self._loopback_path, self._mic_path = _derive_paths(out_path)
        self.capture_device = capture_device
        self.mic_device = mic_device

        self._pa = pyaudio.PyAudio()

        # --- loopback state ---
        self._lb_frames: list[bytes] = []
        self._lb_stream = None
        self._lb_channels: int = 2
        self._lb_rate: int = 48000
        self._lb_t0: float | None = None

        # --- mic state ---
        self._mic_frames: list[bytes] = []
        self._mic_stream = None
        self._mic_channels: int = 1
        self._mic_rate: int = 16000
        self._mic_t0: float | None = None
        self._mic_available: bool = False

    # ------------------------------------------------------------------
    # Device discovery
    # ------------------------------------------------------------------

    def _loopback_device(self) -> dict:
        wasapi = self._pa.get_host_api_info_by_type(pyaudio.paWASAPI)

        # Explicit override (Settings value, else env var): capture the loopback
        # whose name contains this substring.
        preferred = (
            self.capture_device or os.environ.get("MUESLI_CAPTURE_DEVICE", "")
        ).strip()
        if preferred:
            for i in range(self._pa.get_device_count()):
                dev = self._pa.get_device_info_by_index(i)
                if dev.get("isLoopbackDevice") and preferred.lower() in dev["name"].lower():
                    return dev
            raise RuntimeError(
                f"No WASAPI loopback device matches capture device {preferred!r}."
            )

        default_out = self._pa.get_device_info_by_index(wasapi["defaultOutputDevice"])
        for i in range(self._pa.get_device_count()):
            dev = self._pa.get_device_info_by_index(i)
            if dev.get("isLoopbackDevice") and default_out["name"] in dev["name"]:
                return dev
        raise RuntimeError("No WASAPI loopback device found for the default output.")

    def _input_device(self) -> dict:
        wasapi = self._pa.get_host_api_info_by_type(pyaudio.paWASAPI)

        preferred = (self.mic_device or "").strip()
        if preferred:
            for i in range(self._pa.get_device_count()):
                dev = self._pa.get_device_info_by_index(i)
                if (
                    not dev.get("isLoopbackDevice")
                    and int(dev.get("maxInputChannels", 0)) > 0
                    and preferred.lower() in dev["name"].lower()
                ):
                    return dev
            raise RuntimeError(f"No WASAPI input device matches mic device {preferred!r}.")

        default_in_idx = wasapi.get("defaultInputDevice", -1)
        if default_in_idx is None or int(default_in_idx) < 0:
            raise RuntimeError("No default WASAPI input device.")
        return self._pa.get_device_info_by_index(int(default_in_idx))

    # ------------------------------------------------------------------
    # Callbacks (PortAudio drives its own thread; we just buffer)
    # ------------------------------------------------------------------

    def _loopback_callback(self, in_data, frame_count, time_info, status):
        if self._lb_t0 is None:
            self._lb_t0 = time.monotonic()
        self._lb_frames.append(in_data)
        return (None, pyaudio.paContinue)

    def _mic_callback(self, in_data, frame_count, time_info, status):
        if self._mic_t0 is None:
            self._mic_t0 = time.monotonic()
        self._mic_frames.append(in_data)
        return (None, pyaudio.paContinue)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        # --- loopback (required) ---
        lb_dev = self._loopback_device()
        self._lb_channels = int(lb_dev["maxInputChannels"]) or 2
        self._lb_rate = int(lb_dev["defaultSampleRate"])
        self._lb_stream = self._pa.open(
            format=pyaudio.paInt16,
            channels=self._lb_channels,
            rate=self._lb_rate,
            frames_per_buffer=_CHUNK,
            input=True,
            input_device_index=lb_dev["index"],
            stream_callback=self._loopback_callback,
        )

        # --- mic (optional; degrade gracefully on failure) ---
        try:
            mic_dev = self._input_device()
            self._mic_channels = int(mic_dev["maxInputChannels"]) or 1
            self._mic_rate = int(mic_dev["defaultSampleRate"])
            self._mic_stream = self._pa.open(
                format=pyaudio.paInt16,
                channels=self._mic_channels,
                rate=self._mic_rate,
                frames_per_buffer=_CHUNK,
                input=True,
                input_device_index=mic_dev["index"],
                stream_callback=self._mic_callback,
            )
            self._mic_available = True
        except Exception as exc:  # noqa: BLE001
            _log.warning("Mic stream unavailable; recording loopback only. (%s)", exc)
            self._mic_available = False

    def stop(self) -> dict:
        # Closing in callback mode is the supported, thread-safe path.
        for stream in (self._lb_stream, self._mic_stream):
            if stream is not None:
                try:
                    stream.stop_stream()
                except Exception:
                    pass
                try:
                    stream.close()
                except Exception:
                    pass
        self._lb_stream = None
        self._mic_stream = None

        # Write loopback WAV.
        with wave.open(self._loopback_path, "wb") as wf:
            wf.setnchannels(self._lb_channels)
            wf.setsampwidth(self._pa.get_sample_size(pyaudio.paInt16))
            wf.setframerate(self._lb_rate)
            wf.writeframes(b"".join(self._lb_frames))

        # Write mic WAV (only if we actually captured mic frames).
        mic_out: str | None = None
        if self._mic_available and self._mic_frames:
            with wave.open(self._mic_path, "wb") as wf:
                wf.setnchannels(self._mic_channels)
                wf.setsampwidth(self._pa.get_sample_size(pyaudio.paInt16))
                wf.setframerate(self._mic_rate)
                wf.writeframes(b"".join(self._mic_frames))
            mic_out = self._mic_path

        # Offset (seconds; positive = mic's first buffer arrived later than
        # loopback's). 0.0 when we have no mic or never received both streams.
        if mic_out is not None and self._mic_t0 is not None and self._lb_t0 is not None:
            mic_offset = self._mic_t0 - self._lb_t0
        else:
            mic_offset = 0.0

        try:
            self._pa.terminate()
        except Exception:
            pass

        return {
            "loopback": self._loopback_path,
            "mic": mic_out,
            "mic_offset": mic_offset,
        }
