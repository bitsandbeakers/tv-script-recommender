"""Unified metadata enrichment — pulls from TMDB (primary) and TVDB (fallback)."""

import logging

from backend.metadata.tmdb import TMDBClient
from backend.metadata.tvdb import TVDBClient
from backend.core.config import settings

logger = logging.getLogger(__name__)


def enrich_show(query: str, year: int | None = None, imdb_id: str = "") -> dict | None:
    """Look up show metadata from available sources.

    Priority: TMDB (richer data, better rate limits) → TVDB fallback.
    Returns a normalized metadata dict or None.
    """
    metadata = None

    # Try TMDB first
    if settings.tmdb_read_token:
        try:
            with TMDBClient() as client:
                if imdb_id:
                    metadata = client.find_by_imdb(imdb_id)
                    if metadata:
                        metadata = client._normalize(metadata)
                if not metadata:
                    metadata = client.get_show_metadata(query, year=year)
                if metadata:
                    logger.info(f"TMDB: found '{metadata['title']}' ({metadata.get('year')})")
                    return metadata
        except Exception as e:
            logger.warning(f"TMDB lookup failed: {e}")

    # Fall back to TVDB
    if settings.tvdb_api_key:
        try:
            with TVDBClient() as client:
                client.login()
                if imdb_id:
                    hit = client.search_by_imdb(imdb_id)
                    if hit:
                        metadata = client.get_show_metadata(hit["name"])
                if not metadata:
                    metadata = client.get_show_metadata(query, year=year)
                if metadata:
                    logger.info(f"TVDB: found '{metadata['title']}' ({metadata.get('year')})")
                    return metadata
        except Exception as e:
            logger.warning(f"TVDB lookup failed: {e}")

    logger.warning(f"No metadata found for '{query}'")
    return None
