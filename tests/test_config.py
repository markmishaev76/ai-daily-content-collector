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

def load():
    with open("config.yaml") as f:
        return yaml.safe_load(f)


def test_eight_groups_in_order():
    assert [t["name"] for t in load()["topics"]] == GROUPS


def test_no_source_listed_twice():
    urls = [s["url"] for t in load()["topics"] for s in t["sources"]]

    assert len(urls) == len(set(urls))


def test_max_articles_per_topic_is_eight():
    assert load()["brief"]["max_articles_per_topic"] == 8
