import re
from datetime import datetime, timezone

from src import site_builder

NOW = datetime(2026, 11, 1, 8, 0, tzinfo=timezone.utc)


def week(wid="2026-W44", start="2026-10-26", end="2026-11-01", preview=False, top=None, days=None):
    return {"week": wid, "start": start, "end": end, "preview": preview,
            "days": days if days is not None else [
                {"date": "2026-10-26", "lead": {"title": "Mon lead", "link": "https://e.com/mon", "source": "Src",
                                                "section": "Topic", "take": "Mark says <b>hi</b>"}},
                {"date": "2026-10-27", "lead": None}],
            "top": top if top is not None else [
                {"title": "Top story", "link": "https://t.com/1", "source": "T src", "section": "Topic",
                 "date": "2026-10-28", "coverage": 3, "score": 12.5},
                {"title": "Renamed section story", "link": "https://t.com/2", "source": "T2", "section": "Gone",
                 "date": "2026-10-29", "coverage": 1, "score": 1.0}]}


def build(tmp_path, weeks=None, preview=None):
    site_builder.build({"Topic": [{"title": "Story", "link": "https://example.com/s", "summary": "S", "published": NOW,
                                   "source": "Src", "image": None}]}, [], "", tmp_path, NOW, weeks=weeks, week_preview=preview)
    return (tmp_path / "index.html").read_text()


def page(tmp_path, wid=None):
    return (tmp_path / (f"week/{wid}/index.html" if wid else "week/index.html")).read_text()


def block(html, cls):
    start = html.index(f'class="{cls}')
    return html[start:html.index("<!-- /" + cls + " -->", start)]


def test_week_page_lists_leads_takes_and_top(tmp_path):
    build(tmp_path, weeks={"2026-W44": week()})
    html = page(tmp_path, "2026-W44")

    assert "Week in review · Oct 26 – Nov 1, 2026" in html
    leads = block(html, "week-leads")
    assert '<a href="https://e.com/mon" target="_blank" rel="noopener noreferrer">Mon lead</a>' in leads
    assert "Mon Oct 26" in leads and "Mark says &lt;b&gt;hi&lt;/b&gt;" in leads and "Mark's take" in leads
    assert "Tue Oct 27" in leads and "No brief" in leads
    top = block(html, "week-top")
    assert top.index("Top story") < top.index("Renamed section story")
    assert f'style="--c: {site_builder.PALETTE[0]}">Topic<' in top
    assert f'style="--c: {site_builder.NEUTRAL_COLOR}">Gone<' in top
    assert "T src · Wed Oct 28" in top
    assert '<link rel="canonical" href="https://thedailybrief.dev/week/2026-W44/">' in html


def test_latest_week_at_week_root_and_older_weeks_linked(tmp_path):
    build(tmp_path, weeks={"2026-W43": week("2026-W43", "2026-10-19", "2026-10-25"), "2026-W44": week()})

    assert "Oct 26 – Nov 1, 2026" in page(tmp_path)
    assert '<link rel="canonical" href="https://thedailybrief.dev/week/2026-W44/">' in page(tmp_path)
    nav = block(page(tmp_path, "2026-W44"), "week-nav")
    assert '<a href="../2026-W43/" rel="prev">← Oct 19 – 25</a>' in nav
    assert "Oct 19 – Oct 25, 2026" in page(tmp_path, "2026-W43")


def test_copy_for_linkedin_button_and_no_js_details(tmp_path):
    build(tmp_path, weeks={"2026-W44": week()})
    html = page(tmp_path, "2026-W44")

    assert re.search(r'<button type="button" class="copy-week"[^>]*hidden', html)
    details = block(html, "week-text")
    assert "<details" in html and "Copy for LinkedIn" in html
    assert "1. Mon Oct 26: Mon lead https://e.com/mon" in details
    assert "1. Top story https://t.com/1" in details and "https://thedailybrief.dev/week/2026-W44/" in details
    assert re.search(r'<script src="\.\./\.\./static/week\.js\?v=[0-9a-f]{10}" defer></script>', html)
    js = (site_builder.SITE_DIR / "static/week.js").read_text()
    assert "clipboard" in js and "innerHTML" not in js


def test_titles_escaped_and_bad_links_dropped(tmp_path):
    bad = week(top=[{"title": "<script>x</script>", "link": "javascript:alert(1)", "source": "S", "section": "Topic",
                     "date": "2026-10-28", "coverage": 1, "score": 1}],
               days=[{"date": "2026-10-26", "lead": {"title": "<img onerror=x>", "link": "data:x", "source": "S",
                                                     "section": "Topic"}}])
    build(tmp_path, weeks={"2026-W44": bad})
    html = page(tmp_path, "2026-W44")

    assert "<script>x" not in html and "&lt;script&gt;x&lt;/script&gt;" in html and "<img onerror" not in html
    assert "javascript:" not in html and "data:x" not in html


def test_preview_when_no_saved_week(tmp_path):
    build(tmp_path, weeks={}, preview=week(end="2026-10-29", preview=True))
    html = page(tmp_path)

    assert "Week so far · Oct 26 – Oct 29, 2026" in html and "Preview: the week isn't over" in html
    assert not (tmp_path / "week/2026-W44").exists()


def test_week_link_near_day_strip(tmp_path):
    index = build(tmp_path, weeks={"2026-W44": week()})

    assert '<a class="week-link" href="week/">Week in review →</a>' in index
    assert index.index("<!-- /days -->") < index.index('class="week-link"')


def test_no_week_data_means_no_week_pages_or_link(tmp_path):
    index = build(tmp_path)

    assert "week-link" not in index and not (tmp_path / "week").exists()
