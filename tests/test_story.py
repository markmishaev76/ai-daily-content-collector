from datetime import datetime, timezone

from src import story

NOW = datetime(2026, 10, 23, 3, 0, tzinfo=timezone.utc)
TIERS = {"primary": ["datatracker.ietf.org", "openai.com", "aws.amazon.com/blogs/security"],
         "aggregator": ["hnrss.org", "news.ycombinator.com"]}
HN_SUMMARY = ("Article URL: https://example.com/post-2026-11\nComments URL: https://news.ycombinator.com/item?id=1\n"
              "Points: 120\n# Comments: 45")


def art(title, link=None, summary="", published=NOW, source="Src", feed="https://feeds.example.com/rss",
        image=None, section="S"):
    link = link or "https://example.com/" + "".join(c for c in title.lower() if c.isalnum())
    return {"title": title, "link": link, "summary": summary, "published": published, "source": source,
            "feed": feed, "image": image, "section": section}


def test_hn_points_parsed():
    assert story.hn_points(HN_SUMMARY) == 165
    assert story.hn_points("Points: 7") == 7
    assert story.hn_points("A normal summary with 12 points") == 0
    assert story.hn_points(None) == 0


def test_ids_extracted_and_normalized():
    ids = story.extract_ids("Fix for cve-2026-109618 and RFC9700, see draft-ietf-oauth-foo-03")

    assert ids == {"CVE-2026-109618", "RFC 9700", "draft-ietf-oauth-foo"}
    assert story.extract_ids("rfc 6749 basics") == {"RFC 6749"}


def test_hn_boilerplate_has_no_ids_or_tokens():
    article = art("Show HN: a tool", summary=HN_SUMMARY)

    assert story.article_ids(article) == frozenset()
    assert story.title_tokens("The and of a to") == frozenset()


def test_title_tokens_normalized():
    assert story.title_tokens("Microsoft Patches: Exchange Zero-Days!") == {"microsoft", "patche", "exchange",
                                                                          "zero", "day"}


def test_hard_news_wording():
    hard = ["Exchange flaw CVE-2026-1234 exploited", "RFC 9700 published", "New draft-ietf-wimse-arch-01",
            "Kubernetes 1.35 released", "Retailer discloses data breach", "Zero-day actively exploited in Chrome"]
    soft = ["Thoughts on code review", "Why I moved to Rust in 2026", "Version control tips"]

    assert all(story.is_hard_news(art(t)) for t in hard)
    assert not any(story.is_hard_news(art(t)) for t in soft)


def test_source_tier():
    assert story.source_tier(art("a", link="https://datatracker.ietf.org/doc/x/"), TIERS) == "primary"
    assert story.source_tier(art("a", link="https://aws.amazon.com/blogs/security/x/"), TIERS) == "primary"
    assert story.source_tier(art("a", link="https://aws.amazon.com/blogs/aws/x/"), TIERS) == "normal"
    assert story.source_tier(art("a", link="https://example.com/x", feed="https://hnrss.org/newest?q=x"),
                             TIERS) == "aggregator"
    assert story.source_tier(art("a", link="https://openai.com/x", feed="https://hnrss.org/newest"),
                             TIERS) == "primary"
    assert story.source_tier(art("a", link="https://notopenai.com/x"), TIERS) == "normal"


def test_domain_strips_www():
    assert story.domain("https://www.Example.com/a") == "example.com"
    assert story.domain("not a url") == ""
