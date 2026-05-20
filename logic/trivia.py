from __future__ import annotations

import json
import random
from pathlib import Path

from logic.state import CharacterState


APP_ROOT = Path(__file__).resolve().parent.parent
TRIVIA_PATH = APP_ROOT / "dialogue_data" / "trivia.json"


class TriviaManager:
    """Provides occasional low-frequency trivia lines."""

    def __init__(self, data_path: Path = TRIVIA_PATH) -> None:
        self.data_path = data_path
        self.lines = self._load_lines()

    def maybe_pick_line(
        self,
        state: CharacterState,
        paused: bool,
        recent_emotions: list[str] | None = None,
        probability: float = 0.08,
    ) -> str | None:
        recent_emotions = recent_emotions or []
        if paused or state.energy <= 0.35 or state.mood == "sleepy":
            return None
        if any(emotion in {"sad", "lonely", "anxious", "empty", "socially_tired", "overstimulated"} for emotion in recent_emotions[-3:]):
            return None
        if not self.lines or random.random() >= probability:
            return None
        return random.choice(self.lines)

    def _load_lines(self) -> list[str]:
        if not self.data_path.exists():
            return []
        with self.data_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        return [line.strip() for line in payload.get("trivia", []) if line and line.strip()]
