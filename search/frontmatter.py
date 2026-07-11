"""Parse sermon YAML frontmatter, tolerating curly quotes common in Obsidian exports."""

from __future__ import annotations

import re
from typing import Any

import yaml

_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?", re.DOTALL)

# Map curly / typographic quotes to ASCII so PyYAML can parse Obsidian-style YAML.
_QUOTE_MAP = str.maketrans(
    {
        "\u201c": '"',  # “
        "\u201d": '"',  # ”
        "\u2018": "'",  # ‘
        "\u2019": "'",  # ’
        "\u00ab": '"',
        "\u00bb": '"',
    }
)


def normalize_quotes(text: str) -> str:
    return text.translate(_QUOTE_MAP)


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Return (metadata, body). Metadata keys are lowercased strings."""
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return {}, text

    raw = normalize_quotes(match.group(1))
    try:
        data = yaml.safe_load(raw) or {}
    except yaml.YAMLError:
        data = {}

    if not isinstance(data, dict):
        data = {}

    meta: dict[str, Any] = {}
    for key, value in data.items():
        meta[str(key).lower()] = value

    body = text[match.end() :]
    return meta, body


def as_str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str):
        s = value.strip()
        return [s] if s else []
    return [str(value).strip()]


def as_optional_str(value: Any) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    return s or None
