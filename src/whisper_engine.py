from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np


@dataclass(slots=True)
class WordResult:
    start: float
    end: float
    text: str


@dataclass(slots=True)
class SegmentResult:
    start: float
    end: float
    text: str
    words: list[WordResult] = field(default_factory=list)


class WhisperEngine:
    def __init__(
        self,
        model_name: str,
        device: str,
        compute_type: str,
        download_root: Path,
    ) -> None:
        self.model_name = model_name
        self.device = device
        self.compute_type = compute_type
        self.download_root = download_root
        self._model = None

    def load(self) -> None:
        from faster_whisper import WhisperModel

        self.download_root.mkdir(parents=True, exist_ok=True)
        self._model = WhisperModel(
            self.model_name,
            device=self.device,
            compute_type=self.compute_type,
            download_root=str(self.download_root),
        )

    def transcribe(self, audio: np.ndarray, language: str) -> list[SegmentResult]:
        if self._model is None:
            raise RuntimeError("Whisper 模型尚未加载")
        selected_language = None if language == "auto" else language
        segments, _ = self._model.transcribe(
            audio,
            language=selected_language,
            beam_size=1,
            best_of=1,
            temperature=0.0,
            vad_filter=True,
            vad_parameters={
                "min_silence_duration_ms": 350,
                "speech_pad_ms": 180,
            },
            word_timestamps=True,
            condition_on_previous_text=False,
        )
        results: list[SegmentResult] = []
        for segment in segments:
            words = [
                WordResult(float(word.start), float(word.end), word.word)
                for word in (segment.words or [])
                if word.start is not None and word.end is not None
            ]
            results.append(
                SegmentResult(
                    start=float(segment.start),
                    end=float(segment.end),
                    text=segment.text.strip(),
                    words=words,
                )
            )
        return results
