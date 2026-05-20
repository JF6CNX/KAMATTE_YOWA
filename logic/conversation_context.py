from __future__ import annotations

import re
from collections import deque
from dataclasses import dataclass


@dataclass
class ConversationTurn:
    user_text: str
    emotion: str
    summary: str
    ai_text: str = ""


class ConversationContextManager:
    """Stores a light-weight recent conversation state for fallback replies."""

    SERIOUS_EMOTIONS = {
        "sad",
        "lonely",
        "anxious",
        "empty",
        "overstimulated",
        "conflicted",
        "socially_tired",
    }

    def __init__(self, max_turns: int = 12) -> None:
        self.turns: deque[ConversationTurn] = deque(maxlen=max_turns)

    def add_user_message(self, text: str, emotion: str) -> ConversationTurn:
        turn = ConversationTurn(user_text=text.strip(), emotion=emotion, summary=self._summarize(text))
        self.turns.append(turn)
        return turn

    def add_ai_reply(self, reply: str) -> None:
        if self.turns and not self.turns[-1].ai_text:
            self.turns[-1].ai_text = reply.strip()

    def recent_context_text(self, limit: int = 5) -> str:
        recent = list(self.turns)[-limit:]
        lines = []
        for turn in recent:
            line = f"{turn.emotion}: {turn.summary}"
            if turn.ai_text:
                line += f" -> {turn.ai_text}"
            lines.append(line)
        return "\n".join(lines)

    def recent_emotions(self, limit: int = 4) -> list[str]:
        return [turn.emotion for turn in list(self.turns)[-limit:]]

    def last_turn(self) -> ConversationTurn | None:
        return self.turns[-1] if self.turns else None

    def was_recently_serious(self, limit: int = 3) -> bool:
        return any(emotion in self.SERIOUS_EMOTIONS for emotion in self.recent_emotions(limit))

    def previous_user_summary(self) -> str:
        if len(self.turns) < 2:
            return ""
        return list(self.turns)[-2].summary

    def _summarize(self, text: str) -> str:
        normalized = re.sub(r"\s+", " ", text).strip()
        if len(normalized) <= 36:
            return normalized

        chunks = [chunk.strip() for chunk in re.split(r"[。！？!?、,\n]", normalized) if chunk.strip()]
        weighted = [chunk for chunk in chunks if any(marker in chunk for marker in ("けど", "のに", "つら", "疲", "うれ", "不安", "寂", "しんど", "眠", "だめ"))]
        if weighted:
            summary = " / ".join(weighted[:2])
        else:
            summary = " / ".join(chunks[:2])
        return summary[:60]
