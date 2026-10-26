import json
import re
from datetime import datetime, timezone

from src import site_builder, story

NOW = datetime(2026, 10, 22, 6, 0, tzinfo=timezone.utc)


def item(title, link=None, **kw):
    slug = re.sub(r"[^a-z0-9]", "", title.lower())
    return dict({"title": title, "link": link or f"https://example.com/{slug}", "excerpt": "Ex", "source": "Src",
                 "date": "Oct 21", "image": None, "icon": None, "domain": "example.com", "hn": None}, **kw)


def past(day="2026-10-21", lead_title="Past lead", **sections):
    return {"date": day,
            "lead": {"title": lead_title, "link": "https://example.com/pastlead", "excerpt": "Lead excerpt",
                     "source": "Src", "date": "Oct 21", "image": "https://img.example.com/lead.jpg",
                     "image_credit": "The Register", "section": "Topic", "pinned": False, "note": None,
                     "labels": ["3 sources", "CVE-2026-1"],
                     "also": [{"name": "theregister.com", "link": "https://theregister.com/x"}]},
            "pulse": [{"title": "Pulse thread", "thread": "https://news.ycombinator.com/item?id=1",
                       "link": "https://blog.example.com/p", "link_domain": "blog.example.com", "source": "Hacker News",
                       "domain": "blog.example.com", "meta": "Hacker News · 300 points · 12 comments · 5h ago",
                       "also": [], "image": None, "icon": None}],
            "sections": sections.get("sections") or [{"name": "Topic", "cards": [item("Past card")], "more": [item("Past row")]}]}


def article(title, **kw):
    return dict({"title": title, "link": f"https://example.com/{title.lower().replace(' ', '')}", "summary": "Summary",
                 "published": NOW, "source": "Src", "image": None}, **kw)


def local_post():
    return {"title": "Hello", "date": "2026-10-21", "slug": "hello", "summary": "Hi", "html": "<p>Body</p>",
            "url": "blog/hello/", "source": "local"}


def build(tmp_path, briefs=None, **kw):
    feed = kw.pop("feed", {"Topic": [article("Today card")], "Other": [article("Other card")]})
    snap = site_builder.build(feed, kw.pop("posts", [local_post()]), "<p>About</p>", tmp_path, NOW,
                              briefs=briefs or {}, **kw)
    return snap


def page(tmp_path, day=None):
    return (tmp_path / (f"brief/{day}/index.html" if day else "index.html")).read_text()


def block(html, cls):
    start = html.index(f'class="{cls}')
    return html[start:html.index("<!-- /" + cls + " -->", start)]


def days(html):
    return block(html, "days")


def test_build_returns_render_ready_snapshot(tmp_path):
    lead = story.Story(title="Lead", link="https://example.com/lead", summary="Lead summary", source="Src", published=NOW,
                       image="https://img.example.com/l.jpg", image_credit="The Register", section="Topic", coverage=3,
                       also=[("theregister.com", "https://theregister.com/x")])
    pulse = [{"title": "Thread", "source": "Hacker News", "points": 300, "unit": "points", "comments": 12,
              "created": NOW, "thread": "https://news.ycombinator.com/item?id=1", "link": None, "image": None}]

    snap = build(tmp_path, story=lead, pulse=pulse,
                 feed={"Topic": [article("Card", image="https://img.example.com/c.jpg")], "Empty": []})

    assert snap["date"] == "2026-10-22"
    assert snap["lead"]["title"] == "Lead" and snap["lead"]["image_credit"] == "The Register"
    assert snap["lead"]["labels"][0] == "3 sources" and snap["lead"]["also"] == [{"name": "theregister.com", "link": "https://theregister.com/x"}]
    assert [s["name"] for s in snap["sections"]] == ["Topic"]
    assert set(snap["sections"][0]["cards"][0]) >= {"title", "link", "excerpt", "source", "date", "image", "icon", "domain", "hn"}
    assert snap["pulse"][0]["thread"] == "https://news.ycombinator.com/item?id=1"
    assert "color" not in snap["lead"] and "color" not in snap["sections"][0]
    json.dumps(snap)


def test_past_page_renders_full_brief_without_writing_or_learn(tmp_path):
    learn = {"top": [{"id": "WOszaC1WWbQ", "title": "Video", "channel": "AI Engineer", "views": 10, "per_day": 5.0,
                      "published": NOW}], "channels": [], "days": 30}
    build(tmp_path, briefs={"2026-10-21": past()}, learn=learn)
    html = page(tmp_path, "2026-10-21")

    assert "Brief · Wednesday, October 21, 2026" in html
    assert "You're viewing a past brief" in html and '<a href="../../">back to today →</a>' in html
    for text in ("Past lead", "Image: The Register", "Also covered by", "3 sources", "CVE-2026-1", "Pulse thread",
                 "Past card", "Past row", 'id="the-pulse"'):
        assert text in html
    assert 'class="writing"' not in html and 'id="learn"' not in html and "learn.js" not in html
    assert "Today card" not in html
    front = page(tmp_path)
    assert 'class="writing"' in front and 'id="learn"' in front and "Today · Thursday, October 22, 2026" in front


def test_past_page_canonical_and_og_url(tmp_path):
    build(tmp_path, briefs={"2026-10-21": past()})
    html = page(tmp_path, "2026-10-21")

    assert '<link rel="canonical" href="https://thedailybrief.dev/brief/2026-10-21/">' in html
    assert '<meta property="og:url" content="https://thedailybrief.dev/brief/2026-10-21/">' in html


def test_day_strip_on_front_page(tmp_path):
    build(tmp_path, briefs={"2026-10-21": past(), "2026-10-19": past("2026-10-19")})
    strip = days(page(tmp_path))

    assert re.findall(r">([A-Z][a-z]{2} \d+)<", strip) == ["Fri 16", "Sat 17", "Sun 18", "Mon 19", "Tue 20", "Wed 21", "Thu 22"]
    assert '<a href="./" class="active" aria-current="page">Thu 22</a>' in strip
    assert '<a href="brief/2026-10-21/">Wed 21</a>' in strip and '<a href="brief/2026-10-19/">Mon 19</a>' in strip
    assert '<span class="disabled" aria-disabled="true">Tue 20</span>' in strip
    assert '<span class="disabled" aria-disabled="true">Fri 16</span>' in strip


def test_day_strip_on_past_page_highlights_that_day_and_today_links_home(tmp_path):
    build(tmp_path, briefs={"2026-10-21": past()})
    strip = days(page(tmp_path, "2026-10-21"))

    assert '<a href="../../brief/2026-10-21/" class="active" aria-current="page">Wed 21</a>' in strip
    assert '<a href="../../">Thu 22</a>' in strip


def test_prev_next_skip_missing_days_and_stop_at_edges(tmp_path):
    build(tmp_path, briefs={"2026-10-21": past(), "2026-10-19": past("2026-10-19")})

    pager = block(page(tmp_path, "2026-10-21"), "pager")
    assert '<a href="../../brief/2026-10-19/" rel="prev">← Mon 19</a>' in pager
    assert '<a href="../../" rel="next">Thu 22 →</a>' in pager
    oldest = block(page(tmp_path, "2026-10-19"), "pager")
    assert '<span class="disabled">← previous</span>' in oldest
    assert '<a href="../../brief/2026-10-21/" rel="next">Wed 21 →</a>' in oldest
    today = block(page(tmp_path, "2026-10-22"), "pager")
    assert '<a href="../../brief/2026-10-21/" rel="prev">← Wed 21</a>' in today
    assert '<span class="disabled">next →</span>' in today
    assert 'class="pager' not in page(tmp_path)


def test_today_also_has_a_stable_brief_page(tmp_path):
    build(tmp_path)
    html = page(tmp_path, "2026-10-22")

    assert "Brief · Thursday, October 22, 2026" in html and "Today card" in html
    assert "This is today's brief" in html and "You're viewing a past brief" not in html
    assert '<link rel="canonical" href="https://thedailybrief.dev/brief/2026-10-22/">' in html


def test_renamed_section_gets_neutral_color(tmp_path):
    sections = [{"name": "Topic", "cards": [item("Past card")], "more": []},
                {"name": "Old Name", "cards": [item("Renamed card")], "more": []}]
    build(tmp_path, briefs={"2026-10-21": past(sections=sections)})
    html = page(tmp_path, "2026-10-21")

    assert f'id="topic" class="topic" style="--c: {site_builder.PALETTE[0]}"' in html
    assert f'id="old-name" class="topic" style="--c: {site_builder.NEUTRAL_COLOR}"' in html


def test_snapshot_titles_escaped_and_bad_links_dropped(tmp_path):
    bad = past(lead_title="<script>alert(1)</script>",
               sections=[{"name": "Topic", "cards": [item("<img src=x onerror=alert(2)>", link="javascript:alert(3)",
                                                         image="http://x/a.jpg", icon="javascript:alert(4)")],
                          "more": [item("Row", link="data:text/html,hi")]}])
    bad["lead"]["also"] = [{"name": "evil", "link": "javascript:alert(5)"}]
    bad["lead"]["image"] = "http://img.example.com/lead.jpg"
    bad["pulse"][0]["thread"] = "javascript:alert(6)"
    build(tmp_path, briefs={"2026-10-21": bad})
    html = page(tmp_path, "2026-10-21")

    assert "<script>alert(1)" not in html and "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "<img src=x" not in html and "&lt;img src=x onerror=alert(2)&gt;" in html
    assert "javascript:" not in html and "data:text/html" not in html
    assert "http://x/a.jpg" not in html and "http://img.example.com/lead.jpg" not in html
    assert ">evil<" not in html


def test_not_found_page_handles_old_briefs_and_other_paths(tmp_path):
    build(tmp_path)
    html = (tmp_path / "404.html").read_text()
    js = (site_builder.SITE_DIR / "static/notfound.js").read_text()

    assert "Page not found" in html and "This brief is older than a week" in html
    assert re.search(r'data-case="brief"[^>]*hidden', html)
    assert '<a href="/">' in html and 'href="/static/style.css"' in html and 'src="/static/notfound.js"' in html
    assert 'href="../' not in html and 'src="static/' not in html
    assert r"^\/brief\/\d{4}-\d{2}-\d{2}\/?$" in js and "innerHTML" not in js
