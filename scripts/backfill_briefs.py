"""
One-off backfill of data/briefs/2026-10-20.json .. 2026-10-25.json, run on 2026-10-26.

The past-brief strip started on 2026-10-26, so the six days before it had no
snapshot. This script rebuilds them from the feeds as they stood on 2026-10-26
and marks each file "reconstructed": true (the page says so).

How each day D is rebuilt:
- The feeds are fetched once, wide enough to reach every day (FETCH_HOURS, up
  to FETCH_ITEMS per feed), and reused for all days.
- The last build of D is replayed (the last build of a day is final), taken as
  D 23:59 UTC: only articles published before it and inside their feed's window
  (hours_back, default 48h) relative to it. Undated articles are dropped, as
  their time is unknown. (02:17, the first daily slot, would miss the real leads
  of 10-24 and 10-25, published at 14:00 and 11:00 UTC by later builds.)
- No seen.json filtering and no seen.json writes. An article only appears on
  the first backfilled day it qualifies for, so the week doesn't repeat.
- Sections, story of the day and snapshot use the build's own code
  (main.select_articles, src.story.pick_story, site_builder.brief_snapshot).
- Lead: data/lead-history.json has real leads from 2026-10-23 on. Those are used
  (matched by URL) and kept off earlier backfilled days; when the article is no
  longer in the feeds, the lead is built from the history entry. Earlier days
  let the algorithm pick, with the novelty penalty from history before D only.
- The Pulse: Hacker News only, via Algolia with created_at_i bounded to the 24h
  before D 23:59 (points are as of the backfill run, not D). Lobsters has no
  date-bounded API, so it is left out; Reddit is blocked.
- Page images: og:image metadata from data/og-cache.json (fetched when missing);
  the cache file is not written.

Known differences from a real build: Hacker News points (section threshold,
lead scoring, Pulse) are current, and feeds that only keep their newest items
may have lost some older posts.
"""

import copy
import logging
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import requests  # noqa: E402

import build_site  # noqa: E402
from main import load_config, select_articles  # noqa: E402
from src import briefs, enrich, pulse, site_builder, story  # noqa: E402
from src.content_aggregator import ContentAggregator  # noqa: E402
from src.hn import min_points  # noqa: E402
from src.pulse import url_key  # noqa: E402

DAYS = [date(2026, 10, 20) + timedelta(days=n) for n in range(6)]
BUILD_HOUR, BUILD_MINUTE = 23, 59
DEFAULT_HOURS = 48
FETCH_HOURS = 8 * 24
FETCH_ITEMS = 50

logger = logging.getLogger("backfill")


class BackfillAggregator(ContentAggregator):
    """Fetches every feed once with a window and item limit wide enough for all backfilled days."""
    MAX_TOTAL_ARTICLES = 20000

    def fetch_rss_feed(self, url: str, max_items: int = 10, hours_back: Optional[int] = None) -> List[Dict]:
        return super().fetch_rss_feed(url, max_items=FETCH_ITEMS, hours_back=FETCH_HOURS)


def build_time(day: date) -> datetime:
    return datetime(day.year, day.month, day.day, BUILD_HOUR, BUILD_MINUTE, tzinfo=timezone.utc)


def check_days(days: List[date], today: date) -> None:
    if any(d >= today for d in days):
        raise SystemExit(f"refusing to backfill {today} or later; that day has (or will have) a real snapshot")


def feed_windows(config: Dict) -> Dict[str, int]:
    return {s["url"]: s.get("hours_back", DEFAULT_HOURS) for t in config["topics"] for s in t.get("sources", [])}


def articles_for_day(raw: Dict[str, List[Dict]], now: datetime, windows: Dict[str, int],
                     shown: Set[str]) -> Dict[str, List[Dict]]:
    """What a build at `now` would have fetched: published before it, inside the feed's window, not shown on an
    earlier backfilled day."""
    out = {}
    for topic, articles in raw.items():
        out[topic] = []
        for a in articles:
            published = a.get("published")
            if not isinstance(published, datetime):
                continue
            if not now - timedelta(hours=windows.get(a.get("feed"), DEFAULT_HOURS)) <= published < now:
                continue
            if url_key(a.get("link")) in shown:
                continue
            out[topic].append(copy.copy(a))
    return out


def history_before(history: List[Dict], day: date) -> List[Dict]:
    return [e for e in history if str(e.get("date", "")) < day.isoformat()]


def reserved_leads(history: List[Dict], day: date) -> Set[str]:
    """Recorded leads of later backfilled days, kept off `day` so each one first appears on its own day."""
    days = {d.isoformat() for d in DAYS}
    return {url_key(e.get("url")) for e in history if e.get("date") in days and e["date"] > day.isoformat()}


def pick_lead(raw_day: Dict[str, List[Dict]], raw_all: Dict[str, List[Dict]], config: Dict, history: List[Dict],
              day: date, now: datetime) -> Tuple[story.Story, str]:
    """The day's lead: the recorded one from lead-history.json when there is one, else the algorithm's pick."""
    past = history_before(history, day)
    entry = next((e for e in history if e.get("date") == day.isoformat()), None)
    if not entry:
        return story.pick_story(raw_day, config, past, None, now), "algorithm"
    key = url_key(entry.get("url"))

    def find(feed):
        return next(((t, a) for t, arts in feed.items() for a in arts if url_key(a.get("link")) == key), None)

    found = find(raw_day)
    if not found:
        match = find(raw_all)
        if match and isinstance(match[1].get("published"), datetime) and match[1]["published"] < now:
            raw_day.setdefault(match[0], []).append(copy.copy(match[1]))
            found = match
    pinned = {"url": found[1]["link"] if found else entry["url"], "title": None if found else entry.get("title"),
              "note": None, "until": day}
    lead = story.pick_story(raw_day, config, past, pinned, now)
    lead.pinned = False
    if not found:
        lead.section = entry.get("section")
        return lead, "history entry, not in feeds (built from the entry)"
    return lead, "history entry, found in feeds"


def bounded_get(now: datetime):
    """requests.get for the Algolia search with an upper bound on created_at_i, so nothing after `now` comes back."""
    def get(url, **kw):
        params = dict(kw.pop("params", {}))
        params["numericFilters"] = params.get("numericFilters", "") + f",created_at_i<{int(now.timestamp())}"
        return requests.get(url, params=params, **kw)
    return get


def pulse_for_day(config: Dict, now: datetime, shown: Set[str]) -> List[Dict]:
    """The Pulse from Hacker News alone (the only source with a date-bounded query), or [] if unavailable."""
    raw = config.get("pulse") or {}
    hn_only = {k: v for k, v in raw.items() if k not in ("lobsters", "subreddits", "min_upvotes")}
    try:
        items, _ = pulse.collect(dict(config, pulse=hn_only), now, env={}, get=bounded_get(now), shown=shown)
    except pulse.PulseUnavailable as e:
        logger.warning(f"{now.date()}: no Pulse ({e})")
        return []
    return [i for i in items if i["created"] < now]


def backfill_day(day: date, raw_all: Dict, config: Dict, history: List[Dict], windows: Dict[str, int],
                 shown: Set[str], og_cache: Dict) -> Tuple[Dict, str]:
    now = build_time(day)
    raw_day = articles_for_day(raw_all, now, windows, shown | reserved_leads(history, day))
    feed = select_articles(raw_day, config["brief"]["max_articles_per_topic"],
                           min_points(config, "section_min_hn_points"))
    lead, how = pick_lead(raw_day, raw_all, config, history, day, now)
    rendered = build_site._rendered(raw_day, feed, lead)
    page_links = {a.get("link") for a in rendered} | {lead.link}
    pulse_items = pulse_for_day(config, now, page_links)
    need_image = [i for i in pulse_items if i.get("link") and not i.get("image")]
    pulse_pages = [{"link": i["link"], "image": None, "feed": ""} for i in need_image]
    enrich.enrich(rendered + pulse_pages, og_cache, day, fetch=enrich.fetch_meta)
    for item, page in zip(need_image, pulse_pages):
        item["image"], item["icon"] = page.get("image"), page.get("icon")
    lead, how = pick_lead(raw_day, raw_all, config, history, day, now)
    snap = site_builder.brief_snapshot(feed, lead, pulse_items, now)
    snap["reconstructed"] = True
    shown |= {url_key(a.get("link")) for arts in feed.values() for a in arts} | {url_key(lead.link)}
    return snap, how


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    check_days(DAYS, datetime.now(timezone.utc).date())
    config = load_config(str(ROOT / "config.yaml"))
    history = story.load_history(ROOT / "data/lead-history.json")
    og_cache = enrich.load_cache(ROOT / "data/og-cache.json")
    raw_all = BackfillAggregator(hours_back=FETCH_HOURS).aggregate_content(config["topics"])
    windows, shown = feed_windows(config), set()
    for day in DAYS:
        snap, how = backfill_day(day, raw_all, config, history, windows, shown, og_cache)
        briefs.save(ROOT / "data/briefs", day, snap)
        items = sum(len(s["cards"]) + len(s["more"]) for s in snap["sections"])
        logger.info(f"{day}: {items} section items, {len(snap['pulse'])} Pulse, lead ({how}): "
                    f"{snap['lead']['title'] if snap['lead'] else None}")


if __name__ == "__main__":
    main()
