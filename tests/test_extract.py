"""Tests for feature extraction parsing."""

import json

from backend.pipeline.extract import parse_features_response


def test_parse_valid_json():
    """Should parse clean JSON response."""
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
    """Should handle JSON wrapped in markdown code blocks."""
    data = {"themes": ["love"], "tone": ["warm"]}
    response = f"```json\n{json.dumps(data)}\n```"
    features = parse_features_response(response, "Ted Lasso")
    assert features.show_title == "Ted Lasso"
    assert "love" in features.themes
