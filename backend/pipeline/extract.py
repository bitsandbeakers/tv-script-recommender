"""LLM-based feature extraction with hierarchical merging.

Extraction flow:
  Movie/Special:   chunks → extract each → merge all → show features
  Series:          per episode: chunks → extract → merge → episode features
                   per season:  episode features → batch merge → season features
                   show level:  season features → merge → show features

Each merge call handles at most MERGE_BATCH_SIZE items to keep
prompt size manageable for local models.
"""

import json
import logging
from dataclasses import dataclass

import litellm

from backend.core.config import settings
from backend.models.schemas import ScriptFeatures
from backend.pipeline.ingest import chunk_script

logger = logging.getLogger(__name__)

litellm.suppress_debug_info = True

MERGE_BATCH_SIZE = 8

EXTRACTION_PROMPT = """Analyze this TV show subtitle dialogue and extract the following features.
Return valid JSON matching this schema exactly.

Features to extract:
- themes: list of major themes (e.g. "power", "family dysfunction", "class")
- tone: list of tonal qualities (e.g. "dark", "satirical", "warm")
- humor_type: list of humor styles if any (e.g. "dry wit", "absurdist", "physical")
- dialogue_style: list of dialogue characteristics (e.g. "rapid-fire", "poetic", "naturalistic")
- emotional_register: list of emotional qualities (e.g. "restrained", "vulnerable", "manic")
- pacing: single word or short phrase (e.g. "fast", "slow-burn")
- genre_blend: list of genres (e.g. "drama", "comedy")
- narrative_structure: single descriptor (e.g. "serialized", "episodic")
- vocabulary_complexity: one of "simple", "moderate", "dense"
- style_summary: one sentence describing the overall writing style

Dialogue excerpt:
---
{script_text}
---

Return ONLY valid JSON, no markdown formatting."""

MERGE_PROMPT = """I have {count} feature extractions from {source_description}.
Merge them into a single representative feature set.
Deduplicate and keep the most prominent/recurring features.

Individual extractions:
{extractions_json}

Return a single merged JSON with the same schema:
themes, tone, humor_type, dialogue_style, emotional_register, pacing, genre_blend,
narrative_structure, vocabulary_complexity, style_summary.

Return ONLY valid JSON, no markdown formatting."""


@dataclass
class EpisodeDialogue:
    season: int
    episode: int
    text: str


def parse_features_response(response_text: str, show_title: str) -> ScriptFeatures:
    """Parse LLM response into ScriptFeatures."""
    try:
        data = json.loads(response_text)
    except json.JSONDecodeError:
        if "```" in response_text:
            json_str = response_text.split("```")[1]
            if json_str.startswith("json"):
                json_str = json_str[4:]
            data = json.loads(json_str.strip())
        else:
            raise

    return ScriptFeatures(show_title=show_title, **data)


def _call_llm(prompt: str) -> str:
    """Call the configured LLM via LiteLLM and return the response text."""
    kwargs: dict = {
        "model": settings.llm_model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 1024,
    }
    if settings.llm_api_base:
        kwargs["api_base"] = settings.llm_api_base
    if settings.llm_api_key:
        kwargs["api_key"] = settings.llm_api_key

    response = litellm.completion(**kwargs)
    return response.choices[0].message.content


def _features_dict(features: ScriptFeatures) -> dict:
    """Strip metadata fields, keep only the 10 extraction dimensions."""
    return features.model_dump(exclude={"show_title", "season", "episode"})


def _extract_chunk(text: str, show_title: str) -> ScriptFeatures:
    """Extract features from a single text chunk."""
    prompt = EXTRACTION_PROMPT.format(script_text=text)
    response = _call_llm(prompt)
    return parse_features_response(response, show_title)


def _merge_features(
    features_list: list[dict],
    source_description: str,
    show_title: str,
) -> ScriptFeatures:
    """Merge a list of feature dicts into one via LLM. Batches if needed."""
    if len(features_list) == 1:
        return ScriptFeatures(show_title=show_title, **features_list[0])

    # Recursive batching: if too many items, merge in batches first
    if len(features_list) > MERGE_BATCH_SIZE:
        batch_results = []
        for i in range(0, len(features_list), MERGE_BATCH_SIZE):
            batch = features_list[i : i + MERGE_BATCH_SIZE]
            batch_num = i // MERGE_BATCH_SIZE + 1
            logger.info(f"  Merging batch {batch_num} ({len(batch)} items)...")
            merged = _merge_features(batch, source_description, show_title)
            batch_results.append(_features_dict(merged))
        return _merge_features(batch_results, source_description, show_title)

    prompt = MERGE_PROMPT.format(
        count=len(features_list),
        source_description=source_description,
        extractions_json=json.dumps(features_list, indent=2),
    )
    response = _call_llm(prompt)
    return parse_features_response(response, show_title)


def _extract_episode(
    text: str,
    show_title: str,
    season: int,
    episode: int,
) -> ScriptFeatures:
    """Extract features for a single episode: chunk → extract each → merge."""
    chunks = chunk_script(text)
    label = f"S{season:02d}E{episode:02d}"

    if len(chunks) == 1:
        logger.info(f"  {label}: 1 chunk, extracting...")
        return _extract_chunk(chunks[0], show_title)

    logger.info(f"  {label}: {len(chunks)} chunks, extracting and merging...")
    chunk_features = []
    for chunk in chunks:
        features = _extract_chunk(chunk, show_title)
        chunk_features.append(_features_dict(features))

    return _merge_features(
        chunk_features,
        f"different parts of episode {label}",
        show_title,
    )


def extract_show_features(
    episodes: list[EpisodeDialogue],
    show_title: str,
    content_type: str = "Scripted",
) -> ScriptFeatures:
    """Hierarchical feature extraction for a show.

    Movie/Special (single item, no season structure):
      chunks → extract → merge → done

    Series:
      per-episode → chunk, extract, merge → episode features
      per-season  → batch merge episode features → season features
      show level  → merge season features → show features

    Each merge handles ≤8 items, keeping prompts small for local models.
    """
    ct = content_type.lower()
    is_movie = ct in ("movie", "special", "documentary") or len(episodes) <= 1

    if is_movie:
        # Flat extraction — no hierarchy needed
        text = episodes[0].text if episodes else ""
        chunks = chunk_script(text)
        logger.info(f"Movie/special: {len(chunks)} chunks")
        if len(chunks) == 1:
            return _extract_chunk(chunks[0], show_title)
        chunk_features = [_features_dict(_extract_chunk(c, show_title)) for c in chunks]
        return _merge_features(chunk_features, "different parts of the film", show_title)

    # --- Series: hierarchical extraction ---

    # Group episodes by season
    seasons: dict[int, list[EpisodeDialogue]] = {}
    for ep in episodes:
        seasons.setdefault(ep.season, []).append(ep)
    for s in seasons.values():
        s.sort(key=lambda e: e.episode)

    total_eps = len(episodes)
    total_seasons = len(seasons)
    logger.info(f"Hierarchical extraction: {total_eps} episodes across {total_seasons} seasons")

    # Phase 1: Extract per-episode features
    season_features: dict[int, list[dict]] = {}
    for season_num in sorted(seasons):
        eps = seasons[season_num]
        logger.info(f"Season {season_num}: {len(eps)} episodes")
        ep_features = []
        for ep in eps:
            features = _extract_episode(ep.text, show_title, ep.season, ep.episode)
            ep_features.append(_features_dict(features))
        season_features[season_num] = ep_features

    # Phase 2: Merge episode features → season features
    merged_seasons: list[dict] = []
    for season_num in sorted(season_features):
        ep_feats = season_features[season_num]
        logger.info(f"Merging season {season_num} ({len(ep_feats)} episodes)...")
        if len(ep_feats) == 1:
            merged_seasons.append(ep_feats[0])
        else:
            season_merged = _merge_features(
                ep_feats,
                f"different episodes of season {season_num}",
                show_title,
            )
            merged_seasons.append(_features_dict(season_merged))

    # Phase 3: Merge season features → show features
    if len(merged_seasons) == 1:
        return ScriptFeatures(show_title=show_title, **merged_seasons[0])

    logger.info(f"Merging {len(merged_seasons)} seasons into show profile...")
    return _merge_features(
        merged_seasons,
        f"different seasons of {show_title}",
        show_title,
    )


# --- Legacy flat API (still used by tests and simple callers) ---

def extract_features_from_text(text: str, show_title: str) -> ScriptFeatures:
    """Extract features from a single chunk of dialogue text."""
    return _extract_chunk(text, show_title)


def compute_max_chunks(
    available: int,
    content_type: str = "Scripted",
    num_seasons: int = 1,
    num_episodes: int = 0,
) -> int:
    """Compute how many chunks to sample for flat extraction mode."""
    if available <= 2:
        return available
    ct = content_type.lower()
    if ct in ("movie", "special", "documentary") or (num_seasons == 0 and num_episodes <= 1):
        return min(2, available)
    if num_seasons <= 1 and 0 < num_episodes <= 8:
        return min(6, available)
    if num_seasons <= 1:
        return min(10, available)
    if num_seasons <= 5:
        return min(num_seasons * 3, available)
    return min(num_seasons * 2, 30, available)


def extract_and_merge_features(
    chunks: list[str],
    show_title: str,
    content_type: str = "Scripted",
    num_seasons: int = 1,
    num_episodes: int = 0,
) -> ScriptFeatures:
    """Flat extraction fallback — samples chunks and merges in one pass.

    Prefer extract_show_features() for structured episode data.
    """
    max_n = compute_max_chunks(len(chunks), content_type, num_seasons, num_episodes)
    if len(chunks) <= max_n:
        selected = chunks
    else:
        step = len(chunks) / max_n
        selected = [chunks[int(i * step)] for i in range(max_n)]

    logger.info(f"Flat extraction: {len(selected)}/{len(chunks)} chunks")

    individual = [_features_dict(_extract_chunk(c, show_title)) for c in selected]

    if len(individual) == 1:
        return ScriptFeatures(show_title=show_title, **individual[0])

    return _merge_features(individual, "different parts of the show", show_title)
