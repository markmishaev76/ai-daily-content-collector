import yaml

GROUPS = [
    "Agent Identity & Authorization",
    "AI Agents & Agent Security",
    "AI-Assisted Engineering",
    "Security & AppSec",
    "Supply Chain & Builds",
    "Platform, Cloud & Reliability",
    "Leadership",
    "News & Research",
]

UNIQUE_SOURCES_BEFORE_REGROUP = 122


def load():
    with open("config.yaml") as f:
        return yaml.safe_load(f)


def test_eight_groups_in_order():
    assert [t["name"] for t in load()["topics"]] == GROUPS


def test_no_source_lost():
    urls = {s["url"] for t in load()["topics"] for s in t["sources"]}

    assert len(urls) == UNIQUE_SOURCES_BEFORE_REGROUP
    assert "https://openai.com/news/rss.xml" in urls
    assert "https://slsa.dev/feed.xml" in urls


def test_no_duplicate_source_within_topic():
    for topic in load()["topics"]:
        urls = [s["url"] for s in topic["sources"]]
        assert len(urls) == len(set(urls)), topic["name"]


def test_max_articles_per_topic_is_eight():
    assert load()["brief"]["max_articles_per_topic"] == 8
