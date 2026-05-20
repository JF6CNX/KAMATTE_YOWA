from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parent.parent
PERSONA_DIR = APP_ROOT / "persona"
PERSONALITY_PATH = PERSONA_DIR / "personality.json"
EXAMPLES_PATH = PERSONA_DIR / "examples.jsonl"
TOKEN_RE = re.compile(r"[ぁ-んァ-ン一-龠A-Za-z0-9_]+")


@dataclass
class PersonaExample:
    text: str
    score: int = 0
    mood_tag: str = "neutral"


class PersonaRepository:
    """Load persona metadata and emotion-tagged example lines."""

    TAG_RULES = {
        "happy": ("うれしい", "嬉しい", "楽しい", "かわいい", "えらい", "最高", "すごい", "やった"),
        "sad": ("かなしい", "悲しい", "さみしい", "寂しい", "泣", "しょんぼり"),
        "tired": ("疲", "眠", "休", "おふとん", "寝る", "うとうと", "ぬくぬく"),
        "stressed": ("しんど", "つらい", "詰", "不安", "こわい", "焦", "だめかも"),
        "angry": ("怒", "ムカ", "腹立", "許せ", "いらいら"),
    }

    def __init__(
        self,
        personality_path: Path = PERSONALITY_PATH,
        examples_path: Path = EXAMPLES_PATH,
    ) -> None:
        self.personality = self._load_json(personality_path)
        self.examples = self._load_examples(examples_path)

    def build_prompt_fragment(self, max_examples: int = 8) -> str:
        if not self.personality:
            return ""

        lines: list[str] = ["よわ人格メモ:"]
        if self.personality.get("identity"):
            lines.append(f"- 立ち位置: {self.personality['identity']}")

        label_map = {
            "tone_rules": "口調ルール",
            "style_rules": "文体ルール",
            "avoid_rules": "避ける表現",
            "favorite_phrases": "よく使う言い回し",
            "soft_endings": "語尾",
        }
        for key, label in label_map.items():
            values = self.personality.get(key, [])
            if values:
                joined = " / ".join(str(value) for value in values[:10])
                lines.append(f"- {label}: {joined}")

        if self.examples:
            lines.append("話し方の例:")
            for example in self.examples[:max_examples]:
                lines.append(f"- {example.text}")

        return "\n".join(lines)

    def retrieve_reply(self, user_text: str, emotion: str | None = None) -> str | None:
        if not self.examples:
            return None

        pool = self.examples
        if emotion:
            tagged = [example for example in self.examples if example.mood_tag == emotion]
            if tagged:
                pool = tagged

        query_tokens = self._tokenize(user_text)
        best_score = -1.0
        best_text: str | None = None

        for example in pool:
            example_tokens = self._tokenize(example.text)
            overlap = self._overlap_score(query_tokens, example_tokens)
            total = overlap + (example.score * 0.015)
            if total > best_score:
                best_score = total
                best_text = example.text

        return best_text

    def _load_json(self, path: Path) -> dict:
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8-sig"))

    def _load_examples(self, path: Path) -> list[PersonaExample]:
        if not path.exists():
            return []

        rows: list[PersonaExample] = []
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            text = self._clean_example_text(str(row.get("text", "")).strip())
            if text:
                rows.append(
                    PersonaExample(
                        text=text,
                        score=int(row.get("score", 0)),
                        mood_tag=self._infer_mood_tag(text),
                    )
                )
        return rows

    def _clean_example_text(self, text: str) -> str:
        cleaned = re.sub(r"\s+", " ", text).strip()
        cleaned = re.sub(r"^よわ[はがをにと、,\s]*", "", cleaned)
        return cleaned

    def _infer_mood_tag(self, text: str) -> str:
        for tag, markers in self.TAG_RULES.items():
            if any(marker in text for marker in markers):
                return tag
        return "neutral"

    def _tokenize(self, text: str) -> set[str]:
        return {token.lower() for token in TOKEN_RE.findall(text)}

    def _overlap_score(self, left: set[str], right: set[str]) -> float:
        if not left or not right:
            return 0.0
        union = left | right
        if not union:
            return 0.0
        return len(left & right) / len(union)
