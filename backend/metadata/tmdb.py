"""TMDB API v3 client for TV show metadata."""

import logging

import httpx

from backend.core.config import settings

logger = logging.getLogger(__name__)

BASE_URL = "https://api.themoviedb.org/3"
IMAGE_BASE = "https://image.tmdb.org/t/p"


class TMDBClient:
    """Client for The Movie Database API v3."""

    def __init__(self) -> None:
        self._client = httpx.Client(
            base_url=BASE_URL,
            headers={
                "Authorization": f"Bearer {settings.tmdb_read_token}",
                "Accept": "application/json",
            },
            timeout=30.0,
        )

    def search(self, query: str, year: int | None = None) -> list[dict]:
        """Search for TV shows by name."""
        params: dict = {"query": query, "language": "en-US", "page": "1"}
        if year:
            params["first_air_date_year"] = str(year)
        resp = self._client.get("/search/tv", params=params)
        resp.raise_for_status()
        return resp.json().get("results", [])

    def get_details(self, tmdb_id: int) -> dict | None:
        """Get full show details with external IDs in one call."""
        resp = self._client.get(
            f"/tv/{tmdb_id}",
            params={"append_to_response": "external_ids", "language": "en-US"},
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()

    def find_by_imdb(self, imdb_id: str) -> dict | None:
        """Find a TV show by IMDB ID."""
        resp = self._client.get(
            f"/find/{imdb_id}",
            params={"external_source": "imdb_id", "language": "en-US"},
        )
        resp.raise_for_status()
        tv_results = resp.json().get("tv_results", [])
        if not tv_results:
            return None
        return self.get_details(tv_results[0]["id"])

    def get_show_metadata(self, query: str, year: int | None = None) -> dict | None:
        """Search for a show and return normalized metadata."""
        results = self.search(query, year=year)
        if not results:
            return None

        # Get full details for the top result
        details = self.get_details(results[0]["id"])
        if not details:
            return None

        return self._normalize(details)

    def get_show_metadata_by_id(self, tmdb_id: int) -> dict | None:
        """Get normalized metadata by TMDB ID."""
        details = self.get_details(tmdb_id)
        if not details:
            return None
        return self._normalize(details)

    def _normalize(self, details: dict) -> dict:
        """Normalize TMDB response into a standard metadata dict."""
        external = details.get("external_ids", {})
        poster = details.get("poster_path", "")
        networks = details.get("networks", [])

        first_air = details.get("first_air_date", "")
        year = int(first_air[:4]) if first_air and len(first_air) >= 4 else None

        return {
            "source": "tmdb",
            "tmdb_id": details["id"],
            "tvdb_id": external.get("tvdb_id"),
            "imdb_id": external.get("imdb_id", ""),
            "title": details.get("name", ""),
            "year": year,
            "network": networks[0]["name"] if networks else "",
            "genres": [g["name"] for g in details.get("genres", [])],
            "overview": details.get("overview", ""),
            "poster_url": f"{IMAGE_BASE}/w500{poster}" if poster else "",
            "status": details.get("status", ""),
            "vote_average": details.get("vote_average", 0),
            "num_seasons": details.get("number_of_seasons", 0),
            "num_episodes": details.get("number_of_episodes", 0),
        }

    def close(self) -> None:
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
