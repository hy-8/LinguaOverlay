from __future__ import annotations

import re
import time
import unicodedata

from src.whisper_engine import SegmentResult


LEFT_ATTACHING = set(".,!?;:%)]}-–—'’}。，！？、；：）」』】》〉…")
RIGHT_ATTACHING = set("([{（「『【《〈")


def _is_cjk_character(character: str) -> bool:
    if not character:
        return False
    name = unicodedata.name(character, "")
    return any(
        marker in name
        for marker in ("CJK", "HIRAGANA", "KATAKANA", "HANGUL", "IDEOGRAPH")
    )


def join_word_tokens(tokens: list[str]) -> str:
    result = ""
    for raw_token in tokens:
        token = raw_token.strip()
        if not token:
            continue
        if not result:
            result = token
            continue
        if (
            token[0] in LEFT_ATTACHING
            or result[-1] in RIGHT_ATTACHING
            or (_is_cjk_character(result[-1]) and _is_cjk_character(token[0]))
        ):
            result += token
        else:
            result += " " + token
    return result.strip()


def _normalize_token(token: str) -> str:
    return re.sub(r"\s+", "", token).casefold()


class WordStabilizer:
    def __init__(self, time_tolerance: float = 0.08) -> None:
        self.last_committed_end = 0.0
        self.time_tolerance = time_tolerance
        self._recent_tokens: list[str] = []

    def select(
        self,
        segments: list[SegmentResult],
        window_start: float,
        stable_before: float,
    ) -> tuple[str, str]:
        committed: list[str] = []
        preview: list[str] = []
        latest_end = self.last_committed_end

        for segment in segments:
            if segment.words:
                for word in segment.words:
                    absolute_end = window_start + word.end
                    preview.append(word.text)
                    if (
                        absolute_end <= stable_before
                        and absolute_end > self.last_committed_end + self.time_tolerance
                    ):
                        committed.append(word.text)
                        latest_end = max(latest_end, absolute_end)
            else:
                absolute_end = window_start + segment.end
                preview.append(segment.text)
                if (
                    absolute_end <= stable_before
                    and absolute_end > self.last_committed_end + self.time_tolerance
                ):
                    committed.append(segment.text)
                    latest_end = max(latest_end, absolute_end)

        if committed:
            overlap = self._find_recent_overlap(committed)
            committed = committed[overlap:]
            self.last_committed_end = latest_end
            self._recent_tokens.extend(committed)
            self._recent_tokens = self._recent_tokens[-40:]
        return join_word_tokens(committed), join_word_tokens(preview)

    def _find_recent_overlap(self, candidate: list[str]) -> int:
        recent = [_normalize_token(token) for token in self._recent_tokens]
        incoming = [_normalize_token(token) for token in candidate]
        maximum = min(len(recent), len(incoming), 12)
        for size in range(maximum, 0, -1):
            if recent[-size:] == incoming[:size]:
                return size
        return 0


class UtteranceAssembler:
    TERMINAL_PATTERN = re.compile(r"[。！？!?\.][”’」』】）)]?\s*$")

    def __init__(self, max_hold_seconds: float) -> None:
        self.max_hold_seconds = max_hold_seconds
        self._pending = ""
        self._updated_at = 0.0

    def add(self, text: str, now: float | None = None) -> str | None:
        if not text:
            return None
        current = time.monotonic() if now is None else now
        self._pending = join_word_tokens([self._pending, text])
        self._updated_at = current
        if self.TERMINAL_PATTERN.search(self._pending) or len(self._pending) >= 100:
            return self.flush()
        return None

    def poll(self, now: float | None = None) -> str | None:
        if not self._pending:
            return None
        current = time.monotonic() if now is None else now
        if current - self._updated_at >= self.max_hold_seconds:
            return self.flush()
        return None

    def flush(self) -> str | None:
        text = self._pending.strip()
        self._pending = ""
        self._updated_at = 0.0
        return text or None
