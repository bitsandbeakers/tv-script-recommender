#!/usr/bin/env python3
"""Ingest TV show subtitles from the HuggingFace OpenSubtitles dataset.

This avoids OpenSubtitles API rate limits by using the pre-built
bigscience/open_subtitles_monolingual dataset on HuggingFace.

Usage:
    # By IMDB ID (recommended — precise matching)
    python -m scripts.ingest_from_hf --imdb-id tt0903747 --title "Breaking Bad"

    # By show name (uses TMDB/TVDB to find IMDB ID, then fetches from HF)
    python -m scripts.ingest_from_hf --title "Breaking Bad"

    # Skip LLM extraction (just download and parse)
    python -m scripts.ingest_from_hf --imdb-id tt0903747 --title "Breaking Bad" --skip-llm

    # Limit number of episodes
    python -m scripts.ingest_from_hf --imdb-id tt0903747 --title "Breaking Bad" --max-episodes 10
"""

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.db.show_store import init_db, upsert_show as upsert_show_metadata
from backend.db.vector_store import upsert_show as upsert_show_vector
from backend.metadata.enrich import enrich_show
from backend.models.schemas import ShowInfo
from backend.pipeline.embed import embed_text, features_to_text
from backend.pipeline.extract import extract_and_merge_features
from backend.pipeline.hf_subtitles import load_subtitles_for_imdb_ids, search_imdb_episodes
from backend.pipeline.ingest import chunk_script

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

DATA_DIR = Path("data/subtitles")


def resolve_imdb_id(title: str, imdb_id: str = "") -> tuple[str, dict]:
    """Resolve a show's IMDB ID via metadata lookup if not provided."""
    metadata = enrich_show(title, imdb_id=imdb_id) or {}
    if imdb_id:
        return imdb_id, metadata

    resolved = metadata.get("imdb_id", "")
    if resolved:
        logger.info(f"Resolved IMDB ID: {resolved}")
        return resolved, metadata

    logger.error(f"Could not resolve IMDB ID for '{title}'. Provide --imdb-id manually.")
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Ingest subtitles from HuggingFace OpenSubtitles dataset")
    parser.add_argument("--title", required=True, help="TV show title")
    parser.add_argument("--imdb-id", default="", help="IMDB ID (e.g. tt0903747)")
    parser.add_argument("--skip-llm", action="store_true", help="Skip LLM feature extraction")
    parser.add_argument("--max-episodes", type=int, default=50, help="Max episodes to process")
    args = parser.parse_args()

    init_db()

    # Resolve IMDB ID
    imdb_id, metadata = resolve_imdb_id(args.title, args.imdb_id)
    show_name = metadata.get("title", args.title)
    show_id = show_name.lower().replace(" ", "_")
    show_dir = DATA_DIR / show_id
    show_dir.mkdir(parents=True, exist_ok=True)

    # Find episode IMDB IDs
    logger.info(f"Looking up episodes for {imdb_id}...")
    episode_ids = search_imdb_episodes(imdb_id)

    if not episode_ids:
        logger.warning("No episode IDs found, trying to load subtitles for the series ID directly")
        numeric_id = imdb_id.lstrip("t")
        episode_ids = [numeric_id]

    episode_ids = episode_ids[: args.max_episodes]
    logger.info(f"Fetching subtitles for {len(episode_ids)} episodes from HuggingFace...")

    # Load subtitles from HuggingFace
    subtitles = load_subtitles_for_imdb_ids(set(episode_ids), max_docs=1)

    if not subtitles:
        logger.error("No subtitles found in HuggingFace dataset for these IMDB IDs")
        sys.exit(1)

    # Combine all subtitle documents
    all_dialogue = []
    for ep_id, docs in sorted(subtitles.items()):
        for doc in docs:
            all_dialogue.append(f"--- Episode {ep_id} ---\n{doc}")

    combined = "\n\n".join(all_dialogue)
    num_episodes = len(subtitles)
    logger.info(f"Got {len(combined):,} chars of dialogue from {num_episodes} episodes")

    # Save raw dialogue
    dialogue_path = show_dir / "dialogue.txt"
    dialogue_path.write_text(combined, encoding="utf-8")

    if args.skip_llm:
        logger.info("Skipping LLM feature extraction (--skip-llm)")
        show_info = ShowInfo(
            id=show_id,
            title=show_name,
            year=metadata.get("year"),
            network=metadata.get("network", ""),
            genres=metadata.get("genres", []),
            overview=metadata.get("overview", ""),
            poster_url=metadata.get("poster_url", ""),
            imdb_id=metadata.get("imdb_id", imdb_id),
            tmdb_id=metadata.get("tmdb_id"),
            tvdb_id=metadata.get("tvdb_id"),
            status=metadata.get("status", ""),
            num_seasons=metadata.get("num_seasons", 0),
            num_episodes=metadata.get("num_episodes", 0),
            num_episodes_analyzed=num_episodes,
        )
        upsert_show_metadata(show_info)
        logger.info("Done (metadata saved, LLM skipped)")
        return

    # Feature extraction
    chunks = chunk_script(combined)
    logger.info(f"Split into {len(chunks)} chunks for analysis")

    features = extract_and_merge_features(chunks, show_name)
    logger.info(f"Extracted features: {features.style_summary}")

    # Embed and store
    features_dict = features.model_dump(exclude={"show_title", "season", "episode"})
    text_repr = features_to_text(features_dict)
    embedding = embed_text(text_repr)

    vector_metadata = {
        "title": show_name,
        "num_episodes": num_episodes,
        "style_summary": features.style_summary,
        "themes": ",".join(features.themes),
        "tone": ",".join(features.tone),
        "genre": ",".join(features.genre_blend),
    }
    upsert_show_vector(show_id, embedding, vector_metadata)

    show_info = ShowInfo(
        id=show_id,
        title=show_name,
        year=metadata.get("year"),
        network=metadata.get("network", ""),
        genres=metadata.get("genres", []),
        overview=metadata.get("overview", ""),
        poster_url=metadata.get("poster_url", ""),
        imdb_id=metadata.get("imdb_id", imdb_id),
        tmdb_id=metadata.get("tmdb_id"),
        tvdb_id=metadata.get("tvdb_id"),
        status=metadata.get("status", ""),
        num_seasons=metadata.get("num_seasons", 0),
        num_episodes=metadata.get("num_episodes", 0),
        num_episodes_analyzed=num_episodes,
        features=features,
    )
    upsert_show_metadata(show_info)

    features_path = show_dir / "features.json"
    features_path.write_text(features.model_dump_json(indent=2), encoding="utf-8")

    logger.info("Done!")


if __name__ == "__main__":
    main()
