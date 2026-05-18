import random
from dataclasses import dataclass

from logic.activity import UserActivityMonitor
from logic.state import CharacterState


@dataclass
class RandomAction:
    """ランダム行動の結果です。UI はこれを見て表示や移動を行います。"""

    name: str
    line: str
    mood: str | None = None
    move_to_edge: bool = False
    duration_ms: int = 2500


class RandomActionManager:
    """独り言・眠る・伸び・小移動などのランダム行動を決めます。"""

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
            return RandomAction("sleep", "少しだけ、うとうとするね。", "sleepy", False, 5000)

        roll = random.random()
        if roll < 0.2:
            return RandomAction("stretch", "んー、ちょっと伸びるね。", "normal", False, 2800)
        if roll < 0.35:
            return RandomAction("edge_move", "少し場所を変えてみるね。", None, True, 2500)

        if state.mood == "happy":
            return RandomAction("talk", "今ちょっと機嫌いいかも。", "happy")
        if state.mood == "sad":
            return RandomAction("talk", "今日は静かめにそばにいるね。", "sad")
        if state.mood == "sleepy":
            return RandomAction("talk", "眠くなってきちゃった。", "sleepy")
        return RandomAction("talk", "作業、無理しすぎてない？", "normal")
