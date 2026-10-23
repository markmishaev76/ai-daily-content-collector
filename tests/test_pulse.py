from datetime import datetime, timezone

import pytest

from src import pulse

NOW = datetime(2026, 10, 23, 3, 0, tzinfo=timezone.utc)
CONFIG = {"pulse": {"min_upvotes": 100, "limit": 3, "max_age_hours": 24,
                    "subreddits": [{"name": "EngineeringManagers", "min_upvotes": 20}, "ClaudeAI"]}}


def post(title="A post", ups=500, hours=2, sub="ClaudeAI", **kw):
    data = {"title": title, "ups": ups, "score": ups, "num_comments": 42, "created_utc": NOW.timestamp() - hours * 3600,
            "subreddit": sub, "permalink": f"/r/{sub}/comments/abc/a_post/", "url": f"https://www.reddit.com/r/{sub}/comments/abc/a_post/",
            "is_self": True, "stickied": False, "pinned": False, "over_18": False, "author": "someone",
            "selftext": "body", "distinguished": None, "removed_by_category": None, "link_flair_text": None}
    data.update(kw)
    return data


def listing(*posts):
    return {"kind": "Listing", "data": {"children": [{"kind": "t3", "data": p} for p in posts]}}


class Response:
    def __init__(self, status=200, body=None):
        self.status_code, self.body = status, body

    def json(self):
        if isinstance(self.body, Exception):
            raise self.body
        return self.body


def test_settings_with_overrides():
    s = pulse.settings(CONFIG)

    assert s["limit"] == 3 and s["max_age_hours"] == 24
    assert s["subreddits"] == [("EngineeringManagers", 20), ("ClaudeAI", 100)]


@pytest.mark.parametrize("bad", [{"subreddits": []}, {"subreddits": ["bad name!"]}, {"subreddits": ["a"], "min_upvotes": -1},
                                 {"subreddits": [{"name": "a", "min_upvotes": "x"}]}, {"subreddits": ["a"], "limit": 0}])
def test_settings_invalid_raise_naming_config(bad):
    with pytest.raises(ValueError, match="config.yaml: pulse"):
        pulse.settings({"pulse": bad})


def test_settings_absent_means_no_pulse():
    assert pulse.settings({}) is None


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
    assert (item["ups"], item["comments"], item["subreddit"]) == (500, 42, "ClaudeAI")
    assert item["created"] == datetime.fromtimestamp(p["created_utc"], tz=timezone.utc)


def test_to_item_self_post_has_no_external_link_or_http_image():
    item = pulse.to_item(post(preview={"images": [{"source": {"url": "http://x/a.jpg"}}]}))

    assert item["link"] is None and item["image"] is None


def fake_get(responses, calls):
    def get(url, **kw):
        calls.append((url, kw))
        sub = url.split("/r/")[1].split("/")[0]
        return responses[sub]
    return get


def test_collect_public_json_top_across_subs():
    calls = []
    responses = {"EngineeringManagers": Response(200, listing(post("EM low", 30, sub="EngineeringManagers"),
                                                              post("EM too low", 10, sub="EngineeringManagers"))),
                 "ClaudeAI": Response(200, listing(post("C big", 900), post("C mid", 300), post("C small", 150),
                                                   post("C stickied", 5000, stickied=True)))}

    items, counts = pulse.collect(CONFIG, NOW, env={}, get=fake_get(responses, calls))

    assert [i["title"] for i in items] == ["C big", "C mid", "C small"]
    assert counts == {"EngineeringManagers": 1, "ClaudeAI": 3}
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
        pulse.collect(CONFIG, NOW, env={}, get=fake_get(responses, []))


def test_collect_partial_failure_keeps_other_subs():
    responses = {"EngineeringManagers": Response(500, None), "ClaudeAI": Response(200, listing(post()))}

    items, counts = pulse.collect(CONFIG, NOW, env={}, get=fake_get(responses, []))

    assert len(items) == 1 and counts == {"EngineeringManagers": None, "ClaudeAI": 1}


def test_collect_bad_json_or_token_failure_is_unavailable():
    responses = {"EngineeringManagers": Response(200, ValueError("html")), "ClaudeAI": Response(200, {"oops": 1})}
    with pytest.raises(pulse.PulseUnavailable):
        pulse.collect(CONFIG, NOW, env={}, get=fake_get(responses, []))

    with pytest.raises(pulse.PulseUnavailable, match="token"):
        pulse.collect(CONFIG, NOW, env={"REDDIT_CLIENT_ID": "id", "REDDIT_CLIENT_SECRET": "sec"},
                      get=fake_get(responses, []), post=lambda url, **kw: Response(401, {}))
