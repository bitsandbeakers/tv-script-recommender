#!/usr/bin/env python3
"""CLI tool for ingesting TV show subtitles from OpenSubtitles.

Usage:
    python -m scripts.ingest_show "Breaking Bad"
    python -m scripts.ingest_show "Breaking Bad" --season 1
    python -m scripts.ingest_show "Breaking Bad" --imdb-id 903747
    python -m scripts.ingest_show "Breaking Bad" --search-only
    python -m scripts.ingest_show "Breaking Bad" --skip-llm
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
from backend.pipeline.ingest import chunk_script
from backend.pipeline.srt_parser import extract_dialogue
from backend.pipeline.subtitles import OpenSubtitlesClient

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

DATA_DIR = Path("data/subtitles")


def search_show(client: OpenSubtitlesClient, query: str, **kwargs) -> list[dict]:
    """Search for a show and return deduplicated episode results."""
    results = client.search_all_episodes(query, **kwargs)

    episodes: dict[str, dict] = {}
    for item in results:
        attrs = item.get("attributes", {})
        details = attrs.get("feature_details", {})
        season = details.get("season_number", 0)
        episode = details.get("episode_number", 0)
        key = f"S{season:02d}E{episode:02d}"

        download_count = attrs.get("download_count", 0)
        if key not in episodes or download_count > episodes[key]["download_count"]:
            file_id = attrs["files"][0]["file_id"] if attrs.get("files") else None
            episodes[key] = {
                "key": key,
                "title": details.get("title", query),
                "season": season,
                "episode": episode,
                "file_id": file_id,
                "download_count": download_count,
                "parent_title": details.get("parent_title", query),
                "year": details.get("year"),
                "imdb_id": details.get("imdb_id"),
            }

    return sorted(episodes.values(), key=lambda e: (e["season"], e["episode"]))


def download_and_save(client: OpenSubtitlesClient, show_name: str, episodes: list[dict]) -> list[Path]:
    """Download subtitle files and save to data directory."""
    show_dir = DATA_DIR / show_name.lower().replace(" ", "_")
    show_dir.mkdir(parents=True, exist_ok=True)

    saved = []
    for ep in episodes:
        if not ep.get("file_id"):
            logger.warning(f"No file_id for {ep['key']}, skipping")
            continue

        srt_path = show_dir / f"{ep['key']}.srt"
        if srt_path.exists():
            logger.info(f"Already have {ep['key']}, skipping download")
            saved.append(srt_path)
            continue

        try:
            logger.info(f"Downloading {ep['key']}...")
            srt_content = client.download(ep["file_id"])
            srt_path.write_text(srt_content, encoding="utf-8")
            saved.append(srt_path)
        except Exception as e:
            logger.error(f"Failed to download {ep['key']}: {e}")

    return saved


def process_show(
    show_name: str,
    srt_paths: list[Path],
    skip_llm: bool = False,
    year: int | None = None,
    imdb_id: str = "",
) -> None:
    """Process downloaded subtitles: parse, extract features, embed, store."""
    all_dialogue = []
    for path in srt_paths:
        srt_content = path.read_text(encoding="utf-8", errors="replace")
        dialogue = extract_dialogue(srt_content)
        if dialogue:
            all_dialogue.append(f"--- {path.stem} ---\n{dialogue}")

    if not all_dialogue:
        logger.warning(f"No dialogue extracted for {show_name}")
        return

    combined = "\n\n".join(all_dialogue)
    logger.info(f"Extracted {len(combined):,} chars of dialogue from {len(srt_paths)} episodes")

    show_id = show_name.lower().replace(" ", "_")

    # Enrich with metadata from TMDB/TVDB
    logger.info(f"Looking up metadata for '{show_name}'...")
    metadata = enrich_show(show_name, year=year, imdb_id=imdb_id) or {}

    if skip_llm:
        logger.info("Skipping LLM feature extraction (--skip-llm)")
        output_path = DATA_DIR / show_id / "dialogue.txt"
        output_path.write_text(combined, encoding="utf-8")
        logger.info(f"Saved raw dialogue to {output_path}")

        # Still save metadata even without LLM
        init_db()
        show_info = ShowInfo(
            id=show_id,
            title=metadata.get("title", show_name),
            year=metadata.get("year", year),
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
            num_episodes_analyzed=len(srt_paths),
        )
        upsert_show_metadata(show_info)
        return

    # Chunk and extract features
    chunks = chunk_script(combined)
    logger.info(f"Split into {len(chunks)} chunks for analysis")

    features = extract_and_merge_features(chunks, show_name)
    logger.info(f"Extracted features: {features.style_summary}")

    # Generate embedding from features
    features_dict = features.model_dump(exclude={"show_title", "season", "episode"})
    text_repr = features_to_text(features_dict)
    embedding = embed_text(text_repr)

    # Store in vector DB
    vector_metadata = {
        "title": metadata.get("title", show_name),
        "num_episodes": len(srt_paths),
        "style_summary": features.style_summary,
        "themes": ",".join(features.themes),
        "tone": ",".join(features.tone),
        "genre": ",".join(features.genre_blend),
    }
    upsert_show_vector(show_id, embedding, vector_metadata)
    logger.info(f"Stored {show_name} in vector database")

    # Store in SQLite catalog with enriched metadata
    init_db()
    show_info = ShowInfo(
        id=show_id,
        title=metadata.get("title", show_name),
        year=metadata.get("year", year),
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
        num_episodes_analyzed=len(srt_paths),
        features=features,
    )
    upsert_show_metadata(show_info)
    logger.info(f"Stored {show_name} in show catalog")

    # Save features to disk
    features_path = DATA_DIR / show_id / "features.json"
    features_path.write_text(features.model_dump_json(indent=2), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Ingest TV show subtitles from OpenSubtitles")
    parser.add_argument("show", help="TV show name to search for")
    parser.add_argument("--season", type=int, help="Limit to a specific season")
    parser.add_argument("--imdb-id", type=int, help="IMDB ID for precise matching")
    parser.add_argument("--search-only", action="store_true", help="Just search, don't download")
    parser.add_argument("--skip-llm", action="store_true", help="Download and parse only, skip LLM extraction")
    parser.add_argument("--max-episodes", type=int, default=50, help="Max episodes to download (default: 50)")
    args = parser.parse_args()

    with OpenSubtitlesClient() as client:
        client.login()

        search_kwargs = {}
        if args.imdb_id:
            search_kwargs["imdb_id"] = args.imdb_id
        if args.season:
            search_kwargs["season"] = args.season

        logger.info(f"Searching for '{args.show}'...")
        episodes = search_show(client, args.show, **search_kwargs)

        if not episodes:
            logger.error(f"No subtitles found for '{args.show}'")
            sys.exit(1)

        show_name = episodes[0].get("parent_title", args.show)
        year = episodes[0].get("year")
        imdb_id_raw = episodes[0].get("imdb_id")
        imdb_id = f"tt{imdb_id_raw}" if imdb_id_raw and not str(imdb_id_raw).startswith("tt") else str(imdb_id_raw or "")
        logger.info(f"Found {len(episodes)} episodes for '{show_name}'")

        if args.search_only:
            for ep in episodes:
                print(f"  {ep['key']}: {ep.get('title', '?')} (downloads: {ep['download_count']})")
            return

        episodes = episodes[: args.max_episodes]

        srt_paths = download_and_save(client, show_name, episodes)
        logger.info(f"Downloaded {len(srt_paths)} subtitle files")

        process_show(show_name, srt_paths, skip_llm=args.skip_llm, year=year, imdb_id=imdb_id)

    logger.info("Done!")


if __name__ == "__main__":
    main()
