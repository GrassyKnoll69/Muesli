from __future__ import annotations

import threading
import wave
from pathlib import Path

import pyaudiowpatch as pyaudio

_CHUNK = 1024


class Recorder:
    """Records the default WASAPI loopback (system audio) to a WAV file.

    Captures system output (what you hear in the meeting). Mic mixing is a
    follow-up; loopback alone already captures remote participants when audio
    plays through the speakers/headset output device.
    """

    def __init__(self, out_path: str | Path):
        self.out_path = str(out_path)
        self._pa = pyaudio.PyAudio()
        self._frames: list[bytes] = []
        self._stream = None
        self._thread: threading.Thread | None = None
        self._running = False
        self._channels = 2
        self._rate = 48000

    def _loopback_device(self) -> dict:
        wasapi = self._pa.get_host_api_info_by_type(pyaudio.paWASAPI)
        default_out = self._pa.get_device_info_by_index(wasapi["defaultOutputDevice"])
        for i in range(self._pa.get_device_count()):
            dev = self._pa.get_device_info_by_index(i)
            if dev.get("isLoopbackDevice") and default_out["name"] in dev["name"]:
                return dev
        raise RuntimeError("No WASAPI loopback device found for the default output.")

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
        )
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self) -> None:
        while self._running:
            self._frames.append(self._stream.read(_CHUNK, exception_on_overflow=False))

    def stop(self) -> str:
        self._running = False
        if self._thread:
            self._thread.join()
        if self._stream:
            self._stream.stop_stream()
            self._stream.close()
        with wave.open(self.out_path, "wb") as wf:
            wf.setnchannels(self._channels)
            wf.setsampwidth(self._pa.get_sample_size(pyaudio.paInt16))
            wf.setframerate(self._rate)
            wf.writeframes(b"".join(self._frames))
        self._pa.terminate()
        return self.out_path
