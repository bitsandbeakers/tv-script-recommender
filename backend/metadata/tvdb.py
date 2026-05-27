"""TVDB API v4 client for TV show metadata."""

import logging
import time

import httpx

from backend.core.config import settings

logger = logging.getLogger(__name__)

BASE_URL = "https://api4.thetvdb.com/v4"


class TVDBClient:
    """Client for TheTVDB API v4."""

    def __init__(self) -> None:
        self._token: str | None = None
        self._client = httpx.Client(
            base_url=BASE_URL,
            headers={"Accept": "application/json"},
            timeout=30.0,
        )

    def login(self) -> None:
        """Authenticate and get a bearer token (valid for ~1 month)."""
        resp = self._client.post("/login", json={"apikey": settings.tvdb_api_key})
        resp.raise_for_status()
        self._token = resp.json()["data"]["token"]
        self._client.headers["Authorization"] = f"Bearer {self._token}"
        logger.info("Authenticated with TVDB")

    def search(self, query: str, year: int | None = None) -> list[dict]:
        """Search for TV series by name."""
        params: dict = {"query": query, "type": "series"}
        if year:
            params["year"] = str(year)
        resp = self._request("GET", "/search", params=params)
        return resp.json().get("data", [])

    def get_series(self, tvdb_id: int) -> dict | None:
        """Get basic series info by TVDB ID."""
        resp = self._request("GET", f"/series/{tvdb_id}")
        return resp.json().get("data")

    def get_series_extended(self, tvdb_id: int, short: bool = True) -> dict | None:
        """Get extended series info (genres, networks, remote IDs)."""
        params = {"short": "true"} if short else {}
        resp = self._request("GET", f"/series/{tvdb_id}/extended", params=params)
        return resp.json().get("data")

    def search_by_imdb(self, imdb_id: str) -> dict | None:
        """Look up a series by IMDB ID (e.g. 'tt0903747')."""
        params = {"remote_id": imdb_id, "type": "series"}
        resp = self._request("GET", "/search", params=params)
        results = resp.json().get("data", [])
        return results[0] if results else None

    def get_show_metadata(self, query: str, year: int | None = None) -> dict | None:
        """Search for a show and return normalized metadata."""
        results = self.search(query, year=year)
        if not results:
            return None

        hit = results[0]
        imdb_id = ""
        for rid in hit.get("remote_ids", []):
            if rid.get("sourceName") == "IMDB":
                imdb_id = rid["id"]
                break

        return {
            "source": "tvdb",
            "tvdb_id": hit.get("tvdb_id"),
            "title": hit.get("name", ""),
            "year": int(hit["year"]) if hit.get("year") else None,
            "network": hit.get("network", ""),
            "genres": hit.get("genres", []),
            "overview": hit.get("overview", ""),
            "poster_url": hit.get("image_url") or hit.get("poster", ""),
            "imdb_id": imdb_id,
            "status": hit.get("status", ""),
        }

    def _request(self, method: str, path: str, max_retries: int = 3, **kwargs) -> httpx.Response:
        for attempt in range(max_retries + 1):
            resp = self._client.request(method, path, **kwargs)
            if resp.status_code == 401 and attempt == 0:
                logger.info("TVDB token expired, re-authenticating")
                self.login()
                continue
            if resp.status_code == 429:
                wait = 2 ** (attempt + 1)
                logger.warning(f"TVDB rate limited, waiting {wait}s")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp
        raise httpx.HTTPStatusError("TVDB request failed after retries", request=resp.request, response=resp)

    def close(self) -> None:
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
