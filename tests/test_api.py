"""Tests for API endpoints."""


import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def setup_env(monkeypatch, tmp_path):
    """Set up temp database and chroma for testing."""
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("TVR_DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("TVR_CHROMA_PERSIST_DIR", str(tmp_path / "chroma"))

    # Re-import to pick up env changes
    import importlib

    import backend.core.config
    importlib.reload(backend.core.config)

    # Patch settings in all modules
    from backend.core.config import settings
    monkeypatch.setattr("backend.db.show_store.settings", settings)
    monkeypatch.setattr("backend.db.vector_store.settings", settings)
    monkeypatch.setattr("backend.db.user_store.settings", settings)

    # Reset singletons
    import backend.db.vector_store
    backend.db.vector_store._client = None
    import backend.db.show_store
    backend.db.show_store.init_db()
    import backend.db.user_store
    backend.db.user_store.init_db()


@pytest.fixture
def client():
    from backend.app import app
    return TestClient(app)


def test_health(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_list_shows_empty(client):
    resp = client.get("/api/shows")
    assert resp.status_code == 200
    assert resp.json() == []


def test_show_not_found(client):
    resp = client.get("/api/shows/nonexistent")
    assert resp.status_code == 404


def test_recommend_no_query(client):
    resp = client.post("/api/recommend", json={"query": "", "liked_shows": []})
    assert resp.status_code == 400


def test_search_too_short(client):
    resp = client.get("/api/shows/search?q=a")
    assert resp.status_code == 400


# --- Users & feedback ---


def _add_show(show_id="succession", title="Succession"):
    from backend.db import show_store
    from backend.models.schemas import ShowInfo

    show_store.upsert_show(ShowInfo(id=show_id, title=title))


def test_create_and_get_user(client):
    resp = client.post("/api/users", json={"name": "Alice"})
    assert resp.status_code == 200
    user = resp.json()
    assert user["name"] == "Alice"

    resp = client.get(f"/api/users/{user['id']}")
    assert resp.status_code == 200
    assert resp.json()["num_liked"] == 0


def test_create_user_empty_name(client):
    resp = client.post("/api/users", json={"name": "  "})
    assert resp.status_code == 400


def test_user_not_found(client):
    assert client.get("/api/users/nope").status_code == 404
    assert client.delete("/api/users/nope").status_code == 404


def test_feedback_flow(client):
    _add_show()
    user = client.post("/api/users", json={"name": "Bob"}).json()

    resp = client.put(f"/api/users/{user['id']}/feedback", json={"show_id": "succession", "rating": 1})
    assert resp.status_code == 200

    resp = client.get(f"/api/users/{user['id']}/feedback")
    assert resp.status_code == 200
    assert resp.json() == [{"show_id": "succession", "rating": 1}]

    assert client.get(f"/api/users/{user['id']}").json()["num_liked"] == 1

    resp = client.delete(f"/api/users/{user['id']}/feedback/succession")
    assert resp.status_code == 200
    assert client.get(f"/api/users/{user['id']}/feedback").json() == []


def test_feedback_unknown_show(client):
    user = client.post("/api/users", json={"name": "Carol"}).json()
    resp = client.put(f"/api/users/{user['id']}/feedback", json={"show_id": "nope", "rating": 1})
    assert resp.status_code == 404


def test_feedback_invalid_rating(client):
    _add_show()
    user = client.post("/api/users", json={"name": "Dave"}).json()
    resp = client.put(f"/api/users/{user['id']}/feedback", json={"show_id": "succession", "rating": 3})
    assert resp.status_code == 400


def test_personalized_recommendations_no_history(client):
    user = client.post("/api/users", json={"name": "Eve"}).json()
    resp = client.get(f"/api/users/{user['id']}/recommendations")
    assert resp.status_code == 400


def test_personalized_recommendations_unknown_user(client):
    resp = client.get("/api/users/nope/recommendations")
    assert resp.status_code == 404


def test_recommend_with_unknown_user_id(client):
    resp = client.post("/api/recommend", json={"query": "comedy", "user_id": "nope"})
    assert resp.status_code == 404
