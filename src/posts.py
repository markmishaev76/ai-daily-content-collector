"""
Local blog posts: Markdown files with a YAML front matter block.
"""

import re
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List

import markdown
import yaml

FILENAME_RE = re.compile(r'^(\d{4}-\d{2}-\d{2})-([a-z0-9-]+)\.md$')
FRONT_MATTER_RE = re.compile(r'\A---\n(.*?)\n---\n?(.*)\Z', re.S)


def _parse(path: Path) -> Dict:
    match = FILENAME_RE.match(path.name)
    if not match:
        raise ValueError(f"{path.name}: post files must be named YYYY-MM-DD-slug.md (lowercase slug)")

    fm = FRONT_MATTER_RE.match(path.read_text())
    if not fm:
        raise ValueError(f"{path.name}: missing front matter block")
    meta = yaml.safe_load(fm.group(1)) or {}
    if not isinstance(meta, dict):
        raise ValueError(f"{path.name}: front matter must be key: value pairs")

    for field in ('title', 'date'):
        if not meta.get(field):
            raise ValueError(f"{path.name}: front matter needs '{field}'")

    post_date = meta['date']
    if isinstance(post_date, datetime) or not isinstance(post_date, date):
        raise ValueError(f"{path.name}: date must be YYYY-MM-DD, got {post_date!r}")
    post_date = post_date.isoformat()

    slug = match.group(2)
    return {
        'title': str(meta['title']),
        'date': str(post_date),
        'slug': slug,
        'summary': meta.get('summary'),
        'html': markdown.markdown(fm.group(2), extensions=['fenced_code', 'tables']),
        'url': f"blog/{slug}/",
        'source': 'local',
    }


def load_local_posts(posts_dir: Path) -> List[Dict]:
    """Load every post in posts_dir, newest first. Invalid files raise ValueError."""
    if not posts_dir.exists():
        return []
    posts = [_parse(p) for p in posts_dir.glob('*.md')]
    return sorted(posts, key=lambda p: p['date'], reverse=True)


def render_markdown_file(path: Path) -> str:
    return markdown.markdown(path.read_text(), extensions=['fenced_code', 'tables'])
