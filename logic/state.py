from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from data.database import StateRepository


def _clamp(value: float, minimum: float, maximum: float) -> float:
    """値を指定範囲に収めます。"""
    return max(minimum, min(maximum, value))


@dataclass
class CharacterState:
    """キャラクターの現在状態です。将来のAI会話にもこの情報を渡します。"""

    friendship: int
    mood: str
    energy: float
    stress_level: float
    last_interaction: datetime
    last_talk_time: datetime


class CharacterStateService:
    """状態の更新ルールと保存をまとめるクラスです。"""

    VALID_MOODS = {"normal", "happy", "sad", "sleepy"}

    def __init__(self, repository: StateRepository | None = None) -> None:
        self.repository = repository or StateRepository()
        self.state = self._load_or_create_state()

    def _load_or_create_state(self) -> CharacterState:
        row = self.repository.load_state_row()
        if row:
            return CharacterState(**row)

        now = datetime.now()
        return CharacterState(
            friendship=self.repository.load_legacy_friendship(),
            mood="normal",
            energy=1.0,
            stress_level=0.0,
            last_interaction=now,
            last_talk_time=now,
        )

    def save(self) -> None:
        self.repository.save_state(self.state)

    def update_for_time_passage(self, now: datetime | None = None) -> None:
        """時間経過に応じて energy と mood を更新します。"""
        now = now or datetime.now()
        elapsed_minutes = max(0.0, (now - self.state.last_interaction).total_seconds() / 60.0)

        if elapsed_minutes >= 20:
            self.state.energy = _clamp(self.state.energy - 0.02, 0.0, 1.0)
        else:
            self.state.energy = _clamp(self.state.energy + 0.005, 0.0, 1.0)

        self.update_mood_from_friendship()
        self.save()

    def update_mood_from_friendship(self) -> None:
        """友情度と状態から基本 mood を決めます。"""
        if self.state.energy < 0.25:
            self.state.mood = "sleepy"
        elif self.state.stress_level >= 0.7:
            self.state.mood = "sad"
        elif self.state.friendship >= 20:
            self.state.mood = "happy"
        else:
            self.state.mood = "normal"

    def mark_interaction(self) -> None:
        self.state.last_interaction = datetime.now()
        self.save()

    def mark_talked(self) -> None:
        self.state.last_talk_time = datetime.now()
        self.save()

    def set_mood(self, mood: str) -> None:
        if mood in self.VALID_MOODS:
            self.state.mood = mood
            self.save()

    def increase_friendship(self, amount: int = 1) -> None:
        self.state.friendship += amount
        self.state.mood = "happy"
        self.state.stress_level = _clamp(self.state.stress_level - 0.08, 0.0, 1.0)
        self.mark_interaction()

    def apply_emotion(self, emotion: str) -> None:
        """ユーザー入力の感情分類をキャラクター状態へ反映します。"""
        self.mark_interaction()

        if emotion == "happy":
            self.state.stress_level = _clamp(self.state.stress_level - 0.12, 0.0, 1.0)
            self.state.mood = "happy"
        elif emotion in {"stressed", "angry"}:
            self.state.stress_level = _clamp(self.state.stress_level + 0.16, 0.0, 1.0)
            self.state.mood = "sad"
        elif emotion == "sad":
            self.state.stress_level = _clamp(self.state.stress_level + 0.1, 0.0, 1.0)
            self.state.mood = "sad"
        elif emotion == "tired":
            self.state.energy = _clamp(self.state.energy - 0.18, 0.0, 1.0)
            self.state.mood = "sleepy"

        self.save()

    def as_prompt_context(self) -> str:
        """AI会話に渡しやすい、短い状態説明を作ります。"""
        return (
            f"friendship={self.state.friendship}, "
            f"mood={self.state.mood}, "
            f"energy={self.state.energy:.2f}, "
            f"stress_level={self.state.stress_level:.2f}, "
            f"last_interaction={self.state.last_interaction.isoformat()}, "
            f"last_talk_time={self.state.last_talk_time.isoformat()}"
        )
