import re
from datetime import datetime, timezone

import pytest
import yaml

from src import site_builder, story

NOW = datetime(2026, 10, 22, 6, 0, tzinfo=timezone.utc)
IMG = "https://img.example.com/{}.jpg"


def article(title="Title", link=None, published=NOW, summary="Summary", source="Src", image=None, **extra):
    link = link if link is not None else f"https://example.com/{re.sub(r'[^a-z0-9]', '', title.lower())}"
    return {"title": title, "link": link, "summary": summary, "published": published, "source": source,
            "image": image, **extra}


def medium_post(n, date):
    return {"title": f"Medium {n}", "url": f"https://medium.com/@mark-mishaev/p{n}", "date": date, "source": "medium"}


def local_post(slug="hello", date="2026-10-21"):
    return {"title": "Hello", "date": date, "slug": slug, "summary": "Hi", "html": "<p>Body</p>",
            "url": f"blog/{slug}/", "source": "local"}


def build(tmp_path, feed=None, posts=None, story=None):
    site_builder.build(feed or {"Topic": [article()]}, posts or [], "<p>About</p>", tmp_path, NOW, story=story)
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


def lead_story(title="Lead story", link="https://example.com/leadstory", section="Pics", image=None, **kw):
    return story.Story(title=title, link=link, summary=kw.pop("summary", "Lead summary"), source=kw.pop("source", "Src"),
                       published=NOW, image=image, section=section, **kw)


def test_lead_not_repeated_in_sections(tmp_path):
    feed = {"No Pics": [article("Plain")],
            "Pics": [article("Text only"), article("Lead story", image=IMG.format(1)), article("Later pic", image=IMG.format(2))]}

    html = build(tmp_path, feed, story=lead_story(image=IMG.format(1)))
    lead = block(html, "lead")
    body = html.replace(lead, "")

    assert "Lead story" in lead and IMG.format(1) in lead
    assert "Lead story" not in body
    assert "Later pic" in body
    assert site_builder.PALETTE[1] in lead


def test_lead_without_image_renders_placeholder(tmp_path):
    html = build(tmp_path, {"Pics": [article("Other")]}, story=lead_story())
    lead = block(html, "lead")

    assert 'class="lead-image placeholder"' in lead
    assert '<span class="placeholder-label">Pics</span>' in lead
    assert "<img" not in lead


def test_image_credit_rendered_escaped_only_when_set(tmp_path):
    credited = lead_story(image=IMG.format(1), image_credit="The <Hacker> News")
    own = lead_story(image=IMG.format(1))

    lead = block(build(tmp_path, {"Pics": [article("Other")]}, story=credited), "lead")
    plain = block(build(tmp_path, {"Pics": [article("Other")]}, story=own), "lead")

    assert '<span class="image-credit">Image: The &lt;Hacker&gt; News</span>' in lead
    assert "image-credit" not in plain


def test_why_labels_rendered(tmp_path):
    s = lead_story(coverage=6, ids=["CVE-2026-109618"], age_hours=2.4)

    lead = block(build(tmp_path, {"Pics": [article("Other")]}, story=s), "lead")
    labels = re.findall(r"<li>(.*?)</li>", block(lead, "why"))

    assert labels == ["6 sources", "CVE-2026-109618", "Pics", "2h ago"]


def test_age_label_formats():
    assert site_builder.age_label(None) is None
    assert site_builder.age_label(0.2) == "under 1h ago"
    assert site_builder.age_label(23.9) == "23h ago"
    assert site_builder.age_label(49) == "2d ago"


def test_also_covered_escaped_and_safe(tmp_path):
    s = lead_story(also=[("a<b>.com", "https://a.com/1"), ("evil.com", "javascript:alert(1)"), ("c.com", "http://c.com/2")])

    lead = block(build(tmp_path, {"Pics": [article("Other")]}, story=s), "lead")
    also = block(lead, "also")

    assert "Also covered by" in also
    assert "a&lt;b&gt;.com" in also and "<b>" not in also
    assert "javascript:" not in lead and "evil.com" not in lead
    assert '<a href="http://c.com/2" rel="noopener noreferrer">c.com</a>' in also


def test_lead_title_and_labels_escaped(tmp_path):
    s = lead_story(title="<script>x</script>", ids=["<i>"], link="javascript:alert(1)")

    lead = block(build(tmp_path, {"Pics": [article("Other")]}, story=s), "lead")

    assert "<script>" not in lead and "<i>" not in lead and "javascript:" not in lead
    assert "&lt;script&gt;" in lead


def test_pinned_lead_rendered_with_note(tmp_path):
    s = lead_story(section=None, pinned=True, note="Mark's <pick>", summary="")

    lead = block(build(tmp_path, {"Pics": [article("Other")]}, story=s), "lead")

    assert "Editor&#39;s pick" in lead or "Editor's pick" in lead
    assert "Mark&#39;s &lt;pick&gt;" in lead
    assert '<span class="placeholder-label">' in lead


def test_no_story_no_lead(tmp_path):
    html = build(tmp_path, {"Topic": [article("A", image=IMG.format(1)), article("B")]})

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


def test_tile_without_image_shows_logo_and_domain(tmp_path):
    html = build(tmp_path, {"Topic": [article("No pic", link="https://www.example.com/a", source="Feed: raw-tag",
                                              icon="https://example.com/touch.png")]})

    card = block(html, "card")
    tile = card[:card.index("</div>")]
    assert '<img class="logo" src="https://example.com/touch.png"' in tile
    assert '<span class="tile-domain">example.com</span>' in tile
    assert "raw-tag" not in tile


def test_tile_without_image_or_icon_shows_domain_only(tmp_path):
    card = block(build(tmp_path, {"Topic": [article("No pic", link="https://x.org/a",
                                                    icon="http://x.org/fav.ico")]}), "card")

    assert '<span class="tile-domain">x.org</span>' in card
    assert "<img" not in card


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
    assert "https://thedailybrief.dev/blog/hello/" in xml


def test_excerpt_cuts_to_limit():
    assert len(site_builder.excerpt("word " * 200)) <= 300
    assert site_builder.excerpt("short") == "short"


def meta(html, prop):
    match = re.search(rf'<meta (?:property|name)="{re.escape(prop)}" content="([^"]*)"', html)
    return match.group(1) if match else None


def test_home_page_has_fixed_share_preview(tmp_path):
    html = build(tmp_path, {"Topic": [article(title="Todays lead story", image=IMG.format(1))]})

    assert meta(html, "og:title") == "The Daily Brief"
    assert meta(html, "og:url") == "https://thedailybrief.dev/"
    assert meta(html, "og:image") == "https://thedailybrief.dev/static/share.png"
    assert meta(html, "twitter:card") == "summary_large_image"
    assert "security and AI engineering" in meta(html, "og:description")
    assert "Todays lead story" not in meta(html, "og:title")
    assert (tmp_path / "static" / "share.png").exists()


def test_post_page_share_preview_uses_post(tmp_path):
    build(tmp_path, posts=[local_post(slug="x")])

    page = (tmp_path / "blog" / "x" / "index.html").read_text()

    assert meta(page, "og:title") == "Hello"
    assert meta(page, "og:description") == "Hi"
    assert meta(page, "og:url") == "https://thedailybrief.dev/blog/x/"
    assert meta(page, "og:type") == "article"


def test_pages_link_favicons(tmp_path):
    build(tmp_path, posts=[local_post(slug="x")])

    home = (tmp_path / "index.html").read_text()
    post = (tmp_path / "blog" / "x" / "index.html").read_text()

    assert '<link rel="icon" href="static/favicon.svg" type="image/svg+xml">' in home
    assert '<link rel="icon" href="../../static/favicon.svg" type="image/svg+xml">' in post
    assert '<link rel="apple-touch-icon" href="static/apple-touch-icon.png">' in home
    for name in ("favicon.svg", "favicon-32.png", "apple-touch-icon.png"):
        assert (tmp_path / "static" / name).exists()


def test_pages_load_cloudflare_analytics(tmp_path):
    build(tmp_path, posts=[local_post(slug="x")])

    for page in ("index.html", "blog/index.html", "blog/x/index.html", "about/index.html"):
        html = (tmp_path / page).read_text()
        assert 'src="https://static.cloudflareinsights.com/beacon.min.js"' in html
        assert '{&#34;token&#34;: &#34;753e85ce1c8b4659818c074e30218583&#34;}' in html \
            or '{"token": "753e85ce1c8b4659818c074e30218583"}' in html


@pytest.mark.parametrize("raw, clean", [
    ('Hacker News - Newest: "MCP"', "Hacker News"),
    ("Hacker News: Front Page", "Hacker News"),
    ("Hugging Face - Blog", "Hugging Face"),
    ("Simon Willison's Weblog: model-context-protocol", "Simon Willison"),
    ("The Hacker News", "The Hacker News"),
    ("Krebs on Security", "Krebs on Security"),
    ("AWS Security Blog", "AWS Security Blog"),
    ("https://example.com/feed.xml", "example.com"),
    ("", ""),
])
def test_clean_source(raw, clean):
    assert site_builder.clean_source(raw) == clean


HN_FEED = "https://hnrss.org/newest?q=MCP"
HN_SUMMARY = "Article URL: https://github.com/x/y Comments URL: https://news.ycombinator.com/item?id=1 Points: 12 # Comments: 3"


def hn_article(title="HN item", **kw):
    return dict(article(title, link="https://github.com/x/y", summary=HN_SUMMARY, source='Hacker News - Newest: "MCP"'),
                feed=HN_FEED, **kw)


def test_hn_card_shows_domain_and_counts_not_boilerplate(tmp_path):
    html = build(tmp_path, {"Topic": [hn_article()]})
    card = block(html, "card")

    assert "Article URL" not in html and "Comments URL" not in html
    assert '<div class="meta">github.com via Hacker News · Oct 22</div>' in card
    assert "<p>12 points · 3 comments</p>" in card


def test_hn_card_uses_og_description_and_counts_in_meta(tmp_path):
    card = block(build(tmp_path, {"Topic": [hn_article(og_description="A tool for <things>.")]}), "card")

    assert "<p>A tool for &lt;things&gt;.</p>" in card
    assert "github.com via Hacker News · Oct 22 · 12 points · 3 comments" in card


def test_hn_row_meta_has_counts(tmp_path):
    html = build(tmp_path, {"Topic": [article(f"S{i}") for i in range(3)] + [hn_article()]})

    assert "github.com via Hacker News · Oct 22 · 12 points · 3 comments" in block(html, "more")


def test_clean_names_on_cards(tmp_path):
    card = block(build(tmp_path, {"Topic": [article("A", source="Hugging Face - Blog")]}), "card")

    assert "Hugging Face · Oct 22" in card and "- Blog" not in card


def test_hn_lead_uses_description_not_boilerplate(tmp_path):
    s = lead_story(summary=HN_SUMMARY, source='Hacker News - Newest: "MCP"', feed=HN_FEED,
                   link="https://github.com/x/y", description="Real description")

    lead = block(build(tmp_path, {"Pics": [article("Other")]}, story=s), "lead")

    assert "Real description" in lead and "Article URL" not in lead
    assert "github.com via Hacker News" in lead


def pulse_item(title="Thread", **kw):
    item = {"title": title, "source": "r/ClaudeAI", "points": 1234, "unit": "upvotes", "comments": 56,
            "created": datetime(2026, 10, 21, 3, 0, tzinfo=timezone.utc),
            "thread": "https://www.reddit.com/r/ClaudeAI/comments/abc/t/", "link": None, "image": None}
    item.update(kw)
    return item


def build_pulse(tmp_path, items, story=None):
    site_builder.build({"Topic": [article("Section story")]}, [local_post()], "<p>About</p>", tmp_path, NOW,
                       story=story, pulse=items)
    return (tmp_path / "index.html").read_text()


def test_pulse_under_lead_above_writing_and_sections_with_chip(tmp_path):
    html = build_pulse(tmp_path, [pulse_item()], story=lead_story(section="Topic"))

    assert html.index("<!-- /lead -->") < html.index('id="the-pulse"') < html.index('class="writing"') \
        < html.index('id="topic"')
    assert re.findall(r'href="#([a-z-]+)"', block(html, "chips")) == ["the-pulse", "topic"]
    pulse = block(html, "pulse")
    assert '<a href="https://www.reddit.com/r/ClaudeAI/comments/abc/t/" rel="noopener noreferrer">Thread</a>' in pulse
    assert "r/ClaudeAI · 1.2k upvotes · 56 comments · 1d ago" in pulse
    assert '<span class="tile-domain">r/ClaudeAI</span>' in pulse


def test_pulse_link_post_shows_external_link_and_preview(tmp_path):
    pulse = block(build_pulse(tmp_path, [pulse_item(link="https://blog.example.com/x",
                                                    image="https://preview.redd.it/a.jpg")]), "pulse")

    assert '<a href="https://blog.example.com/x" rel="noopener noreferrer">blog.example.com ↗</a>' in pulse
    assert 'src="https://preview.redd.it/a.jpg"' in pulse


def test_pulse_titles_escaped_and_bad_links_dropped(tmp_path):
    pulse = block(build_pulse(tmp_path, [pulse_item("<script>alert(1)</script>", thread="javascript:alert(1)",
                                                    link="javascript:alert(2)", image="http://x/a.jpg")]), "pulse")

    assert "<script>" not in pulse and "&lt;script&gt;" in pulse
    assert "javascript:" not in pulse and "http://x/a.jpg" not in pulse


def test_pulse_feed_item_with_other_discussion_and_subtitle(tmp_path):
    html = build_pulse(tmp_path, [pulse_item("Post", source="Hacker News", points=321, unit="points",
                                             thread="https://news.ycombinator.com/item?id=1",
                                             link="https://blog.example.com/x",
                                             also=[{"source": "Lobsters", "thread": "https://lobste.rs/s/z/x"},
                                                   {"source": "Bad", "thread": "javascript:alert(1)"}]),
                                  pulse_item(source="Lobsters", points=40, unit="points")])
    pulse = block(html, "pulse")

    assert "Top threads on Hacker News and Lobsters, last 24 hours" in html
    assert "Hacker News · 321 points · 56 comments · 1d ago" in pulse
    assert '<a href="https://news.ycombinator.com/item?id=1" rel="noopener noreferrer">Post</a>' in pulse
    assert '<a href="https://blog.example.com/x" rel="noopener noreferrer">blog.example.com ↗</a>' in pulse
    assert 'also on <a href="https://lobste.rs/s/z/x" rel="noopener noreferrer">Lobsters</a>' in pulse
    assert "javascript:" not in pulse and ">Bad<" not in pulse
    assert '<span class="tile-domain">blog.example.com</span>' in pulse


def test_pulse_subtitle_groups_subreddits_as_reddit(tmp_path):
    html = build_pulse(tmp_path, [pulse_item(), pulse_item(source="r/cursor")])

    assert "Top threads on Reddit, last 24 hours" in html


def test_pulse_hidden_when_empty(tmp_path):
    for items in (None, []):
        html = build_pulse(tmp_path, items)
        assert "the-pulse" not in html and "The Pulse" not in html


def test_compact_counts():
    assert [site_builder.compact(n) for n in (999, 1000, 1234, 15600, 1_250_000)] == ["999", "1k", "1.2k", "15.6k", "1.2M"]
