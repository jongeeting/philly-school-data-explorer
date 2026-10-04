"""Philly School Data Explorer: download, identity, and build tools."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "raw"
STAGING = ROOT / "staging"
CORE = ROOT / "core"
SOURCES = ROOT / "sources"
REGISTRY = ROOT / "registry"

USER_AGENT = (
    "philly-school-data-explorer/0.1 (open data project; "
    "https://github.com/jongeeting/philly-school-data-explorer)"
)


def spring_year(text: str) -> int | None:
    """School year in a file name or label -> spring year (2025-2026 or 2025-26 -> 2026)."""
    m = re.search(r"(20\d{2})\s*[-_]\s*(20\d{2}|\d{2})(?!\d)", text)
    if not m:
        return None
    end = m.group(2)
    return int(end) if len(end) == 4 else int(m.group(1)[:2] + end)
