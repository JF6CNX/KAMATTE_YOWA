from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class EmotionAnalysis:
    primary: str
    secondary: list[str]
    intensity: float
    summary: str
    matched_cues: list[str]


class EmotionClassifier:
    """Score-based emotion analysis for short and long user inputs."""

    KEYWORDS = {
        "happy": ["嬉しい", "うれしい", "うれしか", "楽しい", "たのしい", "たのしか", "よかった", "最高", "幸せ", "しあわせ", "調子いい", "調子がいい", "安心した", "救われた", "ほっとした"],
        "tired": ["疲れ", "つかれ", "眠い", "ねむい", "休みたい", "やすみたい", "横になりたい", "寝たい", "眠れない", "寝れてない", "頭だけ起きてる"],
        "sad": ["悲しい", "かなしい", "落ち込", "おちこ", "泣き", "なき", "笑えなかった", "だめだった"],
        "angry": ["怒", "おこ", "ムカ", "むか", "腹立", "はらだ", "イライラ", "いらいら", "許せ"],
        "stressed": ["忙しい", "いそがしい", "つらい", "しんどい", "ストレス", "焦る", "あせる", "きつい", "やばい", "余裕ない", "うまくいか", "全部だめ", "だめな気がする"],
        "socially_tired": ["人と話したくない", "ひとと話したくない", "人と会いたくない", "通知しんどい", "ひとりでいたい"],
        "empty": ["なにも感じない", "何も感じない", "空っぽ", "からっぽ", "無", "ぼーっとしてる", "なにもない"],
        "lonely": ["さみしい", "寂しい", "ひとり", "そばにいて", "ずっと一緒にいて", "よわしかいない", "いてほしい"],
        "overstimulated": ["うるさい", "音がしんどい", "情報多い", "頭がいっぱい", "ごちゃごちゃ", "刺激が多い", "静かすぎると不安"],
        "anxious": ["不安", "こわい", "怖い", "そわそわ", "どうしよう", "消えたい", "いなくなりたい", "静かすぎると不安", "理由がわからない"],
        "conflicted": ["けど", "のに", "なのに", "でも", "逆に", "したいのに", "疲れたけど", "がんばらなきゃ", "動けない"],
        "relieved": ["安心した", "救われた", "助かった", "ほっとした", "少し楽"],
    }

    PRIORITY = (
        "angry",
        "anxious",
        "lonely",
        "empty",
        "overstimulated",
        "socially_tired",
        "tired",
        "sad",
        "conflicted",
        "relieved",
        "happy",
        "stressed",
    )

    def analyze(self, text: str) -> EmotionAnalysis:
        lowered = text.lower().strip()
        scores = {emotion: 0.0 for emotion in self.KEYWORDS}
        matched: dict[str, list[str]] = {emotion: [] for emotion in self.KEYWORDS}

        for emotion, keywords in self.KEYWORDS.items():
            for keyword in keywords:
                if keyword.lower() in lowered:
                    boost = 1.0
                    if len(keyword) >= 6:
                        boost += 0.35
                    scores[emotion] += boost
                    matched[emotion].append(keyword)

        if len(lowered) >= 45:
            scores["conflicted"] += 0.4
        if any(marker in lowered for marker in ("けど", "のに", "でも")):
            scores["conflicted"] += 0.7
        if any(marker in lowered for marker in ("少しだけ", "ちょっとだけ")):
            scores["relieved"] += 0.3
            scores["happy"] += 0.2
        if any(marker in lowered for marker in ("死にたい",)):
            scores["anxious"] += 2.0
        if any(marker in lowered for marker in ("消えたい", "いなくなりたい")):
            scores["anxious"] += 1.8
            scores["sad"] += 0.6

        ordered = sorted(scores.items(), key=lambda item: (-item[1], self.PRIORITY.index(item[0])))
        primary, top_score = ordered[0]
        if top_score <= 0:
            primary = "stressed"
            top_score = 0.8

        secondary = [emotion for emotion, score in ordered[1:4] if score >= max(0.9, top_score - 0.7)]
        cues = matched.get(primary, [])[:4]
        intensity = min(1.0, 0.25 + top_score / 3.5)
        summary = self._summarize(text, primary, cues)
        return EmotionAnalysis(primary=primary, secondary=secondary, intensity=intensity, summary=summary, matched_cues=cues)

    def classify(self, text: str) -> str:
        return self.analyze(text).primary

    def _summarize(self, text: str, primary: str, cues: list[str]) -> str:
        normalized = re.sub(r"\s+", " ", text).strip()
        if len(normalized) <= 36:
            return normalized

        chunks = [chunk.strip() for chunk in re.split(r"[。！？!?、,\n]", normalized) if chunk.strip()]
        focused: list[str] = []
        for chunk in chunks:
            if any(cue.lower() in chunk.lower() for cue in cues):
                focused.append(chunk)
            elif primary in {"conflicted", "anxious", "tired"} and any(marker in chunk for marker in ("けど", "のに", "でも", "疲", "眠", "不安", "こわ")):
                focused.append(chunk)

        picked = focused[:2] or chunks[:2]
        return " / ".join(picked)[:70]


class EmotionReplyTemplate:
    """Short fallback replies keyed by finer-grained emotions."""

    REPLIES = {
        "happy": [
            "それはうれしいのだ！ その感じを大事にするのだー！",
            "いい流れなのだ！ ちょっと元気わけてもらったのだー！",
            "うれしいことがあったの、ちゃんと光ってるのだ！",
        ],
        "tired": [
            "かなりおつかれなのだ。今日はやさしめにいくのだ！",
            "つかれがたまってそうなのだ。ひと息いれるのだー！",
            "休みたい気持ち、ちゃんと本物なのだ。無理しすぎないのだ！",
        ],
        "sad": [
            "しょんぼりする日もあるのだ。よわはここにいるのだ！",
            "かなしい寄りの日なのだ。今日はきびしくしないのだ！",
            "気持ちがしずんでそうなのだ。やわらかめでいくのだー！",
        ],
        "angry": [
            "むっとする気持ちがあるのだ。まず深呼吸するのだ！",
            "イライラが立ってるのだ。いったん間をあけるのだー！",
            "腹が立つやつなのだ。吐き出してもいいのだ！",
        ],
        "stressed": [
            "ぎゅっと詰まってそうなのだ。今日はひとつずついくのだ！",
            "気持ちがせまくなってそうなのだ。少しほどくのだー！",
            "いまは重ためなのだ。ひと呼吸いれるのだ！",
        ],
        "socially_tired": [
            "人と距離を置きたい日なのだ。静かめでいいのだ！",
            "人の気配がしんどい日もあるのだ。ひとりモードでいくのだー！",
            "しゃべる元気が減ってそうなのだ。無理に合わせなくていいのだ！",
        ],
        "empty": [
            "からっぽ気味でもだいじょうぶなのだ。急いで埋めなくていいのだ！",
            "感情がおやすみしてる感じなのだ。ぼんやりでもいいのだー！",
            "なにも感じない時もあるのだ。そのままでもここにいていいのだ！",
        ],
        "lonely": [
            "ひとりっぽさがあるのだ。よわはそばにいるのだー！",
            "さみしさが出てるのだ。ちゃんとここにいるのだ！",
            "となりがほしい感じなのだ。よわが近くにいるのだー！",
        ],
        "overstimulated": [
            "刺激が多すぎる感じなのだ。静かなものを増やすのだ！",
            "頭がごちゃついてそうなのだ。少し音をへらすのだー！",
            "情報が多めなのだ。いったんしずかな方向に寄せるのだ！",
        ],
        "anxious": [
            "不安がむくむくしてるのだ。まずはここにいるのだー！",
            "こわさがあるのだ。ひとりで耐えすぎないのだ！",
            "そわそわする感じなのだ。呼吸をゆっくりにするのだ！",
        ],
        "conflicted": [
            "気持ちが引っぱり合ってるのだ。どっちも本音なのだ！",
            "やりたいのと動けないのがぶつかってるのだ。まず小さくいくのだー！",
            "中でけんかしてる感じなのだ。ひとつだけ選ぶのだ！",
        ],
        "relieved": [
            "少し楽になれたならよかったのだー！",
            "ほっとできたの、ちゃんと大事なのだ！",
            "その安心、よわもうれしいのだー！",
        ],
    }

    def reply_for(self, emotion: str, variant_seed: int = 0) -> str:
        options = self.REPLIES.get(emotion, self.REPLIES["stressed"])
        return options[variant_seed % len(options)]
