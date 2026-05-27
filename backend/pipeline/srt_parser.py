"""SRT subtitle parser — extracts clean dialogue text from subtitle files."""

import re


def parse_srt(srt_content: str) -> list[dict]:
    """Parse SRT content into a list of subtitle entries.

    Returns list of dicts with keys: index, start, end, text
    """
    entries = []
    # Split on blank lines to get subtitle blocks
    blocks = re.split(r"\n\s*\n", srt_content.strip())

    for block in blocks:
        lines = block.strip().split("\n")
        if len(lines) < 3:
            continue

        try:
            index = int(lines[0].strip())
        except ValueError:
            continue

        # Timestamp line: 00:01:23,456 --> 00:01:25,789
        timestamp_match = re.match(
            r"(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})",
            lines[1].strip(),
        )
        if not timestamp_match:
            continue

        text = "\n".join(lines[2:])
        entries.append({
            "index": index,
            "start": timestamp_match.group(1),
            "end": timestamp_match.group(2),
            "text": text,
        })

    return entries


def extract_dialogue(srt_content: str) -> str:
    """Extract clean dialogue text from SRT, removing timestamps and formatting tags."""
    entries = parse_srt(srt_content)

    clean_lines = []
    for entry in entries:
        text = entry["text"]
        # Remove HTML-like tags (italic, bold, font, etc.)
        text = re.sub(r"<[^>]+>", "", text)
        # Remove SRT positioning tags like {\an8}
        text = re.sub(r"\{\\[^}]+\}", "", text)
        # Remove speaker labels in brackets like [Music], (laughing), ♪
        text = re.sub(r"[\[({].*?[\])}]", "", text)
        text = re.sub(r"♪.*?♪", "", text)
        # Remove leading dashes (speaker change indicators)
        text = re.sub(r"^-\s*", "", text, flags=re.MULTILINE)
        # Collapse whitespace
        text = re.sub(r"\s+", " ", text).strip()

        if text and not text.isspace():
            clean_lines.append(text)

    return "\n".join(clean_lines)
