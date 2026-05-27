"""OpenSubtitles API client for searching and downloading subtitles."""

import logging
import time

import httpx

from backend.core.config import settings

logger = logging.getLogger(__name__)

BASE_URL = "https://api.opensubtitles.com/api/v1"


class OpenSubtitlesClient:
    """Client for the OpenSubtitles REST API."""

    def __init__(self) -> None:
        self._token: str | None = None
        self._client = httpx.Client(
            base_url=BASE_URL,
            headers={
                "Api-Key": settings.opensubtitles_api_key,
                "User-Agent": f"{settings.app_name}/0.1.0",
                "Accept": "application/json",
            },
            timeout=30.0,
        )

    def login(self) -> None:
        """Authenticate and store JWT token."""
        if not settings.opensubtitles_username or not settings.opensubtitles_password:
            logger.info("No OpenSubtitles credentials configured, using unauthenticated access")
            return

        resp = self._client.post(
            "/login",
            json={
                "username": settings.opensubtitles_username,
                "password": settings.opensubtitles_password,
            },
        )
        resp.raise_for_status()
        self._token = resp.json()["token"]
        self._client.headers["Authorization"] = f"Bearer {self._token}"
        logger.info("Logged in to OpenSubtitles")

    def search(
        self,
        query: str,
        *,
        season: int | None = None,
        episode: int | None = None,
        imdb_id: int | None = None,
        language: str = "en",
        page: int = 1,
    ) -> dict:
        """Search for subtitles by show name or IMDB ID."""
        params: dict = {
            "languages": language,
            "type": "episode",
            "page": str(page),
        }
        if imdb_id:
            params["imdb_id"] = str(imdb_id)
        else:
            params["query"] = query
        if season is not None:
            params["season_number"] = str(season)
        if episode is not None:
            params["episode_number"] = str(episode)

        resp = self._request_with_retry("GET", "/subtitles", params=params)
        return resp.json()

    def search_all_episodes(
        self,
        query: str,
        *,
        imdb_id: int | None = None,
        language: str = "en",
        max_pages: int = 5,
    ) -> list[dict]:
        """Search for all available episodes of a show across pages."""
        all_results = []
        for page in range(1, max_pages + 1):
            data = self.search(query, imdb_id=imdb_id, language=language, page=page)
            results = data.get("data", [])
            if not results:
                break
            all_results.extend(results)
            total_pages = data.get("total_pages", 1)
            if page >= total_pages:
                break
            time.sleep(0.25)  # respect rate limits
        return all_results

    def download(self, file_id: int) -> str:
        """Download a subtitle file and return the SRT content."""
        # Step 1: Get the temporary download link
        resp = self._request_with_retry("POST", "/download", json={"file_id": file_id})
        download_data = resp.json()

        remaining = download_data.get("remaining", "?")
        logger.info(f"Download quota remaining: {remaining}")

        link = download_data["link"]

        # Step 2: Fetch the actual SRT content from the temporary link
        srt_resp = httpx.get(link, timeout=30.0, follow_redirects=True)
        srt_resp.raise_for_status()
        return srt_resp.text

    def _request_with_retry(self, method: str, path: str, max_retries: int = 3, **kwargs) -> httpx.Response:
        """Make a request with rate limit handling."""
        for attempt in range(max_retries + 1):
            resp = self._client.request(method, path, **kwargs)
            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", 2))
                wait = max(retry_after, 2 ** (attempt + 1))
                logger.warning(f"Rate limited, waiting {wait}s (attempt {attempt + 1})")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp
        raise httpx.HTTPStatusError(
            "Rate limit exceeded after retries",
            request=resp.request,
            response=resp,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
