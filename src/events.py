"""
CFP radar: open calls for talks and upcoming conferences on the site's topics (site only).

Two keyless sources: developers.events (all-cfps.json: CFP deadline, link and the conference) and the
tech-conferences/conference-data files for this year and next (one file per topic). A conference is kept when
its name has a keyword of a category in config.yaml `events.keywords`, or it comes from a topic file mapped to a
category (`events.topic_categories`). The same conference from both sources (normalized name + year) is merged.

Each source fails on its own with a warning; the page shows what is left. collect never raises for a source.
"""

import hashlib
import logging
import re
from datetime import date, datetime, timedelta, timezone
from typing import Callable, Dict, Iterable, List, Optional, Set, Tuple

import requests

CFPS_URL = "https://developers.events/all-cfps.json"
CONFS_URL = "https://raw.githubusercontent.com/tech-conferences/conference-data/main/conferences/{year}/{topic}.json"
USER_AGENT = "web:thedailybrief:1.0 (+https://thedailybrief.dev)"
TIMEOUT = 20
CATEGORIES = {"ai": "AI & agents", "security": "Security & identity", "platform": "Platform & DevOps",
              "leadership": "Leadership"}
DEFAULTS = {
    "horizon_days": 90,
    "closing_days": 7,
    "topics": ["security", "devops", "sre", "leadership", "general", "opensource", "python", "api", "data"],
    "topic_categories": {"security": "security", "devops": "platform", "sre": "platform", "leadership": "leadership"},
    "keywords": {
        "ai": ["AI", "LLM", "LLMs", "GenAI", "agent", "agents", "agentic", "MCP", "ML", "machine learning"],
        "security": ["security", "AppSec", "DevSecOps", "OWASP", "BSides", "DEF CON", "DEFCON", "Black Hat", "cyber",
                     "infosec", "identity", "IAM", "OAuth", "Identiverse"],
        "platform": ["DevOps", "DevOpsDays", "platform", "cloud", "cloud native", "Kubernetes", "KubeCon", "SRE",
                     "SREcon", "observability", "infrastructure"],
        "leadership": ["leadership", "LeadDev", "engineering management", "CTO", "StaffPlus"],
    },
}
TOPIC_RE = re.compile(r"[a-z0-9-]+")
YEAR_RE = re.compile(r"\b(19|20)\d\d\b")

logger = logging.getLogger(__name__)


def _bad(why: str) -> ValueError:
    return ValueError(f"config.yaml: events.{why}")


def _count(value, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise _bad(f"{name} must be a whole number >= 1, got {value!r}")
    return value


def _words(value, name: str) -> List[str]:
    if not isinstance(value, list) or not value or not all(isinstance(v, str) and v.strip() for v in value):
        raise _bad(f"{name} must be a list of non-empty strings, got {value!r}")
    return [v.strip() for v in value]


def settings(config: Dict) -> Optional[Dict]:
    """Validated events settings, or None when config.yaml has no events section."""
    if "events" not in config:
        return None
    raw = config["events"] or {}
    if not isinstance(raw, dict):
        raise ValueError("config.yaml: events must be a mapping")
    unknown = set(raw) - set(DEFAULTS)
    if unknown:
        raise ValueError(f"config.yaml: events has unknown key(s) {', '.join(sorted(map(str, unknown)))}")
    out = {k: _count(raw.get(k, DEFAULTS[k]), k) for k in ("horizon_days", "closing_days")}
    topics = _words(raw.get("topics", DEFAULTS["topics"]), "topics")
    if not all(TOPIC_RE.fullmatch(t) for t in topics):
        raise _bad(f"topics must be conference-data file names like 'security', got {topics!r}")
    out["topics"] = topics
    mapping = raw.get("topic_categories", DEFAULTS["topic_categories"])
    if not isinstance(mapping, dict) or not all(v in CATEGORIES for v in mapping.values()):
        raise _bad(f"topic_categories must map topics to one of {', '.join(CATEGORIES)}, got {mapping!r}")
    out["topic_categories"] = dict(mapping)
    keywords = raw.get("keywords", DEFAULTS["keywords"])
    if not isinstance(keywords, dict) or not set(keywords) <= set(CATEGORIES):
        raise _bad(f"keywords must be a mapping of {', '.join(CATEGORIES)} to word lists")
    out["keywords"] = {cat: _words(words, f"keywords.{cat}") for cat, words in keywords.items()}
    out["patterns"] = {cat: re.compile(r"(?<!\w)(?:" + "|".join(re.escape(w) for w in words) + r")(?!\w)", re.I)
                       for cat, words in out["keywords"].items()}
    return out


def categories(name: str, topic: Optional[str], s: Dict) -> Set[str]:
    cats = {cat for cat, pattern in s["patterns"].items() if pattern.search(name or "")}
    if topic in s["topic_categories"]:
        cats.add(s["topic_categories"][topic])
    return cats


def _ms_date(value) -> Optional[date]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        return datetime.fromtimestamp(value / 1000, tz=timezone.utc).date()
    except (OverflowError, OSError, ValueError):
        return None


def _iso_date(value) -> Optional[date]:
    try:
        return date.fromisoformat(value) if isinstance(value, str) else None
    except ValueError:
        return None


def _web(url) -> Optional[str]:
    return url.strip() if isinstance(url, str) and re.match(r"https?://", url.strip(), re.I) else None


def parse_cfps(data, today: date) -> List[Dict]:
    """Open calls for talks (deadline today or later) from developers.events."""
    if not isinstance(data, list):
        raise ValueError("all-cfps.json is not a list")
    out = []
    for item in data:
        conf = item.get("conf") if isinstance(item, dict) else None
        if not isinstance(conf, dict) or not isinstance(conf.get("name"), str):
            continue
        deadline = _ms_date(item.get("untilDate"))
        dates = [d for d in (_ms_date(v) for v in conf.get("date") or []) if d]
        if not deadline or deadline < today or not dates:
            continue
        location = conf.get("location") if isinstance(conf.get("location"), str) else ""
        out.append({"name": conf["name"].strip(), "url": _web(conf.get("hyperlink")), "cfp_url": _web(item.get("link")),
                    "cfp_end": deadline, "start": dates[0], "end": dates[-1], "year": dates[0].year,
                    "location": location, "online": "online" in location.lower(), "topic": None})
    return out


def parse_conferences(data, topic: str) -> List[Dict]:
    """Conferences from one tech-conferences/conference-data topic file."""
    if not isinstance(data, list):
        raise ValueError("not a list")
    out = []
    for item in data:
        if not isinstance(item, dict) or not isinstance(item.get("name"), str):
            continue
        start, end = _iso_date(item.get("startDate")), _iso_date(item.get("endDate"))
        if not start:
            continue
        place = ", ".join(p for p in (item.get("city"), item.get("country")) if isinstance(p, str) and p)
        online = item.get("online") is True
        out.append({"name": item["name"].strip(), "url": _web(item.get("url")), "cfp_url": _web(item.get("cfpUrl")),
                    "cfp_end": _iso_date(item.get("cfpEndDate")), "start": start, "end": end or start,
                    "year": start.year, "location": place or ("Online" if online else ""), "online": online or not place,
                    "topic": topic})
    return out


def _key(event: Dict) -> Tuple[str, int]:
    name = YEAR_RE.sub(" ", event["name"].lower())
    return " ".join(re.findall(r"[a-z0-9]+", name)), event["year"]


def _merge(found: Iterable[Dict], s: Dict) -> List[Dict]:
    """Relevant events, one per conference: CFP details from developers.events win, the rest fills gaps."""
    merged: Dict[Tuple[str, int], Dict] = {}
    for event in found:
        cats = categories(event["name"], event.get("topic"), s)
        if not cats:
            continue
        key = _key(event)
        if key not in merged:
            merged[key] = dict(event, categories=cats)
            continue
        kept = merged[key]
        kept["categories"] = kept["categories"] | cats
        for field in ("url", "cfp_url", "cfp_end", "location"):
            if not kept.get(field) and event.get(field):
                kept[field] = event[field]
    return list(merged.values())


def _get_json(url: str, get: Callable):
    response = get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
    if response.status_code != 200:
        raise ValueError(f"HTTP {response.status_code}")
    return response.json()


def collect(config: Dict, now: datetime, get: Callable = requests.get) -> Tuple[Dict[str, List[Dict]], Dict]:
    """{"cfps": open calls by deadline, "upcoming": conferences in the next horizon_days by start} and how many
    entries each source gave (None = it failed)."""
    s, today = settings(config), now.date()
    found, counts = [], {}
    try:
        cfps = parse_cfps(_get_json(CFPS_URL, get), today)
        counts["developers.events"] = len(cfps)
        found += cfps
    except (requests.RequestException, ValueError) as e:
        logger.warning(f"Events: developers.events failed ({e.__class__.__name__}: {e})")
        counts["developers.events"] = None
    conference_count, failed, files = 0, 0, 0
    for year in (today.year, today.year + 1):
        for topic in s["topics"]:
            files += 1
            try:
                confs = parse_conferences(_get_json(CONFS_URL.format(year=year, topic=topic), get), topic)
            except (requests.RequestException, ValueError) as e:
                logger.warning(f"Events: conference-data {year}/{topic} failed ({e.__class__.__name__}: {e})")
                failed += 1
                continue
            conference_count += len(confs)
            found += confs
    counts["conference-data"] = None if failed == files else conference_count

    events = _merge(found, s)
    for e in events:
        e["categories"] = sorted(e["categories"])
        e["days_left"] = (e["cfp_end"] - today).days if e.get("cfp_end") else None
        e["closing_soon"] = e["days_left"] is not None and e["days_left"] <= s["closing_days"]
    open_cfps = [e for e in events if e.get("cfp_url") and e.get("cfp_end") and today <= e["cfp_end"] <= e["end"]]
    open_cfps.sort(key=lambda e: (e["cfp_end"], e["name"]))
    horizon = today + timedelta(days=s["horizon_days"])
    upcoming = [e for e in events if e["end"] >= today and e["start"] <= horizon]
    upcoming.sort(key=lambda e: (e["start"], e["name"]))
    return {"cfps": open_cfps, "upcoming": upcoming}, counts


def _escape(text: str) -> str:
    return (text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,")
            .replace("\r\n", "\\n").replace("\n", "\\n"))


def _fold(line: str) -> List[str]:
    """Split a content line into pieces of at most 75 octets (continuations start with a space)."""
    pieces, current, limit = [], b"", 75
    for ch in line:
        encoded = ch.encode("utf-8")
        if len(current) + len(encoded) > limit:
            pieces.append(current.decode("utf-8"))
            current, limit = b"", 74
        current += encoded
    pieces.append(current.decode("utf-8"))
    return [pieces[0]] + [" " + p for p in pieces[1:]]


def _date_range(start: date, end: date) -> str:
    if start == end:
        return f"{start:%b} {start.day}, {start.year}"
    if (start.year, start.month) == (end.year, end.month):
        return f"{start:%b} {start.day}–{end.day}, {start.year}"
    if start.year == end.year:
        return f"{start:%b} {start.day} – {end:%b} {end.day}, {start.year}"
    return f"{start:%b} {start.day}, {start.year} – {end:%b} {end.day}, {end.year}"


def _uid(event: Dict) -> str:
    slug = "-".join(_key(event)[0].split())[:60].strip("-")
    if not slug:
        slug = hashlib.sha1(event["name"].encode("utf-8")).hexdigest()[:12]
    return f"cfp-{slug}-{event['year']}@thedailybrief.dev"


def ics(cfps: List[Dict], now: datetime) -> str:
    """An RFC 5545 calendar with one all-day event on each open CFP's deadline."""
    stamp = now.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//thedailybrief.dev//CFP radar//EN", "CALSCALE:GREGORIAN",
             "METHOD:PUBLISH", "X-WR-CALNAME:Calls for talks closing (The Daily Brief)"]
    for e in cfps:
        where = e.get("location") or ("Online" if e.get("online") else "")
        details = [f"Conference: {_date_range(e['start'], e['end'])}"] + ([where] if where else []) \
            + ([e["url"]] if e.get("url") else [])
        lines += ["BEGIN:VEVENT", f"UID:{_uid(e)}", f"DTSTAMP:{stamp}",
                  f"DTSTART;VALUE=DATE:{e['cfp_end']:%Y%m%d}",
                  f"DTEND;VALUE=DATE:{e['cfp_end'] + timedelta(days=1):%Y%m%d}",
                  f"SUMMARY:{_escape('CFP closes: ' + e['name'])}",
                  f"DESCRIPTION:{_escape(chr(10).join(details))}"]
        if e.get("cfp_url"):
            lines.append(f"URL:{e['cfp_url']}")
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return "".join(piece + "\r\n" for line in lines for piece in _fold(line))
