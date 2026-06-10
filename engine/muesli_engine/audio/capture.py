from __future__ import annotations

import logging
import threading
import time
import wave
from pathlib import Path

import pyaudiowpatch as pyaudio

_CHUNK = 1024
_log = logging.getLogger(__name__)


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
    """Records WASAPI loopback (system audio) and default mic to separate WAV files.

    Captures two concurrent streams:
    - Loopback: what plays through the default output device (remote participants).
    - Mic: default WASAPI input device (local speaker).

    Each stream runs its own thread and frame buffer. If no mic device is
    available, or opening the mic stream fails, the recorder degrades gracefully
    to loopback-only and ``stop()`` returns ``mic=None``.

    ``stop()`` returns::

        {
            "loopback": "<path>",
            "mic": "<path or None>",
            "mic_offset": <float>,  # seconds; positive = mic started later
        }
    """

    def __init__(self, out_path: str | Path):
        self.out_path = str(out_path)
        self._loopback_path, self._mic_path = _derive_paths(out_path)

        self._pa = pyaudio.PyAudio()

        # --- loopback state ---
        self._lb_frames: list[bytes] = []
        self._lb_stream = None
        self._lb_thread: threading.Thread | None = None
        self._lb_channels: int = 2
        self._lb_rate: int = 48000
        self._loopback_t0: float = 0.0

        # --- mic state ---
        self._mic_frames: list[bytes] = []
        self._mic_stream = None
        self._mic_thread: threading.Thread | None = None
        self._mic_channels: int = 1
        self._mic_rate: int = 16000
        self._mic_t0: float = 0.0
        self._mic_available: bool = False

        self._running = False

    # ------------------------------------------------------------------
    # Device discovery
    # ------------------------------------------------------------------

    def _loopback_device(self) -> dict:
        wasapi = self._pa.get_host_api_info_by_type(pyaudio.paWASAPI)
        default_out = self._pa.get_device_info_by_index(wasapi["defaultOutputDevice"])
        for i in range(self._pa.get_device_count()):
            dev = self._pa.get_device_info_by_index(i)
            if dev.get("isLoopbackDevice") and default_out["name"] in dev["name"]:
                return dev
        raise RuntimeError("No WASAPI loopback device found for the default output.")

    def _mic_device(self) -> dict:
        wasapi = self._pa.get_host_api_info_by_type(pyaudio.paWASAPI)
        default_in_idx = wasapi.get("defaultInputDevice", -1)
        if default_in_idx < 0:
            raise RuntimeError("No default WASAPI input device.")
        return self._pa.get_device_info_by_index(int(default_in_idx))

    # ------------------------------------------------------------------
    # Read loops (one per stream)
    # ------------------------------------------------------------------

    def _loopback_loop(self) -> None:
        first = True
        while self._running:
            data = self._lb_stream.read(_CHUNK, exception_on_overflow=False)
            if first:
                self._loopback_t0 = time.monotonic()
                first = False
            self._lb_frames.append(data)

    def _mic_loop(self) -> None:
        first = True
        while self._running:
            data = self._mic_stream.read(_CHUNK, exception_on_overflow=False)
            if first:
                self._mic_t0 = time.monotonic()
                first = False
            self._mic_frames.append(data)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        # --- loopback ---
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
        )

        # --- mic (optional; degrade gracefully on failure) ---
        try:
            mic_dev = self._mic_device()
            self._mic_channels = int(mic_dev["maxInputChannels"]) or 1
            self._mic_rate = int(mic_dev["defaultSampleRate"])
            self._mic_stream = self._pa.open(
                format=pyaudio.paInt16,
                channels=self._mic_channels,
                rate=self._mic_rate,
                frames_per_buffer=_CHUNK,
                input=True,
                input_device_index=mic_dev["index"],
            )
            self._mic_available = True
        except Exception as exc:  # noqa: BLE001
            _log.warning("Mic stream unavailable; recording loopback only. (%s)", exc)
            self._mic_available = False

        self._running = True

        self._lb_thread = threading.Thread(target=self._loopback_loop, daemon=True)
        self._lb_thread.start()

        if self._mic_available:
            self._mic_thread = threading.Thread(target=self._mic_loop, daemon=True)
            self._mic_thread.start()

    def stop(self) -> dict:
        self._running = False

        # Join loopback thread
        if self._lb_thread:
            self._lb_thread.join()
        if self._lb_stream:
            self._lb_stream.stop_stream()
            self._lb_stream.close()

        # Join mic thread
        if self._mic_thread:
            self._mic_thread.join()
        if self._mic_stream:
            self._mic_stream.stop_stream()
            self._mic_stream.close()

        # Write loopback WAV
        with wave.open(self._loopback_path, "wb") as wf:
            wf.setnchannels(self._lb_channels)
            wf.setsampwidth(self._pa.get_sample_size(pyaudio.paInt16))
            wf.setframerate(self._lb_rate)
            wf.writeframes(b"".join(self._lb_frames))

        # Write mic WAV (only if we captured mic frames)
        mic_out: str | None = None
        if self._mic_available and self._mic_frames:
            with wave.open(self._mic_path, "wb") as wf:
                wf.setnchannels(self._mic_channels)
                wf.setsampwidth(self._pa.get_sample_size(pyaudio.paInt16))
                wf.setframerate(self._mic_rate)
                wf.writeframes(b"".join(self._mic_frames))
            mic_out = self._mic_path

        # Compute offset (seconds; positive = mic started later than loopback)
        mic_offset = (self._mic_t0 - self._loopback_t0) if mic_out is not None else 0.0

        self._pa.terminate()

        return {
            "loopback": self._loopback_path,
            "mic": mic_out,
            "mic_offset": mic_offset,
        }
