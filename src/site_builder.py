"""
Static site renderer: today's feed plus Mark's writing, as plain HTML.
"""

import re
import shutil
from datetime import datetime
from email.utils import format_datetime
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlparse

from jinja2 import Environment, FileSystemLoader

SITE_URL = "https://markmishaev76.github.io/ai-daily-content-collector/"
WRITING_LIMIT = 3
EXCERPT_LIMIT = 300
CARDS_PER_SECTION = 3
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


def anchor_id(topic: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", topic.lower()).strip("-")


def safe_image(url: Optional[str]) -> Optional[str]:
    link = safe_link(url or "")
    return link if link and urlparse(link).scheme.lower() == "https" else None


def _sections(feed: Dict[str, List[Dict]]) -> List[Dict]:
    sections = []
    for index, (name, articles) in enumerate(feed.items()):
        if not articles:
            continue
        sections.append({
            "name": name,
            "id": anchor_id(name),
            "color": PALETTE[index % len(PALETTE)],
            "articles": [{
                "title": a.get("title") or "Untitled",
                "link": safe_link(a.get("link", "")),
                "excerpt": excerpt(a.get("summary", "")),
                "source": a.get("source", ""),
                "date": a["published"].strftime("%b %d") if a.get("published") else None,
                "image": safe_image(a.get("image")),
            } for a in sorted(articles, key=lambda a: a.get("published") is None)],
        })
    return sections


def pick_lead(sections: List[Dict]) -> Optional[Dict]:
    """Take the first article with an image, in section order, out of its section."""
    for section in sections:
        for i, item in enumerate(section["articles"]):
            if item["image"]:
                del section["articles"][i]
                return dict(item, section=section["name"], section_id=section["id"], color=section["color"])
    return None


def _split_cards(articles: List[Dict]):
    """Cards prefer articles with pictures, topped up by rank; both keep rank order."""
    with_image = [i for i, a in enumerate(articles) if a["image"]][:CARDS_PER_SECTION]
    without = [i for i, a in enumerate(articles) if not a["image"]]
    chosen = set(with_image + without[:CARDS_PER_SECTION - len(with_image)])
    cards = [a for i, a in enumerate(articles) if i in chosen]
    more = [a for i, a in enumerate(articles) if i not in chosen]
    return cards, more


def _magazine(feed: Dict[str, List[Dict]]) -> Dict:
    sections = _sections(feed)
    lead = pick_lead(sections)
    sections = [s for s in sections if s["articles"]]
    for s in sections:
        s["cards"], s["more"] = _split_cards(s["articles"])
    return {"lead": lead, "sections": sections}


def _sorted_posts(posts: List[Dict]) -> List[Dict]:
    dated = sorted((p for p in posts if p.get("date")), key=lambda p: p["date"], reverse=True)
    return dated + [p for p in posts if not p.get("date")]


def _post_href(post: Dict, root: str) -> str:
    return post["url"] if post["source"] == "medium" else root + post["url"]


def _rss_date(post: Dict) -> Optional[str]:
    if not post.get("date"):
        return None
    return format_datetime(datetime.strptime(post["date"], "%Y-%m-%d").replace(hour=12))


def build(feed: Dict[str, List[Dict]], posts: List[Dict], about_html: str,
          out_dir: Path, now: datetime) -> None:
    env = Environment(loader=FileSystemLoader(SITE_DIR / "templates"), autoescape=True,
                      trim_blocks=True, lstrip_blocks=True)
    env.globals.update(post_href=_post_href, today=now.strftime("%A, %B %d, %Y"),
                       updated=now.strftime("%H:%M UTC"))

    all_posts = _sorted_posts(posts)
    common = {"writing": all_posts[:WRITING_LIMIT]}

    def write(rel: str, template: str, **ctx) -> None:
        path = out_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(env.get_template(template).render(**common, **ctx))

    write("index.html", "index.html", root="", page="feed", **_magazine(feed))
    write("blog/index.html", "blog.html", root="../", page="blog", posts=all_posts)
    for post in all_posts:
        if post["source"] == "local":
            write(f"blog/{post['slug']}/index.html", "post.html", root="../../", page="blog", post=post)
    write("about/index.html", "about.html", root="../", page="about", about_html=about_html)
    write("feed.xml", "feed.xml", site_url=SITE_URL, built=format_datetime(now),
          posts=[dict(p, link=p["url"] if p["source"] == "medium" else SITE_URL + p["url"],
                      rss_date=_rss_date(p)) for p in all_posts])

    shutil.copytree(SITE_DIR / "static", out_dir / "static", dirs_exist_ok=True)
