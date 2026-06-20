import numpy as np

from src.audio_capture import resample_mono
from src.buffer import AudioRingBuffer


def test_resample_changes_length() -> None:
    source = np.linspace(-1, 1, 4800, dtype=np.float32)
    target = resample_mono(source, 48000, 16000)
    assert len(target) == 1600
    assert target.dtype == np.float32


def test_ring_buffer_tracks_absolute_time() -> None:
    buffer = AudioRingBuffer(sample_rate=10, capacity_seconds=2)
    buffer.append(np.ones(15, dtype=np.float32))
    buffer.append(np.ones(15, dtype=np.float32))
    data, start, end = buffer.snapshot(1)
    assert len(data) == 10
    assert start == 2.0
    assert end == 3.0
