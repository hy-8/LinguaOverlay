from __future__ import annotations

import threading
from collections.abc import Callable

import numpy as np


def resample_mono(samples: np.ndarray, source_rate: int, target_rate: int) -> np.ndarray:
    samples = np.asarray(samples, dtype=np.float32)
    if source_rate == target_rate or len(samples) == 0:
        return samples
    target_length = max(1, round(len(samples) * target_rate / source_rate))
    source_positions = np.linspace(0.0, 1.0, num=len(samples), endpoint=False)
    target_positions = np.linspace(0.0, 1.0, num=target_length, endpoint=False)
    return np.interp(target_positions, source_positions, samples).astype(np.float32)


def list_loopback_devices() -> list[dict]:
    import pyaudiowpatch as pyaudio

    audio = pyaudio.PyAudio()
    try:
        return [dict(device) for device in audio.get_loopback_device_info_generator()]
    finally:
        audio.terminate()


def print_loopback_devices() -> None:
    devices = list_loopback_devices()
    if not devices:
        print("未找到 WASAPI 回环设备。")
        return
    for device in devices:
        print(
            f"[{device['index']}] {device['name']} | "
            f"{int(device['defaultSampleRate'])} Hz | "
            f"{device['maxInputChannels']} ch"
        )


class AudioCapture:
    def __init__(
        self,
        target_sample_rate: int,
        on_audio: Callable[[np.ndarray], None],
        device_index: int | None = None,
        on_status: Callable[[str], None] | None = None,
    ) -> None:
        self.target_sample_rate = target_sample_rate
        self.on_audio = on_audio
        self.device_index = device_index
        self.on_status = on_status or (lambda _: None)
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, name="audio-capture", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)

    def _select_device(self, audio) -> dict:
        devices = [dict(device) for device in audio.get_loopback_device_info_generator()]
        if not devices:
            raise RuntimeError("没有找到 WASAPI 回环录音设备")
        if self.device_index is not None:
            for device in devices:
                if int(device["index"]) == self.device_index:
                    return device
            raise RuntimeError(f"找不到音频设备索引 {self.device_index}")
        return dict(audio.get_default_wasapi_loopback())

    def _run(self) -> None:
        import pyaudiowpatch as pyaudio

        audio = pyaudio.PyAudio()
        stream = None
        try:
            device = self._select_device(audio)
            source_rate = int(device["defaultSampleRate"])
            channels = max(1, int(device["maxInputChannels"]))
            frames_per_buffer = max(512, source_rate // 20)
            self.on_status(f"正在捕获：{device['name']}")
            stream = audio.open(
                format=pyaudio.paInt16,
                channels=channels,
                rate=source_rate,
                input=True,
                input_device_index=int(device["index"]),
                frames_per_buffer=frames_per_buffer,
            )
            while not self._stop_event.is_set():
                raw = stream.read(frames_per_buffer, exception_on_overflow=False)
                pcm = np.frombuffer(raw, dtype=np.int16)
                if channels > 1:
                    pcm = pcm.reshape(-1, channels).mean(axis=1)
                mono = pcm.astype(np.float32) / 32768.0
                self.on_audio(resample_mono(mono, source_rate, self.target_sample_rate))
        except Exception as exc:
            self.on_status(f"音频捕获失败：{exc}")
        finally:
            if stream is not None:
                stream.stop_stream()
                stream.close()
            audio.terminate()
