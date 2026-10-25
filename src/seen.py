"""
Articles the site has shown, so each appears on one day only (site only).

data/seen.json maps a normalized article URL (src.pulse.url_key: no scheme,
www., trailing slash or fragment) to the first date the site showed it. A
build drops articles first shown on an earlier day and keeps ones first shown
today, so the several builds of one day agree. Entries older than KEEP_DAYS
are pruned; feeds only reach back a few days.
"""

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

from src.pulse import url_key

KEEP_DAYS = 14


def _is_date(value) -> bool:
    try:
        date.fromisoformat(value)
    except (TypeError, ValueError):
        return False
    return True


def load(path: Path) -> Dict[str, str]:
    """url key -> first date shown. A missing file is empty; a malformed one raises ValueError."""
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        raise ValueError(f"{path.name}: not valid JSON ({e})") from e
    if not isinstance(data, dict) or not all(isinstance(k, str) and _is_date(v) for k, v in data.items()):
        raise ValueError(f"{path.name}: must be a JSON object of article URL -> first date shown (YYYY-MM-DD)")
    return data


def unseen(feed: Dict[str, List[Dict]], seen: Dict[str, str], today: date) -> Tuple[Dict[str, List[Dict]], int]:
    """The feed without articles first shown before today, and how many were dropped."""
    cutoff = today.isoformat()
    kept, skipped = {}, 0
    for topic, articles in feed.items():
        kept[topic] = []
        for article in articles:
            first = seen.get(url_key(article.get("link")))
            if first and first < cutoff:
                skipped += 1
                continue
            kept[topic].append(article)
    return kept, skipped


def record(seen: Dict[str, str], links: Iterable[str], today: date) -> Dict[str, str]:
    """Add links shown today (keeping earlier first dates) and drop entries older than KEEP_DAYS."""
    out = dict(seen)
    for link in links:
        key = url_key(link)
        if key:
            out.setdefault(key, today.isoformat())
    oldest = (today - timedelta(days=KEEP_DAYS)).isoformat()
    return {k: v for k, v in out.items() if v >= oldest}


def save(path: Path, seen: Dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(sorted(seen.items())), indent=2) + "\n")
