"""Helpers for municipality name normalization and slug generation."""

from __future__ import annotations

import re
import unicodedata


def normalize_municipality_name(value: str | None) -> str:
    """Normalize municipality names for case-insensitive matching."""
    if value is None:
        return ""

    text = str(value).strip()
    if not text:
        return ""

    folded = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(char for char in folded if not unicodedata.combining(char))
    ascii_text = ascii_text.lower()
    ascii_text = re.sub(r"[^a-z0-9]+", " ", ascii_text)
    return re.sub(r"\s+", " ", ascii_text).strip()


def municipality_slug(value: str | None) -> str:
    """Create a stable URL slug for municipality names."""
    return normalize_municipality_name(value).replace(" ", "-")
