import sqlite3
from pathlib import Path
from datetime import datetime

DB_PATH = Path("data/warnings.db")


def get_connection():
    DB_PATH.parent.mkdir(exist_ok=True)
    return sqlite3.connect(DB_PATH)


def init_db():
    with get_connection() as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS warnings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            moderator_id INTEGER NOT NULL,
            reason TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """)
def add_warning(guild_id: int, user_id: int, moderator_id: int, reason: str):
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO warnings (guild_id, user_id, moderator_id, reason, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (guild_id, user_id, moderator_id, reason, datetime.utcnow().isoformat())
        )


def count_warnings(guild_id: int, user_id: int) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            """
            SELECT COUNT(*) FROM warnings
            WHERE guild_id = ? AND user_id = ?
            """,
            (guild_id, user_id)
        )
        return cur.fetchone()[0]
    
def delete_warnings(guild_id: int, user_id: int):
    with get_connection() as conn:
        conn.execute(
            """
            DELETE FROM warnings
            WHERE guild_id = ? AND user_id = ?
            """,
            (guild_id, user_id)
        )

def get_last_warning_id(guild_id: int, user_id: int) -> int | None:
    with get_connection() as conn:
        cur = conn.execute(
            """
            SELECT id FROM warnings
            WHERE guild_id = ? AND user_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (guild_id, user_id)
        )
        row = cur.fetchone()
        return row[0] if row else None


def delete_warning_by_id(warn_id: int):
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM warnings WHERE id = ?",
            (warn_id,)
        )
