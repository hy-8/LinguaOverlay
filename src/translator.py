from __future__ import annotations

import re
from dataclasses import dataclass

import httpx


THINK_PATTERN = re.compile(r"<think>.*?</think>", flags=re.DOTALL | re.IGNORECASE)


def clean_model_output(text: str) -> str:
    cleaned = THINK_PATTERN.sub("", text).strip()
    prefixes = ("译文：", "翻译：", "中文字幕：")
    for prefix in prefixes:
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix) :].strip()
    return cleaned


@dataclass(slots=True)
class TranslationContext:
    source: str
    translation: str


class MockTranslator:
    def translate(self, text: str, context: list[TranslationContext]) -> str:
        del context
        return f"【模拟翻译】{text}"

    def close(self) -> None:
        return None


class MiniMaxTranslator:
    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        timeout_seconds: float,
    ) -> None:
        self.model = model
        self.client = httpx.Client(
            base_url=base_url.rstrip("/") + "/",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout_seconds,
        )

    def translate(self, text: str, context: list[TranslationContext]) -> str:
        context_lines = []
        for item in context[-4:]:
            context_lines.append(f"原文：{item.source}\n译文：{item.translation}")
        context_block = "\n\n".join(context_lines) or "无"
        response = self.client.post(
            "chat/completions",
            json={
                "model": self.model,
                "temperature": 0.1,
                "max_tokens": 500,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "你是实时影视字幕翻译器。将日语或英语翻译成自然、简洁的简体中文字幕。"
                            "保留人名和语气，不解释，不添加注释，只输出译文。"
                            "输入可能是尚未结束的短句，应结合上下文合理翻译。"
                        ),
                    },
                    {
                        "role": "user",
                        "content": f"最近上下文：\n{context_block}\n\n待翻译原文：\n{text}",
                    },
                ],
            },
        )
        response.raise_for_status()
        payload = response.json()
        content = payload["choices"][0]["message"]["content"]
        translation = clean_model_output(content)
        if not translation:
            raise RuntimeError("MiniMax 返回了空译文")
        return translation

    def close(self) -> None:
        self.client.close()
