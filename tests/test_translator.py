from src.translator import clean_model_output


def test_clean_model_output_removes_thinking_and_prefix() -> None:
    raw = "<think>internal reasoning</think>\n译文：你好。"
    assert clean_model_output(raw) == "你好。"
