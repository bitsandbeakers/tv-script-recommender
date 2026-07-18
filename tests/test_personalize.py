"""Tests for the personalized recommender (taste vectors + collaborative signal)."""

import importlib

import numpy as np
import pytest


@pytest.fixture(autouse=True)
def setup_env(monkeypatch, tmp_path):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("TVR_DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("TVR_CHROMA_PERSIST_DIR", str(tmp_path / "chroma"))

    import backend.core.config
    importlib.reload(backend.core.config)
    from backend.core.config import settings
    monkeypatch.setattr("backend.db.user_store.settings", settings)
    monkeypatch.setattr("backend.db.show_store.settings", settings)
    monkeypatch.setattr("backend.db.vector_store.settings", settings)

    import backend.db.vector_store
    backend.db.vector_store._client = None

    from backend.db import show_store, user_store
    show_store.init_db()
    user_store.init_db()


# Simple orthogonal-ish fake embeddings so tests avoid the real model
FAKE_EMBEDDINGS = {
    "succession": [1.0, 0.0, 0.0, 0.1],
    "veep": [0.9, 0.1, 0.0, 0.1],
    "the-thick-of-it": [0.85, 0.15, 0.0, 0.1],
    "ncis": [0.0, 1.0, 0.0, 0.1],
    "csi": [0.05, 0.95, 0.0, 0.1],
    "planet-earth": [0.0, 0.0, 1.0, 0.1],
}


def _fake_show_embedding(show_id):
    return FAKE_EMBEDDINGS.get(show_id)


def test_collaborative_scores_overlap():
    from backend.db import user_store
    from backend.recommender.personalize import collaborative_scores

    me = user_store.create_user("me")
    twin = user_store.create_user("twin")
    stranger = user_store.create_user("stranger")

    # I like succession + veep; twin likes succession + veep + thick-of-it
    for s in ["succession", "veep"]:
        user_store.set_feedback(me.id, s, 1)
    for s in ["succession", "veep", "the-thick-of-it"]:
        user_store.set_feedback(twin.id, s, 1)
    # Stranger likes unrelated shows, one of which is a candidate
    for s in ["ncis", "csi"]:
        user_store.set_feedback(stranger.id, s, 1)

    scores = collaborative_scores(me.id, ["the-thick-of-it", "csi", "planet-earth"])

    # Twin's overlap should push the-thick-of-it above csi (stranger shares nothing)
    assert scores["the-thick-of-it"] > scores["csi"]
    assert scores["planet-earth"] == 0.0
    assert scores["the-thick-of-it"] == 1.0  # normalized max


def test_collaborative_scores_no_history():
    from backend.db import user_store
    from backend.recommender.personalize import collaborative_scores

    user = user_store.create_user("newbie")
    scores = collaborative_scores(user.id, ["succession"])
    assert scores == {"succession": 0.0}


def test_build_taste_vector(monkeypatch):
    from backend.db import user_store
    from backend.recommender import personalize

    monkeypatch.setattr(personalize, "get_show_embedding", _fake_show_embedding)

    user = user_store.create_user("u")
    user_store.set_feedback(user.id, "succession", 1)
    user_store.set_feedback(user.id, "veep", 1)
    user_store.set_feedback(user.id, "ncis", -1)

    taste = personalize.build_taste_vector(user.id)
    assert taste is not None
    assert np.isclose(np.linalg.norm(taste), 1.0)

    # Taste should point toward the liked cluster, away from the disliked one
    sim_liked = np.dot(taste, FAKE_EMBEDDINGS["the-thick-of-it"])
    sim_disliked = np.dot(taste, FAKE_EMBEDDINGS["csi"])
    assert sim_liked > sim_disliked


def test_build_taste_vector_no_likes():
    from backend.db import user_store
    from backend.recommender.personalize import build_taste_vector

    user = user_store.create_user("u")
    assert build_taste_vector(user.id) is None


def test_recommend_personalized_excludes_rated(monkeypatch):
    from backend.db import user_store
    from backend.recommender import personalize

    monkeypatch.setattr(personalize, "get_show_embedding", _fake_show_embedding)
    monkeypatch.setattr(personalize, "_dislike_similarity", lambda uid, cids: {})

    def fake_query_similar(embedding, top_k=10):
        # Return everything, ranked by cosine similarity to the query vector
        emb = np.array(embedding)
        scored = []
        for show_id, vec in FAKE_EMBEDDINGS.items():
            v = np.array(vec)
            sim = float(np.dot(emb, v) / (np.linalg.norm(emb) * np.linalg.norm(v)))
            scored.append((show_id, 1 - sim))
        scored.sort(key=lambda x: x[1])
        scored = scored[:top_k]
        return {
            "ids": [[s for s, _ in scored]],
            "distances": [[d for _, d in scored]],
            "metadatas": [[{"title": s} for s, _ in scored]],
        }

    monkeypatch.setattr(personalize, "query_similar", fake_query_similar)

    user = user_store.create_user("u")
    user_store.set_feedback(user.id, "succession", 1)
    user_store.set_feedback(user.id, "ncis", -1)

    results = personalize.recommend_personalized(user.id, top_k=4)
    ids = results["ids"][0]

    # Rated shows never come back as recommendations
    assert "succession" not in ids
    assert "ncis" not in ids
    # Similar-to-liked shows rank above unrelated ones
    assert ids.index("veep") < ids.index("planet-earth")
    # Distances encode the blended score and stay sorted ascending
    assert results["distances"][0] == sorted(results["distances"][0])


def test_recommend_personalized_no_signal():
    from backend.db import user_store
    from backend.recommender.personalize import recommend_personalized

    user = user_store.create_user("u")
    results = recommend_personalized(user.id)
    assert results["ids"][0] == []
