"""
Mark's take: takes.yaml maps a date (YYYY-MM-DD) to a short plain-text comment on that day's story of the day.

Shown under the lead headline and saved in the day's brief snapshot. A missing file means no takes; an
invalid one raises ValueError naming the file, like pinned.yaml.
"""

from datetime import date
from pathlib import Path
from typing import Dict

import yaml

MAX_CHARS = 400


def _day(key, name: str) -> str:
    if isinstance(key, date):
        return key.isoformat()
    try:
        return date.fromisoformat(str(key)).isoformat()
    except ValueError:
        raise ValueError(f"{name}: keys must be dates (YYYY-MM-DD), got {key!r}") from None


def load(path: Path) -> Dict[str, str]:
    """YYYY-MM-DD -> take text (whitespace collapsed)."""
    if not path.exists():
        return {}
    name = path.name
    try:
        data = yaml.safe_load(path.read_text())
    except (yaml.YAMLError, ValueError) as e:
        raise ValueError(f"{name}: not valid YAML ({e})") from e
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValueError(f"{name}: must be date: text pairs")
    out = {}
    for key, value in data.items():
        day = _day(key, name)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{name}: the take for {day} must be non-empty text")
        text = " ".join(value.split())
        if len(text) > MAX_CHARS:
            raise ValueError(f"{name}: the take for {day} is {len(text)} characters; keep it to {MAX_CHARS}")
        out[day] = text
    return out
