"""Tests for the user/feedback SQLite store."""

import importlib

import pytest


@pytest.fixture(autouse=True)
def setup_env(monkeypatch, tmp_path):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("TVR_DATABASE_URL", f"sqlite:///{db_path}")

    import backend.core.config
    importlib.reload(backend.core.config)
    from backend.core.config import settings
    monkeypatch.setattr("backend.db.user_store.settings", settings)
    monkeypatch.setattr("backend.db.show_store.settings", settings)

    from backend.db import user_store
    user_store.init_db()


def test_create_and_get_user():
    from backend.db import user_store

    user = user_store.create_user("Alice")
    assert user.id
    assert user.name == "Alice"

    fetched = user_store.get_user(user.id)
    assert fetched is not None
    assert fetched.name == "Alice"
    assert fetched.num_liked == 0
    assert fetched.num_disliked == 0


def test_get_user_missing():
    from backend.db import user_store

    assert user_store.get_user("nope") is None


def test_feedback_roundtrip():
    from backend.db import user_store

    user = user_store.create_user("Bob")
    user_store.set_feedback(user.id, "succession", 1)
    user_store.set_feedback(user.id, "the-office", 1)
    user_store.set_feedback(user.id, "ncis", -1)

    fetched = user_store.get_user(user.id)
    assert fetched.num_liked == 2
    assert fetched.num_disliked == 1

    assert set(user_store.get_liked_ids(user.id)) == {"succession", "the-office"}
    assert user_store.get_disliked_ids(user.id) == ["ncis"]

    feedback = user_store.get_feedback(user.id)
    assert len(feedback) == 3


def test_feedback_update_overwrites():
    from backend.db import user_store

    user = user_store.create_user("Carol")
    user_store.set_feedback(user.id, "succession", 1)
    user_store.set_feedback(user.id, "succession", -1)

    fetched = user_store.get_user(user.id)
    assert fetched.num_liked == 0
    assert fetched.num_disliked == 1


def test_feedback_invalid_rating():
    from backend.db import user_store

    user = user_store.create_user("Dave")
    with pytest.raises(ValueError):
        user_store.set_feedback(user.id, "succession", 5)


def test_remove_feedback():
    from backend.db import user_store

    user = user_store.create_user("Eve")
    user_store.set_feedback(user.id, "succession", 1)
    assert user_store.remove_feedback(user.id, "succession") is True
    assert user_store.remove_feedback(user.id, "succession") is False
    assert user_store.get_liked_ids(user.id) == []


def test_delete_user_cascades_feedback():
    from backend.db import user_store

    user = user_store.create_user("Frank")
    user_store.set_feedback(user.id, "succession", 1)
    assert user_store.delete_user(user.id) is True
    assert user_store.get_user(user.id) is None
    assert user_store.get_all_likes().get(user.id) is None


def test_get_all_likes():
    from backend.db import user_store

    u1 = user_store.create_user("G")
    u2 = user_store.create_user("H")
    user_store.set_feedback(u1.id, "succession", 1)
    user_store.set_feedback(u1.id, "veep", 1)
    user_store.set_feedback(u2.id, "veep", 1)
    user_store.set_feedback(u2.id, "ncis", -1)  # dislikes excluded

    likes = user_store.get_all_likes()
    assert likes[u1.id] == {"succession", "veep"}
    assert likes[u2.id] == {"veep"}
