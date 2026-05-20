from __future__ import annotations

import json
import random
from pathlib import Path

from logic.recent_responses import RecentResponseManager


APP_ROOT = Path(__file__).resolve().parent.parent
IDLE_DIALOGUE_PATH = APP_ROOT / "dialogue_data" / "idle.json"
REACTIONS_PATH = APP_ROOT / "dialogue_data" / "reactions.json"


class DialogueManager:
    """Load dialogue assets and return non-repetitive lines by situation."""

    def __init__(
        self,
        idle_path: Path = IDLE_DIALOGUE_PATH,
        reactions_path: Path = REACTIONS_PATH,
    ) -> None:
        self.idle_data = self._load_json(idle_path, self._default_idle_data())
        self.reaction_data = self._load_json(reactions_path, self._default_reaction_data())
        self.recent_responses = RecentResponseManager(max_entries=10, similarity_threshold=0.84)

    def friendship_rank(self, friendship: int) -> str:
        if friendship >= 20:
            return "high"
        if friendship >= 8:
            return "middle"
        return "low"

    def random_idle_line(self, friendship: int) -> str:
        rank = self.friendship_rank(friendship)
        return self._pick(self.idle_data["idle"][rank])

    def random_click_line(self, friendship: int) -> str:
        rank = self.friendship_rank(friendship)
        return self._pick(self.reaction_data["click"][rank])

    def random_paused_line(self) -> str:
        return self._pick(self.reaction_data["paused"])

    def random_resumed_line(self) -> str:
        return self._pick(self.reaction_data["resumed"])

    def remember(self, text: str) -> None:
        self.recent_responses.remember(text)

    def _pick(self, options: list[str]) -> str:
        line = self.recent_responses.choose(options, seed=random.randint(0, 10_000))
        self.recent_responses.remember(line)
        return line

    def _load_json(self, path: Path, default: dict) -> dict:
        if path.exists():
            with path.open("r", encoding="utf-8") as handle:
                return json.load(handle)
        return default

    def _default_idle_data(self) -> dict:
        return {
            "idle": {
                "low": [
                    "今日もここにいるのだー！",
                    "あわてなくていいのだ！ ゆっくりいくのだー！",
                    "ひとつできたら十分えらいのだ！",
                ],
                "middle": [
                    "ちょっと休んだらまたいけるのだー！",
                    "ゆっくりでも進んでたら立派なのだ！",
                    "よわはとなりで応援してるのだー！",
                ],
                "high": [
                    "頼ってほしいのだー！",
                    "ここにいてくれてうれしいのだ！",
                    "今日もがんばれるのだー！",
                ],
            }
        }

    def _default_reaction_data(self) -> dict:
        return {
            "click": {
                "low": ["わっ、びっくりしたのだ！", "呼んだのだ？ ちゃんといるのだ！"],
                "middle": ["見つけてくれてうれしいのだ！", "呼んでくれたなら、すぐ行くのだ！"],
                "high": ["近くにいてくれてうれしいのだ！", "今日もがんばれるのだー！"],
            },
            "paused": ["少し静かにしてるのだ！", "また呼んでくれたら戻るのだ！"],
            "resumed": ["戻ってきたのだ！", "また見守るのだ！"],
        }
