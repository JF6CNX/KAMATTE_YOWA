import sqlite3
from datetime import datetime
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parent.parent
DATABASE_PATH = APP_ROOT / "data" / "mascot.sqlite3"


class StateRepository:
    """キャラクター状態を SQLite に保存・読み込みするクラスです。"""

    def __init__(self, database_path: Path = DATABASE_PATH) -> None:
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.database_path)

    def _initialize(self) -> None:
        """初回起動時に必要なテーブルを作ります。"""
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS character_state (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    friendship INTEGER NOT NULL,
                    mood TEXT NOT NULL,
                    energy REAL NOT NULL,
                    stress_level REAL NOT NULL,
                    last_interaction TEXT NOT NULL,
                    last_talk_time TEXT NOT NULL
                )
                """
            )

    def load_state_row(self) -> dict | None:
        """保存された状態を辞書として読み込みます。"""
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT friendship, mood, energy, stress_level, last_interaction, last_talk_time
                FROM character_state
                WHERE id = 1
                """
            ).fetchone()

        if row is None:
            return None

        return {
            "friendship": int(row[0]),
            "mood": str(row[1]),
            "energy": float(row[2]),
            "stress_level": float(row[3]),
            "last_interaction": datetime.fromisoformat(row[4]),
            "last_talk_time": datetime.fromisoformat(row[5]),
        }

    def load_legacy_friendship(self) -> int:
        """
        旧MVPの app_state テーブルから友情度を読みます。

        既存データを消さず、新しい character_state へ引き継ぐための処理です。
        """
        with self._connect() as connection:
            table = connection.execute(
                """
                SELECT name FROM sqlite_master
                WHERE type = 'table' AND name = 'app_state'
                """
            ).fetchone()
            if table is None:
                return 0

            row = connection.execute(
                "SELECT value FROM app_state WHERE key = 'friendship'"
            ).fetchone()

        return int(row[0]) if row else 0

    def save_state(self, state) -> None:
        """現在の状態を SQLite に保存します。"""
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO character_state (
                    id,
                    friendship,
                    mood,
                    energy,
                    stress_level,
                    last_interaction,
                    last_talk_time
                )
                VALUES (1, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    friendship = excluded.friendship,
                    mood = excluded.mood,
                    energy = excluded.energy,
                    stress_level = excluded.stress_level,
                    last_interaction = excluded.last_interaction,
                    last_talk_time = excluded.last_talk_time
                """,
                (
                    state.friendship,
                    state.mood,
                    state.energy,
                    state.stress_level,
                    state.last_interaction.isoformat(),
                    state.last_talk_time.isoformat(),
                ),
            )


class FriendshipRepository:
    """
    旧コードとの互換用です。

    新しいコードでは StateRepository と CharacterStateService を使います。
    """

    def __init__(self, database_path: Path = DATABASE_PATH) -> None:
        self.state_repository = StateRepository(database_path)

    def load_friendship(self) -> int:
        row = self.state_repository.load_state_row()
        if row:
            return int(row["friendship"])
        return self.state_repository.load_legacy_friendship()

    def save_friendship(self, friendship: int) -> None:
        from logic.state import CharacterState

        now = datetime.now()
        state = CharacterState(
            friendship=friendship,
            mood="normal",
            energy=1.0,
            stress_level=0.0,
            last_interaction=now,
            last_talk_time=now,
        )
        self.state_repository.save_state(state)
