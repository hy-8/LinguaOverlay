from __future__ import annotations

import threading

import numpy as np


class AudioRingBuffer:
    def __init__(self, sample_rate: int, capacity_seconds: float) -> None:
        self.sample_rate = sample_rate
        self.capacity_samples = int(sample_rate * capacity_seconds)
        self._data = np.empty(0, dtype=np.float32)
        self._total_samples = 0
        self._lock = threading.Lock()

    def append(self, samples: np.ndarray) -> None:
        values = np.asarray(samples, dtype=np.float32)
        with self._lock:
            self._data = np.concatenate((self._data, values))
            if len(self._data) > self.capacity_samples:
                self._data = self._data[-self.capacity_samples :]
            self._total_samples += len(values)

    def snapshot(self, seconds: float) -> tuple[np.ndarray, float, float]:
        requested = int(self.sample_rate * seconds)
        with self._lock:
            data = self._data[-requested:].copy()
            total_samples = self._total_samples
        end_time = total_samples / self.sample_rate
        start_time = end_time - len(data) / self.sample_rate
        return data, start_time, end_time

    @property
    def duration(self) -> float:
        with self._lock:
            return len(self._data) / self.sample_rate
