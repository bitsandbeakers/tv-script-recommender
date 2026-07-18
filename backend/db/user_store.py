"""SQLite store for user profiles and show feedback (likes/dislikes)."""

import sqlite3
import uuid
from contextlib import contextmanager

from backend.core.config import settings
from backend.models.schemas import FeedbackItem, UserProfile


def _db_path() -> str:
    url = settings.database_url
    if url.startswith("sqlite:///"):
        return url[len("sqlite:///"):]
    return url


@contextmanager
def _get_conn():
    conn = sqlite3.connect(_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    """Create user and feedback tables if they don't exist."""
    with _get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS feedback (
                user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                show_id TEXT NOT NULL,
                rating INTEGER NOT NULL CHECK (rating IN (-1, 1)),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, show_id)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_feedback_show ON feedback(show_id)")


# --- Users ---


def create_user(name: str) -> UserProfile:
    user_id = uuid.uuid4().hex[:12]
    with _get_conn() as conn:
        conn.execute("INSERT INTO users (id, name) VALUES (?, ?)", (user_id, name))
    return UserProfile(id=user_id, name=name)


def get_user(user_id: str) -> UserProfile | None:
    with _get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if not row:
            return None
        counts = conn.execute(
            """
            SELECT
                SUM(CASE WHEN rating = 1 THEN 1 ELSE 0 END) AS liked,
                SUM(CASE WHEN rating = -1 THEN 1 ELSE 0 END) AS disliked
            FROM feedback WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()
        return UserProfile(
            id=row["id"],
            name=row["name"],
            num_liked=counts["liked"] or 0,
            num_disliked=counts["disliked"] or 0,
        )


def list_users() -> list[UserProfile]:
    with _get_conn() as conn:
        rows = conn.execute("SELECT id FROM users ORDER BY created_at").fetchall()
    return [get_user(r["id"]) for r in rows]


def delete_user(user_id: str) -> bool:
    with _get_conn() as conn:
        cursor = conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        return cursor.rowcount > 0


# --- Feedback ---


def set_feedback(user_id: str, show_id: str, rating: int) -> None:
    """Record or update a user's rating for a show. rating is 1 (like) or -1 (dislike)."""
    if rating not in (-1, 1):
        raise ValueError("rating must be 1 or -1")
    with _get_conn() as conn:
        conn.execute(
            """
            INSERT INTO feedback (user_id, show_id, rating)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id, show_id) DO UPDATE SET
                rating = excluded.rating,
                created_at = CURRENT_TIMESTAMP
            """,
            (user_id, show_id, rating),
        )


def remove_feedback(user_id: str, show_id: str) -> bool:
    with _get_conn() as conn:
        cursor = conn.execute(
            "DELETE FROM feedback WHERE user_id = ? AND show_id = ?", (user_id, show_id)
        )
        return cursor.rowcount > 0


def get_feedback(user_id: str) -> list[FeedbackItem]:
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT show_id, rating FROM feedback WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,),
        ).fetchall()
        return [FeedbackItem(show_id=r["show_id"], rating=r["rating"]) for r in rows]


def get_liked_ids(user_id: str) -> list[str]:
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT show_id FROM feedback WHERE user_id = ? AND rating = 1", (user_id,)
        ).fetchall()
        return [r["show_id"] for r in rows]


def get_disliked_ids(user_id: str) -> list[str]:
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT show_id FROM feedback WHERE user_id = ? AND rating = -1", (user_id,)
        ).fetchall()
        return [r["show_id"] for r in rows]


def get_all_likes() -> dict[str, set[str]]:
    """Map of user_id -> set of liked show_ids, across all users (for collaborative filtering)."""
    with _get_conn() as conn:
        rows = conn.execute("SELECT user_id, show_id FROM feedback WHERE rating = 1").fetchall()
    likes: dict[str, set[str]] = {}
    for r in rows:
        likes.setdefault(r["user_id"], set()).add(r["show_id"])
    return likes
