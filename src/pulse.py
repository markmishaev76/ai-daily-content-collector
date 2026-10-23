"""
The Pulse: the day's top Reddit threads from a few subreddits (site only).

Reads /r/<sub>/top?t=day. With REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET in
the environment it uses app-only OAuth (client_credentials) against
oauth.reddit.com; otherwise the public JSON on www.reddit.com, which Reddit
often blocks (403). Failures raise PulseUnavailable and the site hides the
section; they never fail the build.
"""

import html
import logging
import re
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import requests

REDDIT = "https://www.reddit.com"
OAUTH = "https://oauth.reddit.com"
TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
USER_AGENT = "web:thedailybrief:1.0 (+https://thedailybrief.dev)"
TIMEOUT = 10
FETCH_LIMIT = 50
DEFAULTS = {"min_upvotes": 100, "limit": 10, "max_age_hours": 24}
SUBREDDIT_RE = re.compile(r"[A-Za-z0-9_]{2,21}")
META_FLAIR = re.compile(r"\b(meta|mod|mods|moderator|announcements?|rules|megathread)\b", re.I)
REMOVED = {"[removed]", "[deleted]"}

logger = logging.getLogger(__name__)


class PulseUnavailable(Exception):
    pass


def _count(value, name: str, minimum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"config.yaml: pulse.{name} must be a whole number >= {minimum}, got {value!r}")
    return value


def settings(config: Dict) -> Optional[Dict]:
    """Validated pulse settings, or None when config.yaml has no pulse section."""
    raw = config.get("pulse")
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ValueError("config.yaml: pulse must be a mapping")
    out = {k: _count(raw.get(k, v), k, 0 if k == "min_upvotes" else 1) for k, v in DEFAULTS.items()}
    subs = []
    for entry in raw.get("subreddits") or []:
        name, minimum = (entry, out["min_upvotes"]) if isinstance(entry, str) else \
            ((entry or {}).get("name"), (entry or {}).get("min_upvotes", out["min_upvotes"]))
        if not isinstance(name, str) or not SUBREDDIT_RE.fullmatch(name):
            raise ValueError(f"config.yaml: pulse.subreddits has an invalid subreddit name {name!r}")
        subs.append((name, _count(minimum, f"subreddits.{name}.min_upvotes", 0)))
    if not subs:
        raise ValueError("config.yaml: pulse.subreddits must list at least one subreddit")
    out["subreddits"] = subs
    return out


def qualifies(post: Dict, now: datetime, min_upvotes: int, max_age_hours: int) -> bool:
    """A real, recent, popular thread: not stickied, NSFW, removed, or a mod/meta post."""
    if post.get("stickied") or post.get("pinned") or post.get("over_18"):
        return False
    if post.get("removed_by_category") or post.get("author") in REMOVED or post.get("selftext") in REMOVED:
        return False
    if post.get("distinguished") or META_FLAIR.search(post.get("link_flair_text") or ""):
        return False
    age_hours = (now.timestamp() - float(post.get("created_utc") or 0)) / 3600
    return age_hours <= max_age_hours and int(post.get("ups") or 0) >= min_upvotes


def _https(url: Optional[str]) -> Optional[str]:
    url = html.unescape(url or "").strip()
    try:
        return url if urlparse(url).scheme.lower() == "https" else None
    except ValueError:
        return None


def _is_reddit(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return host == "reddit.com" or host.endswith(".reddit.com")


def to_item(post: Dict) -> Dict:
    url = post.get("url") or ""
    external = None if post.get("is_self") or _is_reddit(url) else url
    images = ((post.get("preview") or {}).get("images") or [{}])
    return {
        "title": post.get("title") or "Untitled",
        "subreddit": post.get("subreddit") or "",
        "ups": int(post.get("ups") or 0),
        "comments": int(post.get("num_comments") or 0),
        "created": datetime.fromtimestamp(float(post.get("created_utc") or 0), tz=timezone.utc),
        "thread": REDDIT + (post.get("permalink") or ""),
        "link": external,
        "image": _https((images[0].get("source") or {}).get("url")),
    }


def _token(env: Dict, post: Callable) -> str:
    try:
        response = post(TOKEN_URL, auth=(env["REDDIT_CLIENT_ID"], env["REDDIT_CLIENT_SECRET"]),
                        data={"grant_type": "client_credentials"}, headers={"User-Agent": USER_AGENT},
                        timeout=TIMEOUT)
        token = response.json().get("access_token") if response.status_code == 200 else None
    except (requests.RequestException, ValueError, AttributeError) as e:
        raise PulseUnavailable(f"Reddit OAuth token request failed: {e}") from e
    if not token:
        raise PulseUnavailable(f"Reddit OAuth token request failed (HTTP {response.status_code})")
    return token


def _listing(sub: str, token: Optional[str], get: Callable) -> List[Dict]:
    headers = {"User-Agent": USER_AGENT}
    if token:
        url = f"{OAUTH}/r/{sub}/top"
        headers["Authorization"] = f"Bearer {token}"
    else:
        url = f"{REDDIT}/r/{sub}/top.json"
    try:
        response = get(url, params={"t": "day", "limit": FETCH_LIMIT, "raw_json": 1}, headers=headers,
                       timeout=TIMEOUT)
    except requests.RequestException as e:
        raise PulseUnavailable(f"r/{sub}: {e.__class__.__name__}") from e
    if response.status_code != 200:
        raise PulseUnavailable(f"r/{sub}: HTTP {response.status_code}")
    try:
        children = response.json()["data"]["children"]
        return [c["data"] for c in children if c.get("kind") == "t3"]
    except (ValueError, KeyError, TypeError) as e:
        raise PulseUnavailable(f"r/{sub}: unexpected response") from e


def collect(config: Dict, now: datetime, env: Dict, get: Callable = requests.get,
            post: Callable = requests.post) -> Tuple[List[Dict], Dict[str, Optional[int]]]:
    """Top threads across the configured subreddits and how many qualified per sub (None = fetch failed)."""
    s = settings(config)
    token = _token(env, post) if env.get("REDDIT_CLIENT_ID") and env.get("REDDIT_CLIENT_SECRET") else None
    items, counts, errors = [], {}, []
    for sub, minimum in s["subreddits"]:
        try:
            posts = _listing(sub, token, get)
        except PulseUnavailable as e:
            logger.warning(f"The Pulse: {e}")
            counts[sub], errors = None, errors + [str(e)]
            continue
        good = [to_item(p) for p in posts if qualifies(p, now, minimum, s["max_age_hours"])]
        counts[sub] = len(good)
        items += good
    if errors and len(errors) == len(s["subreddits"]):
        hint = "" if token else "; public JSON is blocked, set REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET for OAuth"
        raise PulseUnavailable(f"every subreddit failed ({', '.join(errors)}){hint}")
    items.sort(key=lambda i: (-i["ups"], i["title"], i["thread"]))
    return items[:s["limit"]], counts
