import re
from datetime import datetime, timezone

import yaml

from src import site_builder

NOW = datetime(2026, 10, 22, 6, 0, tzinfo=timezone.utc)


def article(title="Title", link="https://example.com/a", published=NOW, summary="Summary", source="Src"):
    return {"title": title, "link": link, "summary": summary, "published": published, "source": source}


def medium_post(n, date):
    return {"title": f"Medium {n}", "url": f"https://medium.com/@mark-mishaev/p{n}", "date": date, "source": "medium"}


def local_post(slug="hello", date="2026-10-21"):
    return {"title": "Hello", "date": date, "slug": slug, "summary": "Hi", "html": "<p>Body</p>",
            "url": f"blog/{slug}/", "source": "local"}


def build(tmp_path, feed=None, posts=None):
    site_builder.build(feed or {"Topic": [article()]}, posts or [], "<p>About</p>", tmp_path, NOW)
    return (tmp_path / "index.html").read_text()


def test_script_in_title_is_escaped(tmp_path):
    html = build(tmp_path, {"Topic": [article(title="<script>alert(1)</script>")]})

    assert "<script>alert(1)" not in html
    assert "&lt;script&gt;alert(1)" in html


def test_javascript_link_not_rendered(tmp_path):
    html = build(tmp_path, {"Topic": [article(title="Bad link", link="javascript:alert(1)"),
                                      article(title="No link", link="")]})

    assert "javascript:" not in html
    assert "Bad link" in html and "No link" in html


def test_anchor_ids_unique_and_valid():
    with open("config.yaml") as f:
        names = [t["name"] for t in yaml.safe_load(f)["topics"]]

    ids = [site_builder.anchor_id(n) for n in names]

    assert len(set(ids)) == len(names)
    assert all(re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", i) for i in ids)


def test_empty_topic_hidden_from_nav_and_body(tmp_path):
    html = build(tmp_path, {"Full Topic": [article()], "Empty Topic": []})

    assert "Full Topic" in html
    assert "Empty Topic" not in html


def test_writing_column_shows_five_newest_with_medium_label(tmp_path):
    posts = [medium_post(i, f"2026-0{i}-01") for i in range(1, 7)] + [local_post(date="2026-01-15")]

    html = build(tmp_path, posts=posts)
    writing = html.split('class="writing"')[1]

    assert [t for t in re.findall(r"Medium \d", writing)] == ["Medium 6", "Medium 5", "Medium 4", "Medium 3", "Medium 2"]
    assert "Hello" not in writing
    assert writing.count("on Medium") == 5


def test_post_page_links_use_relative_root(tmp_path):
    build(tmp_path, posts=[local_post(slug="x")])

    page = (tmp_path / "blog" / "x" / "index.html").read_text()

    assert 'href="../../static/style.css"' in page
    assert "<p>Body</p>" in page


def test_undated_item_renders_last_without_date(tmp_path):
    html = build(tmp_path, {"Topic": [article(title="Undated", published=None, source="NoDateSrc"),
                                      article(title="Dated")]})

    assert html.index("Dated") < html.index("Undated")
    assert "NoDateSrc</div>" in html


def test_feed_xml_lists_both_sources(tmp_path):
    build(tmp_path, posts=[medium_post(1, "2026-04-17"), local_post()])

    xml = (tmp_path / "feed.xml").read_text()

    assert "https://medium.com/@mark-mishaev/p1" in xml
    assert "https://markmishaev76.github.io/ai-daily-content-collector/blog/hello/" in xml


def test_excerpt_cuts_to_limit():
    assert len(site_builder.excerpt("word " * 200)) <= 300
    assert site_builder.excerpt("short") == "short"
