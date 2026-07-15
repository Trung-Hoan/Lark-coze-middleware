import sqlite3
import json
from datetime import datetime, timezone

class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.init_db()

    def _conn(self):
        return sqlite3.connect(self.db_path)

    def init_db(self):
        conn = self._conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                lark_user_id TEXT PRIMARY KEY,
                coze_conversation_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lark_user_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                content_type TEXT DEFAULT 'text',
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_messages_user
            ON messages(lark_user_id, created_at)
        """)
        conn.commit()
        conn.close()

    def get_conversation_id(self, lark_user_id: str) -> str | None:
        conn = self._conn()
        cur = conn.execute(
            "SELECT coze_conversation_id FROM conversations WHERE lark_user_id = ?",
            (lark_user_id,)
        )
        row = cur.fetchone()
        conn.close()
        return row[0] if row else None

    def save_conversation_id(self, lark_user_id: str, coze_conversation_id: str):
        now = datetime.now(timezone.utc).isoformat()
        conn = self._conn()
        conn.execute("""
            INSERT INTO conversations (lark_user_id, coze_conversation_id, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(lark_user_id) DO UPDATE SET
                coze_conversation_id = excluded.coze_conversation_id,
                updated_at = excluded.updated_at
        """, (lark_user_id, coze_conversation_id, now, now))
        conn.commit()
        conn.close()

    def save_message(self, lark_user_id: str, role: str, content: str, content_type: str = "text"):
        now = datetime.now(timezone.utc).isoformat()
        conn = self._conn()
        conn.execute("""
            INSERT INTO messages (lark_user_id, role, content, content_type, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (lark_user_id, role, content, content_type, now))
        conn.commit()
        conn.close()

    def get_history(self, lark_user_id: str, limit: int = 10):
        conn = self._conn()
        cur = conn.execute(
            """SELECT role, content, content_type FROM messages
               WHERE lark_user_id = ?
               ORDER BY created_at DESC LIMIT ?""",
            (lark_user_id, limit)
        )
        rows = cur.fetchall()
        conn.close()
        return list(reversed(rows))
