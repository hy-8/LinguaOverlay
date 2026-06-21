from src.translator import clean_model_output, clean_stream_output


def test_clean_model_output_removes_thinking_and_prefix() -> None:
    raw = "<think>internal reasoning</think>\n译文：你好。"
    assert clean_model_output(raw) == "你好。"


def test_clean_stream_output_hides_incomplete_thinking() -> None:
    assert clean_stream_output("<think>still reasoning") == ""
    assert clean_stream_output("<think>done</think>译文：你好") == "你好"
