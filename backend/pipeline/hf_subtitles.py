"""Load subtitle data from the HuggingFace OpenSubtitles monolingual dataset.

Uses bigscience/open_subtitles_monolingual (English config) which provides
whole subtitle documents tagged with IMDB IDs — no API key needed.
"""

import logging
from collections import defaultdict

from datasets import load_dataset

logger = logging.getLogger(__name__)

DATASET_NAME = "bigscience/open_subtitles_monolingual"
IMDB_EPISODE_URL = "https://datasets.imdbws.com/title.episode.tsv.gz"
IMDB_BASICS_URL = "https://datasets.imdbws.com/title.basics.tsv.gz"


def load_subtitles_for_imdb_ids(
    imdb_ids: set[str],
    max_docs: int | None = None,
    streaming: bool = True,
) -> dict[str, list[str]]:
    """Load subtitle documents for specific IMDB IDs from HuggingFace.

    Args:
        imdb_ids: Set of IMDB IDs (numeric strings, no 'tt' prefix) to match.
        max_docs: Max documents to return per IMDB ID.
        streaming: Use streaming mode to avoid downloading the full dataset.

    Returns:
        Dict mapping IMDB ID to list of subtitle document texts.
    """
    logger.info(f"Loading subtitles for {len(imdb_ids)} IMDB IDs from HuggingFace...")
    dataset = load_dataset(DATASET_NAME, "en", split="train", streaming=streaming)

    results: dict[str, list[str]] = defaultdict(list)
    matched = 0

    for example in dataset:
        meta = example.get("meta", {})
        imdb_id = str(meta.get("imdbId", ""))
        if imdb_id not in imdb_ids:
            continue

        subtitle_text = example.get("subtitle", "")
        if not subtitle_text:
            continue

        if max_docs and len(results[imdb_id]) >= max_docs:
            continue

        results[imdb_id].append(subtitle_text)
        matched += 1

        # Check if we've found all we need
        if max_docs and all(len(v) >= max_docs for v in results.values()) and len(results) == len(imdb_ids):
            break

    logger.info(f"Found {matched} subtitle documents across {len(results)} IMDB IDs")
    return dict(results)


def search_imdb_episodes(parent_imdb_id: str) -> list[str]:
    """Look up episode IMDB IDs for a TV series using the IMDB datasets.

    Args:
        parent_imdb_id: IMDB ID of the parent series (e.g. 'tt0903747').

    Returns:
        List of episode IMDB IDs (numeric, no 'tt' prefix).
    """
    import csv
    import gzip
    import io
    import httpx

    logger.info(f"Fetching IMDB episode data for {parent_imdb_id}...")

    resp = httpx.get(IMDB_EPISODE_URL, follow_redirects=True, timeout=60.0)
    resp.raise_for_status()

    episode_ids = []
    content = gzip.decompress(resp.content).decode("utf-8")
    reader = csv.DictReader(io.StringIO(content), delimiter="\t")
    for row in reader:
        if row.get("parentTconst") == parent_imdb_id:
            episode_id = row["tconst"].lstrip("t")
            episode_ids.append(episode_id)

    logger.info(f"Found {len(episode_ids)} episodes for {parent_imdb_id}")
    return episode_ids
