"""Tests for the script ingestion pipeline."""

from backend.pipeline.ingest import chunk_script


def test_chunk_short_script():
    """Short scripts should return a single chunk."""
    text = "INT. OFFICE - DAY\nMichael enters.\nMICHAEL: That's what she said."
    chunks = chunk_script(text)
    assert len(chunks) == 1
    assert chunks[0] == text


def test_chunk_long_script():
    """Long scripts should be split into overlapping chunks."""
    text = "x" * 10000
    chunks = chunk_script(text, chunk_size=4000, overlap=200)
    assert len(chunks) > 1
    # Verify overlap exists
    assert chunks[0][-200:] == chunks[1][:200]


def test_chunk_empty():
    """Empty text returns single empty chunk."""
    chunks = chunk_script("")
    assert len(chunks) == 1
