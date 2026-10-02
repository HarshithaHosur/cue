import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator, List


BASE_DIR = Path(__file__).resolve().parents[2]


class ConversationStore:
    """Persists support conversation turns in the application's SQLite database."""

    def __init__(self):
        self.db_path = BASE_DIR / "database" / "local_store.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS support_conversation (
                    turn_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    user_message TEXT NOT NULL,
                    assistant_response TEXT NOT NULL,
                    action_taken TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'responded'
                )"""
            )
            columns = {
                row[1] for row in connection.execute("PRAGMA table_info(support_conversation)")
            }
            if "status" not in columns:
                connection.execute(
                    "ALTER TABLE support_conversation ADD COLUMN status TEXT NOT NULL DEFAULT 'responded'"
                )

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(str(self.db_path), timeout=10)
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def save_turn(
        self,
        user_message: str,
        assistant_response: str,
        action_taken: str = "",
        status: str = "responded",
        timestamp: float | None = None,
    ) -> int:
        with self._connect() as connection:
            cursor = connection.execute(
                """INSERT INTO support_conversation
                    (timestamp, user_message, assistant_response, action_taken, status)
                    VALUES (?, ?, ?, ?, ?)""",
                (timestamp or time.time(), user_message, assistant_response, action_taken, status),
            )
            return int(cursor.lastrowid)

    def recent_turns(self, limit: int = 100) -> List[Dict[str, Any]]:
        with self._connect() as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """SELECT timestamp, user_message, assistant_response, action_taken, status
                    FROM support_conversation ORDER BY turn_id DESC LIMIT ?""",
                (max(1, min(limit, 500)),),
            ).fetchall()
        return [dict(row) for row in reversed(rows)]

    def update_latest_action(self, action_taken: str, status: str) -> None:
        with self._connect() as connection:
            connection.execute(
                """UPDATE support_conversation
                    SET action_taken = ?, status = ?
                    WHERE turn_id = (SELECT MAX(turn_id) FROM support_conversation)""",
                (action_taken, status),
            )
