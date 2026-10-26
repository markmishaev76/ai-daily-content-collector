"""
Build the public site: today's feed plus Mark's writing, written to public/.
"""

import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple

from main import load_config, select_articles
from src import briefs, enrich, learn, medium, pulse, seen, site_builder, story
from src.content_aggregator import ContentAggregator, validate_sources
from src.hn import min_points
from src.posts import load_local_posts, render_markdown_file

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

MEDIUM_FEED = "https://medium.com/feed/@mark-mishaev"
TOP_CLUSTERS_LOGGED = 5


def fetch_feed(config: dict, aggregator, keep=None) -> Tuple[Dict[str, List[Dict]], Dict[str, List[Dict]]]:
    """All fetched articles (narrowed by `keep`, e.g. seen.unseen), and the same selection as the email
    (main.select_articles)."""
    raw = aggregator.aggregate_content(config['topics'])
    if keep:
        raw = keep(raw)
    return raw, select_articles(raw, config['brief']['max_articles_per_topic'],
                                min_points(config, 'section_min_hn_points'))


def _rendered(raw: Dict[str, List[Dict]], feed: Dict[str, List[Dict]], lead) -> List[Dict]:
    """Raw articles shown on the page: the sections plus the lead's story cluster (for its image)."""
    links = {a.get('link') for articles in feed.values() for a in articles}
    if lead:
        links.add(lead.link)
        cluster = next((s for s in lead.scored if any(m.get('link') == lead.link for m in s.members)), None)
        links |= {m.get('link') for m in (cluster.members if cluster else [])}
    return [a for articles in raw.values() for a in articles if a.get('link') in links]


def _fetch_pulse(config: dict, now: datetime, shown, collect=None):
    """The Pulse's items minus links in `shown`, or None (section hidden) when no source can be read;
    never fails the build."""
    collect = collect or (lambda c, n, s: pulse.collect(c, n, env=os.environ, shown=s))
    try:
        items, counts = collect(config, now, shown)
    except pulse.PulseUnavailable as e:
        logger.warning(f"The Pulse hidden: {e}")
        return None
    logger.info("The Pulse: " + ", ".join(f"{source} {'failed' if n is None else n}" for source, n in counts.items())
                + f"; showing {len(items)}")
    if not items:
        logger.warning("The Pulse hidden: no thread qualified")
    return items or None


def _fetch_learn(config: dict, now: datetime, days: int, collect=None) -> Dict:
    """Learn videos; empty lists (teaser hidden, page says so) when no channel can be read. Never fails the build."""
    collect = collect or learn.collect
    try:
        videos, counts = collect(config, now)
    except learn.LearnUnavailable as e:
        logger.warning(f"Learn hidden: {e}")
        return {"top": [], "channels": [], "days": days}
    logger.info("Learn: " + ", ".join(f"{name} {'failed' if n is None else n}" for name, n in counts.items())
                + f"; showing {len(videos['top'])}")
    return videos


def _tile_counts(feed: Dict[str, List[Dict]]) -> Dict[str, int]:
    counts = {"feed images": 0, "og:images": 0, "logos": 0, "plain tiles": 0}
    for article in (a for articles in feed.values() for a in articles):
        if site_builder.safe_image(article.get("image")):
            counts["og:images" if article.get("og_image") else "feed images"] += 1
        elif site_builder.safe_image(article.get("icon")):
            counts["logos"] += 1
        else:
            counts["plain tiles"] += 1
    return counts


def main(out_dir: Path = Path("public"), config: dict = None, aggregator=None,
         fetch_medium=medium.fetch_medium_posts, data_path: Path = Path("data/medium-posts.json"),
         posts_dir: Path = Path("posts"), about_path: Path = Path("about.md"),
         history_path: Path = Path("data/lead-history.json"), pinned_path: Path = Path("pinned.yaml"),
         seen_path: Path = Path("data/seen.json"), briefs_dir: Path = Path("data/briefs"),
         now: datetime = None, fetch_meta=enrich.fetch_meta,
         og_cache_path: Path = Path("data/og-cache.json"), collect_pulse=None, collect_learn=None) -> int:
    config = config or load_config()
    now = now or datetime.now(timezone.utc)
    try:
        pinned = story.load_pinned(pinned_path, now.date())
        history = story.load_history(history_path)
        shown_before = seen.load(seen_path)
        past_briefs = briefs.load(briefs_dir, now.date())
        validate_sources(config['topics'])
        story.section_weights(config)
        story.lead_min_hn_points(config)
        min_points(config, 'section_min_hn_points')
        pulse_settings = pulse.settings(config)
        learn_settings = learn.settings(config)
    except ValueError as e:
        logger.error(f"Not building: {e}")
        return 1

    aggregator = aggregator or ContentAggregator(hours_back=48)
    def keep(raw):
        fresh, skipped = seen.unseen(raw, shown_before, now.date())
        logger.info(f"Seen: skipped {skipped} articles shown on an earlier day")
        return fresh

    raw, feed = fetch_feed(config, aggregator, keep)
    total = sum(len(articles) for articles in feed.values())
    if total == 0:
        logger.error("Fetched zero articles across all topics; not building, so the live site stays as it is")
        return 1

    lead = story.pick_story(raw, config, history, pinned, now)
    rendered = _rendered(raw, feed, lead)
    shown = {a.get('link') for a in rendered} | ({lead.link} if lead else set())
    pulse_items = _fetch_pulse(config, now, shown, collect_pulse) if pulse_settings else None
    og_cache = enrich.load_cache(og_cache_path)
    started = time.monotonic()
    pulse_pages = [{"link": i["link"], "image": None, "feed": ""} for i in pulse_items or []
                   if i.get("link") and not i.get("image")]
    targets = rendered + pulse_pages
    counts = enrich.enrich(targets, og_cache, now.date(), fetch=fetch_meta)
    logger.info(f"Page metadata: {counts['fetched']} fetched, {counts['cached']} cached, "
                f"{counts['og_images']} og:images in {time.monotonic() - started:.1f}s")
    for item, page in zip([i for i in pulse_items or [] if i.get("link") and not i.get("image")], pulse_pages):
        item["image"], item["icon"] = page.get("image"), page.get("icon")
    lead = story.pick_story(raw, config, history, pinned, now)
    logger.info("Tiles: " + ", ".join(f"{n} {k}" for k, n in _tile_counts(feed).items()))
    for rank, scored in enumerate(lead.scored[:TOP_CLUSTERS_LOGGED] if lead else [], 1):
        logger.info(f"Story #{rank}: {scored.breakdown()}")
    if lead:
        logger.info(f"Lead{' (pinned)' if lead.pinned else ''}: {lead.title} <{lead.link}>")

    saved = medium.load_saved(data_path)
    fetched = fetch_medium(MEDIUM_FEED)
    if fetched is None:
        logger.warning("Medium feed unavailable; using saved posts")
        medium_posts = saved
    else:
        medium_posts = medium.merge_posts(saved, fetched)
        if medium.save(data_path, medium_posts):
            logger.info(f"Saved {len(medium_posts)} Medium posts to {data_path}")

    posts = load_local_posts(posts_dir) + medium_posts
    about_html = render_markdown_file(about_path) if about_path.exists() else ""

    videos = _fetch_learn(config, now, learn_settings["max_age_days"], collect_learn) if learn_settings else None
    today_brief = site_builder.build(feed, posts, about_html, out_dir, now, story=lead, pulse=pulse_items,
                                     learn=videos, briefs=past_briefs)
    briefs.save(briefs_dir, now.date(), today_brief)
    briefs.prune(briefs_dir, now.date())
    logger.info(f"Briefs: saved {now.date()}, past days available: {', '.join(sorted(past_briefs)) or 'none'}")
    enrich.save_cache(og_cache_path, og_cache, now.date())
    if lead:
        history = story.record_lead(history, now.date(), url=lead.link, title=lead.title, section=lead.section,
                                    key_tokens=lead.key_tokens)
        story.save_history(history_path, history)
    shown_links = [a.get('link') for articles in feed.values() for a in articles] + ([lead.link] if lead else [])
    seen.save(seen_path, seen.record(shown_before, shown_links, now.date()))
    logger.info(f"Built site in {out_dir}: {total} articles, {len(posts)} posts")
    return 0


if __name__ == "__main__":
    sys.exit(main())
