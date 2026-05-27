"""Tests for recommendation engine helper functions."""

from backend.recommender.engine import _filter_results, _trim_results


def _make_results(ids, distances=None, metadatas=None):
    n = len(ids)
    return {
        "ids": [ids],
        "distances": [distances or [0.1 * i for i in range(n)]],
        "metadatas": [metadatas or [{"title": f"Show {i}"} for i in range(n)]],
    }


def test_filter_results():
    results = _make_results(["a", "b", "c", "d"])
    filtered = _filter_results(results, ["b", "d"])
    assert filtered["ids"][0] == ["a", "c"]
    assert len(filtered["distances"][0]) == 2
    assert len(filtered["metadatas"][0]) == 2


def test_filter_empty():
    results = _make_results([])
    filtered = _filter_results(results, ["a"])
    assert filtered["ids"][0] == []


def test_trim_results():
    results = _make_results(["a", "b", "c", "d", "e"])
    trimmed = _trim_results(results, 3)
    assert len(trimmed["ids"][0]) == 3
    assert len(trimmed["distances"][0]) == 3
    assert len(trimmed["metadatas"][0]) == 3


def test_trim_already_small():
    results = _make_results(["a", "b"])
    trimmed = _trim_results(results, 10)
    assert len(trimmed["ids"][0]) == 2
