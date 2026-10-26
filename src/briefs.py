"""
Past daily briefs: one render-ready snapshot per day in data/briefs/YYYY-MM-DD.json (site only).

Each build overwrites today's file (src.site_builder.brief_snapshot), so the last
build of a day is final; other days' files are never rewritten, only pruned once
they fall out of the KEEP_DAYS window (today and the six days before). A missing
directory means no past days; a malformed snapshot inside the window raises
ValueError naming the file, like data/lead-history.json.
"""

import json
import re
from datetime import date, timedelta
from pathlib import Path
from typing import Dict, List

KEEP_DAYS = 7
NAME_RE = re.compile(r"(\d{4}-\d{2}-\d{2})\.json")


def window(today: date) -> List[date]:
    """Today and the KEEP_DAYS - 1 days before it, oldest first."""
    return [today - timedelta(days=n) for n in range(KEEP_DAYS - 1, -1, -1)]


def _items_ok(items) -> bool:
    return isinstance(items, list) and all(isinstance(i, dict) and isinstance(i.get("title"), str) for i in items)


def _validate(snap, label: str, day: str) -> Dict:
    def bad(why: str) -> ValueError:
        return ValueError(f"{label}: not a valid brief snapshot ({why})")

    if not isinstance(snap, dict):
        raise bad("must be a JSON object")
    if snap.get("date") != day:
        raise bad(f"date must be {day}, got {snap.get('date')!r}")
    lead = snap.get("lead")
    if lead is not None and not (isinstance(lead, dict) and isinstance(lead.get("title"), str)):
        raise bad("lead must be null or an object with a title")
    if not _items_ok(snap.get("pulse")):
        raise bad("pulse must be a list of items with titles")
    sections = snap.get("sections")
    if not isinstance(sections, list):
        raise bad("sections must be a list")
    for s in sections:
        if not isinstance(s, dict) or not isinstance(s.get("name"), str) \
                or not _items_ok(s.get("cards")) or not _items_ok(s.get("more")):
            raise bad("each section needs a name and lists of cards and more items with titles")
    return snap


def load(directory: Path, today: date) -> Dict[str, Dict]:
    """Snapshots of the past days in the window (today's is rebuilt), keyed by YYYY-MM-DD."""
    out = {}
    for day in window(today)[:-1]:
        path = directory / f"{day.isoformat()}.json"
        if not path.exists():
            continue
        label = f"{directory.name}/{path.name}"
        try:
            snap = json.loads(path.read_text())
        except json.JSONDecodeError as e:
            raise ValueError(f"{label}: not valid JSON ({e})") from e
        out[day.isoformat()] = _validate(snap, label, day.isoformat())
    return out


def save(directory: Path, today: date, snap: Dict) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{today.isoformat()}.json").write_text(json.dumps(snap, indent=2, ensure_ascii=False) + "\n")


def prune(directory: Path, today: date) -> None:
    """Delete snapshots older than the window; other files are left alone."""
    if not directory.exists():
        return
    oldest = window(today)[0].isoformat()
    for path in directory.iterdir():
        match = NAME_RE.fullmatch(path.name)
        if match and match.group(1) < oldest:
            path.unlink()
