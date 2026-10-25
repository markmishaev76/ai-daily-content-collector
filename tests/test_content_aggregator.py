from datetime import datetime, timezone

import feedparser
import pytest

from src.content_aggregator import ContentAggregator, extract_image, validate_sources


def entry(item_xml):
    rss = ('<?xml version="1.0"?><rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/" '
           'xmlns:content="http://purl.org/rss/1.0/modules/content/"><channel><title>F</title>'
           f'<item><title>T</title><link>https://example.com/a</link>{item_xml}</item></channel></rss>')
    return feedparser.parse(rss).entries[0]


def test_duplicate_link_across_topics_kept_in_both_until_selection(monkeypatch):
    aggregator = ContentAggregator(hours_back=48)
    same = {"title": "Same", "link": "https://example.com/x", "summary": "", "published": None, "source": "A"}
    monkeypatch.setattr(aggregator, "fetch_rss_feed", lambda url, **kw: [dict(same)])

    feed = aggregator.aggregate_content([{"name": "First", "sources": [{"type": "rss", "url": "a"}]},
                                         {"name": "Second", "sources": [{"type": "rss", "url": "b"}]}])

    assert len(feed["First"]) == 1
    assert len(feed["Second"]) == 1


def test_malformed_image_url_does_not_drop_feed(monkeypatch):
    rss = ('<?xml version="1.0"?><rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/"><channel><title>F</title>'
           '<item><title>Bad image</title><link>https://example.com/1</link><media:thumbnail url="https://[bad"/></item>'
           '<item><title>Normal</title><link>https://example.com/2</link></item></channel></rss>')

    class Response:
        content = rss.encode()

        def raise_for_status(self):
            pass

    aggregator = ContentAggregator(hours_back=48)
    monkeypatch.setattr(aggregator, "_validate_url", lambda url: True)
    monkeypatch.setattr("src.content_aggregator.requests.get", lambda *a, **k: Response())

    articles = aggregator.fetch_rss_feed("https://feeds.example.com/rss")

    assert [a["title"] for a in articles] == ["Bad image", "Normal"]
    assert articles[0]["image"] is None
    assert articles[0]["feed"] == "https://feeds.example.com/rss"


@pytest.mark.parametrize("item_xml", [
    '<media:thumbnail url="https://img.example.com/a.jpg"/>',
    '<media:content url="https://img.example.com/a.jpg" medium="image"/>',
    '<enclosure url="https://img.example.com/a.jpg" type="image/jpeg" length="1"/>',
    '<description>&lt;p&gt;Hi &lt;img src="https://img.example.com/a.jpg"&gt;&lt;/p&gt;</description>',
    '<content:encoded><![CDATA[<img alt="x" src="https://img.example.com/a.jpg">]]></content:encoded>',
])
def test_extract_image_sources(item_xml):
    assert extract_image(entry(item_xml)) == "https://img.example.com/a.jpg"


@pytest.mark.parametrize("item_xml", [
    '<media:thumbnail url="http://img.example.com/a.jpg"/>',
    '<description>&lt;img src="javascript:alert(1)"&gt;</description>',
    '<description>No picture here</description>',
])
def test_extract_image_rejects_non_https_and_missing(item_xml):
    assert extract_image(entry(item_xml)) is None


def test_duplicate_links_across_sources_kept_once(monkeypatch):
    aggregator = ContentAggregator(hours_back=48)
    same = {"title": "Same", "link": "https://example.com/x", "summary": "", "published": None, "source": "A"}
    other = {"title": "Other", "link": "https://example.com/y", "summary": "", "published": None, "source": "B"}
    monkeypatch.setattr(aggregator, "fetch_rss_feed", lambda url, **kw: [same, other] if url == "a" else [dict(same, source="B")])

    feed = aggregator.aggregate_content([{"name": "T", "sources": [{"type": "rss", "url": "a"}, {"type": "rss", "url": "b"}]}])

    assert [a["title"] for a in feed["T"]] == ["Same", "Other"]
    assert feed["T"][0]["source"] == "A"


def test_feed_name_overrides_feed_title(monkeypatch):
    aggregator = ContentAggregator(hours_back=48)
    monkeypatch.setattr(aggregator, "fetch_rss_feed", lambda url, **kw: [{"title": "T", "link": f"https://e.com/{url}",
                                                                     "source": "Ugly Feed Title: tag"}])

    feed = aggregator.aggregate_content([{"name": "S", "sources": [{"type": "rss", "url": "a", "name": "Nice"},
                                                                   {"type": "rss", "url": "b"}]}])

    assert [a["source"] for a in feed["S"]] == ["Nice", "Ugly Feed Title: tag"]


NOW = datetime(2026, 10, 24, 12, 0, tzinfo=timezone.utc)
DATE_ONLY_60H = ('<?xml version="1.0"?><rss version="2.0"><channel><title>Anthropic Research</title>'
                 '<item><title>LLMs make formal verification feasible</title>'
                 '<link>https://www.anthropic.com/research/formal-verification</link>'
                 '<pubDate>Thu, 22 Oct 2026 00:00:00 +0000</pubDate></item></channel></rss>')


@pytest.fixture
def date_only_feed(monkeypatch):
    class Response:
        content = DATE_ONLY_60H.encode()

        def raise_for_status(self):
            pass

    monkeypatch.setattr(ContentAggregator, "_validate_url", lambda self, url: True)
    monkeypatch.setattr("src.content_aggregator.requests.get", lambda *a, **k: Response())


def topics(**source):
    return [{"name": "News", "sources": [dict({"type": "rss", "url": "https://feeds.example.com/a.xml"}, **source)]}]


def test_date_only_post_60h_old_kept_by_72h_feed(date_only_feed):
    feed = ContentAggregator(hours_back=48, now=NOW).aggregate_content(topics(hours_back=72, name="Anthropic Research"))

    assert [a["link"] for a in feed["News"]] == ["https://www.anthropic.com/research/formal-verification"]
    assert feed["News"][0]["source"] == "Anthropic Research"


def test_date_only_post_60h_old_dropped_by_default_48h_feed(date_only_feed):
    assert ContentAggregator(hours_back=48, now=NOW).aggregate_content(topics())["News"] == []


@pytest.mark.parametrize("bad", [0, -1, "72", True, 1.5, None])
def test_feed_hours_back_must_be_positive_whole_number(bad):
    with pytest.raises(ValueError, match=r"config.yaml: topic 'News' feed https://feeds.example.com/a.xml hours_back"):
        validate_sources(topics(hours_back=bad))


def test_feed_hours_back_optional():
    validate_sources(topics())
    validate_sources(topics(hours_back=72))
