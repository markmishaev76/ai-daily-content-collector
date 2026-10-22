"""
Medium posts: fetch the author feed and keep a saved copy that outlives
Medium's 10-item feed window.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

import feedparser
import requests

logger = logging.getLogger(__name__)


def fetch_medium_posts(url: str) -> Optional[List[Dict]]:
    """Return posts from a Medium feed, or None if the feed can't be read."""
    try:
        response = requests.get(url, timeout=15, headers={
            'User-Agent': 'Mozilla/5.0 (compatible; DailyBrief/1.0)'
        })
        response.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"Error fetching Medium feed {url}: {e}")
        return None

    feed = feedparser.parse(response.content)
    if feed.bozo and not feed.entries:
        logger.error(f"Medium feed {url} could not be parsed: {feed.bozo_exception}")
        return None

    posts = []
    for entry in feed.entries:
        link = entry.get('link')
        if not link:
            continue
        published = entry.get('published_parsed')
        posts.append({
            'title': entry.get('title', 'Untitled'),
            'url': link.split('?')[0],
            'date': f"{published.tm_year:04d}-{published.tm_mon:02d}-{published.tm_mday:02d}" if published else None,
            'source': 'medium',
        })
    return posts


def merge_posts(saved: List[Dict], fetched: List[Dict]) -> List[Dict]:
    """Union by URL, fetched entries win, newest first, undated last."""
    by_url = {p['url']: p for p in saved}
    by_url.update({p['url']: p for p in fetched})
    dated = sorted((p for p in by_url.values() if p.get('date')), key=lambda p: p['date'], reverse=True)
    undated = [p for p in by_url.values() if not p.get('date')]
    return dated + undated


def load_saved(path: Path) -> List[Dict]:
    if not path.exists():
        return []
    return json.loads(path.read_text())


def save(path: Path, posts: List[Dict]) -> bool:
    """Write posts; return True only if the file content changed."""
    content = json.dumps(posts, indent=2, ensure_ascii=False) + "\n"
    if path.exists() and path.read_text() == content:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return True
