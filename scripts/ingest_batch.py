#!/usr/bin/env python3
"""Batch ingest multiple TV shows from a list.

Usage:
    python -m scripts.ingest_batch shows.txt
    python -m scripts.ingest_batch shows.txt --skip-llm
    python -m scripts.ingest_batch shows.txt --max-episodes 10

The input file should have one show per line. Lines starting with # are ignored.
Optional format: "Show Name | IMDB_ID" for precise matching.

Example shows.txt:
    Breaking Bad | 903747
    Better Call Saul | 3032476
    Succession
    # This is a comment
    Fleabag
"""

import argparse
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.ingest_show import (
    OpenSubtitlesClient,
    download_and_save,
    process_show,
    search_show,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def parse_show_list(path: Path) -> list[dict]:
    """Parse a show list file into (name, imdb_id) pairs."""
    shows = []
    for line in path.read_text().strip().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "|" in line:
            name, imdb_id = line.split("|", 1)
            shows.append({"name": name.strip(), "imdb_id": int(imdb_id.strip())})
        else:
            shows.append({"name": line, "imdb_id": None})
    return shows


def main():
    parser = argparse.ArgumentParser(description="Batch ingest TV shows from a list file")
    parser.add_argument("file", type=Path, help="Path to show list file (one show per line)")
    parser.add_argument("--skip-llm", action="store_true", help="Download and parse only, skip LLM extraction")
    parser.add_argument("--max-episodes", type=int, default=20, help="Max episodes per show (default: 20)")
    parser.add_argument("--delay", type=float, default=2.0, help="Delay between shows in seconds (default: 2)")
    args = parser.parse_args()

    if not args.file.exists():
        logger.error(f"File not found: {args.file}")
        sys.exit(1)

    shows = parse_show_list(args.file)
    logger.info(f"Loaded {len(shows)} shows from {args.file}")

    succeeded = []
    failed = []

    with OpenSubtitlesClient() as client:
        client.login()

        for i, show in enumerate(shows):
            name = show["name"]
            logger.info(f"\n{'=' * 60}")
            logger.info(f"[{i + 1}/{len(shows)}] Processing: {name}")
            logger.info(f"{'=' * 60}")

            try:
                search_kwargs = {}
                if show["imdb_id"]:
                    search_kwargs["imdb_id"] = show["imdb_id"]

                episodes = search_show(client, name, **search_kwargs)
                if not episodes:
                    logger.warning(f"No subtitles found for '{name}', skipping")
                    failed.append(name)
                    continue

                show_name = episodes[0].get("parent_title", name)
                year = episodes[0].get("year")
                episodes = episodes[: args.max_episodes]

                srt_paths = download_and_save(client, show_name, episodes)
                if not srt_paths:
                    logger.warning(f"No episodes downloaded for '{name}', skipping")
                    failed.append(name)
                    continue

                process_show(show_name, srt_paths, skip_llm=args.skip_llm, year=year)
                succeeded.append(show_name)

            except Exception as e:
                logger.error(f"Failed to process '{name}': {e}")
                failed.append(name)

            if i < len(shows) - 1:
                time.sleep(args.delay)

    logger.info(f"\n{'=' * 60}")
    logger.info(f"BATCH COMPLETE: {len(succeeded)} succeeded, {len(failed)} failed")
    if succeeded:
        logger.info(f"  Succeeded: {', '.join(succeeded)}")
    if failed:
        logger.info(f"  Failed: {', '.join(failed)}")


if __name__ == "__main__":
    main()
