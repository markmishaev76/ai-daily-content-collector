"""
Static site renderer: today's feed plus Mark's writing, as plain HTML.
"""

import hashlib
import re
import shutil
from datetime import date, datetime, timedelta
from email.utils import format_datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional
from urllib.parse import urlparse

from jinja2 import Environment, FileSystemLoader

from src import briefs as brief_store
from src import events as event_radar
from src import weeks as week_store
from src.hn import HN_BOILERPLATE, hn_counts, is_hn_item
from src.learn import VIDEO_ID

SITE_URL = "https://thedailybrief.dev/"
CF_ANALYTICS_TOKEN = "753e85ce1c8b4659818c074e30218583"
WRITING_LIMIT = 3
EXCERPT_LIMIT = 300
CARDS_PER_SECTION = 3
LEAD_COLOR = "#5a4fcf"
NEUTRAL_COLOR = "#7a7a85"
PULSE_COLOR = "#e8590c"
LEARN_COLOR = "#c92a2a"
LEARN_TEASER = 3
EVENTS_COLOR = "#2b8a3e"
CFP_STRIP = 3
LEAD_ID_LABELS = 2
PALETTE = ["#5a4fcf", "#ad3a8a", "#1f9d8b", "#d6456b", "#e07a1f", "#3577d4", "#7a8b2d", "#5b6270"]

SITE_DIR = Path(__file__).resolve().parent.parent / "site"


def safe_link(url: str) -> Optional[str]:
    """Return url only if it is an http(s) link."""
    if not url:
        return None
    try:
        scheme = urlparse(url.strip()).scheme.lower()
    except ValueError:
        return None
    return url.strip() if scheme in ("http", "https") else None


def excerpt(text: str, limit: int = EXCERPT_LIMIT) -> str:
    text = " ".join((text or "").split())
    if len(text) <= limit:
        return text
    cut = text[:limit - 1].rsplit(" ", 1)[0]
    return cut + "…"


FEED_SUFFIX = re.compile(r"\s*[-–—|:]\s*(blog|news|newest\b.*|front ?page\b.*|rss|feed|latest\b.*|all posts)\s*$", re.I)
TAG_SUFFIX = re.compile(r"\s*:\s*[a-z0-9][a-z0-9-]*$")
WEBLOG_SUFFIX = re.compile(r"['’]s (weblog|blog)$", re.I)


def _domain(url: str) -> str:
    try:
        host = urlparse((url or "").strip()).hostname or ""
    except ValueError:
        return ""
    return host.lower().removeprefix("www.")


def clean_source(name: str) -> str:
    """Short publisher name from a feed title: drop ' - Blog', ': <tag>', ' - Newest...' and "'s Weblog"."""
    text = " ".join((name or "").split())
    if re.match(r"https?://", text, re.I):
        return _domain(text)
    if text.lower().startswith("hacker news"):
        return "Hacker News"
    text = TAG_SUFFIX.sub("", FEED_SUFFIX.sub("", text))
    return WEBLOG_SUFFIX.sub("", text) or " ".join((name or "").split())


def display_source(article: Dict) -> str:
    """Publisher shown on the page; Hacker News items show the linked site, e.g. 'github.com via Hacker News'."""
    if is_hn_item(article):
        host = _domain(article.get("link"))
        return f"{host} via Hacker News" if host and host != "news.ycombinator.com" else "Hacker News"
    return clean_source(article.get("source") or "")


def _hn_line(article: Dict) -> Optional[str]:
    if not is_hn_item(article):
        return None
    points, comments = hn_counts(article.get("summary"))
    return f"{points} points · {comments} comments"


def _summary(summary: str, description: Optional[str], hn_line: Optional[str]) -> str:
    """Excerpt text: Hacker News boilerplate becomes the page description, else the points line."""
    if HN_BOILERPLATE.search(summary or ""):
        return excerpt(description or hn_line or "")
    return excerpt(summary or description or "")


def anchor_id(topic: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", topic.lower()).strip("-")


def safe_image(url: Optional[str]) -> Optional[str]:
    link = safe_link(url or "")
    return link if link and urlparse(link).scheme.lower() == "https" else None


def _item(a: Dict) -> Dict:
    hn_line = _hn_line(a)
    return {
        "title": a.get("title") or "Untitled",
        "link": safe_link(a.get("link", "")),
        "excerpt": _summary(a.get("summary", ""), a.get("og_description"), hn_line),
        "source": display_source(a),
        "date": a["published"].strftime("%b %d") if a.get("published") else None,
        "image": safe_image(a.get("image")),
        "icon": safe_image(a.get("icon")),
        "domain": _domain(a.get("link")),
        "hn": hn_line,
    }


def _sections(feed: Dict[str, List[Dict]]) -> List[Dict]:
    sections = []
    for index, (name, articles) in enumerate(feed.items()):
        if not articles:
            continue
        sections.append({
            "name": name,
            "id": anchor_id(name),
            "color": PALETTE[index % len(PALETTE)],
            "articles": [_item(a) for a in sorted(articles, key=lambda a: a.get("published") is None)],
        })
    return sections


def age_label(hours: Optional[float]) -> Optional[str]:
    if hours is None:
        return None
    if hours < 1:
        return "under 1h ago"
    if hours < 24:
        return f"{int(hours)}h ago"
    return f"{int(hours // 24)}d ago"


def _lead(story, feed: Dict[str, List[Dict]]) -> Dict:
    names = list(feed)
    color = PALETTE[names.index(story.section) % len(PALETTE)] if story.section in names else LEAD_COLOR
    labels = []
    if story.coverage > 1:
        labels.append(f"{story.coverage} sources")
    labels += story.ids[:LEAD_ID_LABELS]
    if story.section:
        labels.append(story.section)
    if age_label(story.age_hours):
        labels.append(age_label(story.age_hours))
    return {
        "title": story.title or "Untitled",
        "link": safe_link(story.link),
        "excerpt": _summary(story.summary, story.description, None),
        "source": display_source({"source": story.source, "link": story.link, "feed": story.feed}),
        "date": story.published.strftime("%b %d") if story.published else None,
        "image": safe_image(story.image),
        "image_credit": story.image_credit if safe_image(story.image) else None,
        "section": story.section,
        "color": color,
        "pinned": story.pinned,
        "note": story.note,
        "labels": labels,
        "also": [{"name": name, "link": safe_link(link)} for name, link in story.also if safe_link(link)],
    }


def compact(n: int) -> str:
    """1234 -> '1.2k', 1250000 -> '1.2M'."""
    for size, suffix in ((1_000_000, "M"), (1_000, "k")):
        if n >= size:
            return f"{n / size:.1f}".rstrip("0").rstrip(".") + suffix
    return str(n)


def _pulse(items: Optional[List[Dict]], now: datetime) -> List[Dict]:
    out = []
    for item in items or []:
        hours = (now - item["created"]).total_seconds() / 3600
        link = safe_link(item.get("link") or "")
        also = [{"source": a["source"], "thread": safe_link(a.get("thread") or "")} for a in item.get("also") or []]
        out.append({
            "title": item["title"],
            "thread": safe_link(item.get("thread") or ""),
            "link": link,
            "link_domain": _domain(link),
            "source": item["source"],
            "domain": _domain(link) or item["source"],
            "meta": f"{item['source']} · {compact(item['points'])} {item['unit']} · {compact(item['comments'])} comments"
                    + (f" · {age_label(hours)}" if age_label(hours) else ""),
            "also": [a for a in also if a["thread"]],
            "image": safe_image(item.get("image")),
            "icon": safe_image(item.get("icon")),
        })
    return out


def _pulse_sources(items: List[Dict]) -> str:
    """'Hacker News, Lobsters and Reddit' in first-seen order, every subreddit counted as Reddit."""
    names = list(dict.fromkeys("Reddit" if (i.get("source") or "").startswith("r/") else i.get("source") or ""
                               for i in items))
    return " and ".join(filter(None, [", ".join(names[:-1]), names[-1]])) if names else ""


def _videos(videos: List[Dict], now: datetime) -> List[Dict]:
    """Videos safe to render: a strict YouTube id, links and thumbnail built from it."""
    out = []
    for v in videos:
        vid = v.get("id") or ""
        if not isinstance(vid, str) or not VIDEO_ID.fullmatch(vid):
            continue
        hours = (now - v["published"]).total_seconds() / 3600
        out.append({
            "id": vid,
            "title": v.get("title") or "Untitled",
            "link": f"https://www.youtube.com/watch?v={vid}",
            "image": f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg",
            "source": v.get("channel") or "",
            "domain": v.get("channel") or "",
            "meta": f"{v.get('channel')} · {compact(v['views'])} views · {compact(int(v['per_day']))}/day"
                    + (f" · {age_label(hours)}" if age_label(hours) else ""),
        })
    return out


def _learn(learn: Optional[Dict], now: datetime) -> Optional[Dict]:
    if learn is None:
        return None
    channels = [{"name": c["name"], "url": safe_link(c.get("url") or ""), "videos": _videos(c.get("videos") or [], now)}
                for c in learn.get("channels") or []]
    return {"top": _videos(learn.get("top") or [], now), "channels": channels, "days": learn.get("days")}


def _event(e: Dict) -> Dict:
    """An event ready for the page: validated link, labels and plain-text dates."""
    link = safe_link(e.get("cfp_url") or "") or safe_link(e.get("url") or "")
    days = e.get("days_left")
    return {"name": e.get("name") or "Untitled", "link": link,
            "deadline": f"{e['cfp_end']:%b} {e['cfp_end'].day}" if e.get("cfp_end") else None,
            "days_left_label": "closes today" if days == 0 else "1 day left" if days == 1 else f"{days} days left",
            "closing_soon": bool(e.get("closing_soon")), "dates": event_radar._date_range(e["start"], e["end"]),
            "location": e.get("location") or "", "online": bool(e.get("online")),
            "cats": " ".join(e.get("categories") or []),
            "labels": [event_radar.CATEGORIES[c] for c in e.get("categories") or [] if c in event_radar.CATEGORIES]}


def _events(events: Optional[Dict]) -> Optional[Dict]:
    if events is None:
        return None
    cfps = [_event(e) for e in events.get("cfps") or []]
    upcoming = [_event(dict(e, cfp_url=None)) for e in events.get("upcoming") or []]
    return {"cfps": [e for e in cfps if e["link"]], "upcoming": upcoming}


def _split_cards(articles: List[Dict]):
    """Cards prefer articles with pictures, topped up by rank; both keep rank order."""
    with_image = [i for i, a in enumerate(articles) if a["image"]][:CARDS_PER_SECTION]
    without = [i for i, a in enumerate(articles) if not a["image"]]
    chosen = set(with_image + without[:CARDS_PER_SECTION - len(with_image)])
    cards = [a for i, a in enumerate(articles) if i in chosen]
    more = [a for i, a in enumerate(articles) if i not in chosen]
    return cards, more


def _magazine(feed: Dict[str, List[Dict]], story=None) -> Dict:
    sections = _sections(feed)
    lead = _lead(story, feed) if story else None
    if lead and lead["link"]:
        for s in sections:
            s["articles"] = [a for a in s["articles"] if a["link"] != lead["link"]]
    sections = [s for s in sections if s["articles"]]
    for s in sections:
        s["cards"], s["more"] = _split_cards(s["articles"])
    return {"lead": lead, "sections": sections}


def brief_snapshot(feed: Dict[str, List[Dict]], story, pulse: Optional[List[Dict]], now: datetime,
                   take: Optional[str] = None) -> Dict:
    """Today's brief as plain JSON data: the lead, The Pulse and each section's cards and headline rows, with
    links and images already validated. Colors and anchors are not stored; they come from config at render time."""
    magazine = _magazine(feed, story)
    lead = {k: v for k, v in magazine["lead"].items() if k != "color"} if magazine["lead"] else None
    if lead and take:
        lead["take"] = take
    signals = {}
    for scored in getattr(story, "scored", None) or []:
        for member in scored.members:
            signals.setdefault((member.get("link") or "").strip(), (round(scored.score, 3), scored.coverage))
    for section in magazine["sections"]:
        for item in section["cards"] + section["more"]:
            if (item.get("link") or "") in signals:
                item["score"], item["coverage"] = signals[item["link"]]
    return {"date": now.date().isoformat(), "lead": lead, "pulse": _pulse(pulse, now),
            "sections": [{"name": s["name"], "cards": s["cards"], "more": s["more"]} for s in magazine["sections"]]}


def _text(value) -> str:
    return value if isinstance(value, str) else ""


def _clean(item: Dict, links=("link",), images=("image", "icon")) -> Dict:
    """A snapshot item with its links and images validated again (the JSON is committed to the repo)."""
    out = dict(item, title=_text(item.get("title")) or "Untitled")
    for key in links:
        out[key] = safe_link(_text(item.get(key)))
    for key in images:
        out[key] = safe_image(_text(item.get(key)))
    return out


def _brief_page(snap: Dict, names: List[str], take: Optional[str] = None, always: Iterable[str] = (),
                empty_link: Optional[Dict] = None) -> Dict:
    """Template context for a snapshot; sections renamed since it was saved get a neutral color. `take`
    (from takes.yaml) wins over the take saved in the snapshot."""
    def color(name: str, missing: str) -> str:
        return PALETTE[names.index(name) % len(PALETTE)] if name in names else missing

    sections = [{"name": s["name"], "id": anchor_id(s["name"]), "color": color(s["name"], NEUTRAL_COLOR),
                 "cards": [_clean(i) for i in s["cards"]], "more": [_clean(i) for i in s["more"]]}
                for s in snap["sections"]]
    present = {s["name"] for s in sections}
    sections += [{"name": n, "id": anchor_id(n), "color": color(n, NEUTRAL_COLOR), "cards": [], "more": [],
                  "empty": empty_link or {}} for n in always if n not in present]
    sections.sort(key=lambda s: names.index(s["name"]) if s["name"] in names else len(names))
    lead = None
    if snap.get("lead"):
        raw = snap["lead"]
        lead = _clean(raw, images=("image",))
        lead["image_credit"] = _text(raw.get("image_credit")) or None if lead["image"] else None
        lead["color"] = color(raw.get("section"), LEAD_COLOR)
        lead["labels"] = [label for label in raw.get("labels") or [] if isinstance(label, str)]
        lead["take"] = take or _text(raw.get("take")) or None
        lead["also"] = [{"name": _text(a.get("name")), "link": safe_link(_text(a.get("link")))}
                        for a in raw.get("also") or [] if isinstance(a, dict) and safe_link(_text(a.get("link")))]
    pulse = []
    for raw in snap["pulse"]:
        item = _clean(raw, links=("thread", "link"))
        item["also"] = [{"source": _text(a.get("source")), "thread": safe_link(_text(a.get("thread")))}
                        for a in raw.get("also") or [] if isinstance(a, dict) and safe_link(_text(a.get("thread")))]
        pulse.append(item)
    return {"lead": lead, "sections": sections, "pulse": pulse, "pulse_sources": _pulse_sources(pulse),
            "reconstructed": snap.get("reconstructed") is True}


def _empty_link(day: date, today: date, available: set, root: str, week: bool) -> Dict:
    """Where an always-on section with nothing new points: the latest brief before `day`, else the week page."""
    earlier = sorted(d for d in available if d < day.isoformat())
    if earlier:
        label = "See the last brief →" if day == today else "See the brief before →"
        return {"href": f"{root}brief/{earlier[-1]}/", "label": label}
    return {"href": f"{root}week/", "label": "See the week in review →"} if week else {}


def _day_label(day: date) -> str:
    return f"{day:%a} {day.day}"


def _day_href(day: date, today: date, root: str) -> str:
    return (root or "./") if day == today else f"{root}brief/{day.isoformat()}/"


def _days(today: date, available: set, current: date, root: str) -> List[Dict]:
    """The last seven days for the strip; days without a saved brief have no link."""
    return [{"label": _day_label(d), "active": d == current,
             "href": _day_href(d, today, root) if d.isoformat() in available else None}
            for d in brief_store.window(today)]


def _pager(today: date, available: set, current: date, root: str) -> Dict:
    """The nearest earlier and later days that have a brief (today's links to the front page)."""
    kept = sorted(date.fromisoformat(d) for d in available)
    earlier = [d for d in kept if d < current]
    later = [d for d in kept if d > current]
    return {"prev": {"label": _day_label(earlier[-1]), "href": _day_href(earlier[-1], today, root)} if earlier else None,
            "next": {"label": _day_label(later[0]), "href": _day_href(later[0], today, root)} if later else None}


def _week_page(week: Dict, names: List[str], base: str, ids: List[str]) -> Dict:
    """Template context for a saved week (or the preview); links checked again, colors from config."""
    def color(name) -> str:
        return PALETTE[names.index(name) % len(PALETTE)] if name in names else NEUTRAL_COLOR

    start, end = date.fromisoformat(week["start"]), date.fromisoformat(week["end"])
    days = []
    for d in week["days"]:
        lead = d.get("lead") if isinstance(d.get("lead"), dict) else None
        days.append({"label": week_store.label(date.fromisoformat(d["date"])), "lead": {
            "title": _text(lead.get("title")) or "Untitled", "link": safe_link(_text(lead.get("link"))),
            "source": _text(lead.get("source")), "section": _text(lead.get("section")),
            "color": color(lead.get("section")), "take": _text(lead.get("take")) or None} if lead else None})
    top = [{"title": _text(t.get("title")) or "Untitled", "link": safe_link(_text(t.get("link"))),
            "source": _text(t.get("source")), "section": _text(t.get("section")), "color": color(t.get("section")),
            "day": week_store.label(date.fromisoformat(t["date"])) if _text(t.get("date")) else ""}
           for t in week["top"]]
    url = SITE_URL + ("week/" if week.get("preview") else f"week/{week['week']}/")
    clean = dict(week, days=[{"date": d["date"], "lead": dict(d["lead"], link=x["lead"]["link"]) if x["lead"] else None}
                             for d, x in zip(week["days"], days)],
                 top=[dict(t, link=x["link"]) for t, x in zip(week["top"], top)])
    index = ids.index(week["week"]) if week["week"] in ids and not week.get("preview") else None
    nav = {}
    if index is not None:
        for key, other in (("prev", index - 1), ("next", index + 1)):
            if 0 <= other < len(ids):
                w = ids[other]
                nav[key] = {"href": f"{base}{w}/", "label": week_store.short_span(*_week_bounds(w))}
    title = "Week so far" if week.get("preview") else "Week in review"
    return {"heading": f"{title} · {week_store.span(start, end)}", "preview": bool(week.get("preview")),
            "days": days, "top": top, "text": week_store.plain_text(clean, url), "week_nav": nav, "page_url": url}


def _week_bounds(wid: str):
    year, week = wid.split("-W")
    monday = date.fromisocalendar(int(year), int(week), 1)
    return monday, monday + timedelta(days=6)


def _sorted_posts(posts: List[Dict]) -> List[Dict]:
    dated = sorted((p for p in posts if p.get("date")), key=lambda p: p["date"], reverse=True)
    return dated + [p for p in posts if not p.get("date")]


def _asset_url(root: str, name: str) -> str:
    """URL of a file in site/static with a content hash, so browsers refetch it when it changes."""
    digest = hashlib.sha256((SITE_DIR / "static" / name).read_bytes()).hexdigest()[:10]
    return f"{root}static/{name}?v={digest}"


def _post_href(post: Dict, root: str) -> str:
    return post["url"] if post["source"] == "medium" else root + post["url"]


def _rss_date(post: Dict) -> Optional[str]:
    if not post.get("date"):
        return None
    return format_datetime(datetime.strptime(post["date"], "%Y-%m-%d").replace(hour=12))


def build(feed: Dict[str, List[Dict]], posts: List[Dict], about_html: str,
          out_dir: Path, now: datetime, story=None, pulse: Optional[List[Dict]] = None,
          learn: Optional[Dict] = None, briefs: Optional[Dict[str, Dict]] = None, always_show: Iterable[str] = (),
          takes: Optional[Dict[str, str]] = None, events: Optional[Dict] = None,
          events_horizon: int = 90, today_brief: Optional[Dict] = None, weeks: Optional[Dict[str, Dict]] = None,
          week_preview: Optional[Dict] = None) -> Dict:
    """Write the site and return today's brief snapshot. `story` is a src.story.Story for the lead, or None for
    no lead; `pulse` is src.pulse.collect's items, or None/[] to hide The Pulse; `learn` is src.learn.collect's
    videos (empty lists when unavailable), or None for no Learn page; `briefs` maps YYYY-MM-DD to earlier
    snapshots (src.briefs.load), each rendered at /brief/<date>/ like today's; `always_show` sections render
    even when empty, with a link to an earlier brief; `takes` is src.takes.load's
    date -> Mark's take, shown under that day's lead; `events` is src.events.collect's data (empty lists when
    unavailable), or None for no Events page; `today_brief` is today's snapshot if already made
    (brief_snapshot); `weeks` are the saved weeks (src.weeks.load) and `week_preview` the week so far, shown at
    /week/ only when no week is saved."""
    env = Environment(loader=FileSystemLoader(SITE_DIR / "templates"), autoescape=True,
                      trim_blocks=True, lstrip_blocks=True)
    env.globals.update(post_href=_post_href, today=now.strftime("%A, %B %d, %Y"),
                       updated=now.strftime("%H:%M UTC"), site_url=SITE_URL,
                       cf_analytics_token=CF_ANALYTICS_TOKEN, learn_page=learn is not None,
                       events_page=events is not None,
                       asset=_asset_url)

    all_posts = _sorted_posts(posts)
    common = {"writing": all_posts[:WRITING_LIMIT]}

    def write(rel: str, template: str, **ctx) -> None:
        path = out_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        page_url = SITE_URL + rel.removesuffix("index.html")
        path.write_text(env.get_template(template).render(**{**common, "page_url": page_url, **ctx}))

    names, today, takes = list(feed), now.date(), takes or {}
    snap = today_brief or brief_snapshot(feed, story, pulse, now, take=takes.get(now.date().isoformat()))
    saved_weeks = dict(sorted((weeks or {}).items()))
    latest_week = week_store.latest(saved_weeks, week_preview)
    window = {d.isoformat() for d in brief_store.window(today)}
    pages = {d: b for d, b in (briefs or {}).items() if d in window}
    pages[today.isoformat()] = snap
    available = set(pages)
    videos = _learn(learn, now)
    radar = _events(events)
    write("index.html", "index.html", root="", page="feed", heading=f"Today · {now:%A, %B %d, %Y}",
          days=_days(today, available, today, ""),
          **_brief_page(snap, names, takes.get(today.isoformat()), always_show,
                        _empty_link(today, today, available, "", latest_week is not None)),
          pulse_color=PULSE_COLOR,
          learn_teaser=videos["top"][:LEARN_TEASER] if videos else [], learn_color=LEARN_COLOR,
          cfp_strip=radar["cfps"][:CFP_STRIP] if radar else [], events_color=EVENTS_COLOR,
          week_link=latest_week is not None)
    for iso, page in sorted(pages.items()):
        day, root = date.fromisoformat(iso), "../../"
        label = f"Brief · {day:%A, %B %d, %Y}"
        write(f"brief/{iso}/index.html", "index.html", root=root, page="feed", heading=label, title_prefix=label,
              days=_days(today, available, day, root), pager=_pager(today, available, day, root),
              is_today=day == today, pulse_color=PULSE_COLOR, writing=[],
              **_brief_page(page, names, takes.get(iso), always_show,
                            _empty_link(day, today, available, root, latest_week is not None)),
              learn_teaser=[], learn_color=LEARN_COLOR, week_link=latest_week is not None)
    write("404.html", "404.html", root="/", page="")
    ids = list(saved_weeks)
    for wid, week in saved_weeks.items():
        write(f"week/{wid}/index.html", "week.html", root="../../", page="week", **_week_page(week, names, "../", ids))
    if latest_week is not None:
        write("week/index.html", "week.html", root="../", page="week", **_week_page(latest_week, names, "", ids))
    if radar is not None:
        ics_url = SITE_URL + "events/cfps.ics"
        write("events/index.html", "events.html", root="../", page="events", events=radar, events_color=EVENTS_COLOR,
              horizon_days=events_horizon, ics_url=ics_url, webcal_url="webcal://" + ics_url.split("://", 1)[1],
              filters=[{"id": "all", "label": "All"}] + [{"id": k, "label": v} for k, v in event_radar.CATEGORIES.items()])
        (out_dir / "events" / "cfps.ics").write_bytes(event_radar.ics(events.get("cfps") or [], now).encode("utf-8"))
    if videos is not None:
        write("learn/index.html", "learn.html", root="../", page="learn", learn=videos, learn_color=LEARN_COLOR)
    write("blog/index.html", "blog.html", root="../", page="blog", posts=all_posts)
    for post in all_posts:
        if post["source"] == "local":
            write(f"blog/{post['slug']}/index.html", "post.html", root="../../", page="blog", post=post)
    write("about/index.html", "about.html", root="../", page="about", about_html=about_html)
    write("feed.xml", "feed.xml", site_url=SITE_URL, built=format_datetime(now),
          posts=[dict(p, link=p["url"] if p["source"] == "medium" else SITE_URL + p["url"],
                      rss_date=_rss_date(p)) for p in all_posts])

    shutil.copytree(SITE_DIR / "static", out_dir / "static", dirs_exist_ok=True)
    return snap
