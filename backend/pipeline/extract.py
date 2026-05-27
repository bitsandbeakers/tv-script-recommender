"""LLM-based feature extraction from script chunks."""

import json
import logging

import litellm

from backend.core.config import settings
from backend.models.schemas import ScriptFeatures

logger = logging.getLogger(__name__)

# Suppress litellm's verbose logging
litellm.suppress_debug_info = True

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

MERGE_PROMPT = """I have multiple feature extractions from different episodes of the same TV show.
Merge them into a single representative feature set for the show overall.
Deduplicate and keep the most prominent/recurring features.

Individual extractions:
{extractions_json}

Return a single merged JSON with the same schema:
themes, tone, humor_type, dialogue_style, emotional_register, pacing, genre_blend,
narrative_structure, vocabulary_complexity, style_summary.

Return ONLY valid JSON, no markdown formatting."""


def compute_max_chunks(
    available: int,
    content_type: str = "Scripted",
    num_seasons: int = 1,
    num_episodes: int = 0,
) -> int:
    """Compute how many chunks to sample based on content scale.

    Sampling targets:
    - Movie / Special:          2 chunks  (small corpus, full coverage)
    - Miniseries (≤8 eps):      6 chunks  (one per episode roughly)
    - Single full season:       10 chunks
    - 2-5 seasons:              3 chunks per season
    - 6+ seasons:               2 chunks per season, capped at 30
    """
    if available <= 2:
        return available

    ct = content_type.lower()

    # Movies and specials
    if ct in ("movie", "special", "documentary") or (num_seasons == 0 and num_episodes <= 1):
        return min(2, available)

    # Miniseries / limited series
    if num_seasons <= 1 and 0 < num_episodes <= 8:
        return min(6, available)

    # Single full season (e.g. 13-26 episodes)
    if num_seasons <= 1:
        return min(10, available)

    # Multi-season
    if num_seasons <= 5:
        return min(num_seasons * 3, available)

    # Long-running (6+ seasons)
    return min(num_seasons * 2, 30, available)


def parse_features_response(response_text: str, show_title: str) -> ScriptFeatures:
    """Parse LLM response into ScriptFeatures."""
    try:
        data = json.loads(response_text)
    except json.JSONDecodeError:
        # Try extracting JSON from markdown code blocks
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


def extract_features_from_text(text: str, show_title: str) -> ScriptFeatures:
    """Extract features from a single chunk of dialogue text."""
    prompt = EXTRACTION_PROMPT.format(script_text=text)
    response = _call_llm(prompt)
    return parse_features_response(response, show_title)


def extract_and_merge_features(
    chunks: list[str],
    show_title: str,
    content_type: str = "Scripted",
    num_seasons: int = 1,
    num_episodes: int = 0,
) -> ScriptFeatures:
    """Extract features from sampled chunks and merge into one show profile.

    Samples adaptively based on content type and scale:
    movies get 2 chunks, miniseries ~6, long-running series up to 30.
    Samples are distributed evenly across the corpus so early, mid,
    and late episodes all contribute.
    """
    max_n = compute_max_chunks(len(chunks), content_type, num_seasons, num_episodes)

    if len(chunks) <= max_n:
        selected = chunks
    else:
        step = len(chunks) / max_n
        selected = [chunks[int(i * step)] for i in range(max_n)]

    logger.info(
        f"Sampling {len(selected)}/{len(chunks)} chunks "
        f"(type={content_type}, seasons={num_seasons}, episodes={num_episodes})"
    )

    individual = []
    for i, chunk in enumerate(selected):
        logger.info(f"  Analyzing chunk {i + 1}/{len(selected)}...")
        features = extract_features_from_text(chunk, show_title)
        individual.append(features.model_dump(exclude={"show_title", "season", "episode"}))

    if len(individual) == 1:
        return ScriptFeatures(show_title=show_title, **individual[0])

    logger.info("Merging features across chunks...")
    merge_prompt = MERGE_PROMPT.format(extractions_json=json.dumps(individual, indent=2))
    response = _call_llm(merge_prompt)
    return parse_features_response(response, show_title)
