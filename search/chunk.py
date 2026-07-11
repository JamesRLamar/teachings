"""Split markdown into overlapping chunks for embedding."""

from __future__ import annotations

import re
from dataclasses import dataclass

_HEADING_RE = re.compile(r"^(#{2,3})\s+(.+)$", re.MULTILINE)

TARGET_WORDS = 350
OVERLAP_WORDS = 50


@dataclass
class Chunk:
    heading: str
    text: str
    start_line: int


def _word_count(text: str) -> int:
    return len(text.split())


def _sliding_window(text: str, heading: str, start_line: int) -> list[Chunk]:
    words = text.split()
    if not words:
        return []
    if len(words) <= TARGET_WORDS:
        return [Chunk(heading=heading, text=text.strip(), start_line=start_line)]

    chunks: list[Chunk] = []
    step = max(1, TARGET_WORDS - OVERLAP_WORDS)
    for i in range(0, len(words), step):
        piece = " ".join(words[i : i + TARGET_WORDS]).strip()
        if piece:
            chunks.append(Chunk(heading=heading, text=piece, start_line=start_line))
        if i + TARGET_WORDS >= len(words):
            break
    return chunks


def _section_start_line(full_text: str, offset: int) -> int:
    return full_text.count("\n", 0, offset) + 1


def chunk_markdown(body: str, default_heading: str = "") -> list[Chunk]:
    """Chunk on ## / ### boundaries; oversized sections use a sliding window."""
    body = body.strip()
    if not body:
        return []

    matches = list(_HEADING_RE.finditer(body))
    if not matches:
        return _sliding_window(body, default_heading, 1)

    chunks: list[Chunk] = []

    # Prefatory content before the first heading
    first = matches[0]
    if first.start() > 0:
        preface = body[: first.start()].strip()
        if preface:
            chunks.extend(
                _sliding_window(preface, default_heading, 1)
            )

    for i, match in enumerate(matches):
        heading = match.group(2).strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        section = body[start:end].strip()
        if not section:
            continue
        start_line = _section_start_line(body, match.start())
        if _word_count(section) <= TARGET_WORDS:
            chunks.append(Chunk(heading=heading, text=section, start_line=start_line))
        else:
            chunks.extend(_sliding_window(section, heading, start_line))

    return chunks
