from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_LOG_PATH = APP_ROOT / "logs" / "conversation_log.txt"


@dataclass
class ConversationEntry:
    timestamp: str
    speaker: str
    message: str

    def as_line(self) -> str:
        sanitized = self.message.replace("\r\n", "\n").replace("\r", "\n").replace("\n", " / ")
        return f"{self.timestamp} / {self.speaker} / {sanitized}"


class ConversationLogManager:
    """Stores recent conversation entries and appends them to a text log file."""

    def __init__(self, log_path: Path = DEFAULT_LOG_PATH, max_entries: int = 200) -> None:
        self.log_path = log_path
        self.max_entries = max_entries
        self.entries: list[ConversationEntry] = []
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def add_entry(self, speaker: str, message: str) -> ConversationEntry:
        entry = ConversationEntry(
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            speaker=speaker,
            message=message.strip(),
        )
        self.entries.append(entry)
        if len(self.entries) > self.max_entries:
            self.entries = self.entries[-self.max_entries :]
        self._append_to_file(entry)
        return entry

    def recent_log_text(self, limit: int = 30) -> str:
        recent = self.entries[-limit:]
        return "\n".join(entry.as_line() for entry in recent)

    def _append_to_file(self, entry: ConversationEntry) -> None:
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(entry.as_line() + "\n")
