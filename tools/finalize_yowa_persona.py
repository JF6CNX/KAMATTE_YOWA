from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


APP_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCE_PATH = APP_ROOT / "persona" / "source_yowa_messages.jsonl"
DEFAULT_DRAFT_PATH = APP_ROOT / "persona" / "personality_draft.json"
DEFAULT_OUTPUT_PERSONALITY = APP_ROOT / "persona" / "personality.json"
DEFAULT_OUTPUT_EXAMPLES = APP_ROOT / "persona" / "examples.jsonl"
DEFAULT_OUTPUT_TRAINING = APP_ROOT / "persona" / "training_dialogues.jsonl"

YOWA_NAME = "よわ"
VALID_YOWA_ENDINGS = ("のだ", "なのだ")
TRAILING_DECORATION_RE = re.compile(r"[。！？!?…~～ー\s]+$")
SYSTEM_PROMPT = "あなたは『よわ』として、やさしく控えめに、語尾を『のだ』で終える。"
FRAGMENT_PREFIXES = (
    "は",
    "が",
    "を",
    "に",
    "へ",
    "と",
    "で",
    "も",
    "の",
    "って",
    "では",
    "には",
    "とは",
    "へは",
)
BAD_START_PREFIXES = (
    "、",
    "，",
    "。",
    "！",
    "!",
    "？",
    "?",
    "ー",
    "～",
    "たち",
    "ーず",
)
STRONG_PATTERNS = (
    "許せん",
    "絶対",
    "ぶっ",
    "殺",
    "死ね",
    "黙れ",
    "気合",
)
NOISY_PATTERNS = (
    "http://",
    "https://",
    "{Attachments}",
    "{Stickers}",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Finalize Yowa persona files from extracted source messages.")
    parser.add_argument("--source", default=str(DEFAULT_SOURCE_PATH), help="Path to source_yowa_messages.jsonl")
    parser.add_argument("--draft", default=str(DEFAULT_DRAFT_PATH), help="Path to personality_draft.json")
    parser.add_argument("--output-personality", default=str(DEFAULT_OUTPUT_PERSONALITY), help="Output path for personality.json")
    parser.add_argument("--output-examples", default=str(DEFAULT_OUTPUT_EXAMPLES), help="Output path for examples.jsonl")
    parser.add_argument("--output-training", default=str(DEFAULT_OUTPUT_TRAINING), help="Output path for training_dialogues.jsonl")
    parser.add_argument("--min-score", type=int, default=6, help="Minimum score for final example selection")
    parser.add_argument("--max-examples", type=int, default=120, help="Maximum finalized examples")
    parser.add_argument("--speaker", default=YOWA_NAME, help="Normalized speaker name to keep")
    parser.add_argument("--dry-run", action="store_true", help="Print summary only and do not write files")
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\r", "\n")).strip()


def canonical_text_key(text: str) -> str:
    return normalize_text(text).lower()


def normalize_for_ending(text: str) -> str:
    return TRAILING_DECORATION_RE.sub("", normalize_text(text))


def ends_with_yowa_style(text: str) -> bool:
    cleaned = normalize_for_ending(text)
    return any(cleaned.endswith(ending) for ending in VALID_YOWA_ENDINGS)


def starts_with_fragment(text: str) -> bool:
    cleaned = normalize_text(text)
    return cleaned.startswith(FRAGMENT_PREFIXES) or cleaned.startswith(BAD_START_PREFIXES)


def is_too_shouty(text: str) -> bool:
    return text.count("!") + text.count("！") >= 3


def contains_strong_tone(text: str) -> bool:
    return any(pattern in text for pattern in STRONG_PATTERNS)


def contains_noise(text: str) -> bool:
    return any(pattern in text for pattern in NOISY_PATTERNS)


def looks_like_complete_yowa_line(text: str) -> bool:
    cleaned = normalize_text(text)
    if len(cleaned) < 8:
        return False
    if starts_with_fragment(cleaned):
        return False
    if contains_noise(cleaned):
        return False
    if contains_strong_tone(cleaned):
        return False
    if is_too_shouty(cleaned):
        return False
    if "俺" in cleaned:
        return False
    if cleaned.count("のだ") + cleaned.count("なのだ") > 2:
        return False
    return True


def looks_like_user_prompt(text: str) -> bool:
    cleaned = normalize_text(text)
    if len(cleaned) < 6 or len(cleaned) > 80:
        return False
    if "http://" in cleaned or "https://" in cleaned:
        return False
    direct_markers = ("よわ", "おちび", "( ーωー)", "?", "？")
    return any(marker in cleaned for marker in direct_markers)


def is_good_example(row: dict[str, Any], min_score: int, speaker: str) -> bool:
    text = str(row.get("text", "")).strip()
    if row.get("speaker") != speaker:
        return False
    if int(row.get("score", 0)) < min_score:
        return False
    if not ends_with_yowa_style(text):
        return False
    if not looks_like_complete_yowa_line(text):
        return False
    return True


def parse_timestamp(value: str) -> tuple[int, str]:
    formats = (
        "%Y/%m/%d %H:%M",
        "%Y/%m/%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
    )
    for fmt in formats:
        try:
            return (0, datetime.strptime(value, fmt).isoformat())
        except ValueError:
            continue
    return (1, value)


def select_examples(rows: list[dict[str, Any]], min_score: int, max_examples: int, speaker: str) -> list[dict[str, Any]]:
    candidates = [row for row in rows if is_good_example(row, min_score, speaker)]
    candidates.sort(
        key=lambda row: (
            -int(row.get("score", 0)),
            "persona_prefix_override" not in row.get("reasons", []),
            parse_timestamp(str(row.get("timestamp", ""))),
        )
    )

    selected: list[dict[str, Any]] = []
    seen_keys: set[str] = set()
    for row in candidates:
        text = normalize_text(str(row.get("text", "")))
        key = canonical_text_key(text)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        selected.append(
            {
                "speaker": row.get("speaker", speaker),
                "original_speaker": row.get("original_speaker", ""),
                "timestamp": row.get("timestamp", ""),
                "text": text,
                "score": int(row.get("score", 0)),
                "reasons": row.get("reasons", []),
                "source_file": row.get("source_file", ""),
            }
        )
        if len(selected) >= max_examples:
            break
    return selected


def build_phrase_stats(examples: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
    phrase_candidates = (
        "……",
        "たぶん",
        "少しだけ",
        "うまく言えないけど",
        "無理しすぎないで",
        "となりにいる",
        "ゆっくり",
        "おちび",
        "こわい",
        "のだ",
    )
    ending_candidates = ("のだ", "なのだ")

    phrase_counts: dict[str, int] = {phrase: 0 for phrase in phrase_candidates}
    ending_counts: dict[str, int] = {ending: 0 for ending in ending_candidates}

    for row in examples:
        text = str(row["text"])
        for phrase in phrase_candidates:
            if phrase in text:
                phrase_counts[phrase] += 1
        cleaned = normalize_for_ending(text)
        for ending in ending_candidates:
            if cleaned.endswith(ending):
                ending_counts[ending] += 1

    favorite_phrases = [phrase for phrase, count in sorted(phrase_counts.items(), key=lambda item: (-item[1], item[0])) if count > 0]
    soft_endings = [ending for ending, count in sorted(ending_counts.items(), key=lambda item: (-item[1], item[0])) if count > 0]
    return favorite_phrases[:10], soft_endings[:4]


def build_final_personality(draft: dict[str, Any], examples: list[dict[str, Any]], min_score: int) -> dict[str, Any]:
    favorite_phrases, soft_endings = build_phrase_stats(examples)
    source_summary = draft.get("source_summary", {})

    return {
        "name": YOWA_NAME,
        "identity": "少し不安げで、やさしく寄り添う存在",
        "tone_hypotheses": ["控えめ", "やさしい", "少し不安げ", "断定しすぎない", "相手を追い詰めない"],
        "tone_rules": [
            "語尾は必ず『のだ』で終える",
            "控えめでやさしい口調を保つ",
            "少し不安げでも相手を追い詰めない",
            "強く断定しすぎない",
            "励ましすぎず、となりにいる感じを優先する",
        ],
        "style_rules": [
            "短文から中くらいの文を中心にする",
            "必要に応じて『……』『たぶん』『少しだけ』のような余白を残す",
            "相手のしんどさをすぐ否定しない",
            "豆知識を言う時も、やさしく少し不思議そうに言う",
        ],
        "avoid_rules": [
            "攻撃的な言い方",
            "命令口調",
            "強い断定",
            "過剰な励まし",
            "下品すぎる言い方",
            "語尾が『のだ』で終わらない返答",
        ],
        "favorite_phrases": favorite_phrases,
        "soft_endings": soft_endings or ["のだ"],
        "response_length_policy": {
            "preferred": "short_to_medium",
            "note": "長くなりすぎず、ひと息おける返答を優先する",
        },
        "trivia_style": "やさしく少し不思議そうな豆知識を低頻度で話す",
        "source_summary": {
            "accepted_messages": source_summary.get("accepted_messages", 0),
            "input_files": source_summary.get("input_files", []),
            "final_examples": len(examples),
            "final_min_score": min_score,
            "ending_policy": "must_end_with_no_da",
        },
        "review_notes": [
            "断片的な文や主語途中の文は finalizer で除外している",
            "examples.jsonl は人が確認してさらに削る前提の下書きでもある",
        ],
    }


def build_training_dialogues(rows: list[dict[str, Any]], speaker: str, min_score: int) -> list[dict[str, Any]]:
    ordered = sorted(
        rows,
        key=lambda row: (parse_timestamp(str(row.get("timestamp", ""))), str(row.get("source_file", "")), str(row.get("timestamp", ""))),
    )

    training: list[dict[str, Any]] = []
    seen_keys: set[str] = set()

    for previous, current in zip(ordered, ordered[1:]):
        if current.get("speaker") != speaker:
            continue
        if int(current.get("score", 0)) < min_score:
            continue
        if previous.get("speaker") == speaker:
            continue

        user_text = normalize_text(str(previous.get("text", "")))
        assistant_text = normalize_text(str(current.get("text", "")))

        if not looks_like_user_prompt(user_text):
            continue
        if not ends_with_yowa_style(assistant_text):
            continue
        if not looks_like_complete_yowa_line(assistant_text):
            continue
        if len(assistant_text) < 8 or len(assistant_text) > 80:
            continue

        key = f"{canonical_text_key(user_text)} -> {canonical_text_key(assistant_text)}"
        if key in seen_keys:
            continue
        seen_keys.add(key)

        training.append(
            {
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_text},
                    {"role": "assistant", "content": assistant_text},
                ],
                "metadata": {
                    "user_speaker": previous.get("speaker", ""),
                    "assistant_original_speaker": current.get("original_speaker", ""),
                    "timestamp": current.get("timestamp", ""),
                    "source_file": current.get("source_file", ""),
                    "assistant_score": int(current.get("score", 0)),
                },
            }
        )
    return training


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> int:
    args = parse_args()
    source_path = Path(args.source)
    draft_path = Path(args.draft)
    output_personality = Path(args.output_personality)
    output_examples = Path(args.output_examples)
    output_training = Path(args.output_training)

    draft = read_json(draft_path)
    rows = read_jsonl(source_path)
    examples = select_examples(rows, args.min_score, args.max_examples, args.speaker)
    training = build_training_dialogues(rows, args.speaker, args.min_score)
    personality = build_final_personality(draft, examples, args.min_score)

    if args.dry_run:
        print(f"source_rows={len(rows)}")
        print(f"selected_examples={len(examples)}")
        print(f"training_dialogues={len(training)}")
        print(f"output_personality={output_personality}")
        print(f"output_examples={output_examples}")
        print(f"output_training={output_training}")
        return 0

    write_json(output_personality, personality)
    write_jsonl(output_examples, examples)
    write_jsonl(output_training, training)

    print(f"Wrote finalized personality to {output_personality}")
    print(f"Wrote {len(examples)} finalized examples to {output_examples}")
    print(f"Wrote {len(training)} training dialogues to {output_training}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
