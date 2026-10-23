"""
Build the public site: today's feed plus Mark's writing, written to public/.
"""

import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple

from main import load_config, select_articles
from src import enrich, medium, site_builder, story
from src.content_aggregator import ContentAggregator
from src.hn import min_points
from src.posts import load_local_posts, render_markdown_file

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

MEDIUM_FEED = "https://medium.com/feed/@mark-mishaev"
TOP_CLUSTERS_LOGGED = 5


def fetch_feed(config: dict, aggregator) -> Tuple[Dict[str, List[Dict]], Dict[str, List[Dict]]]:
    """All fetched articles, and the same selection as the email (main.select_articles)."""
    raw = aggregator.aggregate_content(config['topics'])
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
         now: datetime = None, fetch_meta=enrich.fetch_meta,
         og_cache_path: Path = Path("data/og-cache.json")) -> int:
    config = config or load_config()
    now = now or datetime.now(timezone.utc)
    try:
        pinned = story.load_pinned(pinned_path, now.date())
        history = story.load_history(history_path)
        story.section_weights(config)
        story.lead_min_hn_points(config)
        min_points(config, 'section_min_hn_points')
    except ValueError as e:
        logger.error(f"Not building: {e}")
        return 1

    aggregator = aggregator or ContentAggregator(hours_back=48)
    raw, feed = fetch_feed(config, aggregator)
    total = sum(len(articles) for articles in feed.values())
    if total == 0:
        logger.error("Fetched zero articles across all topics; not building, so the live site stays as it is")
        return 1

    lead = story.pick_story(raw, config, history, pinned, now)
    og_cache = enrich.load_cache(og_cache_path)
    started = time.monotonic()
    targets = _rendered(raw, feed, lead)
    counts = enrich.enrich(targets, og_cache, now.date(), fetch=fetch_meta)
    logger.info(f"Page metadata: {counts['fetched']} fetched, {counts['cached']} cached, "
                f"{counts['og_images']} og:images in {time.monotonic() - started:.1f}s")
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

    site_builder.build(feed, posts, about_html, out_dir, now, story=lead)
    enrich.save_cache(og_cache_path, og_cache, now.date())
    if lead:
        history = story.record_lead(history, now.date(), url=lead.link, title=lead.title, section=lead.section,
                                    key_tokens=lead.key_tokens)
        story.save_history(history_path, history)
    logger.info(f"Built site in {out_dir}: {total} articles, {len(posts)} posts")
    return 0


if __name__ == "__main__":
    sys.exit(main())
