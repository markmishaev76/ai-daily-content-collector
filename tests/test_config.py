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


def test_pulse_feeds():
    from src import pulse

    s = pulse.settings(load())

    assert s["hacker_news"] == {"min_points": 100}
    assert s["lobsters"]["min_score"] == 15 and {"ai", "security", "vibecoding"} <= s["lobsters"]["tags"]
    assert pulse.relevant("Anthropic ships Claude 5", None, (), s)
    assert not pulse.relevant("Air purifiers as white noise machines", None, (), s)


def test_learn_channels():
    from src import learn

    s = learn.settings(load())

    assert s["channels"] == [{"name": "AI Engineer", "id": "UCLKPca3kwwd-B59HNr-_lvA"},
                             {"name": "Anthropic", "id": "UCrDwWp7EBBv4NwvScIpBDOA"},
                             {"name": "The Pragmatic Engineer", "id": "UCPbwhExawYrn9xxI21TFfyw"}]
    assert (s["max_age_days"], s["per_channel"], s["limit"], s["recent_per_channel"]) == (30, 2, 6, 5)


ANTHROPIC = "https://raw.githubusercontent.com/Olshansk/rss-feeds/main/feeds/feed_anthropic_"


def test_anthropic_feeds_first_in_their_sections_with_72h_window():
    from src.content_aggregator import validate_sources

    topics = {t["name"]: t["sources"] for t in load()["topics"]}

    assert topics["AI-Assisted Engineering"][0] == {"type": "rss", "url": ANTHROPIC + "engineering.xml",
                                                    "name": "Anthropic Engineering", "hours_back": 72}
    assert topics["News & Research"][:2] == [
        {"type": "rss", "url": ANTHROPIC + "research.xml", "name": "Anthropic Research", "hours_back": 72},
        {"type": "rss", "url": ANTHROPIC + "news.xml", "name": "Anthropic", "hours_back": 72}]
    validate_sources(load()["topics"])


def test_first_party_post_survives_section_cut_and_is_primary():
    from main import select_articles
    from src import story

    config = load()
    fv = {"title": "LLMs are making formal software verification feasible at a massive scale",
          "link": "https://www.anthropic.com/research/formal-verification", "summary": "Formal verification can prove..."}
    others = [{"title": f"Other {n}", "link": f"https://e.com/{n}", "summary": ""} for n in range(20)]

    picked = select_articles({"News & Research": [fv] + others}, config["brief"]["max_articles_per_topic"])

    assert fv in picked["News & Research"]
    assert story.source_tier(fv, config["story"]["source_tiers"]) == "primary"


def test_events_settings():
    from src import events

    s = events.settings(load())

    assert s["horizon_days"] == 90 and s["closing_days"] == 7 and len(s["topics"]) == 9
    assert {"MCP", "agentic"} <= set(s["keywords"]["ai"]) and "LeadDev" in s["keywords"]["leadership"]



def sources(name):
    return next(t["sources"] for t in load()["topics"] if t["name"] == name)


def test_ai_sections_always_show():
    from src import story

    assert story.always_show(load()) == ["AI-Assisted Engineering", "AI Agents & Agent Security"]


def test_ai_engineering_blogs_named_listed_early_with_week_window():
    feeds = sources("AI-Assisted Engineering")
    by_name = {s.get("name"): s for s in feeds}
    for name in ("Addy Osmani", "Kent Beck", "Martin Fowler", "Hamel Husain", "Eugene Yan", "Mitchell Hashimoto",
                 "Armin Ronacher", "GitHub AI & ML", "Cursor changelog"):
        assert by_name[name]["hours_back"] == 168, name
    first_hn = next(i for i, s in enumerate(feeds) if "hnrss.org" in s["url"])
    assert all(i < first_hn for i, s in enumerate(feeds) if s.get("hours_back") == 168)
    assert by_name["Simon Willison"]["url"] == "https://simonwillison.net/atom/everything/"
    assert by_name["Addy Osmani"]["url"] == "https://addyosmani.com/rss.xml"
    assert by_name["Kent Beck"]["url"] == "https://newsletter.kentbeck.com/feed"
    assert "hours_back" not in by_name["Simon Willison"]


def test_no_duplicate_or_dead_feeds():
    urls = [s["url"] for t in load()["topics"] for s in t["sources"]]

    assert len(urls) == len(set(urls))
    assert not any("huyenchip.com" in u or "cursor.com/blog" in u for u in urls)
    assert not any(".substack.com" in u for u in urls)          # Substack answers 403 to GitHub's runners
    assert sum("simonwillison.net/atom/everything" in u for u in urls) == 1


def test_week_window_only_on_blog_feeds_in_ai_sections():
    for topic in load()["topics"]:
        for s in topic["sources"]:
            if s.get("hours_back") == 168:
                assert topic["name"] in ("AI-Assisted Engineering", "AI Agents & Agent Security")
                assert "hnrss.org" not in s["url"]
