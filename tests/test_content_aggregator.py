import feedparser
import pytest

from src.content_aggregator import ContentAggregator, extract_image


def entry(item_xml):
    rss = ('<?xml version="1.0"?><rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/" '
           'xmlns:content="http://purl.org/rss/1.0/modules/content/"><channel><title>F</title>'
           f'<item><title>T</title><link>https://example.com/a</link>{item_xml}</item></channel></rss>')
    return feedparser.parse(rss).entries[0]


def test_duplicate_link_across_topics_kept_in_first_topic(monkeypatch):
    aggregator = ContentAggregator(hours_back=48)
    same = {"title": "Same", "link": "https://example.com/x", "summary": "", "published": None, "source": "A"}
    monkeypatch.setattr(aggregator, "fetch_rss_feed", lambda url: [dict(same)])

    feed = aggregator.aggregate_content([{"name": "First", "sources": [{"type": "rss", "url": "a"}]},
                                         {"name": "Second", "sources": [{"type": "rss", "url": "b"}]}])

    assert len(feed["First"]) == 1
    assert feed["Second"] == []


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
    monkeypatch.setattr(aggregator, "fetch_rss_feed", lambda url: [same, other] if url == "a" else [dict(same, source="B")])

    feed = aggregator.aggregate_content([{"name": "T", "sources": [{"type": "rss", "url": "a"}, {"type": "rss", "url": "b"}]}])

    assert [a["title"] for a in feed["T"]] == ["Same", "Other"]
    assert feed["T"][0]["source"] == "A"
