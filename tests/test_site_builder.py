import re
from datetime import datetime, timezone

import yaml

from src import site_builder

NOW = datetime(2026, 10, 22, 6, 0, tzinfo=timezone.utc)
IMG = "https://img.example.com/{}.jpg"


def article(title="Title", link=None, published=NOW, summary="Summary", source="Src", image=None):
    link = link if link is not None else f"https://example.com/{re.sub(r'[^a-z0-9]', '', title.lower())}"
    return {"title": title, "link": link, "summary": summary, "published": published, "source": source,
            "image": image}


def medium_post(n, date):
    return {"title": f"Medium {n}", "url": f"https://medium.com/@mark-mishaev/p{n}", "date": date, "source": "medium"}


def local_post(slug="hello", date="2026-10-21"):
    return {"title": "Hello", "date": date, "slug": slug, "summary": "Hi", "html": "<p>Body</p>",
            "url": f"blog/{slug}/", "source": "local"}


def build(tmp_path, feed=None, posts=None):
    site_builder.build(feed or {"Topic": [article()]}, posts or [], "<p>About</p>", tmp_path, NOW)
    return (tmp_path / "index.html").read_text()


def block(html, cls):
    """Inner HTML of the first element whose class attribute starts with cls."""
    start = html.index(f'class="{cls}')
    return html[start:html.index("<!-- /" + cls + " -->", start)]


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


def test_empty_topic_hidden(tmp_path):
    html = build(tmp_path, {"Full Topic": [article()], "Empty Topic": []})

    assert "Full Topic" in html
    assert "Empty Topic" not in html


def test_chips_in_section_order_with_colors(tmp_path):
    html = build(tmp_path, {"First": [article("a")], "Empty": [], "Third": [article("b")]})
    chips = block(html, "chips")

    assert re.findall(r'href="#([a-z-]+)"', chips) == ["first", "third"]
    assert site_builder.PALETTE[0] in chips
    assert site_builder.PALETTE[2] in chips


def test_lead_is_first_image_article_and_not_repeated(tmp_path):
    feed = {"No Pics": [article("Plain")],
            "Pics": [article("Text only"), article("Lead story", image=IMG.format(1)), article("Later pic", image=IMG.format(2))]}

    html = build(tmp_path, feed)
    lead = block(html, "lead")
    body = html.replace(lead, "")

    assert "Lead story" in lead and IMG.format(1) in lead
    assert "Lead story" not in body


def test_no_images_no_lead(tmp_path):
    html = build(tmp_path, {"Topic": [article("A"), article("B")]})

    assert 'class="lead' not in html
    assert "A" in html and "B" in html


def test_short_section_has_no_empty_cards(tmp_path):
    html = build(tmp_path, {"Topic": [article("Only one")]})

    assert html.count('class="card"') == 1
    assert 'class="more' not in html


def test_cards_then_headlines(tmp_path):
    html = build(tmp_path, {"Topic": [article(f"Story {i}") for i in range(8)]})

    assert html.count('class="card"') == 3
    assert block(html, "more").count('class="row"') == 5
    assert html.index("Story 2") < html.index('class="more')


def test_cards_prefer_articles_with_pictures(tmp_path):
    feed = {"Lead": [article("Lead", image=IMG.format(0))],
            "Topic": [article("Plain 1"), article("Plain 2"), article("Pic A", image=IMG.format(1)),
                      article("Plain 3"), article("Pic B", image=IMG.format(2))]}

    html = build(tmp_path, feed)
    topic = html[html.index('id="topic"'):]
    cards = topic[:topic.index('class="more')]

    assert re.findall(r"(Pic A|Pic B|Plain 1|Plain 2|Plain 3)</a>", cards) == ["Plain 1", "Pic A", "Pic B"]


def test_image_attrs_lazy_no_referrer(tmp_path):
    html = build(tmp_path, {"Topic": [article("Text"), article("Pic", image=IMG.format(1)), article("Pic 2", image=IMG.format(2))]})

    img = re.search(r'<img[^>]+' + re.escape(IMG.format(2)) + r'[^>]*>', html).group(0)
    assert 'loading="lazy"' in img
    assert 'referrerpolicy="no-referrer"' in img
    assert 'onerror="this.remove()"' in img


def test_http_image_not_rendered(tmp_path):
    html = build(tmp_path, {"Topic": [article("A", image="http://img.example.com/x.jpg"),
                                      article("B", image="javascript:alert(1)")]})

    assert "img.example.com" not in html
    assert "javascript:" not in html


def test_placeholder_shows_source(tmp_path):
    html = build(tmp_path, {"Topic": [article("No pic", source="The Hacker News")]})

    card = block(html, "card")
    assert '<span class="thumb-label">The Hacker News</span>' in card


def test_writing_strip_three_newest(tmp_path):
    posts = [medium_post(i, f"2026-0{i}-01") for i in range(1, 6)] + [local_post(date="2026-01-15")]

    strip = block(build(tmp_path, posts=posts), "writing")

    assert re.findall(r"Medium \d", strip) == ["Medium 5", "Medium 4", "Medium 3"]
    assert strip.count("on Medium") == 3


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


def test_about_page_has_photo_and_profile_links(tmp_path):
    build(tmp_path)

    page = (tmp_path / "about" / "index.html").read_text()

    assert 'href="https://www.linkedin.com/in/mark-mishaev-64a25452/"' in page
    assert 'href="https://medium.com/@mark-mishaev"' in page
    assert re.search(r'<img[^>]+src="\.\./static/mark\.jpg"', page)
    assert (tmp_path / "static" / "mark.jpg").exists()


def test_feed_xml_lists_both_sources(tmp_path):
    build(tmp_path, posts=[medium_post(1, "2026-04-17"), local_post()])

    xml = (tmp_path / "feed.xml").read_text()

    assert "https://medium.com/@mark-mishaev/p1" in xml
    assert "https://markmishaev76.github.io/ai-daily-content-collector/blog/hello/" in xml


def test_excerpt_cuts_to_limit():
    assert len(site_builder.excerpt("word " * 200)) <= 300
    assert site_builder.excerpt("short") == "short"
