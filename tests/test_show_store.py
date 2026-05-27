"""Tests for SQLite show catalog store."""

import os
import tempfile

import pytest

from backend.models.schemas import ScriptFeatures, ShowInfo


@pytest.fixture(autouse=True)
def tmp_db(monkeypatch):
    """Use a temporary database for each test."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    monkeypatch.setattr("backend.db.show_store.settings", type("S", (), {"database_url": f"sqlite:///{db_path}"})())
    from backend.db.show_store import init_db
    init_db()
    yield db_path
    os.unlink(db_path)


def test_init_db_creates_table():
    from backend.db.show_store import get_show_count
    assert get_show_count() == 0


def test_upsert_and_get():
    from backend.db.show_store import get_show, upsert_show
    show = ShowInfo(id="breaking_bad", title="Breaking Bad", year=2008, num_episodes_analyzed=5)
    upsert_show(show)
    result = get_show("breaking_bad")
    assert result is not None
    assert result.title == "Breaking Bad"
    assert result.year == 2008


def test_upsert_with_features():
    from backend.db.show_store import get_show, upsert_show
    features = ScriptFeatures(
        show_title="Succession",
        themes=["power", "family"],
        tone=["dark", "satirical"],
        style_summary="Sharp prestige drama.",
    )
    show = ShowInfo(id="succession", title="Succession", features=features)
    upsert_show(show)
    result = get_show("succession")
    assert result.features is not None
    assert "power" in result.features.themes
    assert result.features.style_summary == "Sharp prestige drama."


def test_upsert_updates_existing():
    from backend.db.show_store import get_show, upsert_show
    show1 = ShowInfo(id="test", title="Test Show", year=2020)
    upsert_show(show1)
    show2 = ShowInfo(id="test", title="Test Show Updated", year=2021)
    upsert_show(show2)
    result = get_show("test")
    assert result.title == "Test Show Updated"
    assert result.year == 2021


def test_list_shows():
    from backend.db.show_store import list_shows, upsert_show
    upsert_show(ShowInfo(id="b_show", title="B Show"))
    upsert_show(ShowInfo(id="a_show", title="A Show"))
    shows = list_shows()
    assert len(shows) == 2
    assert shows[0].title == "A Show"  # sorted alphabetically


def test_search_shows():
    from backend.db.show_store import search_shows, upsert_show
    upsert_show(ShowInfo(id="breaking_bad", title="Breaking Bad"))
    upsert_show(ShowInfo(id="better_call_saul", title="Better Call Saul"))
    upsert_show(ShowInfo(id="fleabag", title="Fleabag"))

    results = search_shows("break")
    assert len(results) == 1
    assert results[0].id == "breaking_bad"

    results = search_shows("better")
    assert len(results) == 1  # Better Call Saul only


def test_delete_show():
    from backend.db.show_store import delete_show, get_show, get_show_count, upsert_show
    upsert_show(ShowInfo(id="test", title="Test"))
    assert get_show_count() == 1
    assert delete_show("test") is True
    assert get_show("test") is None
    assert get_show_count() == 0


def test_delete_nonexistent():
    from backend.db.show_store import delete_show
    assert delete_show("nonexistent") is False


def test_get_nonexistent():
    from backend.db.show_store import get_show
    assert get_show("nonexistent") is None
