from __future__ import annotations

import os
import wave
from pathlib import Path

import pyaudiowpatch as pyaudio

_CHUNK = 1024


class Recorder:
    """Records the default WASAPI loopback (system audio) to a WAV file.

    Captures system output (what you hear in the meeting). Mic mixing is a
    follow-up; loopback alone already captures remote participants when audio
    plays through the speakers/headset output device.

    Uses PortAudio callback mode: PortAudio drives its own audio thread and
    hands us each buffer via ``_callback``. This avoids a manual read loop,
    whose blocking ``stream.read()`` either hangs on ``stop`` (when no audio is
    playing) or crashes natively if the stream is closed mid-read from another
    thread. ``stop_stream``/``close`` are thread-safe in callback mode.
    """

    def __init__(self, out_path: str | Path):
        self.out_path = str(out_path)
        self._pa = pyaudio.PyAudio()
        self._frames: list[bytes] = []
        self._stream = None
        self._channels = 2
        self._rate = 48000

    def _loopback_device(self) -> dict:
        wasapi = self._pa.get_host_api_info_by_type(pyaudio.paWASAPI)

        # Explicit override: capture the loopback whose name contains this
        # substring. Needed when the default output is a virtual device (e.g.
        # SteelSeries Sonar / VoiceMeeter) that splits audio into multiple
        # streams -- capturing the physical endpoint (e.g. "Arctis Nova 7")
        # records everything you actually hear, regardless of app routing.
        preferred = os.environ.get("MUESLI_CAPTURE_DEVICE", "").strip()
        if preferred:
            for i in range(self._pa.get_device_count()):
                dev = self._pa.get_device_info_by_index(i)
                if dev.get("isLoopbackDevice") and preferred.lower() in dev["name"].lower():
                    return dev
            raise RuntimeError(
                f"No WASAPI loopback device matches MUESLI_CAPTURE_DEVICE={preferred!r}."
            )

        default_out = self._pa.get_device_info_by_index(wasapi["defaultOutputDevice"])
        for i in range(self._pa.get_device_count()):
            dev = self._pa.get_device_info_by_index(i)
            if dev.get("isLoopbackDevice") and default_out["name"] in dev["name"]:
                return dev
        raise RuntimeError("No WASAPI loopback device found for the default output.")

    def _callback(self, in_data, frame_count, time_info, status):
        self._frames.append(in_data)
        return (None, pyaudio.paContinue)

    def start(self) -> None:
        dev = self._loopback_device()
        self._channels = int(dev["maxInputChannels"]) or 2
        self._rate = int(dev["defaultSampleRate"])
        self._stream = self._pa.open(
            format=pyaudio.paInt16,
            channels=self._channels,
            rate=self._rate,
            frames_per_buffer=_CHUNK,
            input=True,
            input_device_index=dev["index"],
            stream_callback=self._callback,
        )

    def stop(self) -> str:
        stream = self._stream
        self._stream = None
        if stream is not None:
            try:
                stream.stop_stream()
            except Exception:
                pass
            try:
                stream.close()
            except Exception:
                pass
        with wave.open(self.out_path, "wb") as wf:
            wf.setnchannels(self._channels)
            wf.setsampwidth(self._pa.get_sample_size(pyaudio.paInt16))
            wf.setframerate(self._rate)
            wf.writeframes(b"".join(self._frames))
        try:
            self._pa.terminate()
        except Exception:
            pass
        return self.out_path
