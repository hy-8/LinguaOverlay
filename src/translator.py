from __future__ import annotations

import json
import re
import threading
from collections.abc import Callable
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


def clean_stream_output(text: str) -> str:
    lower = text.lower()
    think_start = lower.find("<think>")
    if think_start >= 0 and "</think>" not in lower[think_start:]:
        return clean_model_output(text[:think_start])
    return clean_model_output(text)


@dataclass(slots=True)
class TranslationContext:
    source: str
    translation: str


class MockTranslator:
    def translate(self, text: str, context: list[TranslationContext]) -> str:
        del context
        return f"【模拟翻译】{text}"

    def translate_stream(
        self,
        text: str,
        context: list[TranslationContext],
        on_partial: Callable[[str], None],
    ) -> str:
        result = self.translate(text, context)
        on_partial(result)
        return result

    def close(self) -> None:
        return None


class MiniMaxTranslator:
    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        timeout_seconds: float,
        context_items: int = 2,
    ) -> None:
        self.model = model
        self.context_items = context_items
        self.client = httpx.Client(
            base_url=base_url.rstrip("/") + "/",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout_seconds,
        )

    def translate(self, text: str, context: list[TranslationContext]) -> str:
        return self.translate_stream(text, context, lambda _: None)

    def _payload(
        self,
        text: str,
        context: list[TranslationContext],
        *,
        stream: bool,
    ) -> dict:
        context_lines = []
        for item in context[-self.context_items :]:
            context_lines.append(f"原文：{item.source}\n译文：{item.translation}")
        context_block = "\n\n".join(context_lines) or "无"
        return {
            "model": self.model,
            "temperature": 0.0,
            "max_tokens": 256,
            "stream": stream,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是低延迟实时字幕翻译器。将日语或英语翻译成自然、简洁的简体中文。"
                        "保留人名和语气，不解释，不添加注释，只输出译文。"
                        "输入可能是短句片段，应结合上下文直接翻译。"
                    ),
                },
                {
                    "role": "user",
                    "content": f"最近上下文：\n{context_block}\n\n待翻译原文：\n{text}",
                },
            ],
        }

    def translate_stream(
        self,
        text: str,
        context: list[TranslationContext],
        on_partial: Callable[[str], None],
    ) -> str:
        raw_content = ""
        last_partial = ""
        with self.client.stream(
            "POST",
            "chat/completions",
            json=self._payload(text, context, stream=True),
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if not data or data == "[DONE]":
                    continue
                chunk = json.loads(data)
                choices = chunk.get("choices") or []
                if not choices:
                    continue
                delta = choices[0].get("delta") or {}
                content = delta.get("content")
                if not isinstance(content, str) or not content:
                    continue
                raw_content += content
                partial = clean_stream_output(raw_content)
                if partial and partial != last_partial:
                    last_partial = partial
                    on_partial(partial)

        translation = clean_model_output(raw_content)
        if not translation:
            raise RuntimeError("MiniMax 返回了空译文")
        return translation

    def close(self) -> None:
        self.client.close()


class QwenMTTranslator:
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

    def _payload(self, text: str, *, stream: bool) -> dict:
        return {
            "model": self.model,
            "stream": stream,
            "messages": [{"role": "user", "content": text}],
            "translation_options": {
                "source_lang": "auto",
                "target_lang": "Chinese",
            },
        }

    def translate(self, text: str, context: list[TranslationContext]) -> str:
        del context
        response = self.client.post(
            "chat/completions",
            json=self._payload(text, stream=False),
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        translation = clean_model_output(content)
        if not translation:
            raise RuntimeError("Qwen-MT 返回了空译文")
        return translation

    def translate_stream(
        self,
        text: str,
        context: list[TranslationContext],
        on_partial: Callable[[str], None],
    ) -> str:
        del context
        raw_content = ""
        last_partial = ""
        with self.client.stream(
            "POST",
            "chat/completions",
            json=self._payload(text, stream=True),
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if not data or data == "[DONE]":
                    continue
                chunk = json.loads(data)
                choices = chunk.get("choices") or []
                if not choices:
                    continue
                delta = choices[0].get("delta") or {}
                content = delta.get("content")
                if not isinstance(content, str) or not content:
                    continue
                raw_content += content
                partial = clean_model_output(raw_content)
                if partial and partial != last_partial:
                    last_partial = partial
                    on_partial(partial)

        translation = clean_model_output(raw_content)
        if not translation:
            raise RuntimeError("Qwen-MT 返回了空译文")
        return translation

    def close(self) -> None:
        self.client.close()


class FallbackTranslator:
    def __init__(
        self,
        primary,
        fallback,
        primary_name: str,
        fallback_name: str,
    ) -> None:
        self.primary = primary
        self.fallback = fallback
        self.primary_name = primary_name
        self.fallback_name = fallback_name
        self._primary_enabled = True
        self._lock = threading.Lock()

    @property
    def active_name(self) -> str:
        with self._lock:
            return self.primary_name if self._primary_enabled else self.fallback_name

    def prepare(self) -> bool:
        try:
            self.primary.translate("Hello.", [])
            return True
        except Exception:
            self._disable_primary()
            return False

    def _disable_primary(self) -> None:
        with self._lock:
            self._primary_enabled = False

    def _use_primary(self) -> bool:
        with self._lock:
            return self._primary_enabled

    def translate(self, text: str, context: list[TranslationContext]) -> str:
        if not self._use_primary():
            return self.fallback.translate(text, context)
        try:
            return self.primary.translate(text, context)
        except Exception:
            self._disable_primary()
            return self.fallback.translate(text, context)

    def translate_stream(
        self,
        text: str,
        context: list[TranslationContext],
        on_partial: Callable[[str], None],
    ) -> str:
        if not self._use_primary():
            return self.fallback.translate_stream(text, context, on_partial)
        try:
            return self.primary.translate_stream(text, context, on_partial)
        except Exception:
            self._disable_primary()
            return self.fallback.translate_stream(text, context, on_partial)

    def close(self) -> None:
        self.primary.close()
        self.fallback.close()
