"""Script ingestion pipeline: load, chunk, and prepare scripts for analysis."""

from pathlib import Path

# Chunk size in characters — scripts are chunked to fit LLM context windows
CHUNK_SIZE = 4000
CHUNK_OVERLAP = 200


def load_script(path: Path) -> str:
    """Load a script file as text."""
    return path.read_text(encoding="utf-8", errors="replace")


def chunk_script(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split a script into overlapping chunks for analysis."""
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start = end - overlap
    return chunks
