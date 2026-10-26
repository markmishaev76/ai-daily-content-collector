import importlib.util
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "backfill_briefs.py"
spec = importlib.util.spec_from_file_location("backfill_briefs", SCRIPT)
backfill = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backfill)

DAY = date(2026, 10, 22)
NOW = datetime(2026, 10, 22, 23, 59, tzinfo=timezone.utc)
FAST, SLOW = "https://feeds.example.com/fast.xml", "https://feeds.example.com/slow.xml"
WINDOWS = {FAST: 48, SLOW: 72}


def art(n, hours_before, feed=FAST, **kw):
    published = None if hours_before is None else NOW - timedelta(hours=hours_before)
    return dict({"title": f"A{n}", "link": f"https://example.com/{n}", "summary": "", "published": published,
                 "source": "S", "feed": feed}, **kw)


def test_build_time_is_the_daily_slot():
    assert backfill.build_time(DAY) == NOW


def test_only_articles_published_before_the_build_and_inside_their_feed_window():
    raw = {"T": [art(1, 1), art(2, -1), art(3, 0), art(4, 47), art(5, 49), art(6, 60, SLOW), art(7, 73, SLOW),
                 art(8, None)]}

    kept = backfill.articles_for_day(raw, NOW, WINDOWS, shown=set())

    assert [a["title"] for a in kept["T"]] == ["A1", "A4", "A6"]


def test_articles_shown_on_an_earlier_backfilled_day_are_skipped():
    raw = {"T": [art(1, 1), art(2, 2)]}

    kept = backfill.articles_for_day(raw, NOW, WINDOWS, shown={"example.com/1"})

    assert [a["title"] for a in kept["T"]] == ["A2"]


def test_unknown_feed_uses_default_window():
    raw = {"T": [art(1, 47, "https://other.example.com/x"), art(2, 49, "https://other.example.com/x")]}

    assert [a["title"] for a in backfill.articles_for_day(raw, NOW, {}, set())["T"]] == ["A1"]


def test_hacker_news_query_gets_an_upper_bound(monkeypatch):
    calls = []
    monkeypatch.setattr(backfill.requests, "get", lambda url, **kw: calls.append((url, kw)) or "response")

    get = backfill.bounded_get(NOW)
    get("https://hn.algolia.com/api/v1/search", params={"numericFilters": "created_at_i>1,points>=100"}, timeout=10)

    assert calls[0][1]["params"]["numericFilters"] == f"created_at_i>1,points>=100,created_at_i<{int(NOW.timestamp())}"
    assert calls[0][1]["timeout"] == 10


def test_pulse_uses_hacker_news_only_and_drops_anything_after_the_build(monkeypatch):
    seen = {}

    def collect(config, now, env, get, shown):
        seen["config"] = config["pulse"]
        return [{"title": "old", "created": NOW - timedelta(hours=3)}, {"title": "late", "created": NOW}], {}

    monkeypatch.setattr(backfill.pulse, "collect", collect)
    config = {"pulse": {"limit": 10, "hacker_news": {"min_points": 100}, "lobsters": {"min_score": 15},
                        "subreddits": ["ClaudeAI"], "min_upvotes": 100}}

    items = backfill.pulse_for_day(config, NOW, set())

    assert [i["title"] for i in items] == ["old"]
    assert set(seen["config"]) == {"limit", "hacker_news"}


def test_pulse_unavailable_means_no_pulse(monkeypatch):
    def collect(*a, **kw):
        raise backfill.pulse.PulseUnavailable("down")

    monkeypatch.setattr(backfill.pulse, "collect", collect)

    assert backfill.pulse_for_day({"pulse": {"hacker_news": {}}}, NOW, set()) == []


CONFIG = {"topics": [{"name": "T", "weight": 1.0, "sources": []}], "story": {"source_tiers": {}}}


def test_recorded_lead_used_when_found_and_not_marked_pinned():
    raw_day = {"T": [art(1, 2, title="Big CVE-2026-1 story"), art(2, 3, title="The real lead")]}
    history = [{"date": "2026-10-22", "url": "https://example.com/2", "title": "The real lead", "section": "T"}]

    lead, how = backfill.pick_lead(raw_day, raw_day, CONFIG, history, DAY, NOW)

    assert lead.link == "https://example.com/2" and lead.title == "The real lead"
    assert not lead.pinned and how == "history entry, found in feeds"


def test_recorded_lead_older_than_window_is_brought_in_but_never_a_future_one():
    raw_all = {"T": [art(1, 2), art(2, 100, title="Old lead"), art(3, -5, title="Future lead")]}
    raw_day = backfill.articles_for_day(raw_all, NOW, WINDOWS, set())

    lead, _ = backfill.pick_lead(raw_day, raw_all, CONFIG,
                                 [{"date": "2026-10-22", "url": "https://example.com/2", "title": "Old lead"}], DAY, NOW)
    assert lead.link == "https://example.com/2"

    lead, how = backfill.pick_lead(backfill.articles_for_day(raw_all, NOW, WINDOWS, set()), raw_all, CONFIG,
                                   [{"date": "2026-10-22", "url": "https://example.com/3", "title": "Future lead",
                                     "section": "T"}], DAY, NOW)
    assert lead.title == "Future lead" and lead.section == "T" and not lead.pinned
    assert how == "history entry, not in feeds (built from the entry)"


def test_without_a_recorded_lead_the_algorithm_picks_using_earlier_history_only():
    raw_day = {"T": [art(1, 2, title="Patch now: CVE-2026-109618")]}
    later = [{"date": "2026-10-23", "url": "https://example.com/1", "title": "x", "key_tokens": ["cve-2026-109618"]}]

    lead, how = backfill.pick_lead(raw_day, raw_day, CONFIG, later, DAY, NOW)

    assert lead.link == "https://example.com/1" and how == "algorithm"
    assert backfill.history_before(later, DAY) == []


def test_only_the_backfill_days_and_never_today():
    assert backfill.DAYS == [date(2026, 10, d) for d in range(20, 26)]
    with pytest.raises(SystemExit):
        backfill.check_days(backfill.DAYS + [date(2026, 10, 26)], today=date(2026, 10, 26))
    backfill.check_days(backfill.DAYS, today=date(2026, 10, 26))


def test_recorded_leads_are_reserved_for_their_own_day():
    history = [{"date": "2026-10-21", "url": "https://example.com/old"},
               {"date": "2026-10-23", "url": "https://www.example.com/later/"},
               {"date": "2026-10-26", "url": "https://example.com/today"}]

    assert backfill.reserved_leads(history, DAY) == {"example.com/later"}
