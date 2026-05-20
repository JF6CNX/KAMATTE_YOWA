from __future__ import annotations

import re
from collections import deque
from dataclasses import dataclass
from difflib import SequenceMatcher


_PUNCT_RE = re.compile(r"[。！？!?…ー〜\s]+")
_ENDING_RE = re.compile(r"(のだ|なのだ)(ー+)?([。！？!?]+)?$")


@dataclass
class RecentResponse:
    text: str
    fingerprint: str
    shape: str


class RecentResponseManager:
    """Keeps recent responses and avoids repeating the same wording or shape."""

    def __init__(self, max_entries: int = 12, similarity_threshold: float = 0.88) -> None:
        self.history: deque[RecentResponse] = deque(maxlen=max_entries)
        self.similarity_threshold = similarity_threshold

    def remember(self, text: str) -> None:
        normalized = self._normalize(text)
        self.history.append(
            RecentResponse(
                text=text,
                fingerprint=normalized,
                shape=self._shape(normalized),
            )
        )

    def choose(self, options: list[str], seed: int = 0) -> str:
        if not options:
            return "だいじょうぶなのだー！"

        start = seed % len(options)
        ranked = options[start:] + options[:start]
        for candidate in ranked:
            if not self.is_blocked(candidate):
                return candidate
        return ranked[0]

    def is_blocked(self, text: str) -> bool:
        normalized = self._normalize(text)
        if not normalized:
            return False
        shape = self._shape(normalized)

        for item in self.history:
            if normalized == item.fingerprint:
                return True
            if shape == item.shape:
                return True
            if SequenceMatcher(None, normalized, item.fingerprint).ratio() >= self.similarity_threshold:
                return True
        return False

    def _normalize(self, text: str) -> str:
        lowered = text.strip().lower()
        lowered = _ENDING_RE.sub("", lowered)
        lowered = _PUNCT_RE.sub("", lowered)
        return lowered

    def _shape(self, normalized: str) -> str:
        if not normalized:
            return ""
        normalized = re.sub(r"[ぁ-んァ-ン]", "あ", normalized)
        normalized = re.sub(r"[一-龠]", "漢", normalized)
        normalized = re.sub(r"[a-z]", "a", normalized)
        normalized = re.sub(r"\d", "0", normalized)
        return normalized[:18]
