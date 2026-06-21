from src.translator import (
    FallbackTranslator,
    QwenMTTranslator,
    clean_model_output,
    clean_stream_output,
)


def test_clean_model_output_removes_thinking_and_prefix() -> None:
    raw = "<think>internal reasoning</think>\n译文：你好。"
    assert clean_model_output(raw) == "你好。"


def test_clean_stream_output_hides_incomplete_thinking() -> None:
    assert clean_stream_output("<think>still reasoning") == ""
    assert clean_stream_output("<think>done</think>译文：你好") == "你好"


def test_qwen_mt_payload_uses_translation_options() -> None:
    translator = QwenMTTranslator("key", "https://example.com/v1", "qwen-mt-lite", 5)
    payload = translator._payload("Hello", stream=True)
    translator.close()

    assert payload["model"] == "qwen-mt-lite"
    assert payload["messages"] == [{"role": "user", "content": "Hello"}]
    assert payload["translation_options"] == {
        "source_lang": "auto",
        "target_lang": "Chinese",
    }


class FakeTranslator:
    def __init__(self, result: str = "", error: Exception | None = None) -> None:
        self.result = result
        self.error = error
        self.calls = 0

    def translate(self, text, context):
        self.calls += 1
        if self.error:
            raise self.error
        return self.result

    def translate_stream(self, text, context, on_partial):
        result = self.translate(text, context)
        on_partial(result)
        return result

    def close(self):
        return None


def test_fallback_translator_disables_failed_primary_after_probe() -> None:
    primary = FakeTranslator(error=RuntimeError("invalid key"))
    fallback = FakeTranslator(result="你好")
    translator = FallbackTranslator(primary, fallback, "qwen", "minimax")

    assert translator.prepare() is False
    assert translator.active_name == "minimax"
    assert translator.translate("Hello", []) == "你好"
    assert primary.calls == 1
    assert fallback.calls == 1
