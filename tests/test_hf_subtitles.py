"""Tests for HuggingFace subtitle loading (unit tests, no actual HF downloads)."""

from unittest.mock import patch, MagicMock


def test_load_subtitles_filters_by_imdb_id():
    """Should only return docs matching requested IMDB IDs."""
    mock_dataset = [
        {"meta": {"imdbId": 12345}, "subtitle": "Hello there."},
        {"meta": {"imdbId": 99999}, "subtitle": "Wrong show."},
        {"meta": {"imdbId": 12345}, "subtitle": "General Kenobi."},
    ]

    with patch("backend.pipeline.hf_subtitles.load_dataset", return_value=mock_dataset):
        from backend.pipeline.hf_subtitles import load_subtitles_for_imdb_ids
        results = load_subtitles_for_imdb_ids({"12345"})

    assert "12345" in results
    assert len(results["12345"]) == 2
    assert "99999" not in results


def test_load_subtitles_max_docs():
    """Should respect max_docs limit per IMDB ID."""
    mock_dataset = [
        {"meta": {"imdbId": 100}, "subtitle": "Line 1"},
        {"meta": {"imdbId": 100}, "subtitle": "Line 2"},
        {"meta": {"imdbId": 100}, "subtitle": "Line 3"},
    ]

    with patch("backend.pipeline.hf_subtitles.load_dataset", return_value=mock_dataset):
        from backend.pipeline.hf_subtitles import load_subtitles_for_imdb_ids
        results = load_subtitles_for_imdb_ids({"100"}, max_docs=2)

    assert len(results["100"]) == 2


def test_load_subtitles_empty():
    """Should return empty dict when no matches found."""
    with patch("backend.pipeline.hf_subtitles.load_dataset", return_value=[]):
        from backend.pipeline.hf_subtitles import load_subtitles_for_imdb_ids
        results = load_subtitles_for_imdb_ids({"999"})

    assert results == {}
