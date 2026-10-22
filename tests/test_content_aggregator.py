from src.content_aggregator import ContentAggregator


def test_duplicate_links_across_sources_kept_once(monkeypatch):
    aggregator = ContentAggregator(hours_back=48)
    same = {"title": "Same", "link": "https://example.com/x", "summary": "", "published": None, "source": "A"}
    other = {"title": "Other", "link": "https://example.com/y", "summary": "", "published": None, "source": "B"}
    monkeypatch.setattr(aggregator, "fetch_rss_feed", lambda url: [same, other] if url == "a" else [dict(same, source="B")])

    feed = aggregator.aggregate_content([{"name": "T", "sources": [{"type": "rss", "url": "a"}, {"type": "rss", "url": "b"}]}])

    assert [a["title"] for a in feed["T"]] == ["Same", "Other"]
    assert feed["T"][0]["source"] == "A"
