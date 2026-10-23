"""
Story of the day: pick the site's lead from all of the day's fetched articles.

No AI and no embeddings. Same input and `now` always give the same pick.

1. Candidates: every fetched article across all sections, deduped by link
   (first section in config order wins).
2. Clusters: two articles are the same story when the idf-weighted Jaccard
   similarity of their title tokens is at least SIMILARITY_THRESHOLD, or
   when they share a CVE id, RFC number or IETF draft name. Clusters are the
   connected groups (union-find). Coverage is the number of distinct link
   domains in a cluster.
3. Score per cluster:

       base = 1
            + RELEVANCE_PTS * log2(1 + keyword score of the best member)
            + COVERAGE_PTS  * min(coverage - 1, COVERAGE_CAP)
            + HARD_NEWS_PTS if any member has a CVE/RFC/draft id, a version
                            release or breach wording
            + HN_PTS        * log10(1 + Hacker News points + comments)

       score = base * freshness * section_weight * tier_mult * novelty

       freshness      = ((age_hours + 2) / 2) ** -GRAVITY, where age_hours is
                        the age of the newest dated member; clusters with no
                        dated member are treated as UNDATED_AGE_HOURS old
                        (middle of the 48h fetch window: neutral to low)
       section_weight = `weight:` of the cluster's section in config.yaml; the
                        section is the member section with the highest weight
       tier_mult      = TIER_MULT of the best member tier (config.yaml
                        story.source_tiers)
       novelty        = SECTION_REPEAT if the section led on one of the
                        previous NOVELTY_DAYS days, times STORY_REPEAT if the
                        cluster repeats a recent lead (same url, a shared id,
                        or key-token Jaccard >= STORY_REPEAT_JACCARD)

   Ties break on lead title, then link.
"""

import math
import re
from typing import Dict, FrozenSet, Optional
from urllib.parse import urlparse

STOPWORDS = frozenset("""
a an the and or but nor of to in on for with by from at as is are was were be been being it its
this that these those you your we our us i my me he she they them their his her how why what when
where who whom which will would can could should may might must do does did not no yes vs via into
over about after before up out new than more most just so if then there here all any some show ask hn
""".split())

HN_BOILERPLATE = re.compile(r"(Article URL:|Comments URL:|Points:\s*\d|#\s*Comments:)")
HN_POINTS = re.compile(r"\bPoints:\s*(\d+)")
HN_COMMENTS = re.compile(r"#\s*Comments:\s*(\d+)")

CVE_RE = re.compile(r"\bCVE-\d{4}-\d{4,7}\b", re.I)
RFC_RE = re.compile(r"\bRFC[\s-]?(\d{3,5})\b", re.I)
DRAFT_RE = re.compile(r"\bdraft-[a-z0-9]+(?:-[a-z0-9]+)+", re.I)
DRAFT_VERSION = re.compile(r"-\d{2}$")
VERSION_RE = re.compile(r"\bv?\d+\.\d+(?:\.\d+)*\b", re.I)
RELEASE_RE = re.compile(r"\b(released?|releases|launch(?:es|ed)?|now available|generally available|ga)\b", re.I)
BREACH_RE = re.compile(r"\b(breach(?:es|ed)?|data leak|leaked|hacked|ransomware|zero-day|0-day|"
                       r"actively exploited|exploited in the wild|compromised)\b", re.I)


def _stem(token: str) -> str:
    if len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
        return token[:-1]
    return token


def title_tokens(title: str) -> FrozenSet[str]:
    """Lowercase word tokens without punctuation, stopwords, 1-char words or a plural s."""
    words = re.findall(r"[a-z0-9]+", (title or "").lower())
    return frozenset(_stem(w) for w in words if len(w) > 1 and w not in STOPWORDS)


def extract_ids(text: str) -> FrozenSet[str]:
    """CVE ids, RFC numbers and IETF draft names (without the -NN version), normalized."""
    text = text or ""
    ids = {m.group(0).upper() for m in CVE_RE.finditer(text)}
    ids |= {f"RFC {int(m.group(1))}" for m in RFC_RE.finditer(text)}
    ids |= {DRAFT_VERSION.sub("", m.group(0).lower()) for m in DRAFT_RE.finditer(text)}
    return frozenset(ids)


def first_sentence(summary: str) -> str:
    """First sentence of a summary, or '' for Hacker News boilerplate."""
    text = " ".join((summary or "").split())
    if HN_BOILERPLATE.search(text):
        return ""
    return re.split(r"(?<=[.!?])\s+", text, maxsplit=1)[0][:300]


def article_ids(article: Dict) -> FrozenSet[str]:
    return extract_ids(f"{article.get('title') or ''} {first_sentence(article.get('summary'))}")


def hn_points(summary: Optional[str]) -> int:
    """Points plus comments from an hnrss summary ('Points: N # Comments: M'), else 0."""
    text = summary or ""
    total = 0
    for pattern in (HN_POINTS, HN_COMMENTS):
        match = pattern.search(text)
        if match:
            total += int(match.group(1))
    return total


def is_hard_news(article: Dict) -> bool:
    title = article.get("title") or ""
    if article_ids(article):
        return True
    if VERSION_RE.search(title) and RELEASE_RE.search(title):
        return True
    return bool(BREACH_RE.search(title))


def domain(url: str) -> str:
    try:
        host = urlparse((url or "").strip()).hostname or ""
    except ValueError:
        return ""
    return host.lower().removeprefix("www.")


def _matches(url: str, pattern: str) -> bool:
    host, _, path = pattern.lower().partition("/")
    url_host = domain(url)
    if not url_host or not (url_host == host or url_host.endswith("." + host)):
        return False
    try:
        url_path = urlparse(url.strip()).path.lower()
    except ValueError:
        return False
    return not path or url_path.startswith("/" + path)


def source_tier(article: Dict, tiers: Dict) -> str:
    """'primary' if the link is a primary source, 'aggregator' if link or feed is one, else 'normal'."""
    link = article.get("link") or ""
    if any(_matches(link, p) for p in tiers.get("primary", [])):
        return "primary"
    feed = article.get("feed") or ""
    if any(_matches(u, p) for u in (link, feed) for p in tiers.get("aggregator", [])):
        return "aggregator"
    return "normal"
