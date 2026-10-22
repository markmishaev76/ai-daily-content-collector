"""
Build the public site: today's feed plus Mark's writing, written to public/.
"""

import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

from main import load_config, select_articles
from src import medium, site_builder
from src.content_aggregator import ContentAggregator
from src.posts import load_local_posts, render_markdown_file

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

MEDIUM_FEED = "https://medium.com/feed/@mark-mishaev"


def select_feed(config: dict, aggregator) -> Dict[str, List[Dict]]:
    """Same selection as the email: aggregate, then main.select_articles."""
    feed = aggregator.aggregate_content(config['topics'])
    return select_articles(feed, config['brief']['max_articles_per_topic'])


def main(out_dir: Path = Path("public"), config: dict = None, aggregator=None,
         fetch_medium=medium.fetch_medium_posts, data_path: Path = Path("data/medium-posts.json"),
         posts_dir: Path = Path("posts"), about_path: Path = Path("about.md")) -> int:
    config = config or load_config()
    aggregator = aggregator or ContentAggregator(hours_back=48)

    feed = select_feed(config, aggregator)
    total = sum(len(articles) for articles in feed.values())
    if total == 0:
        logger.error("Fetched zero articles across all topics; not building, so the live site stays as it is")
        return 1

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

    site_builder.build(feed, posts, about_html, out_dir, datetime.now(timezone.utc))
    logger.info(f"Built site in {out_dir}: {total} articles, {len(posts)} posts")
    return 0


if __name__ == "__main__":
    sys.exit(main())
