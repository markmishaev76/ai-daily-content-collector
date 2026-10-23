"""
Page metadata for rendered articles: og:image, description and site icon.

Only the <head> of each linked page is read (MAX_BYTES cap, TIMEOUT per
request, WORKERS threads). Results, misses included, are cached in
data/og-cache.json: hits are reused for CACHE_DAYS, misses for MISS_DAYS.
A failed fetch is a miss, never a build failure. Pages without an icon link
fall back to the site's own /favicon.ico (no third-party favicon service, so
visitors' browsers only contact the publisher, as they do for its images).
"""

import ipaddress
import json
import logging
import socket
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from typing import Callable, Dict, List, Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from src.hn import is_hn_item

TIMEOUT = 5
DEADLINE_SECONDS = 8
MAX_BYTES = 512 * 1024
CHUNK = 16 * 1024
WORKERS = 8
CACHE_DAYS = 30
MISS_DAYS = 7
USER_AGENT = "Mozilla/5.0 (compatible; DailyBrief/1.0; +https://thedailybrief.dev)"
SKIP_HOSTS = ("news.ycombinator.com",)

IMAGE_KEYS = (("property", "og:image"), ("property", "og:image:url"), ("name", "twitter:image"),
              ("name", "twitter:image:src"), ("property", "twitter:image"))
DESCRIPTION_KEYS = (("property", "og:description"), ("name", "description"), ("name", "twitter:description"))
ICON_RELS = ("apple-touch-icon", "apple-touch-icon-precomposed", "icon", "shortcut icon")

logger = logging.getLogger(__name__)


def _https(url: Optional[str], base: str) -> Optional[str]:
    if not url:
        return None
    try:
        absolute = urljoin(base, url.strip())
        return absolute if urlparse(absolute).scheme.lower() == "https" else None
    except ValueError:
        return None


def _meta(soup: BeautifulSoup, keys) -> List[str]:
    values = []
    for attr, name in keys:
        for tag in soup.find_all("meta", attrs={attr: name}):
            if tag.get("content"):
                values.append(tag["content"])
    return values


def parse_meta(html: str, base_url: str) -> Dict[str, Optional[str]]:
    """og/twitter image (https, absolute), description and best site icon from a page head."""
    soup = BeautifulSoup(html or "", "html.parser")
    image = next((u for u in (_https(v, base_url) for v in _meta(soup, IMAGE_KEYS)) if u), None)
    description = next((" ".join(v.split()) for v in _meta(soup, DESCRIPTION_KEYS) if v.strip()), None)
    icons = {}
    for link in soup.find_all("link", href=True):
        rel = " ".join(link.get("rel") or []).lower()
        if rel in ICON_RELS and rel not in icons:
            icons[rel] = _https(link["href"], base_url)
    icon = next((icons[r] for r in ICON_RELS if icons.get(r)), None)
    return {"image": image, "description": description, "icon": icon}


def is_public(url: str) -> bool:
    """http(s) URL whose host resolves only to public addresses."""
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            return False
        addresses = {info[4][0] for info in socket.getaddrinfo(parsed.hostname, None)}
    except (ValueError, OSError):
        return False
    for address in addresses:
        ip = ipaddress.ip_address(address.split("%")[0])
        if ip.is_private or ip.is_loopback or ip.is_reserved or ip.is_link_local or ip.is_multicast:
            return False
    return bool(addresses)


def fetch_meta(url: str, is_public: Callable[[str], bool] = is_public) -> Optional[Dict[str, Optional[str]]]:
    """Read the head of url and parse its metadata; None on any failure."""
    try:
        if urlparse(url).scheme not in ("http", "https") or not is_public(url):
            return None
        response = requests.get(url, timeout=TIMEOUT, stream=True, allow_redirects=True,
                                headers={"User-Agent": USER_AGENT, "Accept": "text/html"})
        try:
            response.raise_for_status()
            if "html" not in (response.headers.get("Content-Type") or "").lower():
                return None
            body, started = b"", time.monotonic()
            for chunk in response.iter_content(CHUNK):
                body += chunk
                if len(body) >= MAX_BYTES or b"</head>" in body.lower() or time.monotonic() - started > DEADLINE_SECONDS:
                    break
        finally:
            response.close()
        html = body[:MAX_BYTES].decode(response.encoding or "utf-8", errors="replace")
        return parse_meta(html, response.url or url)
    except Exception as e:  # any per-page failure is a miss; the build goes on
        logger.info(f"No page metadata for {url}: {e.__class__.__name__}: {e}")
        return None


def is_fresh(entry: Dict, today: date) -> bool:
    age = _age_days(entry, today)
    return age is not None and age <= (CACHE_DAYS if entry.get("image") else MISS_DAYS)


def load_cache(path: Path) -> Dict[str, Dict]:
    """The page-metadata cache; missing or unreadable means empty (it is only a cache)."""
    if not path.exists():
        return {}
    try:
        cache = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        logger.warning(f"{path.name}: unreadable ({e}); starting an empty cache")
        return {}
    return cache if isinstance(cache, dict) else {}


def save_cache(path: Path, cache: Dict[str, Dict], today: date) -> None:
    """Write the cache without entries older than CACHE_DAYS."""
    kept = {url: e for url, e in cache.items()
            if isinstance(e, dict) and _age_days(e, today) is not None and _age_days(e, today) <= CACHE_DAYS}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(kept, indent=1, sort_keys=True, ensure_ascii=False) + "\n")


def _age_days(entry: Dict, today: date) -> Optional[int]:
    try:
        return (today - date.fromisoformat(entry["fetched"])).days
    except (KeyError, TypeError, ValueError):
        return None


def _site_favicon(link: str) -> Optional[str]:
    """The site's own /favicon.ico for https links; the page drops it if it fails to load."""
    parsed = urlparse(link)
    return f"https://{parsed.netloc}/favicon.ico" if parsed.scheme == "https" and parsed.netloc else None


def _needs_meta(article: Dict) -> bool:
    host = (urlparse(article.get("link") or "").hostname or "").lower()
    if host in SKIP_HOSTS or not article.get("link"):
        return False
    return not article.get("image") or is_hn_item(article)


def enrich(articles: List[Dict], cache: Dict[str, Dict], today: date,
           fetch: Callable[[str], Optional[Dict]] = fetch_meta) -> Dict[str, int]:
    """Fill image (if missing), og_description and icon on articles in place; returns counts."""
    wanted = [a for a in articles if _needs_meta(a)]
    urls = list(dict.fromkeys(a["link"] for a in wanted))
    stale = [u for u in urls if not (u in cache and is_fresh(cache[u], today))]
    def safe(url: str) -> Optional[Dict]:
        try:
            return fetch(url)
        except Exception as e:  # a fetch is never allowed to fail the build
            logger.info(f"No page metadata for {url}: {e.__class__.__name__}: {e}")
            return None

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        for url, meta in zip(stale, pool.map(safe, stale)):
            cache[url] = {"fetched": today.isoformat(), "image": None, "description": None, "icon": None,
                          **(meta or {})}

    og_images = 0
    for article in wanted:
        meta = cache[article["link"]]
        if not article.get("image") and meta.get("image"):
            article["image"] = meta["image"]
            article["og_image"] = True
            og_images += 1
        if meta.get("description"):
            article["og_description"] = meta["description"]
        icon = meta.get("icon") or _site_favicon(article["link"])
        if icon:
            article["icon"] = icon
    return {"fetched": len(stale), "cached": len(urls) - len(stale), "og_images": og_images}
