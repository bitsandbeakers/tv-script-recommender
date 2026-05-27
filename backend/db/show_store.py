"""SQLite metadata store for the show catalog."""

import json
import sqlite3
from contextlib import contextmanager

from backend.core.config import settings
from backend.models.schemas import ScriptFeatures, ShowInfo


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


def init_db() -> None:
    """Create tables if they don't exist."""
    with _get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS shows (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                year INTEGER,
                network TEXT DEFAULT '',
                genres TEXT DEFAULT '[]',
                overview TEXT DEFAULT '',
                poster_url TEXT DEFAULT '',
                imdb_id TEXT DEFAULT '',
                tmdb_id INTEGER,
                tvdb_id INTEGER,
                status TEXT DEFAULT '',
                num_seasons INTEGER DEFAULT 0,
                num_episodes INTEGER DEFAULT 0,
                num_episodes_analyzed INTEGER DEFAULT 0,
                features_json TEXT DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)


def upsert_show(show: ShowInfo) -> None:
    """Insert or update a show in the catalog."""
    features_json = show.features.model_dump_json() if show.features else "{}"
    genres_json = json.dumps(show.genres)
    with _get_conn() as conn:
        conn.execute(
            """
            INSERT INTO shows (id, title, year, network, genres, overview, poster_url,
                               imdb_id, tmdb_id, tvdb_id, status, num_seasons, num_episodes,
                               num_episodes_analyzed, features_json, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(id) DO UPDATE SET
                title = excluded.title,
                year = COALESCE(excluded.year, shows.year),
                network = CASE WHEN excluded.network != '' THEN excluded.network ELSE shows.network END,
                genres = CASE WHEN excluded.genres != '[]' THEN excluded.genres ELSE shows.genres END,
                overview = CASE WHEN excluded.overview != '' THEN excluded.overview ELSE shows.overview END,
                poster_url = CASE WHEN excluded.poster_url != '' THEN excluded.poster_url ELSE shows.poster_url END,
                imdb_id = CASE WHEN excluded.imdb_id != '' THEN excluded.imdb_id ELSE shows.imdb_id END,
                tmdb_id = COALESCE(excluded.tmdb_id, shows.tmdb_id),
                tvdb_id = COALESCE(excluded.tvdb_id, shows.tvdb_id),
                status = CASE WHEN excluded.status != '' THEN excluded.status ELSE shows.status END,
                num_seasons = CASE WHEN excluded.num_seasons > 0 THEN excluded.num_seasons ELSE shows.num_seasons END,
                num_episodes = CASE WHEN excluded.num_episodes > 0 THEN excluded.num_episodes ELSE shows.num_episodes END,
                num_episodes_analyzed = CASE WHEN excluded.num_episodes_analyzed > 0 THEN excluded.num_episodes_analyzed ELSE shows.num_episodes_analyzed END,
                features_json = CASE WHEN excluded.features_json != '{}' THEN excluded.features_json ELSE shows.features_json END,
                updated_at = CURRENT_TIMESTAMP
            """,
            (show.id, show.title, show.year, show.network, genres_json, show.overview,
             show.poster_url, show.imdb_id, show.tmdb_id, show.tvdb_id, show.status,
             show.num_seasons, show.num_episodes, show.num_episodes_analyzed, features_json),
        )


def get_show(show_id: str) -> ShowInfo | None:
    """Get a show by ID."""
    with _get_conn() as conn:
        row = conn.execute("SELECT * FROM shows WHERE id = ?", (show_id,)).fetchone()
        if not row:
            return None
        return _row_to_show(row)


def list_shows() -> list[ShowInfo]:
    """List all shows in the catalog."""
    with _get_conn() as conn:
        rows = conn.execute("SELECT * FROM shows ORDER BY title").fetchall()
        return [_row_to_show(r) for r in rows]


def search_shows(query: str) -> list[ShowInfo]:
    """Search shows by title (case-insensitive substring match)."""
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM shows WHERE LOWER(title) LIKE ? ORDER BY title",
            (f"%{query.lower()}%",),
        ).fetchall()
        return [_row_to_show(r) for r in rows]


def delete_show(show_id: str) -> bool:
    """Delete a show. Returns True if it existed."""
    with _get_conn() as conn:
        cursor = conn.execute("DELETE FROM shows WHERE id = ?", (show_id,))
        return cursor.rowcount > 0


def get_show_count() -> int:
    """Return total number of shows in the catalog."""
    with _get_conn() as conn:
        row = conn.execute("SELECT COUNT(*) as cnt FROM shows").fetchone()
        return row["cnt"]


def _row_to_show(row: sqlite3.Row) -> ShowInfo:
    features_data = json.loads(row["features_json"]) if row["features_json"] != "{}" else None
    features = ScriptFeatures(**features_data) if features_data else None
    genres = json.loads(row["genres"]) if row["genres"] else []
    return ShowInfo(
        id=row["id"],
        title=row["title"],
        year=row["year"],
        network=row["network"] or "",
        genres=genres,
        overview=row["overview"] or "",
        poster_url=row["poster_url"] or "",
        imdb_id=row["imdb_id"] or "",
        tmdb_id=row["tmdb_id"],
        tvdb_id=row["tvdb_id"],
        status=row["status"] or "",
        num_seasons=row["num_seasons"] or 0,
        num_episodes=row["num_episodes"] or 0,
        num_episodes_analyzed=row["num_episodes_analyzed"] or 0,
        features=features,
    )
