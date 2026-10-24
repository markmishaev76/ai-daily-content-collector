from datetime import datetime, timedelta, timezone

import pytest
import requests

from src import pulse

NOW = datetime(2026, 10, 23, 3, 0, tzinfo=timezone.utc)
CONFIG = {"pulse": {"min_upvotes": 100, "limit": 3, "max_age_hours": 24,
                    "subreddits": [{"name": "EngineeringManagers", "min_upvotes": 20}, "ClaudeAI"]}}
KEYWORDS = ["claude", "security", "hacked"]
FEEDS = {"pulse": {"limit": 10, "max_age_hours": 24, "keywords": KEYWORDS,
                   "hacker_news": {"min_points": 100}, "lobsters": {"min_score": 15, "tags": ["ai", "security"]}},
         "story": {"source_tiers": {"primary": ["openai.com"]}}}


def post(title="A post", ups=500, hours=2, sub="ClaudeAI", **kw):
    slug = title.lower().replace(" ", "_")
    data = {"title": title, "ups": ups, "score": ups, "num_comments": 42, "created_utc": NOW.timestamp() - hours * 3600,
            "subreddit": sub, "permalink": f"/r/{sub}/comments/abc/{slug}/", "url": f"https://www.reddit.com/r/{sub}/comments/abc/{slug}/",
            "is_self": True, "stickied": False, "pinned": False, "over_18": False, "author": "someone",
            "selftext": "body", "distinguished": None, "removed_by_category": None, "link_flair_text": None}
    data.update(kw)
    return data


def hit(title="Claude ships a thing", points=300, hours=2, url="https://example.com/a", id="1", comments=50):
    return {"objectID": id, "title": title, "url": url, "points": points, "num_comments": comments,
            "created_at_i": int(NOW.timestamp() - hours * 3600)}


def story(title="Claude ships a thing", score=40, hours=2, url="https://example.com/a", id="abc", tags=("programming",),
          comments=7):
    created = (NOW - timedelta(hours=hours)).astimezone(timezone(timedelta(hours=-5))).isoformat()
    return {"short_id": id, "title": title, "url": url, "score": score, "comment_count": comments, "tags": list(tags),
            "created_at": created, "comments_url": f"https://lobste.rs/s/{id}/slug"}


def listing(*posts):
    return {"kind": "Listing", "data": {"children": [{"kind": "t3", "data": p} for p in posts]}}


class Response:
    def __init__(self, status=200, body=None):
        self.status_code, self.body = status, body

    def json(self):
        if isinstance(self.body, Exception):
            raise self.body
        return self.body


def fake_get(responses, calls=None):
    def get(url, **kw):
        if calls is not None:
            calls.append((url, kw))
        key = "hn" if "algolia" in url else "lobsters" if "lobste.rs" in url else url.split("/r/")[1].split("/")[0]
        response = responses[key]
        if isinstance(response, Exception):
            raise response
        return response
    return get


def feeds(hn=(), lobsters=(), **kw):
    responses = {"hn": hn if isinstance(hn, (Response, Exception)) else Response(200, {"hits": list(hn)}),
                 "lobsters": lobsters if isinstance(lobsters, (Response, Exception)) else Response(200, list(lobsters))}
    return pulse.collect(FEEDS, NOW, env={}, get=fake_get(responses), **kw)


# Settings

def test_settings_with_overrides():
    s = pulse.settings(CONFIG)

    assert s["limit"] == 3 and s["max_age_hours"] == 24
    assert s["subreddits"] == [("EngineeringManagers", 20), ("ClaudeAI", 100)]
    assert s["hacker_news"] is None and s["lobsters"] is None


def test_settings_feed_sources_and_defaults():
    s = pulse.settings({"pulse": {"hacker_news": {}, "lobsters": {"tags": ["ai"]}}})

    assert s["subreddits"] == []
    assert s["hacker_news"] == {"min_points": 100}
    assert s["lobsters"] == {"min_score": 15, "tags": frozenset({"ai"})}


@pytest.mark.parametrize("bad", [{"subreddits": []}, {"subreddits": ["bad name!"]}, {"subreddits": ["a"], "min_upvotes": -1},
                                 {"subreddits": [{"name": "a", "min_upvotes": "x"}]}, {"subreddits": ["a"], "limit": 0},
                                 {}, {"hacker_news": {"min_points": 0}}, {"hacker_news": {"min_points": True}},
                                 {"hacker_news": "yes"}, {"hacker_news": {"points": 5}},
                                 {"lobsters": {"min_score": "15"}}, {"lobsters": {"tags": "ai"}},
                                 {"lobsters": {"tags": ["Not A Tag"]}}, {"hacker_news": {}, "keywords": "ai"},
                                 {"hacker_news": {}, "keywords": ["ai", ""]}, {"hacker_news": {}, "keyword": ["ai"]}])
def test_settings_invalid_raise_naming_config(bad):
    with pytest.raises(ValueError, match="config.yaml: pulse"):
        pulse.settings({"pulse": bad})


def test_settings_absent_means_no_pulse():
    assert pulse.settings({}) is None


# Relevance

@pytest.mark.parametrize("title,link,tags", [
    ("Building an MCP server for docs", None, ()),                           # main.AX_THEME_KEYWORDS
    ("A security review of iOS", None, ()),                                  # pulse.keywords
    ("Hacker leaks data; database was compromised", None, ()),               # story.BREACH_RE
    ("Notes on CVE-2026-12345", None, ()),                                   # story CVE ids
    ("Securing our training environment", "https://openai.com/index/x", ()),  # story.source_tiers.primary
    ("Swedish offices ban ChatGPT and CLAUDE", None, ()),                    # keywords are case-insensitive
    ("UB is fine", None, ("c", "security")),                                 # Lobsters tag allowlist
])
def test_relevant(title, link, tags):
    assert pulse.relevant(title, link, tags, pulse.settings(FEEDS))


@pytest.mark.parametrize("title,link,tags", [
    ("Apple Music 404 Not Found", "https://music.apple.com/x", ()),
    ("Claudette's bakery opens", None, ()),        # whole words only
    ("Docker is weird", None, ("programming",)),
])
def test_not_relevant(title, link, tags):
    assert not pulse.relevant(title, link, tags, pulse.settings(FEEDS))


# Reddit

@pytest.mark.parametrize("kw", [{"stickied": True}, {"pinned": True}, {"over_18": True},
                                {"removed_by_category": "moderator"}, {"author": "[deleted]"}, {"selftext": "[removed]"},
                                {"distinguished": "moderator"}, {"link_flair_text": "Meta"},
                                {"link_flair_text": "Weekly Megathread"}, {"hours": 25}, {"ups": 99}])
def test_qualifies_excludes(kw):
    assert not pulse.qualifies(post(**kw), NOW, 100, 24)


def test_qualifies_normal_post():
    assert pulse.qualifies(post(link_flair_text="Discussion"), NOW, 100, 24)


def test_to_item_link_post_with_preview():
    p = post(is_self=False, url="https://blog.example.com/x",
             preview={"images": [{"source": {"url": "https://preview.redd.it/a.jpg?width=640&amp;s=1"}}]})

    item = pulse.to_item(p)

    assert item["thread"] == "https://www.reddit.com/r/ClaudeAI/comments/abc/a_post/"
    assert item["link"] == "https://blog.example.com/x"
    assert item["image"] == "https://preview.redd.it/a.jpg?width=640&s=1"
    assert (item["points"], item["unit"], item["comments"], item["source"]) == (500, "upvotes", 42, "r/ClaudeAI")
    assert item["created"] == datetime.fromtimestamp(p["created_utc"], tz=timezone.utc)


def test_to_item_self_post_has_no_external_link_or_http_image():
    item = pulse.to_item(post(preview={"images": [{"source": {"url": "http://x/a.jpg"}}]}))

    assert item["link"] is None and item["image"] is None


def test_collect_public_json_top_across_subs():
    calls = []
    responses = {"EngineeringManagers": Response(200, listing(post("EM low", 30, sub="EngineeringManagers"),
                                                              post("EM too low", 10, sub="EngineeringManagers"))),
                 "ClaudeAI": Response(200, listing(post("C big", 900), post("C mid", 300), post("C small", 150),
                                                   post("C stickied", 5000, stickied=True)))}

    items, counts = pulse.collect(CONFIG, NOW, env={}, get=fake_get(responses, calls))

    assert [i["title"] for i in items] == ["C big", "C mid", "C small"]   # C small and EM low tie at 1.5x
    assert counts == {"r/EngineeringManagers": 1, "r/ClaudeAI": 3}
    url, kw = calls[0]
    assert url == "https://www.reddit.com/r/EngineeringManagers/top.json"
    assert kw["params"]["t"] == "day" and "thedailybrief" in kw["headers"]["User-Agent"]


def test_collect_uses_oauth_when_credentials_set():
    calls, posts = [], []

    def post_token(url, **kw):
        posts.append((url, kw))
        return Response(200, {"access_token": "tok", "token_type": "bearer"})

    responses = {"EngineeringManagers": Response(200, listing()), "ClaudeAI": Response(200, listing(post()))}
    items, _ = pulse.collect(CONFIG, NOW, env={"REDDIT_CLIENT_ID": "id", "REDDIT_CLIENT_SECRET": "sec"},
                             get=fake_get(responses, calls), post=post_token)

    assert posts[0][0] == "https://www.reddit.com/api/v1/access_token"
    assert posts[0][1]["auth"] == ("id", "sec") and posts[0][1]["data"] == {"grant_type": "client_credentials"}
    assert calls[0][0] == "https://oauth.reddit.com/r/EngineeringManagers/top"
    assert calls[0][1]["headers"]["Authorization"] == "Bearer tok"
    assert len(items) == 1


def test_collect_all_blocked_raises_with_hint():
    responses = {"EngineeringManagers": Response(403, None), "ClaudeAI": Response(403, None)}

    with pytest.raises(pulse.PulseUnavailable, match="REDDIT_CLIENT_ID"):
        pulse.collect(CONFIG, NOW, env={}, get=fake_get(responses))


def test_collect_partial_failure_keeps_other_subs():
    responses = {"EngineeringManagers": Response(500, None), "ClaudeAI": Response(200, listing(post()))}

    items, counts = pulse.collect(CONFIG, NOW, env={}, get=fake_get(responses))

    assert len(items) == 1 and counts == {"r/EngineeringManagers": None, "r/ClaudeAI": 1}


def test_collect_bad_json_or_token_failure_is_unavailable():
    responses = {"EngineeringManagers": Response(200, ValueError("html")), "ClaudeAI": Response(200, {"oops": 1})}
    with pytest.raises(pulse.PulseUnavailable):
        pulse.collect(CONFIG, NOW, env={}, get=fake_get(responses))

    with pytest.raises(pulse.PulseUnavailable, match="token"):
        pulse.collect(CONFIG, NOW, env={"REDDIT_CLIENT_ID": "id", "REDDIT_CLIENT_SECRET": "sec"},
                      get=fake_get(responses), post=lambda url, **kw: Response(401, {}))


# Hacker News and Lobsters

def test_hacker_news_request_and_item():
    calls = []
    responses = {"hn": Response(200, {"hits": [hit(id="42", comments=12)]}), "lobsters": Response(200, [])}

    items, counts = pulse.collect(FEEDS, NOW, env={}, get=fake_get(responses, calls))

    url, kw = calls[0]
    assert url == "https://hn.algolia.com/api/v1/search"
    assert kw["params"]["tags"] == "story"
    assert kw["params"]["numericFilters"] == f"created_at_i>{int(NOW.timestamp()) - 24 * 3600},points>=100"
    item = items[0]
    assert (item["source"], item["points"], item["unit"], item["comments"]) == ("Hacker News", 300, "points", 12)
    assert item["thread"] == "https://news.ycombinator.com/item?id=42"
    assert item["link"] == "https://example.com/a" and item["image"] is None
    assert item["created"] == NOW - timedelta(hours=2)
    assert counts == {"Hacker News": 1, "Lobsters": 0}


def test_hacker_news_filters_age_score_and_relevance():
    items, counts = feeds(hn=[hit("Claude ok", id="1"), hit("Claude old", hours=25, id="2"),
                              hit("Claude low", points=99, id="3"), hit("Off topic", id="4"),
                              hit("Ask HN: Claude?", url=None, id="5"), hit(None, id="6")])

    assert [i["title"] for i in items] == ["Ask HN: Claude?", "Claude ok"]
    assert next(i for i in items if i["title"].startswith("Ask"))["link"] is None
    assert counts["Hacker News"] == 2


def test_lobsters_filters_age_score_tags_and_relevance():
    items, counts = feeds(lobsters=[story("Claude ok", id="a", url="https://x.dev/1"),
                                    story("Claude old", hours=25, id="b", url="https://x.dev/2"),
                                    story("Claude low", score=14, id="c", url="https://x.dev/3"),
                                    story("Off topic", id="d", url="https://x.dev/4"),
                                    story("Tagged", tags=("ai",), id="e", url=""),
                                    story("Mangled", id="f", url="https://x.dev/6") | {"score": None},
                                    story("Claude odd", id="g", url="https://x.dev/7") | {"comment_count": "many"}])

    by_title = {i["title"]: i for i in items}
    assert set(by_title) == {"Claude ok", "Tagged", "Claude odd"} and by_title["Claude odd"]["comments"] == 0
    tagged = by_title["Tagged"]
    assert (tagged["source"], tagged["points"], tagged["unit"], tagged["comments"]) == ("Lobsters", 40, "points", 7)
    assert tagged["link"] is None and tagged["thread"] == "https://lobste.rs/s/e/slug"
    assert tagged["created"] == NOW - timedelta(hours=2)
    assert counts["Lobsters"] == 3


def test_dedupe_against_page_links():
    shown = ["https://www.example.com/a/", "https://example.com/lead"]
    items, _ = feeds(hn=[hit(url="http://example.com/a", id="1"), hit(url="https://example.com/lead#top", id="2"),
                         hit(url="https://example.com/b", id="3")], shown=shown)

    assert [i["link"] for i in items] == ["https://example.com/b"]


def test_dedupe_across_sources_keeps_higher_rank_and_both_discussions():
    items, _ = feeds(hn=[hit(points=200, url="https://example.com/a", id="9")],
                     lobsters=[story(score=60, url="https://www.example.com/a/", id="z")])

    assert len(items) == 1
    item = items[0]
    assert item["source"] == "Lobsters" and item["points"] == 60
    assert item["also"] == [{"source": "Hacker News", "thread": "https://news.ycombinator.com/item?id=9"}]


def test_ranking_normalizes_points_by_each_source_threshold():
    config = {"pulse": dict(FEEDS["pulse"], subreddits=[{"name": "EngineeringManagers", "min_upvotes": 25}])}
    responses = {"hn": Response(200, {"hits": [hit("Claude HN", points=300, url="https://e.com/1")]}),
                 "lobsters": Response(200, [story("Claude Lob", score=60, url="https://e.com/2")]),
                 "EngineeringManagers": Response(200, listing(post("EM", 50, sub="EngineeringManagers")))}

    items, _ = pulse.collect(config, NOW, env={}, get=fake_get(responses))

    assert [i["title"] for i in items] == ["Claude Lob", "Claude HN", "EM"]   # 60/15=4, 300/100=3, 50/25=2


def test_limit_applies_after_merge():
    config = {"pulse": dict(FEEDS["pulse"], limit=2)}
    responses = {"hn": Response(200, {"hits": [hit(f"Claude {n}", points=100 + n, url=f"https://e.com/{n}", id=str(n))
                                               for n in range(5)]}), "lobsters": Response(200, [])}

    items, _ = pulse.collect(config, NOW, env={}, get=fake_get(responses))

    assert [i["title"] for i in items] == ["Claude 4", "Claude 3"]


@pytest.mark.parametrize("broken", [Response(500, None), Response(200, ValueError("html")), Response(200, {"oops": 1}),
                                    requests.ConnectionError("down")])
def test_one_source_failing_keeps_the_others(broken, caplog):
    items, counts = feeds(hn=broken, lobsters=[story()])

    assert [i["source"] for i in items] == ["Lobsters"]
    assert counts == {"Hacker News": None, "Lobsters": 1}
    assert "The Pulse: Hacker News" in caplog.text


def test_lobsters_bad_shape_is_a_source_failure():
    items, counts = feeds(hn=[hit()], lobsters=Response(200, {"not": "a list"}))

    assert counts == {"Hacker News": 1, "Lobsters": None} and len(items) == 1


def test_every_source_failing_raises():
    with pytest.raises(pulse.PulseUnavailable, match="Hacker News.*Lobsters"):
        feeds(hn=Response(503, None), lobsters=requests.Timeout("slow"))
