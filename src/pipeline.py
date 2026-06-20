from __future__ import annotations

import queue
import threading
import time
from collections import deque
from collections.abc import Callable
from pathlib import Path

from src.audio_capture import AudioCapture
from src.buffer import AudioRingBuffer
from src.config import Settings
from src.stabilizer import UtteranceAssembler, WordStabilizer
from src.translator import MiniMaxTranslator, MockTranslator, TranslationContext
from src.whisper_engine import WhisperEngine


class RealtimePipeline:
    def __init__(
        self,
        settings: Settings,
        project_dir: Path,
        force_mock: bool,
        on_status: Callable[[str], None],
        on_preview: Callable[[str], None],
        on_subtitle: Callable[[str, str], None],
    ) -> None:
        self.settings = settings
        self.project_dir = project_dir
        self.on_status = on_status
        self.on_preview = on_preview
        self.on_subtitle = on_subtitle
        self.buffer = AudioRingBuffer(
            settings.target_sample_rate,
            capacity_seconds=max(settings.window_seconds + 3, 15),
        )
        self.capture = AudioCapture(
            target_sample_rate=settings.target_sample_rate,
            on_audio=self.buffer.append,
            device_index=settings.audio_device_index,
            on_status=on_status,
        )
        self.whisper = WhisperEngine(
            settings.whisper_model,
            settings.whisper_device,
            settings.whisper_compute_type,
            project_dir / "models",
        )
        self.translator = (
            MockTranslator()
            if force_mock or not settings.minimax_api_key
            else MiniMaxTranslator(
                settings.minimax_api_key,
                settings.minimax_base_url,
                settings.minimax_model,
                settings.translation_timeout_seconds,
            )
        )
        self.using_mock = isinstance(self.translator, MockTranslator)
        self._translation_queue: queue.Queue[str | None] = queue.Queue(maxsize=20)
        self._context: deque[TranslationContext] = deque(maxlen=6)
        self._stop_event = threading.Event()
        self._transcribe_thread: threading.Thread | None = None
        self._translate_thread: threading.Thread | None = None

    def start(self) -> None:
        if self._transcribe_thread and self._transcribe_thread.is_alive():
            return
        self._stop_event.clear()
        self._translate_thread = threading.Thread(
            target=self._translation_loop, name="translation", daemon=True
        )
        self._transcribe_thread = threading.Thread(
            target=self._transcription_loop, name="transcription", daemon=True
        )
        self._translate_thread.start()
        self._transcribe_thread.start()

    def stop(self) -> None:
        if self._stop_event.is_set():
            return
        self._stop_event.set()
        self.capture.stop()
        try:
            self._translation_queue.put_nowait(None)
        except queue.Full:
            pass
        for thread in (self._transcribe_thread, self._translate_thread):
            if thread and thread.is_alive():
                thread.join(timeout=4)
        self.translator.close()

    def _transcription_loop(self) -> None:
        try:
            self.on_status(f"正在加载 Whisper：{self.settings.whisper_model}")
            self.whisper.load()
            mode = "模拟翻译" if self.using_mock else f"MiniMax {self.settings.minimax_model}"
            self.on_status(f"模型已加载 · {mode}")
            self.capture.start()

            stabilizer = WordStabilizer()
            assembler = UtteranceAssembler(self.settings.translation_hold_seconds)

            while not self._stop_event.wait(self.settings.hop_seconds):
                if self.buffer.duration < 1.5:
                    continue
                audio, window_start, window_end = self.buffer.snapshot(
                    self.settings.window_seconds
                )
                segments = self.whisper.transcribe(audio, self.settings.source_language)
                stable_before = window_end - self.settings.finalize_delay_seconds
                committed, preview = stabilizer.select(
                    segments, window_start, stable_before
                )
                if preview:
                    self.on_preview(preview[-220:])
                ready = assembler.add(committed) if committed else assembler.poll()
                if ready:
                    self._enqueue_translation(ready)
        except Exception as exc:
            self.on_status(f"识别失败：{exc}")
        finally:
            pending = locals().get("assembler")
            if pending:
                ready = pending.flush()
                if ready:
                    self._enqueue_translation(ready)

    def _enqueue_translation(self, text: str) -> None:
        try:
            self._translation_queue.put_nowait(text)
            self.on_status("正在翻译…")
        except queue.Full:
            try:
                self._translation_queue.get_nowait()
                self._translation_queue.put_nowait(text)
            except queue.Empty:
                pass

    def _translation_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                source = self._translation_queue.get(timeout=0.5)
            except queue.Empty:
                continue
            if source is None:
                break
            try:
                translation = self.translator.translate(source, list(self._context))
                self._context.append(TranslationContext(source, translation))
                self.on_subtitle(source, translation)
                self.on_status("监听中")
            except Exception as exc:
                self.on_subtitle(source, f"翻译失败：{exc}")
                self.on_status("翻译失败，识别仍在继续")
