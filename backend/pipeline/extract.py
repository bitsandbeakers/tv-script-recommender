"""LLM-based feature extraction from script chunks."""

import json
import logging

import anthropic

from backend.core.config import settings
from backend.models.schemas import ScriptFeatures

logger = logging.getLogger(__name__)

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
    """Call the configured LLM and return the response text."""
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    message = client.messages.create(
        model=settings.llm_model,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def extract_features_from_text(text: str, show_title: str) -> ScriptFeatures:
    """Extract features from a single chunk of dialogue text."""
    prompt = EXTRACTION_PROMPT.format(script_text=text)
    response = _call_llm(prompt)
    return parse_features_response(response, show_title)


def extract_and_merge_features(
    chunks: list[str],
    show_title: str,
    max_chunks: int = 5,
) -> ScriptFeatures:
    """Extract features from multiple chunks and merge into one profile.

    Analyzes up to max_chunks sampled evenly across the dialogue corpus,
    then asks the LLM to merge the individual extractions.
    """
    # Sample chunks evenly across the corpus
    if len(chunks) <= max_chunks:
        selected = chunks
    else:
        step = len(chunks) / max_chunks
        selected = [chunks[int(i * step)] for i in range(max_chunks)]

    logger.info(f"Extracting features from {len(selected)} of {len(chunks)} chunks")

    # Extract features from each chunk
    individual = []
    for i, chunk in enumerate(selected):
        logger.info(f"  Analyzing chunk {i + 1}/{len(selected)}...")
        features = extract_features_from_text(chunk, show_title)
        individual.append(features.model_dump(exclude={"show_title", "season", "episode"}))

    # If only one chunk, no merge needed
    if len(individual) == 1:
        return ScriptFeatures(show_title=show_title, **individual[0])

    # Merge via LLM
    logger.info("Merging features across chunks...")
    merge_prompt = MERGE_PROMPT.format(extractions_json=json.dumps(individual, indent=2))
    response = _call_llm(merge_prompt)
    return parse_features_response(response, show_title)
