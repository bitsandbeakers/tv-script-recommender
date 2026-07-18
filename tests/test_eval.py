"""Tests for evaluation metrics and harness."""

import importlib

import pytest

from backend.eval.metrics import (
    aggregate,
    evaluate_ranking,
    hit_rate_at_k,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
)

RANKED = ["a", "b", "c", "d", "e"]


def test_precision_at_k():
    assert precision_at_k(RANKED, {"a", "c"}, 2) == 0.5
    assert precision_at_k(RANKED, {"a", "c"}, 5) == 0.4
    assert precision_at_k(RANKED, {"z"}, 5) == 0.0
    assert precision_at_k([], {"a"}, 5) == 0.0
    assert precision_at_k(RANKED, {"a"}, 0) == 0.0


def test_recall_at_k():
    assert recall_at_k(RANKED, {"a", "c"}, 5) == 1.0
    assert recall_at_k(RANKED, {"a", "c"}, 1) == 0.5
    assert recall_at_k(RANKED, {"z", "y"}, 5) == 0.0
    assert recall_at_k(RANKED, set(), 5) == 0.0


def test_hit_rate():
    assert hit_rate_at_k(RANKED, {"c"}, 3) == 1.0
    assert hit_rate_at_k(RANKED, {"c"}, 2) == 0.0


def test_reciprocal_rank():
    assert reciprocal_rank(RANKED, {"a"}) == 1.0
    assert reciprocal_rank(RANKED, {"c"}) == pytest.approx(1 / 3)
    assert reciprocal_rank(RANKED, {"z"}) == 0.0


def test_ndcg_perfect_ranking():
    assert ndcg_at_k(["a", "b"], {"a", "b"}, 2) == pytest.approx(1.0)


def test_ndcg_partial():
    # Relevant item at position 2 of 2, one relevant item total
    ndcg = ndcg_at_k(["x", "a"], {"a"}, 2)
    assert 0 < ndcg < 1


def test_ndcg_empty():
    assert ndcg_at_k(RANKED, set(), 5) == 0.0
    assert ndcg_at_k([], {"a"}, 5) == 0.0


def test_evaluate_ranking_keys():
    result = evaluate_ranking(RANKED, {"a"}, [5, 10])
    assert "mrr" in result
    for k in [5, 10]:
        for m in ["precision", "recall", "hit_rate", "ndcg"]:
            assert f"{m}@{k}" in result


def test_aggregate():
    agg = aggregate([{"mrr": 1.0, "p": 0.5}, {"mrr": 0.0, "p": 0.5}])
    assert agg == {"mrr": 0.5, "p": 0.5}
    assert aggregate([]) == {}


# --- Harness ---


@pytest.fixture(autouse=True)
def setup_env(monkeypatch, tmp_path):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("TVR_DATABASE_URL", f"sqlite:///{db_path}")

    import backend.core.config
    importlib.reload(backend.core.config)
    from backend.core.config import settings
    monkeypatch.setattr("backend.db.show_store.settings", settings)

    from backend.db import show_store
    show_store.init_db()


GROUND_TRUTH = {
    "similar_groups": [
        {"name": "g1", "shows": ["a", "b", "c"]},
        {"name": "g2", "shows": ["x", "y"]},  # y not in catalog -> skipped
    ],
    "query_cases": [
        {"name": "q1", "query": "some style", "expected": ["a", "b"]},
        {"name": "q2", "query": "other style", "expected": ["zzz"]},  # skipped
    ],
}


def _populate_catalog(ids):
    from backend.db import show_store
    from backend.models.schemas import ShowInfo

    for show_id in ids:
        show_store.upsert_show(ShowInfo(id=show_id, title=show_id.title()))


def _perfect_recommender(relevant_map):
    """Recommender that returns exactly what ground truth expects, best-first."""
    def fn(key, top_k):
        ids = relevant_map.get(key, [])[:top_k]
        return {"ids": [ids], "distances": [[0.1] * len(ids)], "metadatas": [[{}] * len(ids)]}
    return fn


def test_evaluate_similar_shows_perfect():
    from backend.eval.harness import evaluate_similar_shows

    _populate_catalog(["a", "b", "c", "x"])
    recommend = _perfect_recommender({"a": ["b", "c"], "b": ["a", "c"], "c": ["a", "b"]})

    report = evaluate_similar_shows(GROUND_TRUTH, k_values=[5], recommend_fn=recommend)

    assert len(report["cases"]) == 3  # one per show in g1
    assert len(report["skipped"]) == 1  # g2 has only one show in catalog
    assert report["aggregate"]["precision@5"] == pytest.approx(2 / 5)
    assert report["aggregate"]["recall@5"] == pytest.approx(1.0)
    assert report["aggregate"]["mrr"] == pytest.approx(1.0)
    assert report["aggregate"]["ndcg@5"] == pytest.approx(1.0)


def test_evaluate_similar_shows_bad_recommender():
    from backend.eval.harness import evaluate_similar_shows

    _populate_catalog(["a", "b", "c"])
    recommend = _perfect_recommender({})  # returns nothing

    report = evaluate_similar_shows(GROUND_TRUTH, k_values=[5], recommend_fn=recommend)
    assert report["aggregate"]["recall@5"] == 0.0
    assert report["aggregate"]["mrr"] == 0.0


def test_evaluate_text_queries():
    from backend.eval.harness import evaluate_text_queries

    _populate_catalog(["a", "b"])
    recommend = _perfect_recommender({"some style": ["a", "b"], "other style": []})

    report = evaluate_text_queries(GROUND_TRUTH, k_values=[5], recommend_fn=recommend)

    assert len(report["cases"]) == 1
    assert report["cases"][0]["case"] == "q1"
    assert len(report["skipped"]) == 1
    assert report["aggregate"]["recall@5"] == pytest.approx(1.0)


def test_ground_truth_file_loads():
    from backend.eval.harness import DEFAULT_GROUND_TRUTH, load_ground_truth

    gt = load_ground_truth(DEFAULT_GROUND_TRUTH)
    assert gt["similar_groups"]
    assert gt["query_cases"]
    for group in gt["similar_groups"]:
        assert len(group["shows"]) >= 2
    for case in gt["query_cases"]:
        assert case["query"]
        assert case["expected"]
