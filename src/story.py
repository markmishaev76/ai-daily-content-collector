"""
Story of the day: pick the site's lead from all of the day's fetched articles.

No AI and no embeddings. Same input and `now` always give the same pick.

1. Candidates: every fetched article across all sections, deduped by link
   (first section in config order wins).
2. Clusters: two articles are the same story when the idf-weighted Jaccard
   similarity of their title + first-sentence tokens is at least
   SIMILARITY_THRESHOLD with at least MIN_SHARED_TOKENS in common, or
   when they share a CVE id, RFC number or IETF draft name. Clusters are the
   connected groups (union-find). Then each cluster covering at least
   SIGNATURE_MIN_DOMAINS domains pulls in every article whose title has one
   of its signature words (a coined name like "PHP2Shell": see _signature).
   Coverage is the number of distinct link domains in a cluster.
3. Score per cluster:

       base = 1
            + RELEVANCE_PTS * log2(1 + best member's main._score_article,
                                   ignoring Hacker News boilerplate)
            + COVERAGE_PTS  * min(coverage - 1, COVERAGE_CAP)
            + HARD_NEWS_PTS if any member has a CVE/RFC/draft id, a version
                            release or breach wording
            + HN_PTS        * log10(1 + Hacker News points + comments)

       score = base * freshness * section_weight * tier_mult * novelty

       freshness      = ((age_hours + AGE_OFFSET_HOURS) / AGE_OFFSET_HOURS)
                        ** -GRAVITY (Hacker News gravity with a 12h offset, as
                        the site is built once a day: 1/2 at 12h, 1/3 at 24h),
                        where age_hours is the age of the newest dated
                        member; clusters with no
                        dated member are treated as UNDATED_AGE_HOURS old
                        (middle of the 48h fetch window: neutral to low)
       section_weight = `weight:` of the cluster's section in config.yaml; the
                        section is the most common member section (ties: the
                        higher weight, then earlier in config)
       tier_mult      = TIER_MULT of the best member tier (config.yaml
                        story.source_tiers)
       novelty        = SECTION_REPEAT if the section led on one of the
                        previous NOVELTY_DAYS days, times STORY_REPEAT if the
                        cluster repeats a recent lead (same url, a shared id,
                        or key-token Jaccard >= STORY_REPEAT_JACCARD)

   Ties break on lead title, then link.
4. Lead shown: the winning cluster's member with an https image, then the
   best tier, then the highest keyword score, then the freshest, then link.
   An unexpired pinned.yaml overrides the pick.
"""

import json
import logging
import math
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, FrozenSet, List, Optional, Sequence, Tuple
from urllib.parse import urlparse

import yaml

from main import _score_article

# Clustering
SIMILARITY_THRESHOLD = 0.2   # idf-weighted Jaccard of title + first-sentence tokens
MIN_SHARED_TOKENS = 3        # and at least this many shared tokens
SIGNATURE_MIN_DOMAINS = 3    # clusters this wide pull in titles that use their signature word
SIGNATURE_SHARE = 0.75       # signature: a title word in at least this share of member titles
SIGNATURE_MAX_SPREAD = 4     # and in at most this many titles per member across the pool

# Base points
RELEVANCE_PTS = 2.0          # per log2(1 + keyword score)
COVERAGE_PTS = 4.0           # per extra source domain
COVERAGE_CAP = 5             # extra domains that count
HARD_NEWS_PTS = 6.0
HN_PTS = 3.0                 # per log10(1 + points + comments)

# Multipliers
AGE_OFFSET_HOURS = 12         # freshness halves at this age
GRAVITY = 1.0
UNDATED_AGE_HOURS = 24
TIER_MULT = {"primary": 1.25, "normal": 1.0, "aggregator": 0.85}
TIER_RANK = {"aggregator": 0, "normal": 1, "primary": 2}
NOVELTY_DAYS = 3
SECTION_REPEAT = 0.8
STORY_REPEAT = 0.5
STORY_REPEAT_JACCARD = 0.5

ALSO_CAP = 6                 # 'Also covered by' links
HISTORY_CAP = 30
PINNED_FIELDS = {"url", "title", "note", "until"}

logger = logging.getLogger(__name__)

STOPWORDS = frozenset("""
a an the and or but nor of to in on for with by from at as is are was were be been being it its
this that these those you your we our us i my me he she they them their his her how why what when
where who whom which will would can could should may might must do does did not no yes vs via into
over about after before up out new than more most just so if then there here all any some show ask hn
has have had using use used now first get got make made run build one two inside introducing announcing
""".split())
# In most of this feed's titles, so they say nothing about which story an article is.
GENERIC_WORDS = frozenset({"ai", "agent", "agentic", "llm", "model"})

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
    words = re.findall(r"[a-z0-9]+(?:\.[0-9]+)+|[a-z0-9]+", (title or "").lower())
    stems = (_stem(w) for w in words if len(w) > 1 and w not in STOPWORDS)
    return frozenset(w for w in stems if w not in STOPWORDS and w not in GENERIC_WORDS)


def story_tokens(article: Dict) -> FrozenSet[str]:
    """Tokens of the title and the summary's first sentence, used for clustering."""
    return title_tokens(article.get("title")) | title_tokens(first_sentence(article.get("summary")))


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


def _web_link(url: str) -> bool:
    try:
        return urlparse((url or "").strip()).scheme.lower() in ("http", "https")
    except ValueError:
        return False


def candidates(feed: Dict[str, List[Dict]]) -> List[Dict]:
    """Every article with an http(s) link, deduped by link. Copies carry `section` and `hn`."""
    by_link: Dict[str, Dict] = {}
    for section, articles in feed.items():
        for article in articles:
            link = article.get("link") or ""
            if not _web_link(link):
                continue
            points = hn_points(article.get("summary"))
            if link in by_link:
                by_link[link]["hn"] = max(by_link[link]["hn"], points)
                continue
            by_link[link] = dict(article, section=section, hn=points)
    return list(by_link.values())


def _similar(a: FrozenSet[str], b: FrozenSet[str], idf: Dict[str, float]) -> bool:
    shared = a & b
    if len(shared) < MIN_SHARED_TOKENS:
        return False
    union = sum(idf[t] for t in a | b)
    return sum(idf[t] for t in shared) / union >= SIMILARITY_THRESHOLD


def cluster(cands: List[Dict]) -> List[List[Dict]]:
    """Group candidates into same-story clusters, ordered by first member, members in input order."""
    n = len(cands)
    tokens = [story_tokens(c) for c in cands]
    df = Counter(t for toks in tokens for t in toks)
    idf = {t: math.log((n + 1) / (count + 1)) + 1 for t, count in df.items()}

    parent = list(range(n))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i: int, j: int) -> None:
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[max(ri, rj)] = min(ri, rj)

    first_with_id: Dict[str, int] = {}
    for i, c in enumerate(cands):
        for ident in sorted(article_ids(c)):
            if ident in first_with_id:
                union(first_with_id[ident], i)
            else:
                first_with_id[ident] = i

    for i in range(n):
        for j in range(i + 1, n):
            if _similar(tokens[i], tokens[j], idf):
                union(i, j)

    titles = [title_tokens(c.get("title")) for c in cands]
    title_df = Counter(t for toks in titles for t in toks)
    first_pass: Dict[int, List[int]] = {}
    for i in range(n):
        first_pass.setdefault(find(i), []).append(i)
    for root in sorted(first_pass):
        members = first_pass[root]
        if coverage([cands[i] for i in members]) < SIGNATURE_MIN_DOMAINS:
            continue
        signature = _signature([titles[i] for i in members], title_df)
        for j in range(n):
            if titles[j] & signature:
                union(root, j)

    groups: Dict[int, List[Dict]] = {}
    for i, c in enumerate(cands):
        groups.setdefault(find(i), []).append(c)
    return [groups[root] for root in sorted(groups)]


def _signature(member_titles: List[FrozenSet[str]], title_df: Counter) -> FrozenSet[str]:
    """Title words most members use and the rest of the pool mostly doesn't."""
    counts = Counter(t for toks in member_titles for t in toks)
    size = len(member_titles)
    return frozenset(t for t, k in counts.items()
                     if k >= SIGNATURE_SHARE * size and title_df[t] <= SIGNATURE_MAX_SPREAD * size)


def coverage(members: List[Dict]) -> int:
    """Number of distinct link domains."""
    return len({domain(m.get("link")) for m in members} - {""})


def freshness(age_hours: float) -> float:
    return ((max(age_hours, 0.0) + AGE_OFFSET_HOURS) / AGE_OFFSET_HOURS) ** -GRAVITY


def section_weights(config: Dict) -> Dict[str, float]:
    weights = {}
    for topic in config.get("topics", []):
        weight = topic.get("weight", 1.0)
        if isinstance(weight, bool) or not isinstance(weight, (int, float)) or weight <= 0:
            raise ValueError(f"config.yaml: topic {topic.get('name')!r} weight must be a positive number, "
                             f"got {weight!r}")
        weights[topic["name"]] = float(weight)
    return weights


def key_tokens(lead: Dict, ids: FrozenSet[str]) -> FrozenSet[str]:
    return title_tokens(lead.get("title")) | ids


def _age_hours(article: Dict, now: datetime) -> Optional[float]:
    published = article.get("published")
    if not isinstance(published, datetime):
        return None
    return max((now - published).total_seconds() / 3600, 0.0)


def _jaccard(a: FrozenSet[str], b: FrozenSet[str]) -> float:
    return len(a & b) / len(a | b) if a | b else 0.0


@dataclass
class Scored:
    members: List[Dict]
    lead: Dict
    section: str
    coverage: int
    ids: FrozenSet[str]
    keywords: float
    relevance_pts: float
    coverage_pts: float
    hard_pts: float
    hn: int
    hn_pts: float
    base: float
    age_hours: Optional[float]
    freshness: float
    section_weight: float
    tier: str
    tier_mult: float
    novelty: float
    score: float

    def breakdown(self) -> str:
        age = "undated" if self.age_hours is None else f"{self.age_hours:.1f}h"
        return (f"{self.score:6.2f} = base {self.base:.2f} (relevance {self.relevance_pts:.2f} [kw {self.keywords:g}]"
                f" + coverage {self.coverage_pts:g} [{self.coverage} domains] + hard {self.hard_pts:g}"
                f" + hn {self.hn_pts:.2f} [{self.hn}]) x fresh {self.freshness:.2f} [{age}]"
                f" x section {self.section_weight:g} [{self.section}] x tier {self.tier_mult:g} [{self.tier}]"
                f" x novelty {self.novelty:g} | {len(self.members)} items | {self.lead.get('title')}")


def _recent(history: Sequence[Dict], today: date) -> List[Dict]:
    start = (today - timedelta(days=NOVELTY_DAYS)).isoformat()
    return [e for e in history if start <= str(e.get("date", "")) < today.isoformat()]


def _novelty(section: str, members: List[Dict], keys: FrozenSet[str], ids: FrozenSet[str],
             recent: List[Dict]) -> float:
    novelty = 1.0
    if any(e.get("section") == section for e in recent):
        novelty *= SECTION_REPEAT
    links = {m.get("link") for m in members}
    for e in recent:
        past = frozenset(e.get("key_tokens") or [])
        if e.get("url") in links or ids & past or _jaccard(keys, past) >= STORY_REPEAT_JACCARD:
            novelty *= STORY_REPEAT
            break
    return novelty


def _keywords(article: Dict) -> float:
    """main._score_article, without counting Hacker News boilerplate (URLs) as body text."""
    if HN_BOILERPLATE.search(article.get("summary") or ""):
        article = dict(article, summary="")
    return _score_article(article)


def _lead_member(members: List[Dict], tiers: Dict, now: datetime) -> Dict:
    def key(m: Dict):
        image = (m.get("image") or "").lower().startswith("https://")
        age = _age_hours(m, now)
        return (not image, -TIER_RANK[source_tier(m, tiers)], -_keywords(m),
                UNDATED_AGE_HOURS if age is None else age, m.get("link") or "")
    return min(members, key=key)


def score_clusters(clusters: List[List[Dict]], config: Dict, history: Sequence[Dict],
                   now: datetime) -> List[Scored]:
    """Score every cluster with the formula in the module docstring, best first."""
    weights = section_weights(config)
    order = list(weights)
    tiers = (config.get("story") or {}).get("source_tiers") or {}
    recent = _recent(history, now.date())
    scored = []
    for members in clusters:
        counts = Counter(m.get("section") for m in members)
        section = min(counts, key=lambda s: (-counts[s], -weights.get(s, 1.0),
                                             order.index(s) if s in order else len(order), str(s)))
        ids = frozenset().union(*(article_ids(m) for m in members))
        keywords = max(_keywords(m) for m in members)
        cov = coverage(members)
        hn = max(m.get("hn", 0) for m in members)
        relevance_pts = RELEVANCE_PTS * math.log2(1 + keywords)
        coverage_pts = COVERAGE_PTS * min(max(cov - 1, 0), COVERAGE_CAP)
        hard_pts = HARD_NEWS_PTS if any(is_hard_news(m) for m in members) else 0.0
        hn_pts = HN_PTS * math.log10(1 + hn)
        base = 1 + relevance_pts + coverage_pts + hard_pts + hn_pts

        ages = [a for a in (_age_hours(m, now) for m in members) if a is not None]
        age = min(ages) if ages else None
        fresh = freshness(UNDATED_AGE_HOURS if age is None else age)
        tier = max((source_tier(m, tiers) for m in members), key=TIER_RANK.__getitem__)
        lead = _lead_member(members, tiers, now)
        novelty = _novelty(section, members, key_tokens(lead, ids), ids, recent)
        weight = weights.get(section, 1.0)
        score = base * fresh * weight * TIER_MULT[tier] * novelty
        scored.append(Scored(members, lead, section, cov, ids, keywords, relevance_pts, coverage_pts, hard_pts,
                             hn, hn_pts, base, age, fresh, weight, tier, TIER_MULT[tier], novelty, score))
    scored.sort(key=lambda s: (-s.score, s.lead.get("title") or "", s.lead.get("link") or ""))
    return scored


def load_history(path: Path) -> List[Dict]:
    """Past leads, oldest first. A missing file is empty; a malformed one raises ValueError."""
    if not path.exists():
        return []
    try:
        history = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        raise ValueError(f"{path.name}: not valid JSON ({e})") from e
    if not isinstance(history, list) or not all(isinstance(e, dict) for e in history):
        raise ValueError(f"{path.name}: must be a JSON list of objects")
    return history


def record_lead(history: List[Dict], today: date, url: str, title: str, section: Optional[str],
                key_tokens) -> List[Dict]:
    """Replace today's entry with this lead and keep the newest HISTORY_CAP entries."""
    entry = {"date": today.isoformat(), "url": url, "title": title, "section": section,
             "key_tokens": sorted(key_tokens)}
    kept = [e for e in history if e.get("date") != entry["date"]] + [entry]
    kept.sort(key=lambda e: str(e.get("date", "")))
    return kept[-HISTORY_CAP:]


def save_history(path: Path, history: List[Dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(history, indent=2, ensure_ascii=False) + "\n")


def _pinned_date(value, name: str) -> date:
    if isinstance(value, datetime):
        raise ValueError(f"{name}: until must be a date (YYYY-MM-DD), got {value!r}")
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        raise ValueError(f"{name}: until must be a date (YYYY-MM-DD), got {value!r}") from None


def load_pinned(path: Path, today: date) -> Optional[Dict]:
    """Editor's pick from pinned.yaml, or None if absent, empty or expired. Invalid files raise ValueError."""
    if not path.exists():
        return None
    name = path.name
    try:
        data = yaml.safe_load(path.read_text())
    except yaml.YAMLError as e:
        raise ValueError(f"{name}: not valid YAML ({e})") from e
    if data is None:
        return None
    if not isinstance(data, dict):
        raise ValueError(f"{name}: must be key: value pairs (url, title, note, until)")
    unknown = set(data) - PINNED_FIELDS
    if unknown:
        raise ValueError(f"{name}: unknown field(s) {', '.join(sorted(map(str, unknown)))}")
    url = data.get("url")
    if not isinstance(url, str) or not _web_link(url):
        raise ValueError(f"{name}: url must be an http(s) link, got {url!r}")
    if "until" not in data:
        raise ValueError(f"{name}: needs 'until' (last day to show the pick, YYYY-MM-DD)")
    until = _pinned_date(data["until"], name)
    for field in ("title", "note"):
        if data.get(field) is not None and not isinstance(data[field], str):
            raise ValueError(f"{name}: {field} must be text, got {data[field]!r}")
    if until < today:
        logger.info(f"{name}: pick expired on {until}; ignoring it")
        return None
    return {"url": url.strip(), "title": data.get("title"), "note": data.get("note"), "until": until}


@dataclass
class Story:
    title: str
    link: str
    summary: str
    source: str
    published: Optional[datetime]
    image: Optional[str]
    section: Optional[str]
    coverage: int = 1
    ids: List[str] = field(default_factory=list)
    age_hours: Optional[float] = None
    also: List[Tuple[str, str]] = field(default_factory=list)
    note: Optional[str] = None
    pinned: bool = False
    key_tokens: FrozenSet[str] = frozenset()
    scored: List[Scored] = field(default_factory=list)


def _also(members: List[Dict], lead: Dict) -> List[Tuple[str, str]]:
    seen = {domain(lead.get("link"))}
    also = []
    for m in members:
        host = domain(m.get("link"))
        if host and host not in seen:
            seen.add(host)
            also.append((host, m["link"]))
    return also[:ALSO_CAP]


def _same_url(a: str, b: str) -> bool:
    return (a or "").strip().rstrip("/") == (b or "").strip().rstrip("/")


def pick_story(feed: Dict[str, List[Dict]], config: Dict, history: Sequence[Dict], pinned: Optional[Dict],
               now: datetime) -> Optional[Story]:
    """Story of the day from every fetched article (before the per-section cut), or None if there are none."""
    scored = score_clusters(cluster(candidates(feed)), config, history, now)
    chosen, lead = None, None
    if pinned:
        for s in scored:
            lead = next((m for m in s.members if _same_url(m.get("link"), pinned["url"])), None)
            if lead:
                chosen = s
                break
        if not chosen:
            title = pinned.get("title") or pinned["url"]
            return Story(title=title, link=pinned["url"], summary="", source=domain(pinned["url"]), published=None,
                         image=None, section=None, note=pinned.get("note"), pinned=True,
                         key_tokens=title_tokens(title), scored=scored)
    elif scored:
        chosen, lead = scored[0], scored[0].lead
    else:
        return None
    return Story(title=(pinned or {}).get("title") or lead.get("title") or "Untitled", link=lead["link"],
                 summary=lead.get("summary") or "", source=lead.get("source") or "",
                 published=lead.get("published"), image=lead.get("image"), section=chosen.section,
                 coverage=chosen.coverage, ids=sorted(chosen.ids), age_hours=chosen.age_hours,
                 also=_also(chosen.members, lead), note=(pinned or {}).get("note"), pinned=bool(pinned),
                 key_tokens=key_tokens(lead, chosen.ids), scored=scored)
