"""Tests for feature extraction parsing, adaptive sampling, and hierarchical merging."""

import json
from unittest.mock import patch

from backend.pipeline.extract import (
    EpisodeDialogue,
    compute_max_chunks,
    extract_show_features,
    parse_features_response,
)


# --- Parsing ---

def test_parse_valid_json():
    data = {
        "themes": ["power", "family"],
        "tone": ["dark", "satirical"],
        "humor_type": ["dry wit"],
        "dialogue_style": ["rapid-fire"],
        "emotional_register": ["restrained"],
        "pacing": "fast",
        "genre_blend": ["drama"],
        "narrative_structure": "serialized",
        "vocabulary_complexity": "dense",
        "style_summary": "Sharp, prestige drama with biting dialogue.",
    }
    features = parse_features_response(json.dumps(data), "Succession")
    assert features.show_title == "Succession"
    assert "power" in features.themes
    assert features.pacing == "fast"


def test_parse_markdown_wrapped_json():
    data = {"themes": ["love"], "tone": ["warm"]}
    response = f"```json\n{json.dumps(data)}\n```"
    features = parse_features_response(response, "Ted Lasso")
    assert features.show_title == "Ted Lasso"
    assert "love" in features.themes


# --- Adaptive sampling ---

def test_compute_max_chunks_movie():
    """Movies should use at most 2 chunks."""
    assert compute_max_chunks(10, content_type="Movie") == 2
    assert compute_max_chunks(1, content_type="Movie") == 1


def test_compute_max_chunks_miniseries():
    """Mini-series (1 season, ≤8 episodes) should use up to 6 chunks."""
    assert compute_max_chunks(100, content_type="Scripted", num_seasons=1, num_episodes=6) == 6
    assert compute_max_chunks(4, content_type="Scripted", num_seasons=1, num_episodes=6) == 4


def test_compute_max_chunks_single_full_season():
    """Single full season (22 eps) should use up to 10 chunks."""
    assert compute_max_chunks(100, content_type="Scripted", num_seasons=1, num_episodes=22) == 10


def test_compute_max_chunks_multi_season():
    """Multi-season shows: 3 chunks per season."""
    assert compute_max_chunks(100, content_type="Scripted", num_seasons=3, num_episodes=39) == 9
    assert compute_max_chunks(100, content_type="Scripted", num_seasons=5, num_episodes=65) == 15


def test_compute_max_chunks_long_running():
    """Long-running shows (6+ seasons) capped at 30."""
    assert compute_max_chunks(1000, content_type="Scripted", num_seasons=10, num_episodes=220) == 20
    assert compute_max_chunks(1000, content_type="Scripted", num_seasons=20, num_episodes=400) == 30


def test_compute_max_chunks_respects_available():
    """Never return more chunks than are available."""
    assert compute_max_chunks(3, content_type="Scripted", num_seasons=5, num_episodes=65) == 3


def test_compute_max_chunks_few_available():
    """Always return all chunks when very few are available."""
    assert compute_max_chunks(2) == 2
    assert compute_max_chunks(1) == 1


# --- LiteLLM integration (mocked) ---

def test_extract_and_merge_single_chunk():
    """Single chunk should skip the merge call."""
    from backend.pipeline.extract import extract_and_merge_features

    fake_response = json.dumps({
        "themes": ["crime"], "tone": ["tense"], "humor_type": [],
        "dialogue_style": ["terse"], "emotional_register": ["controlled"],
        "pacing": "slow-burn", "genre_blend": ["drama"],
        "narrative_structure": "serialized", "vocabulary_complexity": "moderate",
        "style_summary": "Slow-burn crime drama with terse dialogue.",
    })

    with patch("backend.pipeline.extract._call_llm", return_value=fake_response) as mock_llm:
        features = extract_and_merge_features(
            ["some dialogue text"],
            "Breaking Bad",
            content_type="Scripted",
            num_seasons=5,
            num_episodes=62,
        )

    # With 1 chunk available, only 1 LLM call (extraction, no merge)
    assert mock_llm.call_count == 1
    assert features.show_title == "Breaking Bad"
    assert features.pacing == "slow-burn"


def test_extract_and_merge_uses_adaptive_count():
    """Correct number of chunks sampled for a multi-season show."""
    from backend.pipeline.extract import extract_and_merge_features

    fake_response = json.dumps({
        "themes": ["power"], "tone": ["dark"], "humor_type": ["dry wit"],
        "dialogue_style": ["rapid-fire"], "emotional_register": ["restrained"],
        "pacing": "fast", "genre_blend": ["drama"],
        "narrative_structure": "serialized", "vocabulary_complexity": "dense",
        "style_summary": "Sharp prestige drama.",
    })

    # 4 seasons → compute_max_chunks gives 12, but we only have 10 chunks
    chunks = [f"chunk {i}" for i in range(10)]
    with patch("backend.pipeline.extract._call_llm", return_value=fake_response) as mock_llm:
        extract_and_merge_features(
            chunks, "Succession",
            content_type="Scripted", num_seasons=4, num_episodes=40,
        )

    # 10 chunks extracted + 3 merge calls (batch of 8 + batch of 2 + final merge) = 13
    assert mock_llm.call_count == 13


# --- Hierarchical extraction (mocked) ---

FAKE_FEATURES_JSON = json.dumps({
    "themes": ["crime"], "tone": ["tense"], "humor_type": [],
    "dialogue_style": ["terse"], "emotional_register": ["controlled"],
    "pacing": "slow-burn", "genre_blend": ["drama"],
    "narrative_structure": "serialized", "vocabulary_complexity": "moderate",
    "style_summary": "Slow-burn crime drama with terse dialogue.",
})


def test_extract_show_features_movie():
    """Movie (single episode) uses flat extraction, no hierarchy."""
    episodes = [EpisodeDialogue(season=1, episode=1, text="Some movie dialogue.")]

    with patch("backend.pipeline.extract._call_llm", return_value=FAKE_FEATURES_JSON) as mock_llm:
        features = extract_show_features(episodes, "No Country", content_type="Movie")

    assert mock_llm.call_count == 1
    assert features.show_title == "No Country"
    assert features.pacing == "slow-burn"


def test_extract_show_features_single_episode_series():
    """Single-episode series treated as movie (flat extraction)."""
    episodes = [EpisodeDialogue(season=1, episode=1, text="Pilot dialogue.")]

    with patch("backend.pipeline.extract._call_llm", return_value=FAKE_FEATURES_JSON) as mock_llm:
        features = extract_show_features(episodes, "Pilot Show", content_type="Scripted")

    assert mock_llm.call_count == 1
    assert features.show_title == "Pilot Show"


def test_extract_show_features_single_season():
    """Single season: per-episode extraction + season merge (no show-level merge)."""
    episodes = [
        EpisodeDialogue(season=1, episode=1, text="Episode 1 dialogue."),
        EpisodeDialogue(season=1, episode=2, text="Episode 2 dialogue."),
    ]

    with patch("backend.pipeline.extract._call_llm", return_value=FAKE_FEATURES_JSON) as mock_llm:
        features = extract_show_features(episodes, "Fleabag")

    # 2 episode extractions + 1 season merge = 3 calls
    # (single season → season result IS the show result, no extra merge)
    assert mock_llm.call_count == 3
    assert features.show_title == "Fleabag"


def test_extract_show_features_multi_season():
    """Multi-season: per-episode + per-season merges + show-level merge."""
    episodes = [
        EpisodeDialogue(season=1, episode=1, text="S1E1 dialogue."),
        EpisodeDialogue(season=1, episode=2, text="S1E2 dialogue."),
        EpisodeDialogue(season=2, episode=1, text="S2E1 dialogue."),
    ]

    with patch("backend.pipeline.extract._call_llm", return_value=FAKE_FEATURES_JSON) as mock_llm:
        features = extract_show_features(episodes, "Breaking Bad")

    # 3 episode extractions + 1 merge for S1 (2 eps) + 0 merge for S2 (1 ep)
    # + 1 show-level merge (2 seasons) = 5
    assert mock_llm.call_count == 5
    assert features.show_title == "Breaking Bad"


def test_extract_show_features_groups_by_season():
    """Episodes are correctly grouped by season number."""
    episodes = [
        EpisodeDialogue(season=2, episode=1, text="S2E1."),
        EpisodeDialogue(season=1, episode=1, text="S1E1."),
        EpisodeDialogue(season=1, episode=2, text="S1E2."),
    ]

    call_prompts = []

    def capture_llm(prompt):
        call_prompts.append(prompt)
        return FAKE_FEATURES_JSON

    with patch("backend.pipeline.extract._call_llm", side_effect=capture_llm):
        features = extract_show_features(episodes, "Test Show")

    assert features.show_title == "Test Show"
    # Should have processed S1 first (2 eps), then S2 (1 ep)
    # Verify merge prompts mention the right seasons
    merge_prompts = [p for p in call_prompts if "Merge" in p]
    assert any("season 1" in p for p in merge_prompts)
    assert any("seasons of Test Show" in p for p in merge_prompts)
