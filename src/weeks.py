"""
Week in review: the week's stories of the day and its top articles, from the saved daily snapshots (site only).

A week is an ISO week, Monday to Sunday. Sunday builds save it to data/weeks/YYYY-Www.json (the last build of
the Sunday is final) and keep the newest KEEP_WEEKS. Before any week is saved, the site shows a preview of the
week so far, which is not saved.

Top articles: every section item of the week's snapshots is re-clustered with src.story.cluster (title and
excerpt), so the same story on different days counts once. Clusters holding a story of the day are left out.
Rank: coverage (distinct sites across the week, or the saved per-day coverage if higher), then the best saved
story score (snapshots from before 2026-11-01 have none; their items use the theme-keyword score the sections
rank by), then the section's weight in config.yaml. One article per cluster: the best-scored one.
"""

import json
import re
from datetime import date, timedelta
from pathlib import Path
from typing import Dict, List, Optional

from main import _score_article
from src import story

KEEP_WEEKS = 8
TOP = 10
NAME_RE = re.compile(r"(\d{4}-W\d{2})\.json")


def week_id(day: date) -> str:
    year, week, _ = day.isocalendar()
    return f"{year}-W{week:02d}"


def week_dates(day: date) -> List[date]:
    monday = day - timedelta(days=day.weekday())
    return [monday + timedelta(days=n) for n in range(7)]


def label(day: date) -> str:
    return f"{day:%a %b} {day.day}"


def span(start: date, end: date) -> str:
    return f"{start:%b} {start.day} – {end:%b} {end.day}, {end.year}"


def short_span(start: date, end: date) -> str:
    return f"{start:%b} {start.day} – {end.day}" if start.month == end.month else \
        f"{start:%b} {start.day} – {end:%b} {end.day}"


def _number(value) -> float:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else 0.0


def build_week(snapshots: Dict[str, Dict], end: date, config: Dict, preview: bool = False) -> Dict:
    """The week holding `end`: its days up to `end` (all seven unless a preview) and its top articles."""
    days = [d for d in week_dates(end) if d <= end] if preview else week_dates(end)
    weights = story.section_weights(config)
    out_days, pool, lead_links = [], [], set()
    for day in days:
        snap = snapshots.get(day.isoformat()) or {}
        lead = snap.get("lead") if isinstance(snap.get("lead"), dict) else None
        out_days.append({"date": day.isoformat(), "lead": {k: lead.get(k) for k in ("title", "link", "source", "section", "take")
                                                           if lead.get(k)} if lead else None})
        if lead:
            lead_links.add(lead.get("link"))
            pool.append({"title": lead.get("title") or "", "summary": lead.get("excerpt") or "", "link": lead.get("link"),
                         "lead": True})
        for section in snap.get("sections") or []:
            for item in (section.get("cards") or []) + (section.get("more") or []):
                pool.append({"title": item.get("title") or "", "summary": item.get("excerpt") or "",
                             "link": item.get("link"), "source": item.get("source") or "",
                             "section": section.get("name"), "date": day.isoformat(),
                             "score": _number(item["score"]) if "score" in item else _score_article(
                                 {"title": item.get("title") or "", "summary": item.get("excerpt") or ""}),
                             "coverage": int(_number(item.get("coverage")))})
    ranked = []
    for members in story.cluster(pool):
        if any(m.get("lead") or m.get("link") in lead_links for m in members):
            continue
        best = min(members, key=lambda m: (-m["score"], m["date"], m.get("link") or ""))
        coverage = max(story.coverage(members), max(m["coverage"] for m in members))
        ranked.append({"title": best["title"], "link": best["link"], "source": best["source"],
                       "section": best["section"], "date": best["date"], "coverage": coverage,
                       "score": round(max(m["score"] for m in members), 3)})
    ranked.sort(key=lambda r: (-r["coverage"], -r["score"], -weights.get(r["section"], 1.0), r["title"]))
    return {"week": week_id(end), "start": days[0].isoformat(), "end": days[-1].isoformat(), "preview": preview,
            "days": out_days, "top": ranked[:TOP]}


def plain_text(week: Dict, url: str) -> str:
    """The week as plain text for pasting into a LinkedIn post."""
    lines = [f"The Daily Brief · week in review, {span(date.fromisoformat(week['start']), date.fromisoformat(week['end']))}",
             "", "Stories of the day:"]
    leads = [d for d in week["days"] if d.get("lead")]
    lines += [f"{n}. {label(date.fromisoformat(d['date']))}: {d['lead'].get('title')} {d['lead'].get('link') or ''}".rstrip()
              for n, d in enumerate(leads, 1)]
    lines += ["", "Top of the week:"]
    lines += [f"{n}. {t['title']} {t.get('link') or ''}".rstrip() for n, t in enumerate(week["top"], 1)]
    lines += ["", f"All of it: {url}"]
    return "\n".join(lines) + "\n"


def _validate(data, label_: str, wid: str) -> Dict:
    def bad(why: str) -> ValueError:
        return ValueError(f"{label_}: not a valid week ({why})")

    if not isinstance(data, dict):
        raise bad("must be a JSON object")
    if data.get("week") != wid:
        raise bad(f"week must be {wid}, got {data.get('week')!r}")
    for key in ("start", "end"):
        try:
            date.fromisoformat(data.get(key))
        except (TypeError, ValueError):
            raise bad(f"{key} must be a date (YYYY-MM-DD)") from None
    days, top = data.get("days"), data.get("top")
    if not isinstance(days, list) or not all(isinstance(d, dict) and isinstance(d.get("date"), str) for d in days):
        raise bad("days must be a list of objects with a date")
    if not isinstance(top, list) or not all(isinstance(t, dict) and isinstance(t.get("title"), str) for t in top):
        raise bad("top must be a list of items with titles")
    return data


def load(directory: Path) -> Dict[str, Dict]:
    """Saved weeks by id. A missing directory is empty; a malformed file raises ValueError naming it."""
    if not directory.exists():
        return {}
    out = {}
    for path in sorted(directory.iterdir()):
        match = NAME_RE.fullmatch(path.name)
        if not match:
            continue
        label_ = f"{directory.name}/{path.name}"
        try:
            data = json.loads(path.read_text())
        except json.JSONDecodeError as e:
            raise ValueError(f"{label_}: not valid JSON ({e})") from e
        out[match.group(1)] = _validate(data, label_, match.group(1))
    return out


def save(directory: Path, week: Dict) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{week['week']}.json").write_text(json.dumps(week, indent=2, ensure_ascii=False) + "\n")


def prune(directory: Path, keep: int = KEEP_WEEKS) -> None:
    if not directory.exists():
        return
    files = sorted(p for p in directory.iterdir() if NAME_RE.fullmatch(p.name))
    for path in files[:-keep]:
        path.unlink()


def latest(saved: Dict[str, Dict], preview: Optional[Dict]) -> Optional[Dict]:
    return saved[max(saved)] if saved else preview
