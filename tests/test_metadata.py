"""Tests for TMDB and TVDB metadata clients (unit tests with mocking)."""

from unittest.mock import MagicMock, patch

from backend.metadata.tmdb import TMDBClient


def test_tmdb_normalize():
    """Test TMDB response normalization."""
    details = {
        "id": 1399,
        "name": "Breaking Bad",
        "first_air_date": "2008-01-20",
        "overview": "A chemistry teacher becomes a meth dealer.",
        "poster_path": "/ggFHVNu6YYI5L9pCfOacjizRGt.jpg",
        "genres": [{"id": 18, "name": "Drama"}, {"id": 80, "name": "Crime"}],
        "networks": [{"id": 174, "name": "AMC", "logo_path": "/x.png", "origin_country": "US"}],
        "status": "Ended",
        "vote_average": 8.9,
        "number_of_seasons": 5,
        "number_of_episodes": 62,
        "external_ids": {"imdb_id": "tt0903747", "tvdb_id": 81189},
    }

    client = TMDBClient.__new__(TMDBClient)
    result = client._normalize(details)

    assert result["source"] == "tmdb"
    assert result["tmdb_id"] == 1399
    assert result["title"] == "Breaking Bad"
    assert result["year"] == 2008
    assert result["network"] == "AMC"
    assert result["genres"] == ["Drama", "Crime"]
    assert result["imdb_id"] == "tt0903747"
    assert result["tvdb_id"] == 81189
    assert result["poster_url"].startswith("https://image.tmdb.org")
    assert result["num_seasons"] == 5
    assert result["num_episodes"] == 62


def test_tmdb_normalize_missing_fields():
    """Test normalization with missing optional fields."""
    details = {
        "id": 999,
        "name": "Unknown Show",
        "first_air_date": "",
        "genres": [],
        "networks": [],
        "external_ids": {},
    }

    client = TMDBClient.__new__(TMDBClient)
    result = client._normalize(details)

    assert result["year"] is None
    assert result["network"] == ""
    assert result["genres"] == []
    assert result["imdb_id"] == ""
    assert result["poster_url"] == ""


def test_tvdb_get_show_metadata():
    """Test TVDB metadata extraction from search results."""
    from backend.metadata.tvdb import TVDBClient

    client = TVDBClient.__new__(TVDBClient)
    client._client = MagicMock()
    client._token = "fake"

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "data": [{
            "tvdb_id": "81189",
            "name": "Breaking Bad",
            "year": "2008",
            "network": "AMC",
            "genres": ["Drama", "Thriller"],
            "overview": "A chemistry teacher...",
            "image_url": "https://artworks.thetvdb.com/poster.jpg",
            "poster": "",
            "status": "Ended",
            "remote_ids": [{"id": "tt0903747", "type": 2, "sourceName": "IMDB"}],
        }],
    }
    client._client.request.return_value = mock_resp

    result = client.get_show_metadata("Breaking Bad")
    assert result is not None
    assert result["source"] == "tvdb"
    assert result["title"] == "Breaking Bad"
    assert result["year"] == 2008
    assert result["imdb_id"] == "tt0903747"
    assert result["network"] == "AMC"
