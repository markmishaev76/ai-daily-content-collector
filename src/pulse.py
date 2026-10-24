"""
The Pulse: the day's most-discussed threads on Hacker News, Lobsters and Reddit (site only).

Hacker News comes from the Algolia search API and Lobsters from its hottest
page JSON; neither needs keys. Their posts must also be on the site's topics
(see relevant). Reddit reads /r/<sub>/top?t=day: with REDDIT_CLIENT_ID and
REDDIT_CLIENT_SECRET in the environment it uses app-only OAuth
(client_credentials) against oauth.reddit.com; otherwise the public JSON on
www.reddit.com, which Reddit often blocks (403). Subreddits are on-topic by
choice, so their threads skip the relevance check.

Each source fails on its own with a warning; only when every source fails
does collect raise PulseUnavailable, and the site hides the section. The
build never fails.
"""

import html
import logging
import re
from datetime import datetime, timezone
from typing import Callable, Dict, Iterable, List, Optional, Tuple
from urllib.parse import urlparse

import requests

from main import _score_article
from src import story

REDDIT = "https://www.reddit.com"
OAUTH = "https://oauth.reddit.com"
TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
HN_SEARCH = "https://hn.algolia.com/api/v1/search"
HN_ITEM = "https://news.ycombinator.com/item?id="
LOBSTERS_HOTTEST = "https://lobste.rs/hottest.json"
HN, LOBSTERS = "Hacker News", "Lobsters"
USER_AGENT = "web:thedailybrief:1.0 (+https://thedailybrief.dev)"
TIMEOUT = 10
FETCH_LIMIT = 50
HN_HITS = 100
DEFAULTS = {"min_upvotes": 100, "limit": 10, "max_age_hours": 24}
HN_DEFAULTS = {"min_points": 100}
LOBSTERS_MIN_SCORE = 15
KNOWN_KEYS = set(DEFAULTS) | {"subreddits", "keywords", "hacker_news", "lobsters"}
SUBREDDIT_RE = re.compile(r"[A-Za-z0-9_]{2,21}")
LOBSTERS_TAG_RE = re.compile(r"[a-z0-9][a-z0-9+.-]*")
META_FLAIR = re.compile(r"\b(meta|mod|mods|moderator|announcements?|rules|megathread)\b", re.I)
REMOVED = {"[removed]", "[deleted]"}

logger = logging.getLogger(__name__)


class PulseUnavailable(Exception):
    pass


def _count(value, name: str, minimum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"config.yaml: pulse.{name} must be a whole number >= {minimum}, got {value!r}")
    return value


def _mapping(raw, name: str, allowed: Iterable[str]) -> Dict:
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise ValueError(f"config.yaml: pulse.{name} must be a mapping")
    unknown = set(raw) - set(allowed)
    if unknown:
        raise ValueError(f"config.yaml: pulse.{name} has unknown key(s) {', '.join(sorted(map(str, unknown)))}")
    return raw


def _strings(value, name: str, pattern: Optional[re.Pattern] = None) -> List[str]:
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(v, str) and v.strip() for v in value):
        raise ValueError(f"config.yaml: pulse.{name} must be a list of non-empty strings, got {value!r}")
    bad = [v for v in value if pattern and not pattern.fullmatch(v)]
    if bad:
        raise ValueError(f"config.yaml: pulse.{name} has invalid entries {bad!r}")
    return [v.strip() for v in value]


def _keyword_re(keywords: List[str]) -> Optional[re.Pattern]:
    if not keywords:
        return None
    return re.compile(r"(?<!\w)(?:" + "|".join(re.escape(k) for k in keywords) + r")(?!\w)", re.I)


def settings(config: Dict) -> Optional[Dict]:
    """Validated pulse settings, or None when config.yaml has no pulse section."""
    raw = config.get("pulse")
    if raw is None:
        return None
    raw = _mapping(raw, "pulse", KNOWN_KEYS) if raw else {}
    out = {k: _count(raw.get(k, v), k, 0 if k == "min_upvotes" else 1) for k, v in DEFAULTS.items()}
    subs = []
    for entry in raw.get("subreddits") or []:
        name, minimum = (entry, out["min_upvotes"]) if isinstance(entry, str) else \
            ((entry or {}).get("name"), (entry or {}).get("min_upvotes", out["min_upvotes"]))
        if not isinstance(name, str) or not SUBREDDIT_RE.fullmatch(name):
            raise ValueError(f"config.yaml: pulse.subreddits has an invalid subreddit name {name!r}")
        subs.append((name, _count(minimum, f"subreddits.{name}.min_upvotes", 0)))
    out["subreddits"] = subs
    out["hacker_news"] = None
    if "hacker_news" in raw:
        hn = _mapping(raw["hacker_news"], "hacker_news", HN_DEFAULTS)
        out["hacker_news"] = {"min_points": _count(hn.get("min_points", HN_DEFAULTS["min_points"]),
                                                   "hacker_news.min_points", 1)}
    out["lobsters"] = None
    if "lobsters" in raw:
        lob = _mapping(raw["lobsters"], "lobsters", ("min_score", "tags"))
        out["lobsters"] = {"min_score": _count(lob.get("min_score", LOBSTERS_MIN_SCORE), "lobsters.min_score", 1),
                           "tags": frozenset(_strings(lob.get("tags"), "lobsters.tags", LOBSTERS_TAG_RE))}
    if not subs and not out["hacker_news"] and not out["lobsters"]:
        raise ValueError("config.yaml: pulse needs at least one source (subreddits, hacker_news or lobsters)")
    out["keywords"] = _keyword_re(_strings(raw.get("keywords"), "keywords"))
    out["primary"] = ((config.get("story") or {}).get("source_tiers") or {}).get("primary") or []
    return out


def relevant(title: str, link: Optional[str], tags: Iterable[str], s: Dict) -> bool:
    """On the site's topics: an allowed Lobsters tag, a main.AX_THEME_KEYWORDS hit, a CVE/RFC/draft id or
    breach wording (as for the lead), a primary-source link (story.source_tiers), or a pulse.keywords word."""
    if s["lobsters"] and set(tags) & s["lobsters"]["tags"]:
        return True
    if _score_article({"title": title, "summary": ""}) > 0:
        return True
    if story.extract_ids(title) or story.BREACH_RE.search(title):
        return True
    if link and story.source_tier({"link": link}, {"primary": s["primary"]}) == "primary":
        return True
    return bool(s["keywords"] and s["keywords"].search(title))


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


def _web(url: Optional[str]) -> Optional[str]:
    url = (url or "").strip()
    try:
        return url if urlparse(url).scheme.lower() in ("http", "https") else None
    except ValueError:
        return None


def _is_reddit(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return host == "reddit.com" or host.endswith(".reddit.com")


def url_key(url: Optional[str]) -> str:
    """Same page, ignoring scheme, www., a trailing slash and the fragment ('' if not a web link)."""
    try:
        parts = urlparse((url or "").strip())
    except ValueError:
        return ""
    if parts.scheme.lower() not in ("http", "https") or not parts.hostname:
        return ""
    key = parts.hostname.lower().removeprefix("www.") + parts.path.rstrip("/")
    return key + ("?" + parts.query if parts.query else "")


def to_item(post: Dict) -> Dict:
    url = post.get("url") or ""
    external = None if post.get("is_self") or _is_reddit(url) else url
    images = ((post.get("preview") or {}).get("images") or [{}])
    return {
        "title": post.get("title") or "Untitled",
        "source": f"r/{post.get('subreddit') or ''}",
        "points": int(post.get("ups") or 0),
        "unit": "upvotes",
        "comments": int(post.get("num_comments") or 0),
        "created": datetime.fromtimestamp(float(post.get("created_utc") or 0), tz=timezone.utc),
        "thread": REDDIT + (post.get("permalink") or ""),
        "link": external,
        "image": _https((images[0].get("source") or {}).get("url")),
    }


def _get_json(label: str, url: str, get: Callable, **kw):
    try:
        response = get(url, timeout=TIMEOUT, **kw)
    except requests.RequestException as e:
        raise PulseUnavailable(f"{label}: {e.__class__.__name__}") from e
    if response.status_code != 200:
        raise PulseUnavailable(f"{label}: HTTP {response.status_code}")
    try:
        return response.json()
    except ValueError as e:
        raise PulseUnavailable(f"{label}: unexpected response") from e


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
    body = _get_json(f"r/{sub}", url, get, params={"t": "day", "limit": FETCH_LIMIT, "raw_json": 1}, headers=headers)
    try:
        return [c["data"] for c in body["data"]["children"] if c.get("kind") == "t3"]
    except (KeyError, TypeError, AttributeError) as e:
        raise PulseUnavailable(f"r/{sub}: unexpected response") from e


def _whole(value) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _age_ok(created: datetime, now: datetime, max_age_hours: int) -> bool:
    return (now - created).total_seconds() <= max_age_hours * 3600


def _hacker_news(s: Dict, now: datetime, get: Callable) -> List[Dict]:
    minimum, since = s["hacker_news"]["min_points"], int(now.timestamp()) - s["max_age_hours"] * 3600
    body = _get_json(HN, HN_SEARCH, get, headers={"User-Agent": USER_AGENT},
                     params={"tags": "story", "numericFilters": f"created_at_i>{since},points>={minimum}",
                             "hitsPerPage": HN_HITS})
    try:
        hits = [h for h in body["hits"] if isinstance(h, dict)]
    except (KeyError, TypeError) as e:
        raise PulseUnavailable(f"{HN}: unexpected response") from e
    items = []
    for h in hits:
        title, points = h.get("title"), _whole(h.get("points"))
        if not isinstance(title, str) or not title.strip() or points < minimum:
            continue
        if not isinstance(h.get("created_at_i"), int) or not h.get("objectID"):
            continue
        created = datetime.fromtimestamp(h["created_at_i"], tz=timezone.utc)
        link = _web(h.get("url"))
        if not _age_ok(created, now, s["max_age_hours"]) or not relevant(title, link, (), s):
            continue
        items.append({"title": title, "source": HN, "points": points, "unit": "points",
                      "comments": _whole(h.get("num_comments")), "created": created,
                      "thread": HN_ITEM + str(h["objectID"]), "link": link, "image": None,
                      "rank": points / minimum})
    return items


def _lobsters(s: Dict, now: datetime, get: Callable) -> List[Dict]:
    minimum = s["lobsters"]["min_score"]
    body = _get_json(LOBSTERS, LOBSTERS_HOTTEST, get, headers={"User-Agent": USER_AGENT})
    if not isinstance(body, list):
        raise PulseUnavailable(f"{LOBSTERS}: unexpected response")
    items = []
    for st in (b for b in body if isinstance(b, dict)):
        title, score, tags = st.get("title"), _whole(st.get("score")), st.get("tags") or []
        if not isinstance(title, str) or not title.strip() or score < minimum:
            continue
        try:
            created = datetime.fromisoformat(st.get("created_at") or "")
        except (TypeError, ValueError):
            continue
        thread, link = _web(st.get("comments_url")), _web(st.get("url"))
        if created.tzinfo is None or not thread or not _age_ok(created, now, s["max_age_hours"]):
            continue
        if not relevant(title, link, tags if isinstance(tags, list) else [], s):
            continue
        items.append({"title": title, "source": LOBSTERS, "points": score, "unit": "points",
                      "comments": _whole(st.get("comment_count")), "created": created, "thread": thread,
                      "link": link, "image": None, "rank": score / minimum})
    return items


def _reddit(s: Dict, now: datetime, env: Dict, get: Callable, post: Callable,
            counts: Dict, errors: List[str]) -> Tuple[List[Dict], Optional[str]]:
    """Qualifying threads from every subreddit; fills counts and errors per sub. Returns the items and a hint."""
    oauth = bool(env.get("REDDIT_CLIENT_ID") and env.get("REDDIT_CLIENT_SECRET"))
    try:
        token = _token(env, post) if oauth else None
    except PulseUnavailable as e:
        logger.warning(f"The Pulse: {e}")
        for sub, _ in s["subreddits"]:
            counts[f"r/{sub}"] = None
        errors.append(str(e))
        return [], None
    items, failed = [], 0
    for sub, minimum in s["subreddits"]:
        try:
            posts = _listing(sub, token, get)
        except PulseUnavailable as e:
            logger.warning(f"The Pulse: {e}")
            counts[f"r/{sub}"], failed = None, failed + 1
            errors.append(str(e))
            continue
        good = [dict(to_item(p), rank=int(p.get("ups") or 0) / max(minimum, 1))
                for p in posts if qualifies(p, now, minimum, s["max_age_hours"])]
        counts[f"r/{sub}"] = len(good)
        items += good
    blocked = failed == len(s["subreddits"]) and not token
    return items, "public JSON is blocked, set REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET for OAuth" if blocked else None


def _merge(items: List[Dict], shown: Iterable[str]) -> List[Dict]:
    """Drop links already on the page; one item per external link, the best-ranked, listing the other threads."""
    on_page = {url_key(u) for u in shown} - {""}
    groups: Dict[str, List[Dict]] = {}
    for item in items:
        key = url_key(item.get("link"))
        if key and key in on_page:
            continue
        groups.setdefault(key or item["thread"], []).append(item)
    merged = []
    for group in groups.values():
        group.sort(key=lambda i: (-i["rank"], i["source"], i["thread"]))
        best = dict(group[0], also=[{"source": i["source"], "thread": i["thread"]} for i in group[1:]])
        merged.append(best)
    return merged


def collect(config: Dict, now: datetime, env: Dict, get: Callable = requests.get,
            post: Callable = requests.post, shown: Iterable[str] = ()) -> Tuple[List[Dict], Dict[str, Optional[int]]]:
    """Top threads across all sources, skipping links in `shown`, and how many qualified per source
    (None = fetch failed). Raises PulseUnavailable only when every source failed."""
    s = settings(config)
    items, counts, errors, hint = [], {}, [], None
    for label, fetch in ((HN, _hacker_news if s["hacker_news"] else None),
                         (LOBSTERS, _lobsters if s["lobsters"] else None)):
        if not fetch:
            continue
        try:
            found = fetch(s, now, get)
        except PulseUnavailable as e:
            logger.warning(f"The Pulse: {e}")
            counts[label] = None
            errors.append(str(e))
            continue
        counts[label] = len(found)
        items += found
    if s["subreddits"]:
        found, hint = _reddit(s, now, env, get, post, counts, errors)
        items += found
    if counts and all(n is None for n in counts.values()):
        raise PulseUnavailable(f"every source failed ({', '.join(errors)})" + (f"; {hint}" if hint else ""))
    # Points aren't comparable across sources, so rank is points over that source's threshold.
    merged = _merge(items, shown)
    merged.sort(key=lambda i: (-i["rank"], i["title"], i["thread"]))
    return merged[:s["limit"]], counts
