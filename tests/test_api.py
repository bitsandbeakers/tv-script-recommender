"""Tests for API endpoints."""

import os
import tempfile

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

    # Reset singletons
    import backend.db.vector_store
    backend.db.vector_store._client = None
    import backend.db.show_store
    backend.db.show_store.init_db()


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
