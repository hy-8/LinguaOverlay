from src.stabilizer import UtteranceAssembler, WordStabilizer, join_word_tokens
from src.whisper_engine import SegmentResult, WordResult


def test_word_stabilizer_only_commits_stable_new_words() -> None:
    stabilizer = WordStabilizer()
    segments = [
        SegmentResult(
            0.0,
            2.0,
            "Hello world",
            [
                WordResult(0.0, 0.5, " Hello"),
                WordResult(0.5, 1.0, " world"),
            ],
        )
    ]
    committed, preview = stabilizer.select(segments, window_start=10.0, stable_before=10.7)
    assert committed == "Hello"
    assert preview == "Hello world"

    committed, _ = stabilizer.select(segments, window_start=10.0, stable_before=11.2)
    assert committed == "world"


def test_assembler_flushes_on_japanese_punctuation() -> None:
    assembler = UtteranceAssembler(max_hold_seconds=2)
    assert assembler.add("今日は", now=1.0) is None
    assert assembler.add("いい天気です。", now=1.2) == "今日はいい天気です。"


def test_assembler_preserves_spacing_across_english_batches() -> None:
    assembler = UtteranceAssembler(max_hold_seconds=2)
    assert assembler.add("Hello, this is a", now=1.0) is None
    assert assembler.add("real-time test.", now=1.2) == "Hello, this is a real-time test."


def test_assembler_flushes_after_timeout() -> None:
    assembler = UtteranceAssembler(max_hold_seconds=2)
    assert assembler.add("unfinished", now=1.0) is None
    assert assembler.poll(now=2.9) is None
    assert assembler.poll(now=3.1) == "unfinished"


def test_assembler_flushes_continuous_speech_after_max_buffer() -> None:
    assembler = UtteranceAssembler(
        max_hold_seconds=2,
        max_buffer_seconds=1.2,
        max_chars=100,
    )
    assert assembler.add("continuous", now=1.0) is None
    assert assembler.add("speech", now=1.8) is None
    assert assembler.add("keeps going", now=2.3) == "continuous speech keeps going"


def test_assembler_flushes_at_low_latency_character_limit() -> None:
    assembler = UtteranceAssembler(
        max_hold_seconds=2,
        max_buffer_seconds=10,
        max_chars=12,
    )
    assert assembler.add("short", now=1.0) is None
    assert assembler.add("subtitle", now=1.1) == "short subtitle"


def test_join_word_tokens_handles_english_and_japanese_spacing() -> None:
    assert (
        join_word_tokens(["Hello", ",", "this", "is", "a", "real", "-time", "test", "."])
        == "Hello, this is a real-time test."
    )
    assert join_word_tokens(["今日", "は", "いい", "天気", "です", "。"]) == "今日はいい天気です。"


def test_word_stabilizer_drops_shifted_boundary_duplicate() -> None:
    stabilizer = WordStabilizer()
    first = [
        SegmentResult(
            0.0,
            2.6,
            "subtitle translation",
            [
                WordResult(2.0, 2.2, "subtitle"),
                WordResult(2.2, 2.6, "translation"),
            ],
        )
    ]
    committed, _ = stabilizer.select(first, window_start=0.0, stable_before=2.7)
    assert committed == "subtitle translation"

    shifted = [
        SegmentResult(
            0.0,
            3.1,
            "translation test",
            [
                WordResult(2.3, 2.75, "translation"),
                WordResult(2.75, 3.1, "test"),
            ],
        )
    ]
    committed, _ = stabilizer.select(shifted, window_start=0.0, stable_before=3.2)
    assert committed == "test"


def test_word_stabilizer_ignores_punctuation_when_deduplicating() -> None:
    stabilizer = WordStabilizer()
    first = [
        SegmentResult(
            0.0,
            1.0,
            "test",
            [WordResult(0.0, 1.0, "test")],
        )
    ]
    committed, _ = stabilizer.select(first, window_start=0.0, stable_before=1.1)
    assert committed == "test"

    shifted = [
        SegmentResult(
            0.0,
            1.5,
            "test, next",
            [
                WordResult(0.9, 1.1, "test,"),
                WordResult(1.1, 1.5, "next"),
            ],
        )
    ]
    committed, _ = stabilizer.select(shifted, window_start=0.0, stable_before=1.6)
    assert committed == "next"
