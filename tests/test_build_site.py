import json
from datetime import datetime, timedelta, timezone

import build_site


class FakeAggregator:
    def __init__(self, feed):
        self.feed = feed

    def aggregate_content(self, topics):
        return self.feed


def article(n):
    return {"title": f"A{n}", "link": f"https://example.com/{n}", "summary": "",
            "published": datetime(2026, 10, 22, tzinfo=timezone.utc), "source": "S"}


CONFIG = {"topics": [{"name": "T", "sources": []}], "brief": {"max_articles_per_topic": 5}}


NOW = datetime(2026, 10, 23, 3, 0, tzinfo=timezone.utc)


def run(tmp_path, feed, fetch_medium=lambda url: [], fetch_meta=lambda url: None, now=NOW):
    out = tmp_path / "public"
    code = build_site.main(out_dir=out, config=CONFIG, aggregator=FakeAggregator(feed),
                           fetch_meta=fetch_meta, og_cache_path=tmp_path / "og-cache.json",
                           fetch_medium=fetch_medium, data_path=tmp_path / "medium.json",
                           posts_dir=tmp_path / "posts", about_path=tmp_path / "about.md",
                           history_path=tmp_path / "lead-history.json", seen_path=tmp_path / "seen.json", pinned_path=tmp_path / "pinned.yaml",
                           now=now)
    return code, out


def lead_block(out):
    html = (out / "index.html").read_text()
    start = html.index('class="lead')
    return html[start:html.index("<!-- /lead -->", start)], html


def test_zero_articles_exits_1_and_writes_nothing(tmp_path):
    code, out = run(tmp_path, {"T": []})

    assert code == 1
    assert not (out / "index.html").exists()


def test_medium_failure_keeps_saved_file(tmp_path):
    saved = [{"title": "Kept", "url": "https://medium.com/p/1", "date": "2025-01-01", "source": "medium"}]
    (tmp_path / "medium.json").write_text(json.dumps(saved))
    before = (tmp_path / "medium.json").read_text()

    code, out = run(tmp_path, {"T": [article(1)]}, fetch_medium=lambda url: None)

    assert code == 0
    assert (tmp_path / "medium.json").read_text() == before
    assert "Kept" in (out / "index.html").read_text()


def test_cuts_to_max_per_topic():
    raw, feed = build_site.fetch_feed(CONFIG, FakeAggregator({"T": [article(i) for i in range(8)]}))

    assert len(raw["T"]) == 8
    assert len(feed["T"]) == 5


def test_lead_uses_articles_below_cut_and_writes_history(tmp_path):
    items = [article(i) for i in range(7)] + [dict(article(7), title="Patch now: CVE-2026-109618")]

    code, out = run(tmp_path, {"T": items})
    lead, html = lead_block(out)
    history = json.loads((tmp_path / "lead-history.json").read_text())

    assert code == 0
    assert "CVE-2026-109618" in lead
    assert html.count("Patch now: CVE-2026-109618") == 1
    assert [(e["date"], e["url"], e["section"]) for e in history] == [("2026-10-23", "https://example.com/7", "T")]
    assert "CVE-2026-109618" in history[0]["key_tokens"]


def test_pinned_lead_through_build(tmp_path):
    (tmp_path / "pinned.yaml").write_text("url: https://example.com/2\nnote: Worth it\nuntil: 2026-10-23\n")

    code, out = run(tmp_path, {"T": [article(i) for i in range(4)]})
    lead, _ = lead_block(out)

    assert code == 0
    assert "A2" in lead and "Worth it" in lead


def test_invalid_pinned_fails_build(tmp_path, caplog):
    (tmp_path / "pinned.yaml").write_text("url: javascript:alert(1)\nuntil: 2026-10-30\n")

    code, out = run(tmp_path, {"T": [article(1)]})

    assert code == 1
    assert not (out / "index.html").exists()
    assert not (tmp_path / "lead-history.json").exists()
    assert "pinned.yaml" in caplog.text


def test_rendered_articles_get_og_images_and_cache_written(tmp_path):
    fetched = []

    def fetch_meta(url):
        fetched.append(url)
        return {"image": f"https://img.example.com/{url[-1]}.png", "description": None, "icon": None}

    code, out = run(tmp_path, {"T": [article(i) for i in range(7)]}, fetch_meta=fetch_meta)
    html = (out / "index.html").read_text()
    cache = json.loads((tmp_path / "og-cache.json").read_text())

    assert code == 0
    assert 5 <= len(fetched) <= 6 and set(cache) == set(fetched)
    assert "https://img.example.com/0.png" in html


def test_only_rendered_articles_fetched(tmp_path):
    fetched = []

    run(tmp_path, {"T": [article(i) for i in range(9)]}, fetch_meta=lambda url: fetched.append(url))

    assert len(fetched) <= 5 + 1


def test_og_fetch_failures_do_not_fail_build(tmp_path):
    def fetch_meta(url):
        raise RuntimeError("network down")

    code, out = run(tmp_path, {"T": [article(1)]}, fetch_meta=fetch_meta)

    assert code == 0 and (out / "index.html").exists()


def run_pulse(tmp_path, collect, fetch_meta=lambda url: None, feed=None):
    out = tmp_path / "public"
    code = build_site.main(out_dir=out, config=dict(CONFIG, pulse={"subreddits": ["ClaudeAI"]}),
                           aggregator=FakeAggregator(feed or {"T": [article(1)]}), fetch_medium=lambda url: [],
                           data_path=tmp_path / "medium.json", posts_dir=tmp_path / "posts",
                           about_path=tmp_path / "about.md", history_path=tmp_path / "h.json", seen_path=tmp_path / "seen.json",
                           pinned_path=tmp_path / "pinned.yaml", now=NOW, fetch_meta=fetch_meta,
                           og_cache_path=tmp_path / "og.json", collect_pulse=collect)
    return code, (out / "index.html").read_text() if (out / "index.html").exists() else ""


def test_pulse_failure_hides_section_and_build_succeeds(tmp_path, caplog):
    from src.pulse import PulseUnavailable

    def collect(config, now, shown):
        raise PulseUnavailable("every source failed (r/ClaudeAI: HTTP 403)")

    code, html = run_pulse(tmp_path, collect)

    assert code == 0 and "the-pulse" not in html
    assert "The Pulse hidden" in caplog.text and "HTTP 403" in caplog.text


def pulse_item(title="Big thread", link="https://blog.example.com/p"):
    return {"title": title, "source": "Hacker News", "points": 900, "unit": "points", "comments": 10, "created": NOW,
            "thread": "https://news.ycombinator.com/item?id=1", "link": link, "image": None}


def test_pulse_rendered_with_link_post_thumbnail_from_page(tmp_path, caplog):
    caplog.set_level("INFO")
    code, html = run_pulse(tmp_path, lambda config, now, shown: ([pulse_item()], {"Hacker News": 1, "Lobsters": None}),
                           fetch_meta=lambda url: {"image": "https://blog.example.com/og.png", "description": None,
                                                   "icon": None})

    assert code == 0 and "Big thread" in html and "https://blog.example.com/og.png" in html
    assert "The Pulse: Hacker News 1, Lobsters failed; showing 1" in caplog.text


def test_pulse_gets_page_links_to_dedupe(tmp_path):
    seen = []

    def collect(config, now, shown):
        seen.append(set(shown))
        return [pulse_item()], {"Hacker News": 1}

    code, _ = run_pulse(tmp_path, collect, feed={"T": [article(i) for i in range(7)]})

    assert code == 0
    assert {f"https://example.com/{i}" for i in range(5)} <= seen[0]
    assert "https://example.com/6" not in seen[0]


def test_no_pulse_config_skips_reddit(tmp_path):
    called = []
    code, out = run(tmp_path, {"T": [article(1)]})

    assert code == 0 and "the-pulse" not in (out / "index.html").read_text()


def run_learn(tmp_path, collect, caplog):
    caplog.set_level("INFO")
    out = tmp_path / "public"
    channels = [{"name": "AI Engineer", "id": "UCLKPca3kwwd-B59HNr-_lvA"}]
    code = build_site.main(out_dir=out, config=dict(CONFIG, learn={"channels": channels}),
                           aggregator=FakeAggregator({"T": [article(1)]}), fetch_medium=lambda url: [],
                           data_path=tmp_path / "medium.json", posts_dir=tmp_path / "posts",
                           about_path=tmp_path / "about.md", history_path=tmp_path / "h.json", seen_path=tmp_path / "seen.json",
                           pinned_path=tmp_path / "pinned.yaml", now=NOW, fetch_meta=lambda url: None,
                           og_cache_path=tmp_path / "og.json", collect_learn=collect)
    return code, out


def test_learn_failure_hides_teaser_keeps_page_and_build_succeeds(tmp_path, caplog):
    from src.learn import LearnUnavailable

    def collect(config, now):
        raise LearnUnavailable("every channel failed (AI Engineer: HTTP 500)")

    code, out = run_learn(tmp_path, collect, caplog)

    assert code == 0 and 'id="learn"' not in (out / "index.html").read_text()
    assert "No videos right now" in (out / "learn/index.html").read_text()
    assert "Learn hidden" in caplog.text and "HTTP 500" in caplog.text


def test_learn_rendered_and_counts_logged(tmp_path, caplog):
    vid = {"id": "WOszaC1WWbQ", "title": "Evals talk", "channel": "AI Engineer", "views": 5000, "per_day": 2500.0,
           "published": NOW, "link": "https://www.youtube.com/watch?v=WOszaC1WWbQ",
           "thumb": "https://i.ytimg.com/vi/WOszaC1WWbQ/hqdefault.jpg"}
    data = {"top": [vid], "channels": [{"name": "AI Engineer", "url": "https://www.youtube.com/channel/x", "videos": []}]}

    code, out = run_learn(tmp_path, lambda config, now: (data, {"AI Engineer": 1, "Anthropic": None}), caplog)

    assert code == 0 and "Evals talk" in (out / "index.html").read_text()
    assert "Evals talk" in (out / "learn/index.html").read_text()
    assert "Learn: AI Engineer 1, Anthropic failed; showing 1" in caplog.text


def test_invalid_learn_config_fails_build(tmp_path, caplog):
    out = tmp_path / "public"
    code = build_site.main(out_dir=out, config=dict(CONFIG, learn={"channels": [{"name": "X", "id": "@x"}]}),
                           aggregator=FakeAggregator({"T": [article(1)]}), fetch_medium=lambda url: [],
                           data_path=tmp_path / "medium.json", posts_dir=tmp_path / "posts",
                           about_path=tmp_path / "about.md", history_path=tmp_path / "h.json", seen_path=tmp_path / "seen.json",
                           pinned_path=tmp_path / "pinned.yaml", now=NOW, fetch_meta=lambda url: None,
                           og_cache_path=tmp_path / "og.json")

    assert code == 1 and not (out / "index.html").exists()
    assert "config.yaml: learn" in caplog.text


def test_seen_articles_shown_once_across_days_stable_within_a_day(tmp_path):
    code, out = run(tmp_path, {"T": [article(i) for i in range(3)]})
    seen = json.loads((tmp_path / "seen.json").read_text())
    assert code == 0 and seen == {f"example.com/{i}": "2026-10-23" for i in range(3)}

    code, out = run(tmp_path, {"T": [article(i) for i in range(4)]}, now=NOW.replace(hour=15))
    html = (out / "index.html").read_text()
    assert code == 0 and all(f'https://example.com/{i}"' in html for i in range(4))

    code, out = run(tmp_path, {"T": [article(i) for i in range(6)]}, now=NOW + timedelta(days=1))
    html = (out / "index.html").read_text()
    assert code == 0
    assert not any(f'https://example.com/{i}"' in html for i in range(4))
    assert 'https://example.com/4"' in html and 'https://example.com/5"' in html


def test_seen_skips_lead_candidates_too(tmp_path):
    (tmp_path / "seen.json").write_text(json.dumps({"example.com/7": "2026-10-22"}))
    items = [article(i) for i in range(3)] + [dict(article(7), title="Patch now: CVE-2026-109618")]

    code, out = run(tmp_path, {"T": items})

    assert code == 0 and "CVE-2026-109618" not in (out / "index.html").read_text()


def test_corrupt_seen_fails_build_naming_file(tmp_path, caplog):
    (tmp_path / "seen.json").write_text("{not json")

    code, out = run(tmp_path, {"T": [article(1)]})

    assert code == 1 and not (out / "index.html").exists()
    assert "seen.json" in caplog.text


def test_feed_hours_back_validated_before_fetching(tmp_path, caplog):
    config = dict(CONFIG, topics=[{"name": "T", "sources": [{"type": "rss", "url": "https://e.com/f", "hours_back": 0}]}])

    code = build_site.main(out_dir=tmp_path / "public", config=config, aggregator=FakeAggregator({"T": [article(1)]}),
                           fetch_medium=lambda url: [], data_path=tmp_path / "medium.json", posts_dir=tmp_path / "posts",
                           about_path=tmp_path / "about.md", history_path=tmp_path / "h.json",
                           seen_path=tmp_path / "seen.json", pinned_path=tmp_path / "pinned.yaml", now=NOW,
                           fetch_meta=lambda url: None, og_cache_path=tmp_path / "og.json")

    assert code == 1 and "config.yaml" in caplog.text and "hours_back" in caplog.text
