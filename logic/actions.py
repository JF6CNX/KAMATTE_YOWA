from __future__ import annotations

import random
from dataclasses import dataclass

from logic.activity import UserActivityMonitor
from logic.state import CharacterState


@dataclass
class RandomAction:
    """Random mascot action selected from current state and user activity."""

    name: str
    line: str | None = None
    mood: str | None = None
    move_to_edge: bool = False
    animation: str | None = None
    duration_ms: int = 2500


class RandomActionManager:
    """Chooses low-frequency random actions without interrupting active behavior."""

    def __init__(self, activity_monitor: UserActivityMonitor | None = None) -> None:
        self.activity_monitor = activity_monitor or UserActivityMonitor()
        self.is_acting = False

    def choose_action(self, state: CharacterState) -> RandomAction | None:
        if self.is_acting:
            return None

        probability = self.activity_monitor.conversation_probability()
        if random.random() > probability:
            return None

        if state.energy < 0.25 or random.random() < 0.12:
            return RandomAction(
                name="sleep",
                line="少しだけ、まぶたが重いかも……",
                mood="sleepy",
                animation="sleepy",
                duration_ms=5000,
            )

        roll = random.random()
        if roll < 0.18:
            return RandomAction(
                name="stretch",
                line="んん……ちょっとだけ、のびてみるね……",
                mood="normal",
                animation="idle",
                duration_ms=2800,
            )
        if roll < 0.3:
            return RandomAction(
                name="edge_move",
                line="すみっこに寄ったら、少し落ち着くかな……",
                move_to_edge=True,
                animation="idle",
                duration_ms=2500,
            )

        return RandomAction(
            name="talk",
            line=None,
            mood=state.mood if state.mood in {"happy", "sad", "sleepy"} else "normal",
            animation=None,
            duration_ms=4200,
        )
