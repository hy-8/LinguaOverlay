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
from src.stabilizer import UtteranceAssembler, WordStabilizer, join_word_tokens
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
                settings.translation_context_items,
            )
        )
        self.using_mock = isinstance(self.translator, MockTranslator)
        self._translation_queue: queue.Queue[tuple[int, str] | None] = queue.Queue(
            maxsize=settings.translation_queue_size
        )
        self._context: deque[TranslationContext] = deque(maxlen=6)
        self._display_history: deque[TranslationContext] = deque(
            maxlen=settings.subtitle_history_items
        )
        self._pending_results: dict[int, TranslationContext] = {}
        self._state_lock = threading.Lock()
        self._next_display_sequence = 1
        self._next_sequence = 0
        self._last_emitted_subtitle: tuple[str, str] | None = None
        self._stop_event = threading.Event()
        self._transcribe_thread: threading.Thread | None = None
        self._translate_threads: list[threading.Thread] = []
        self._last_asr_seconds = 0.0

    def start(self) -> None:
        if self._transcribe_thread and self._transcribe_thread.is_alive():
            return
        self._stop_event.clear()
        self._translate_threads = [
            threading.Thread(
                target=self._translation_loop,
                name=f"translation-{index + 1}",
                daemon=True,
            )
            for index in range(self.settings.translation_workers)
        ]
        self._transcribe_thread = threading.Thread(
            target=self._transcription_loop, name="transcription", daemon=True
        )
        for thread in self._translate_threads:
            thread.start()
        self._transcribe_thread.start()

    def stop(self) -> None:
        if self._stop_event.is_set():
            return
        self._stop_event.set()
        self.capture.stop()
        for _ in self._translate_threads:
            try:
                self._translation_queue.put_nowait(None)
            except queue.Full:
                break
        for thread in (self._transcribe_thread, *self._translate_threads):
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
            assembler = UtteranceAssembler(
                self.settings.translation_hold_seconds,
                self.settings.translation_max_buffer_seconds,
                self.settings.translation_max_chars,
            )
            next_transcription = time.monotonic()

            while not self._stop_event.is_set():
                wait_seconds = max(0.0, next_transcription - time.monotonic())
                if self._stop_event.wait(wait_seconds):
                    break
                cycle_started = time.monotonic()
                if self.buffer.duration < self.settings.minimum_audio_seconds:
                    next_transcription = cycle_started + self.settings.hop_seconds
                    continue
                audio, window_start, window_end = self.buffer.snapshot(
                    self.settings.window_seconds
                )
                segments = self.whisper.transcribe(audio, self.settings.source_language)
                self._last_asr_seconds = time.monotonic() - cycle_started
                stable_before = window_end - self.settings.finalize_delay_seconds
                committed, preview = stabilizer.select(
                    segments, window_start, stable_before
                )
                if preview:
                    self.on_preview(preview[-220:])
                ready = assembler.add(committed) if committed else assembler.poll()
                if ready:
                    self._enqueue_translation(ready)
                next_transcription = max(
                    next_transcription + self.settings.hop_seconds,
                    time.monotonic(),
                )
        except Exception as exc:
            self.on_status(f"识别失败：{exc}")
        finally:
            pending = locals().get("assembler")
            if pending:
                ready = pending.flush()
                if ready:
                    self._enqueue_translation(ready)

    def _enqueue_translation(self, text: str) -> None:
        with self._state_lock:
            self._next_sequence += 1
            sequence = self._next_sequence
        try:
            self._translation_queue.put_nowait((sequence, text))
            self.on_status("正在翻译…")
        except queue.Full:
            pending: list[str] = []
            try:
                while True:
                    item = self._translation_queue.get_nowait()
                    if item is not None:
                        _, queued_text = item
                        pending.append(queued_text)
            except queue.Empty:
                pass
            merged = self._merge_chunks([*pending, text])
            self._translation_queue.put_nowait((sequence, merged))

    @staticmethod
    def _merge_chunks(chunks: list[str]) -> str:
        return " ".join(chunk.strip() for chunk in chunks if chunk.strip()).strip()

    def _translation_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                item = self._translation_queue.get(timeout=0.5)
            except queue.Empty:
                continue
            if item is None:
                break
            sequence, source = item
            try:
                translation_started = time.monotonic()
                last_partial_at = 0.0
                with self._state_lock:
                    context = list(self._context)

                def on_partial(partial: str) -> None:
                    nonlocal last_partial_at
                    now = time.monotonic()
                    if now - last_partial_at >= 0.08:
                        self._emit_partial(sequence, source, partial)
                        last_partial_at = now

                if self.settings.translation_stream:
                    translation = self.translator.translate_stream(
                        source,
                        context,
                        on_partial,
                    )
                else:
                    translation = self.translator.translate(source, context)
                self._complete_translation(sequence, source, translation)
                translation_seconds = time.monotonic() - translation_started
                self.on_status(
                    f"监听中 · 识别 {self._last_asr_seconds:.1f}s"
                    f" · 翻译 {translation_seconds:.1f}s"
                )
            except Exception as exc:
                self._complete_translation(sequence, source, f"翻译失败：{exc}")
                self.on_status("翻译失败，识别仍在继续")

    @staticmethod
    def _render_items(items: list[TranslationContext]) -> tuple[str, str]:
        return (
            join_word_tokens([item.source for item in items]),
            join_word_tokens([item.translation for item in items]),
        )

    def _emit_partial(self, sequence: int, source: str, translation: str) -> bool:
        with self._state_lock:
            if sequence != self._next_display_sequence:
                return False
            source_text, translation_text = self._render_items(
                [*self._display_history, TranslationContext(source, translation)]
            )
        return self._publish_subtitle(source_text, translation_text)

    def _complete_translation(
        self,
        sequence: int,
        source: str,
        translation: str,
    ) -> bool:
        rendered: tuple[str, str] | None = None
        with self._state_lock:
            self._pending_results[sequence] = TranslationContext(source, translation)
            while self._next_display_sequence in self._pending_results:
                item = self._pending_results.pop(self._next_display_sequence)
                self._context.append(item)
                self._display_history.append(item)
                self._next_display_sequence += 1
                rendered = self._render_items(list(self._display_history))
        if rendered is None:
            return False
        return self._publish_subtitle(*rendered)

    def _publish_subtitle(self, source: str, translation: str) -> bool:
        value = (source, translation)
        with self._state_lock:
            if value == self._last_emitted_subtitle:
                return False
            self._last_emitted_subtitle = value
        self.on_subtitle(source, translation)
        return True
