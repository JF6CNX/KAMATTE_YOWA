class EmotionClassifier:
    """ユーザー入力を簡単なルールで感情分類します。"""

    KEYWORDS = {
        "happy": ["嬉しい", "楽しい", "最高", "よかった", "できた", "幸せ", "happy"],
        "stressed": ["忙しい", "つらい", "しんどい", "ストレス", "焦る", "stressed"],
        "sad": ["悲しい", "寂しい", "落ち込", "泣き", "sad"],
        "angry": ["怒", "ムカ", "腹立", "許せ", "angry"],
        "tired": ["疲れ", "眠い", "だるい", "休みたい", "tired"],
    }

    def classify(self, text: str) -> str:
        lowered = text.lower()
        for emotion, keywords in self.KEYWORDS.items():
            if any(keyword in lowered for keyword in keywords):
                return emotion
        return "stressed" if len(text) > 80 else "happy"


class EmotionReplyTemplate:
    """感情分類に応じたルールベース返答です。"""

    REPLIES = {
        "happy": "それ聞けて嬉しい。いい流れ、ちゃんと味わっておこうね。",
        "stressed": "かなり詰まってそうだね。今は一つだけ小さく片づけよ。",
        "sad": "そっか、今日は重たい日なんだね。ここでは無理に元気なふりしなくていいよ。",
        "angry": "それは腹が立つよね。まず息を整えて、言葉にする順番を一緒に戻そう。",
        "tired": "疲れてるんだね。少し休むのも作業のうちだよ。",
    }

    def reply_for(self, emotion: str) -> str:
        return self.REPLIES.get(emotion, self.REPLIES["stressed"])
