"""
Hacker News items as hnrss delivers them: detection, points and comments.
"""

import re
from typing import Dict, Optional, Tuple
from urllib.parse import urlparse

HN_BOILERPLATE = re.compile(r"(Article URL:|Comments URL:|Points:\s*\d|#\s*Comments:)")
HN_POINTS = re.compile(r"\bPoints:\s*(\d+)")
HN_COMMENTS = re.compile(r"#\s*Comments:\s*(\d+)")
HN_HOSTS = ("hnrss.org", "news.ycombinator.com")


def hn_counts(summary: Optional[str]) -> Tuple[int, int]:
    """(points, comments) from an hnrss summary ('Points: N # Comments: M'), zeros if absent."""
    text = summary or ""
    counts = []
    for pattern in (HN_POINTS, HN_COMMENTS):
        match = pattern.search(text)
        counts.append(int(match.group(1)) if match else 0)
    return counts[0], counts[1]


def _host(url: str) -> str:
    try:
        return (urlparse((url or "").strip()).hostname or "").lower()
    except ValueError:
        return ""


def is_hn_item(article: Dict) -> bool:
    """Came from Hacker News: an hnrss feed or a news.ycombinator.com link."""
    hosts = {_host(article.get("feed")), _host(article.get("link"))}
    return any(h == base or h.endswith("." + base) for h in hosts for base in HN_HOSTS)


def min_points(config: Dict, key: str) -> int:
    """A whole-number points threshold from config.yaml's story section (0 if unset)."""
    value = (config.get("story") or {}).get(key, 0)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"config.yaml: story.{key} must be a whole number >= 0, got {value!r}")
    return value
