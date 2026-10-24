from datetime import datetime, timedelta, timezone
from xml.sax.saxutils import escape

import pytest
import requests

from src import learn

NOW = datetime(2026, 10, 24, 12, 0, tzinfo=timezone.utc)
AIE, ANT, PRAG = "UCLKPca3kwwd-B59HNr-_lvA", "UCrDwWp7EBBv4NwvScIpBDOA", "UCPbwhExawYrn9xxI21TFfyw"
CONFIG = {"learn": {"max_age_days": 30, "per_channel": 2, "limit": 6,
                    "channels": [{"name": "AI Engineer", "id": AIE}, {"name": "Anthropic", "id": ANT},
                                 {"name": "The Pragmatic Engineer", "id": PRAG}]}}


def entry(vid, title="A talk", days=2.0, views=1000, shorts=False):
    published = (NOW - timedelta(days=days)).isoformat()
    link = f"https://www.youtube.com/{'shorts/' + vid if shorts else 'watch?v=' + vid}"
    stats = "" if views is None else f'<media:community><media:statistics views="{views}"/></media:community>'
    return f"""<entry><id>yt:video:{vid}</id><yt:videoId>{vid}</yt:videoId><title>{escape(title)}</title>
      <link rel="alternate" href="{link}"/><published>{published}</published>
      <media:group><media:title>{escape(title)}</media:title>
      <media:thumbnail url="https://i4.ytimg.com/vi/{vid}/hqdefault.jpg" width="480" height="360"/>{stats}</media:group></entry>"""


def feed(*entries):
    return ('<?xml version="1.0" encoding="UTF-8"?><feed xmlns:yt="http://www.youtube.com/xml/schemas/2015" '
            'xmlns:media="http://search.yahoo.com/mrss/" xmlns="http://www.w3.org/2005/Atom"><title>Ch</title>'
            + "".join(entries) + "</feed>").encode()


class Response:
    def __init__(self, status=200, content=b""):
        self.status_code, self.content = status, content


def fake_get(responses, calls=None):
    def get(url, **kw):
        if calls is not None:
            calls.append((url, kw))
        response = responses[url.split("channel_id=")[1]]
        if isinstance(response, Exception):
            raise response
        return response
    return get


def collect(responses, config=CONFIG):
    return learn.collect(config, NOW, get=fake_get(responses))


# Settings

def test_settings_defaults_and_channels():
    s = learn.settings({"learn": {"channels": [{"name": "AI Engineer", "id": AIE}]}})

    assert (s["max_age_days"], s["per_channel"], s["limit"]) == (30, 2, 6)
    assert s["channels"] == [{"name": "AI Engineer", "id": AIE}]


def test_settings_absent_means_no_learn():
    assert learn.settings({}) is None


@pytest.mark.parametrize("bad", [{}, {"channels": []}, {"channels": [{"name": "X", "id": "@handle"}]},
                                 {"channels": [{"name": "X", "id": "UCshort"}]},
                                 {"channels": [{"name": "", "id": AIE}]}, {"channels": ["AI Engineer"]},
                                 {"channels": [{"name": "A", "id": AIE}, {"name": "B", "id": AIE}]},
                                 {"channels": [{"name": "A", "id": AIE, "handle": 3}]},
                                 {"channels": [{"name": "A", "id": AIE, "url": "x"}]},
                                 {"channels": [{"name": "A", "id": AIE}], "limit": 0},
                                 {"channels": [{"name": "A", "id": AIE}], "per_channel": True},
                                 {"channels": [{"name": "A", "id": AIE}], "max_age_days": "30"},
                                 {"channels": [{"name": "A", "id": AIE}], "max_days": 30}])
def test_settings_invalid_raise_naming_config(bad):
    with pytest.raises(ValueError, match="config.yaml: learn"):
        learn.settings({"learn": bad})


def test_settings_not_a_mapping():
    with pytest.raises(ValueError, match="config.yaml: learn"):
        learn.settings({"learn": ["x"]})


# Parsing and filtering

def test_parse_feed_reads_views_link_and_thumbnail():
    videos = learn.parse_feed(feed(entry("WOszaC1WWbQ", "Evals & <b>agents</b>", days=3, views=12345)),
                              "AI Engineer", AIE)

    v = videos[0]
    assert (v["id"], v["title"], v["channel"], v["views"]) == ("WOszaC1WWbQ", "Evals & <b>agents</b>", "AI Engineer", 12345)
    assert v["published"] == NOW - timedelta(days=3)
    assert v["link"] == "https://www.youtube.com/watch?v=WOszaC1WWbQ"
    assert v["thumb"] == "https://i.ytimg.com/vi/WOszaC1WWbQ/hqdefault.jpg"
    assert v["shorts"] is False


@pytest.mark.parametrize("bad_id", ["short", "WOszaC1WWbQX", "WOszaC1WW<Q", "WOszaC1WW Q", ""])
def test_parse_feed_drops_invalid_video_ids(bad_id):
    assert learn.parse_feed(feed(entry(bad_id)), "AI Engineer", AIE) == []


def test_parse_feed_rejects_non_feed():
    with pytest.raises(learn.LearnUnavailable):
        learn.parse_feed(b"<html><body>Sorry</body></html>", "AI Engineer", AIE)


def test_filters_shorts_zero_views_missing_views_and_old():
    videos = collect({AIE: Response(200, feed(entry("aaaaaaaaaaa", "Keep", days=29),
                                              entry("bbbbbbbbbbb", "Short", shorts=True),
                                              entry("ccccccccccc", "Premiere", views=0),
                                              entry("ddddddddddd", "No stats", views=None),
                                              entry("eeeeeeeeeee", "Old", days=31))),
                      ANT: Response(200, feed()), PRAG: Response(200, feed())})[0]

    assert [v["title"] for v in videos["top"]] == ["Keep"]


def test_ranks_by_views_per_day_with_one_day_floor():
    videos, counts = collect({AIE: Response(200, feed(entry("aaaaaaaaaaa", "New", days=0.1, views=900),
                                                      entry("bbbbbbbbbbb", "Steady", days=10, views=20000))),
                              ANT: Response(200, feed(entry("ccccccccccc", "Mid", days=4, views=4000))),
                              PRAG: Response(200, feed())})

    assert [(v["title"], v["per_day"]) for v in videos["top"]] == [("Steady", 2000), ("Mid", 1000), ("New", 900)]
    assert counts == {"AI Engineer": 2, "Anthropic": 1, "The Pragmatic Engineer": 0}


def test_per_channel_cap_and_limit_then_rest_per_channel():
    config = {"learn": dict(CONFIG["learn"], limit=3)}
    aie = [entry(f"aie{n}xxxxxxx"[:11], f"AIE {n}", days=n + 1, views=10000) for n in range(4)]
    videos, _ = collect({AIE: Response(200, feed(*aie)),
                         ANT: Response(200, feed(entry("antxxxxxxxx", "ANT", days=5, views=500))),
                         PRAG: Response(200, feed(entry("pragxxxxxxx", "PRAG", days=1, views=300)))}, config)

    assert [v["title"] for v in videos["top"]] == ["AIE 0", "AIE 1", "PRAG"]   # AIE 2 is capped out
    rest = {c["name"]: [v["title"] for v in c["videos"]] for c in videos["channels"]}
    assert rest == {"AI Engineer": ["AIE 2", "AIE 3"], "Anthropic": ["ANT"], "The Pragmatic Engineer": []}
    assert videos["channels"][0]["url"] == f"https://www.youtube.com/channel/{AIE}"


def test_request_url_and_user_agent():
    calls = []
    learn.collect(CONFIG, NOW, get=fake_get({AIE: Response(200, feed()), ANT: Response(200, feed()),
                                             PRAG: Response(200, feed())}, calls))

    assert calls[0][0] == f"https://www.youtube.com/feeds/videos.xml?channel_id={AIE}"
    assert "thedailybrief" in calls[0][1]["headers"]["User-Agent"] and calls[0][1]["timeout"]


@pytest.mark.parametrize("broken", [Response(404), Response(200, b"<html>nope</html>"),
                                    requests.ConnectionError("down")])
def test_one_channel_failing_keeps_the_others(broken, caplog):
    videos, counts = collect({AIE: broken, ANT: Response(200, feed(entry("antxxxxxxxx", "ANT"))),
                              PRAG: Response(200, feed())})

    assert [v["title"] for v in videos["top"]] == ["ANT"]
    assert counts == {"AI Engineer": None, "Anthropic": 1, "The Pragmatic Engineer": 0}
    assert [c["name"] for c in videos["channels"]] == ["Anthropic", "The Pragmatic Engineer"]
    assert "Learn: AI Engineer" in caplog.text


def test_every_channel_failing_raises():
    with pytest.raises(learn.LearnUnavailable, match="AI Engineer.*Anthropic.*Pragmatic"):
        collect({AIE: Response(500), ANT: requests.Timeout("slow"), PRAG: Response(200, b"garbage")})
