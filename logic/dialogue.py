import random


class DialogueManager:
    """友情度に応じたセリフを選ぶクラスです。"""

    IDLE_LINES = {
        "low": [
            "今日は静かだね。",
            "ここ、落ち着くかも。",
            "少しだけ見守ってるよ。",
        ],
        "middle": [
            "ちゃんと休憩してる？",
            "作業、いい感じに進んでる？",
            "そばにいると安心するね。",
        ],
        "high": [
            "今日も一緒にがんばろうね。",
            "きみのペース、けっこう好きだよ。",
            "疲れたら、少しだけ深呼吸しよ。",
        ],
    }

    CLICK_LINES = {
        "low": [
            "わっ、びっくりした。",
            "な、なに？",
            "呼んだ？",
        ],
        "middle": [
            "えへへ、なあに？",
            "ちょっと元気出た。",
            "クリック、確認しました。",
        ],
        "high": [
            "ふふ、会いに来てくれた？",
            "きみが来ると嬉しいな。",
            "今日も味方だよ。",
        ],
    }

    PAUSED_LINES = [
        "一時停止するね。",
        "静かにしてるね。",
        "また呼んでね。",
    ]

    RESUMED_LINES = [
        "戻ってきたよ。",
        "また見守るね。",
        "再開するね。",
    ]

    def friendship_rank(self, friendship: int) -> str:
        """友情度を low / middle / high の3段階に分けます。"""
        if friendship >= 20:
            return "high"
        if friendship >= 8:
            return "middle"
        return "low"

    def random_idle_line(self, friendship: int) -> str:
        rank = self.friendship_rank(friendship)
        return random.choice(self.IDLE_LINES[rank])

    def random_click_line(self, friendship: int) -> str:
        rank = self.friendship_rank(friendship)
        return random.choice(self.CLICK_LINES[rank])

    def random_paused_line(self) -> str:
        return random.choice(self.PAUSED_LINES)

    def random_resumed_line(self) -> str:
        return random.choice(self.RESUMED_LINES)
