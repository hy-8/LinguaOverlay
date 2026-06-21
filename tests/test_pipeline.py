import threading
from collections import deque

from src.pipeline import RealtimePipeline
from src.translator import TranslationContext


def test_merge_chunks_keeps_order_without_backlog_loss() -> None:
    assert RealtimePipeline._merge_chunks(
        ["Hello.", "This is", "a subtitle."]
    ) == "Hello. This is a subtitle."


def make_pipeline_for_display_tests():
    emitted = []
    pipeline = object.__new__(RealtimePipeline)
    pipeline._state_lock = threading.Lock()
    pipeline._context = deque(maxlen=6)
    pipeline._display_history = deque(maxlen=2)
    pipeline._pending_results = {}
    pipeline._next_display_sequence = 1
    pipeline._last_emitted_subtitle = None
    pipeline.on_subtitle = lambda source, translation: emitted.append(
        (source, translation)
    )
    return pipeline, emitted


def test_concurrent_results_are_displayed_in_sequence() -> None:
    pipeline, emitted = make_pipeline_for_display_tests()

    assert pipeline._complete_translation(2, "second", "第二") is False
    assert pipeline._complete_translation(1, "first", "第一") is True
    assert emitted == [("first second", "第一第二")]


def test_partial_translation_includes_previous_completed_subtitle() -> None:
    pipeline, emitted = make_pipeline_for_display_tests()

    pipeline._complete_translation(1, "first", "第一")
    assert pipeline._emit_partial(2, "second", "第二") is True
    assert emitted[-1] == ("first second", "第一第二")


def test_duplicate_final_stream_update_is_suppressed() -> None:
    pipeline, emitted = make_pipeline_for_display_tests()

    assert pipeline._emit_partial(1, "hello", "你好") is True
    assert pipeline._complete_translation(1, "hello", "你好") is False
    assert emitted == [("hello", "你好")]
