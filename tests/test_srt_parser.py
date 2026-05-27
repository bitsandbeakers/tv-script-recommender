"""Tests for SRT subtitle parser."""

from backend.pipeline.srt_parser import extract_dialogue, parse_srt

SAMPLE_SRT = """1
00:00:01,000 --> 00:00:03,000
Previously on Breaking Bad...

2
00:00:05,500 --> 00:00:08,200
<i>You're a killer.</i>

3
00:00:10,000 --> 00:00:12,500
- I am the one who knocks!
- Walt, please.

4
00:00:15,000 --> 00:00:17,000
[dramatic music]

5
00:00:18,000 --> 00:00:20,000
{\\an8}♪ Baby blue ♪
"""


def test_parse_srt_entries():
    """Should parse SRT into structured entries."""
    entries = parse_srt(SAMPLE_SRT)
    assert len(entries) == 5
    assert entries[0]["index"] == 1
    assert entries[0]["start"] == "00:00:01,000"
    assert entries[0]["text"] == "Previously on Breaking Bad..."


def test_extract_dialogue_removes_tags():
    """Should strip HTML tags from dialogue."""
    dialogue = extract_dialogue(SAMPLE_SRT)
    assert "<i>" not in dialogue
    assert "You're a killer." in dialogue


def test_extract_dialogue_removes_brackets():
    """Should remove bracketed annotations like [dramatic music]."""
    dialogue = extract_dialogue(SAMPLE_SRT)
    assert "dramatic music" not in dialogue


def test_extract_dialogue_removes_music_notes():
    """Should remove music notation with ♪."""
    dialogue = extract_dialogue(SAMPLE_SRT)
    assert "♪" not in dialogue
    assert "Baby blue" not in dialogue


def test_extract_dialogue_removes_speaker_dashes():
    """Should remove leading dashes from speaker changes."""
    dialogue = extract_dialogue(SAMPLE_SRT)
    assert "I am the one who knocks!" in dialogue
    assert "Walt, please." in dialogue


def test_extract_empty_srt():
    """Should handle empty input gracefully."""
    assert extract_dialogue("") == ""


def test_extract_malformed_srt():
    """Should handle malformed SRT without crashing."""
    malformed = "not a real srt file\njust some text\n"
    result = extract_dialogue(malformed)
    assert isinstance(result, str)
