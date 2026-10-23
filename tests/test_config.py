import yaml

GROUPS = [
    "AI-Assisted Engineering",
    "AI Agents & Agent Security",
    "Leadership",
    "Agent Identity & Authorization",
    "Supply Chain & Builds",
    "Security & AppSec",
    "Platform, Cloud & Reliability",
    "News & Research",
]

def load():
    with open("config.yaml") as f:
        return yaml.safe_load(f)


def test_eight_groups_in_order():
    assert [t["name"] for t in load()["topics"]] == GROUPS


def test_section_weights():
    assert [t["weight"] for t in load()["topics"]] == [1.5, 1.25, 1.25, 1.0, 1.0, 0.75, 0.75, 0.75]


def test_story_tiers_listed():
    tiers = load()["story"]["source_tiers"]

    assert "datatracker.ietf.org" in tiers["primary"]
    assert "aws.amazon.com/blogs/security" in tiers["primary"]
    assert "hnrss.org" in tiers["aggregator"]
    assert "news.ycombinator.com" in tiers["aggregator"]


def test_news_outlets_listed():
    outlets = load()["story"]["news_outlets"]

    assert {"thehackernews.com", "securityweek.com", "theregister.com", "bleepingcomputer.com"} <= set(outlets)
    assert "about.gitlab.com" not in outlets


def test_lead_min_hn_points():
    assert load()["story"]["lead_min_hn_points"] == 50


def test_no_source_listed_twice():
    urls = [s["url"] for t in load()["topics"] for s in t["sources"]]

    assert len(urls) == len(set(urls))


def test_max_articles_per_topic_is_eight():
    assert load()["brief"]["max_articles_per_topic"] == 8


def test_section_min_hn_points():
    assert load()["story"]["section_min_hn_points"] == 10


def test_feed_names_are_text():
    names = [s["name"] for t in load()["topics"] for s in t["sources"] if "name" in s]

    assert names and all(isinstance(n, str) and n.strip() for n in names)


def test_pulse_subreddits():
    from src import pulse

    s = pulse.settings(load())

    assert [name for name, _ in s["subreddits"]] == ["EngineeringManagers", "ClaudeAI", "cybersecurity",
                                                     "ChatGPTCoding", "cursor"]
    assert s["min_upvotes"] == 100 and s["limit"] == 10 and s["max_age_hours"] == 24
