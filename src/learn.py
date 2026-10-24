"""
Learn: popular recent videos from a few YouTube channels (site only).

Reads each channel's keyless RSS feed (the newest 15 uploads, with view
counts). Keeps videos from the last max_age_days that are not Shorts and
have views (premieres and upcoming streams show 0), ranks them by views per
day since publish (at least one day, so a video an hour old doesn't jump the
queue), and picks the top `limit` with at most `per_channel` from one
channel; if that leaves slots open, the next best from any channel fill them
(after the capped picks). The other recent videos are listed per channel,
newest first, at most `recent_per_channel` each.

Each channel fails on its own with a warning; only when every channel fails
does collect raise LearnUnavailable, and the site hides the teaser. The build
never fails.
"""

import logging
import re
from datetime import datetime
from typing import Callable, Dict, List, Optional, Tuple

import feedparser
import requests

FEED_URL = "https://www.youtube.com/feeds/videos.xml?channel_id="
CHANNEL_URL = "https://www.youtube.com/channel/"
WATCH_URL = "https://www.youtube.com/watch?v="
THUMB_URL = "https://i.ytimg.com/vi/{}/hqdefault.jpg"
USER_AGENT = "web:thedailybrief:1.0 (+https://thedailybrief.dev)"
TIMEOUT = 10
DEFAULTS = {"max_age_days": 30, "per_channel": 2, "limit": 6, "recent_per_channel": 5}
CHANNEL_KEYS = {"name", "id", "handle"}
VIDEO_ID = re.compile(r"[A-Za-z0-9_-]{11}")
CHANNEL_ID = re.compile(r"UC[A-Za-z0-9_-]{22}")

logger = logging.getLogger(__name__)


class LearnUnavailable(Exception):
    pass


def _count(value, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"config.yaml: learn.{name} must be a whole number >= 1, got {value!r}")
    return value


def _channel(entry) -> Dict:
    if not isinstance(entry, dict):
        raise ValueError(f"config.yaml: learn.channels entries need a name and an id, got {entry!r}")
    unknown = set(entry) - CHANNEL_KEYS
    if unknown:
        raise ValueError(f"config.yaml: learn.channels has unknown key(s) {', '.join(sorted(map(str, unknown)))}")
    name, cid = entry.get("name"), entry.get("id")
    if not isinstance(name, str) or not name.strip():
        raise ValueError(f"config.yaml: learn.channels needs a name for {cid!r}")
    if not isinstance(cid, str) or not CHANNEL_ID.fullmatch(cid):
        raise ValueError(f"config.yaml: learn.channels {name!r} needs a channel id like UC... (24 chars), got {cid!r}")
    if "handle" in entry and not isinstance(entry["handle"], str):
        raise ValueError(f"config.yaml: learn.channels {name!r} handle must be text")
    return {"name": name.strip(), "id": cid}


def settings(config: Dict) -> Optional[Dict]:
    """Validated learn settings, or None when config.yaml has no learn section."""
    raw = config.get("learn")
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ValueError("config.yaml: learn must be a mapping")
    unknown = set(raw) - set(DEFAULTS) - {"channels"}
    if unknown:
        raise ValueError(f"config.yaml: learn has unknown key(s) {', '.join(sorted(map(str, unknown)))}")
    out = {k: _count(raw.get(k, v), k) for k, v in DEFAULTS.items()}
    channels = [_channel(e) for e in raw.get("channels") or []]
    if not channels:
        raise ValueError("config.yaml: learn.channels must list at least one channel")
    ids = [c["id"] for c in channels]
    if len(set(ids)) != len(ids):
        raise ValueError("config.yaml: learn.channels lists a channel id twice")
    out["channels"] = channels
    return out


def _views(entry) -> int:
    try:
        return int((entry.get("media_statistics") or {}).get("views") or 0)
    except (TypeError, ValueError):
        return 0


def parse_feed(content: bytes, channel: str, channel_id: str) -> List[Dict]:
    """Videos in a channel feed; entries without a valid video id or publish time are dropped."""
    parsed = feedparser.parse(content)
    if not parsed.get("version"):
        raise LearnUnavailable(f"{channel}: not a feed")
    videos = []
    for e in parsed.entries:
        vid = e.get("yt_videoid") or ""
        try:
            published = datetime.fromisoformat(e.get("published") or "")
        except ValueError:
            continue
        if not VIDEO_ID.fullmatch(vid) or published.tzinfo is None:
            continue
        videos.append({"id": vid, "title": e.get("title") or "Untitled", "channel": channel,
                       "channel_id": channel_id, "views": _views(e), "published": published,
                       "link": WATCH_URL + vid, "thumb": THUMB_URL.format(vid),
                       "shorts": "/shorts/" in (e.get("link") or "")})
    return videos


def _fetch(channel: Dict, get: Callable) -> List[Dict]:
    name = channel["name"]
    try:
        response = get(FEED_URL + channel["id"], headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
    except requests.RequestException as e:
        raise LearnUnavailable(f"{name}: {e.__class__.__name__}") from e
    if response.status_code != 200:
        raise LearnUnavailable(f"{name}: HTTP {response.status_code}")
    return parse_feed(response.content, name, channel["id"])


def collect(config: Dict, now: datetime, get: Callable = requests.get) -> Tuple[Dict, Dict[str, Optional[int]]]:
    """{"top": ranked picks, "channels": [{name, url, videos: the rest, newest first}], "days": max_age_days}
    and how many videos
    qualified per channel (None = fetch failed). Raises LearnUnavailable only when every channel failed."""
    s = settings(config)
    pool, channels, counts, errors = [], [], {}, []
    for channel in s["channels"]:
        try:
            videos = _fetch(channel, get)
        except LearnUnavailable as e:
            logger.warning(f"Learn: {e}")
            counts[channel["name"]] = None
            errors.append(str(e))
            continue
        good = []
        for v in videos:
            age_days = (now - v["published"]).total_seconds() / 86400
            if v["shorts"] or v["views"] <= 0 or age_days > s["max_age_days"]:
                continue
            good.append(dict(v, per_day=v["views"] / max(age_days, 1.0)))
        counts[channel["name"]] = len(good)
        pool += good
        channels.append({"name": channel["name"], "id": channel["id"], "url": CHANNEL_URL + channel["id"]})
    if errors and len(errors) == len(s["channels"]):
        raise LearnUnavailable(f"every channel failed ({', '.join(errors)})")
    pool.sort(key=lambda v: (-v["per_day"], v["title"], v["id"]))
    top, taken = [], {}
    for v in pool:
        if len(top) < s["limit"] and taken.get(v["channel_id"], 0) < s["per_channel"]:
            top.append(v)
            taken[v["channel_id"]] = taken.get(v["channel_id"], 0) + 1
    picked = {v["id"] for v in top}
    top += [v for v in pool if v["id"] not in picked][:s["limit"] - len(top)]
    picked = {v["id"] for v in top}
    for c in channels:
        rest = [v for v in pool if v["channel_id"] == c["id"] and v["id"] not in picked]
        c["videos"] = sorted(rest, key=lambda v: (v["published"], v["id"]), reverse=True)[:s["recent_per_channel"]]
    return {"top": top, "channels": channels, "days": s["max_age_days"]}, counts
