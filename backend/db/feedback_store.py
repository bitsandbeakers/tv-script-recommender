"""SQLite store for user feedback signals."""

import sqlite3
from contextlib import contextmanager

from backend.core.config import settings
from backend.models.schemas import FeedbackSignal


def _db_path() -> str:
    url = settings.database_url
    if url.startswith("sqlite:///"):
        return url[len("sqlite:///"):]
    return url


@contextmanager
def _get_conn():
    conn = sqlite3.connect(_db_path())
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_feedback_table() -> None:
    with _get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                show_id TEXT NOT NULL,
                signal TEXT NOT NULL CHECK(signal IN ('like', 'dislike', 'skip')),
                dimension TEXT,
                note TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_feedback_show ON feedback(show_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_feedback_signal ON feedback(signal)")


def record_feedback(fb: FeedbackSignal) -> int:
    """Insert a feedback record. Returns the new row ID."""
    with _get_conn() as conn:
        cursor = conn.execute(
            "INSERT INTO feedback (show_id, signal, dimension, note) VALUES (?, ?, ?, ?)",
            (fb.show_id, fb.signal, fb.dimension, fb.note),
        )
        return cursor.lastrowid


def get_feedback_for_show(show_id: str) -> list[dict]:
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM feedback WHERE show_id = ? ORDER BY created_at DESC",
            (show_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_signals(signal: str) -> list[str]:
    """Return distinct show_ids that have received a given signal."""
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT DISTINCT show_id FROM feedback WHERE signal = ?", (signal,)
        ).fetchall()
        return [r["show_id"] for r in rows]


def get_dimension_feedback() -> list[dict]:
    """Aggregate feedback counts by dimension and signal — for weight tuning."""
    with _get_conn() as conn:
        rows = conn.execute("""
            SELECT dimension, signal, COUNT(*) as count
            FROM feedback
            WHERE dimension IS NOT NULL
            GROUP BY dimension, signal
            ORDER BY dimension, signal
        """).fetchall()
        return [dict(r) for r in rows]
