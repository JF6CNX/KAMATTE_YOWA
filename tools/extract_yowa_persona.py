from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any


APP_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT_PATH = APP_ROOT / "input"
DEFAULT_CONFIG_PATH = APP_ROOT / "tools" / "config_yowa_keywords.json"
DEFAULT_OUTPUT_PATH = APP_ROOT / "persona" / "source_yowa_messages.jsonl"
DEFAULT_PERSONALITY_PATH = APP_ROOT / "persona" / "personality_draft.json"
DEFAULT_EXAMPLES_PATH = APP_ROOT / "persona" / "examples_draft.jsonl"
SUPPORTED_SUFFIXES = {".txt", ".json", ".jsonl", ".csv"}
DEFAULT_YOWA_SPEAKER = "よわ"

URL_ONLY_RE = re.compile(r"^\s*https?://\S+\s*$", re.IGNORECASE)
STAMP_ONLY_RE = re.compile(r"^\s*<a?:\w+:\d+>\s*$")
SHORT_NO_CONTEXT_RE = re.compile(r"^[!！?？。、…wW]+$")
HEADER_LIKE_RE = re.compile(r"^(channel|server|guild|exported at)\b", re.IGNORECASE)

SOFT_ENDINGS = (
    "のだ",
    "なのだ",
)

PRIVACY_PATTERNS = (
    re.compile(r"\b\d{2,4}[- ]?\d{2,4}[- ]?\d{3,4}\b"),
    re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
)

MESSAGE_START_PATTERNS = (
    re.compile(r"^\[(?P<timestamp>[^\]]+)\]\s*(?P<speaker>[^:]{1,120})\s*:\s*(?P<text>.*)$"),
    re.compile(r"^\[(?P<timestamp>[^\]]+)\]\s*(?P<speaker>[^\[][^:]{1,120})\s*$"),
    re.compile(r"^(?P<timestamp>\d{4}[-/]\d{2}[-/]\d{2}[ T]\d{1,2}:\d{2}(?::\d{2})?)\s*[-|]\s*(?P<speaker>[^:]{1,120})\s*:\s*(?P<text>.*)$"),
    re.compile(r"^(?P<timestamp>\d{4}[-/]\d{2}[-/]\d{2}[ T]\d{1,2}:\d{2}(?::\d{2})?)\s+(?P<speaker>[^:]{1,120})\s*:\s*(?P<text>.*)$"),
    re.compile(r"^(?P<speaker>[^(\[][\S ].{0,100}?)\s*\((?P<timestamp>\d{4}[-/]\d{2}[-/]\d{2}[ T]\d{1,2}:\d{2}(?::\d{2})?)\)\s*:\s*(?P<text>.*)$"),
)


@dataclass
class MessageRecord:
    speaker: str
    text: str
    timestamp: str
    source_file: str
    original_speaker: str


@dataclass
class ScoredRecord:
    score: int
    speaker: str
    timestamp: str
    text: str
    reasons: list[str]
    source_file: str
    original_speaker: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract Yowa-like lines from Discord exports and draft persona files."
    )
    parser.add_argument(
        "--input",
        default=str(DEFAULT_INPUT_PATH),
        help="Path to a Discord export file or a folder containing export files. Default: ./input",
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT_PATH),
        help="Output JSONL path for extracted source messages.",
    )
    parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG_PATH),
        help="Config JSON path for speakers, keywords, and threshold.",
    )
    parser.add_argument(
        "--min-score",
        type=int,
        default=None,
        help="Override the configured minimum accepted score.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print counts only and do not write output files.",
    )
    return parser.parse_args()


def load_config(path: Path) -> dict[str, Any]:
    return json.loads(read_text_any_utf8(path))


def resolve_input_files(path: Path) -> list[Path]:
    if not path.exists():
        raise FileNotFoundError(f"Input path not found: {path}")
    if path.is_file():
        return [path]

    files = sorted(
        [
            candidate
            for candidate in path.rglob("*")
            if candidate.is_file() and candidate.suffix.lower() in SUPPORTED_SUFFIXES
        ],
        key=lambda candidate: (candidate.suffix.lower() != ".txt", -candidate.stat().st_size, candidate.name.lower()),
    )
    if not files:
        raise FileNotFoundError(f"No supported input files found in: {path}")
    return files


def read_messages_from_path(path: Path) -> list[MessageRecord]:
    suffix = path.suffix.lower()
    if suffix == ".json":
        return read_json_messages(path)
    if suffix == ".jsonl":
        return read_jsonl_messages(path)
    if suffix == ".csv":
        return read_csv_messages(path)
    return read_plain_text_messages(path)


def read_json_messages(path: Path) -> list[MessageRecord]:
    payload = json.loads(read_text_any_utf8(path))
    raw_messages: list[Any]
    if isinstance(payload, list):
        raw_messages = payload
    elif isinstance(payload, dict):
        if isinstance(payload.get("messages"), list):
            raw_messages = payload["messages"]
        elif isinstance(payload.get("channel", {}).get("messages"), list):
            raw_messages = payload["channel"]["messages"]
        else:
            raw_messages = [payload]
    else:
        raw_messages = []
    return [
        record
        for item in raw_messages
        if (record := normalize_message(item, source_file=path.name)) is not None
    ]


def read_jsonl_messages(path: Path) -> list[MessageRecord]:
    records: list[MessageRecord] = []
    for line in read_text_any_utf8(path).splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        record = normalize_message(item, source_file=path.name)
        if record is not None:
            records.append(record)
    return records


def read_csv_messages(path: Path) -> list[MessageRecord]:
    records: list[MessageRecord] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            record = normalize_message(row, source_file=path.name)
            if record is not None:
                records.append(record)
    return records


def read_plain_text_messages(path: Path) -> list[MessageRecord]:
    records: list[MessageRecord] = []
    current: MessageRecord | None = None

    for raw_line in read_text_any_utf8(path).splitlines():
        stripped = raw_line.strip()
        if not stripped:
            flush_current(records, current)
            current = None
            continue
        if HEADER_LIKE_RE.match(stripped):
            continue

        parsed = parse_plain_text_line(stripped, source_file=path.name)
        if parsed is not None:
            flush_current(records, current)
            current = parsed
            continue

        if current is not None:
            current.text = f"{current.text}\n{stripped}".strip()

    flush_current(records, current)
    return records


def flush_current(records: list[MessageRecord], current: MessageRecord | None) -> None:
    if current is None:
        return
    if current.speaker and current.text:
        records.append(current)


def parse_plain_text_line(line: str, source_file: str) -> MessageRecord | None:
    for pattern in MESSAGE_START_PATTERNS:
        match = pattern.match(line)
        if match:
            text = match.groupdict().get("text", "") or ""
            speaker = match.group("speaker").strip()
            return MessageRecord(
                speaker=speaker,
                timestamp=match.group("timestamp").strip(),
                text=text.strip(),
                source_file=source_file,
                original_speaker=speaker,
            )
    return None


def normalize_message(item: Any, source_file: str) -> MessageRecord | None:
    if not isinstance(item, dict):
        return None

    speaker = first_non_empty(
        nested_value(item, "speaker"),
        nested_value(item, "author.name"),
        nested_value(item, "author.username"),
        nested_value(item, "user.name"),
        nested_value(item, "username"),
        nested_value(item, "name"),
    )
    text = first_non_empty(
        nested_value(item, "content"),
        nested_value(item, "text"),
        nested_value(item, "message"),
        nested_value(item, "body"),
    )
    timestamp = first_non_empty(
        nested_value(item, "timestamp"),
        nested_value(item, "created_at"),
        nested_value(item, "date"),
        nested_value(item, "datetime"),
    )

    if not speaker or not text:
        return None

    speaker_text = str(speaker).strip()
    return MessageRecord(
        speaker=speaker_text,
        text=str(text).strip(),
        timestamp=str(timestamp or "").strip(),
        source_file=source_file,
        original_speaker=speaker_text,
    )


def read_text_any_utf8(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def nested_value(item: dict[str, Any], dotted_key: str) -> Any:
    current: Any = item
    for part in dotted_key.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def first_non_empty(*values: Any) -> Any:
    for value in values:
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        return value
    return None


def score_message(record: MessageRecord, config: dict[str, Any]) -> tuple[int, list[str], str | None]:
    record = normalize_yowa_persona_message(record, config)
    score = 0
    reasons: list[str] = []
    text = record.text.strip()

    if len(re.sub(r"\s+", "", text)) < 5:
        return score, reasons, "too_short"
    if URL_ONLY_RE.match(text):
        return score, reasons, "url_only"
    if STAMP_ONLY_RE.match(text):
        return score, reasons, "stamp_only"
    if looks_like_bot_notification(record):
        return score, reasons, "bot_notification"
    if contains_private_info(text):
        return score, reasons, "personal_info"
    if record.speaker == DEFAULT_YOWA_SPEAKER and not has_soft_ending(text):
        return score, reasons, "not_yowa_ending"

    normalized_speaker = record.speaker.lower()
    target_speakers = [speaker.lower() for speaker in config.get("target_speakers", [])]
    if normalized_speaker in target_speakers:
        score += 5
        reasons.append("target_speaker")
    if record.speaker != record.original_speaker:
        score += 4
        reasons.append("persona_prefix_override")

    for keyword in config.get("positive_keywords", []):
        if keyword and keyword in text:
            score += 2
            reasons.append(f"positive:{keyword}")

    for keyword in config.get("negative_keywords", []):
        if keyword and keyword in text:
            score -= 3
            reasons.append(f"negative:{keyword}")

    if "……" in text or "…" in text or "..." in text:
        score += 1
        reasons.append("ellipsis")

    if has_soft_ending(text):
        score += 1
        reasons.append("soft_ending")

    if has_yowa_style(text):
        score += 1
        reasons.append("yowa_style")

    if contains_trivia_tone(text):
        score += 1
        reasons.append("gentle_trivia")

    if looks_aggressive(text):
        score -= 3
        reasons.append("aggressive_tone")

    if looks_overly_pushy(text):
        score -= 2
        reasons.append("pushy_tone")

    if not has_contextual_length(text):
        return score, reasons, "too_short_contextless"

    return score, unique_preserving_order(reasons), None


def looks_like_bot_notification(record: MessageRecord) -> bool:
    speaker = record.speaker.lower()
    text = record.text.lower()
    bot_markers = ("bot", "dyno", "mudae", "ticket tool", "probot")
    notification_markers = (
        "joined the server",
        "pinned a message",
        "started a thread",
        "created a thread",
        "added ",
        "removed ",
    )
    return any(marker in speaker for marker in bot_markers) or any(marker in text for marker in notification_markers)


def contains_private_info(text: str) -> bool:
    return any(pattern.search(text) for pattern in PRIVACY_PATTERNS)


def normalize_yowa_persona_message(record: MessageRecord, config: dict[str, Any]) -> MessageRecord:
    prefixes = [prefix for prefix in config.get("persona_text_prefixes", []) if prefix]
    text = record.text.lstrip()
    for prefix in prefixes:
        if text.startswith(prefix):
            # Keep sentences that start with "よわ..." intact so they do not become fragments like "は..." or "が...".
            if prefix == "よわ":
                stripped = text
            else:
                stripped = text[len(prefix):].lstrip(" 　:：>＞-")
            return MessageRecord(
                speaker=DEFAULT_YOWA_SPEAKER,
                text=stripped or text,
                timestamp=record.timestamp,
                source_file=record.source_file,
                original_speaker=record.original_speaker,
            )
    return record


def has_soft_ending(text: str) -> bool:
    cleaned = text.strip().rstrip("。！？!?… ")
    return any(cleaned.endswith(ending) for ending in SOFT_ENDINGS)


def has_yowa_style(text: str) -> bool:
    style_patterns = (
        "のだ",
        "なのだ",
        "……",
        "たぶん",
        "少しだけ",
        "ちょっとだけ",
        "うまく言えないけど",
        "無理しすぎないで",
        "となりにいる",
        "そばにいる",
    )
    return any(pattern in text for pattern in style_patterns)


def contains_trivia_tone(text: str) -> bool:
    trivia_patterns = ("らしい", "だって", "らしいよ", "なんだって", "不思議", "みたい")
    return any(pattern in text for pattern in trivia_patterns)


def looks_aggressive(text: str) -> bool:
    aggressive_patterns = ("黙れ", "消えろ", "うるさい", "死ね", "ふざけるな", "命令", "やれ")
    return any(pattern in text for pattern in aggressive_patterns)


def looks_overly_pushy(text: str) -> bool:
    pushy_patterns = ("絶対大丈夫", "頑張れ", "気合", "今すぐ", "ちゃんとしろ", "甘えるな")
    return any(pattern in text for pattern in pushy_patterns)


def has_contextual_length(text: str) -> bool:
    visible = re.sub(r"\s+", "", text)
    return len(visible) >= 5 and not SHORT_NO_CONTEXT_RE.fullmatch(visible)


def unique_preserving_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def build_personality_draft(records: list[ScoredRecord], config: dict[str, Any], input_files: list[Path]) -> dict[str, Any]:
    speakers = Counter(record.speaker for record in records)
    original_speakers = Counter(record.original_speaker for record in records)
    source_files = Counter(record.source_file for record in records)
    reason_counts = Counter()
    phrase_counts = Counter()
    ending_counts = Counter()
    length_buckets = Counter()

    repeated_phrases = (
        "のだ",
        "なのだ",
        "……",
        "たぶん",
        "少しだけ",
        "ちょっとだけ",
        "うまく言えないけど",
        "無理しすぎないで",
        "となりにいる",
        "そばにいる",
    )

    for record in records:
        reason_counts.update(record.reasons)
        for phrase in repeated_phrases:
            if phrase in record.text:
                phrase_counts[phrase] += 1
        for ending in SOFT_ENDINGS:
            if record.text.rstrip("。！？!?… ").endswith(ending):
                ending_counts[ending] += 1
        length = len(re.sub(r"\s+", "", record.text))
        if length < 20:
            length_buckets["short"] += 1
        elif length < 60:
            length_buckets["medium"] += 1
        else:
            length_buckets["long"] += 1

    return {
        "name": DEFAULT_YOWA_SPEAKER,
        "source_summary": {
            "accepted_messages": len(records),
            "input_files": [path.name for path in input_files],
            "target_speakers": config.get("target_speakers", []),
            "top_speakers": [{"speaker": speaker, "count": count} for speaker, count in speakers.most_common(10)],
            "top_original_speakers": [{"speaker": speaker, "count": count} for speaker, count in original_speakers.most_common(10)],
            "top_source_files": [{"source_file": name, "count": count} for name, count in source_files.most_common(10)],
            "ending_policy": "must_end_with_no_da",
        },
        "tone_hypotheses": [
            "控えめ",
            "やさしい",
            "少し不安げ",
            "断定しすぎない",
            "相手を追い詰めない",
        ],
        "favorite_phrases": [phrase for phrase, _count in phrase_counts.most_common(12)],
        "soft_endings": [ending for ending, _count in ending_counts.most_common(8)],
        "message_length_tendency": dict(length_buckets),
        "reason_counts": dict(reason_counts),
        "style_rules_draft": [
            "語尾は『のだ』または『なのだ』で終える",
            "命令口調を避ける",
            "短文から中くらいの文を中心にする",
            "必要に応じて『……』『たぶん』『少しだけ』のような余白を残す",
            "となりにいる感じを優先する",
        ],
        "review_notes": [
            "この draft は『のだ』語尾だけに絞って生成される",
            "examples_draft.jsonl を確認して、よわ本人らしくない行は手で除外するとさらに精度が上がる",
        ],
    }


def build_examples_draft(records: list[ScoredRecord]) -> list[dict[str, Any]]:
    return [
        {
            "speaker": record.speaker,
            "timestamp": record.timestamp,
            "text": record.text,
            "score": record.score,
            "reasons": record.reasons,
            "source_file": record.source_file,
            "original_speaker": record.original_speaker,
        }
        for record in sorted(records, key=lambda item: (-item.score, item.timestamp, item.speaker))[:80]
    ]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)
    config_path = Path(args.config)

    config = load_config(config_path)
    if args.min_score is not None:
        config["min_score"] = args.min_score

    input_files = resolve_input_files(input_path)
    messages: list[MessageRecord] = []
    file_message_counts: dict[str, int] = {}
    for file_path in input_files:
        file_messages = read_messages_from_path(file_path)
        messages.extend(file_messages)
        file_message_counts[file_path.name] = len(file_messages)

    accepted: list[ScoredRecord] = []
    excluded = Counter()

    for record in messages:
        normalized_record = normalize_yowa_persona_message(record, config)
        score, reasons, exclusion = score_message(normalized_record, config)
        if exclusion is not None:
            excluded[exclusion] += 1
            continue
        if score < int(config.get("min_score", 3)):
            excluded["below_min_score"] += 1
            continue
        accepted.append(
            ScoredRecord(
                score=score,
                speaker=normalized_record.speaker,
                timestamp=normalized_record.timestamp,
                text=normalized_record.text,
                reasons=reasons,
                source_file=normalized_record.source_file,
                original_speaker=normalized_record.original_speaker,
            )
        )

    accepted_rows = [
        {
            "score": record.score,
            "speaker": record.speaker,
            "timestamp": record.timestamp,
            "text": record.text,
            "reasons": record.reasons,
            "source_file": record.source_file,
            "original_speaker": record.original_speaker,
        }
        for record in sorted(accepted, key=lambda item: (-item.score, item.timestamp, item.speaker))
    ]

    if args.dry_run:
        print(f"input_files={len(input_files)}")
        print(f"input_messages={len(messages)}")
        print(f"accepted_messages={len(accepted_rows)}")
        print(f"file_message_counts={json.dumps(file_message_counts, ensure_ascii=False)}")
        print(f"excluded_breakdown={json.dumps(dict(excluded), ensure_ascii=False)}")
        return 0

    persona_dir = output_path.parent
    personality_path = persona_dir / DEFAULT_PERSONALITY_PATH.name
    examples_path = persona_dir / DEFAULT_EXAMPLES_PATH.name

    write_jsonl(output_path, accepted_rows)
    write_json(personality_path, build_personality_draft(accepted, config, input_files))
    write_jsonl(examples_path, build_examples_draft(accepted))

    print(f"Read {len(input_files)} input file(s)")
    print(f"Wrote {len(accepted_rows)} extracted messages to {output_path}")
    print(f"Wrote personality draft to {personality_path}")
    print(f"Wrote examples draft to {examples_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
