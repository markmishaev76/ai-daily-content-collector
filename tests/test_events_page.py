import re
from datetime import date, datetime, timezone

from src import site_builder

NOW = datetime(2026, 11, 1, 8, 0, tzinfo=timezone.utc)


def ev(name="AI Engineer Summit", cfp_end=date(2026, 11, 5), start=date(2027, 2, 10), end=date(2027, 2, 11),
       cats=("ai",), **kw):
    days_left = (cfp_end - NOW.date()).days if cfp_end else None
    return dict({"name": name, "year": start.year, "url": "https://ai.example.com", "cfp_url": "https://cfp.example.com/ai",
                 "cfp_end": cfp_end, "start": start, "end": end, "location": "Berlin (Germany)", "online": False,
                 "categories": list(cats), "days_left": days_left, "closing_soon": days_left is not None and days_left <= 7},
                **kw)


def data(cfps=None, upcoming=None):
    return {"cfps": [ev()] if cfps is None else cfps,
            "upcoming": [ev("KubeCon", cfp_end=None, start=date(2026, 12, 1), end=date(2026, 12, 3), cats=("platform",),
                            location="Amsterdam, Netherlands", cfp_url=None)] if upcoming is None else upcoming}


def build(tmp_path, events, **kw):
    site_builder.build({"Topic": [{"title": "Story", "link": "https://example.com/s", "summary": "S", "published": NOW,
                                   "source": "Src", "image": None}]}, [], "", tmp_path, NOW, events=events, **kw)
    return (tmp_path / "index.html").read_text()


def events_page(tmp_path):
    return (tmp_path / "events/index.html").read_text()


def block(html, cls):
    start = html.index(f'class="{cls}')
    return html[start:html.index("<!-- /" + cls + " -->", start)]


def test_events_page_lists_open_cfps_and_upcoming(tmp_path):
    build(tmp_path, data(cfps=[ev(), ev("BSides Online", cfp_end=date(2026, 11, 30), cats=("security",), online=True,
                                         location="Online")]))
    html = events_page(tmp_path)
    cfps = block(html, "cfp-list")

    assert cfps.index("AI Engineer Summit") < cfps.index("BSides Online")
    assert '<a href="https://cfp.example.com/ai" target="_blank" rel="noopener noreferrer">' in cfps
    assert "Closes Nov 5" in cfps and "4 days left" in cfps and 'class="soon"' in cfps
    assert cfps.count('class="soon"') == 1
    assert "Feb 10–11, 2027" in cfps and "Berlin (Germany)" in cfps and "Online" in cfps
    assert 'data-cats="ai"' in cfps and 'data-cats="security"' in cfps
    upcoming = block(html, "upcoming-list")
    assert "KubeCon" in upcoming and "Dec 1–3, 2026" in upcoming and "Amsterdam, Netherlands" in upcoming
    assert '<link rel="canonical" href="https://thedailybrief.dev/events/">' in html


def test_filter_chips_hidden_until_js_and_script_versioned(tmp_path):
    build(tmp_path, data())
    html = events_page(tmp_path)

    chips = block(html, "event-filters")
    assert re.search(r'<div class="event-filters"[^>]*hidden', html)
    assert [label for label in re.findall(r'data-filter="[a-z]+"[^>]*>([^<]+)<', chips)] == [
        "All", "AI &amp; agents", "Security &amp; identity", "Platform &amp; DevOps", "Leadership"]
    assert re.search(r'<script src="\.\./static/events\.js\?v=[0-9a-f]{10}" defer></script>', html)
    js = (site_builder.SITE_DIR / "static/events.js").read_text()
    assert "innerHTML" not in js and "data-cats" in js and "hidden" in js


def test_calendar_feed_written_and_linked(tmp_path):
    build(tmp_path, data())
    html = events_page(tmp_path)
    ics = (tmp_path / "events/cfps.ics").read_bytes().decode("utf-8")

    assert ics.startswith("BEGIN:VCALENDAR\r\n") and "SUMMARY:CFP closes: AI Engineer Summit" in ics
    assert 'href="webcal://thedailybrief.dev/events/cfps.ics"' in html
    assert 'href="https://thedailybrief.dev/events/cfps.ics"' in html
    assert "Subscribe in your calendar" in html


def test_names_escaped_and_bad_links_dropped(tmp_path):
    bad = ev("<script>alert(1)</script>", cfp_url="javascript:alert(2)", url="http://ok.example.com")
    build(tmp_path, data(cfps=[bad], upcoming=[]))
    html = events_page(tmp_path)

    assert "<script>alert(1)" not in html and "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "javascript:" not in html


def test_menu_has_events_between_learn_and_about(tmp_path):
    index = build(tmp_path, data(), learn={"top": [], "channels": [], "days": 30})
    nav = index[index.index('<header class="site-header">'):index.index("</header>")]

    assert nav.index(">Learn<") < nav.index(">Events<") < nav.index(">About<")
    assert '<a href="events/">Events</a>' in nav
    page = events_page(tmp_path)
    assert '<a href="../events/" class="active">Events</a>' in page


def test_front_page_strip_top_three_after_learn_teaser(tmp_path):
    learn = {"top": [{"id": "WOszaC1WWbQ", "title": "Video", "channel": "AI Engineer", "views": 10, "per_day": 5.0,
                      "published": NOW}], "channels": [], "days": 30}
    cfps = [ev(f"AI Conf {n}", cfp_end=date(2026, 11, 2 + n)) for n in range(5)]
    index = build(tmp_path, data(cfps=cfps), learn=learn)
    strip = block(index, "cfp-strip")

    assert index.index('id="learn"') < index.index('class="cfp-strip') < index.index('id="topic"')
    assert strip.count('class="cfp-row"') == 3 and "AI Conf 3" not in strip
    assert '<a class="see-all" href="events/">All events →</a>' in strip


def test_front_strip_hidden_and_page_says_so_when_empty(tmp_path):
    index = build(tmp_path, data(cfps=[], upcoming=[]))

    assert "cfp-strip" not in index
    assert "No open calls for talks right now" in events_page(tmp_path)


def test_no_events_config_means_no_page_or_menu(tmp_path):
    index = build(tmp_path, None)

    assert ">Events<" not in index and not (tmp_path / "events").exists()
