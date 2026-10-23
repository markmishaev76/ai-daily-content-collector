from datetime import date

from src import enrich

TODAY = date(2026, 10, 23)
PAGE = """<html><head>
<meta property="og:image" content="/img/cover.png">
<meta property="og:description" content="A real description.">
<link rel="icon" href="/favicon.png">
<link rel="apple-touch-icon" href="https://cdn.example.com/touch.png">
</head><body>ignored</body></html>"""


def test_parse_meta_resolves_relative_and_prefers_touch_icon():
    meta = enrich.parse_meta(PAGE, "https://example.com/post/1")

    assert meta == {"image": "https://example.com/img/cover.png", "description": "A real description.",
                    "icon": "https://cdn.example.com/touch.png"}


def test_parse_meta_falls_back_and_drops_http():
    page = """<head><meta property="og:image" content="http://x.com/a.png">
    <meta name="twitter:image" content="https://x.com/t.png"><meta name="description" content="Plain">
    <link rel="shortcut icon" href="http://x.com/fav.ico"></head>"""

    assert enrich.parse_meta(page, "https://x.com/") == {"image": "https://x.com/t.png", "description": "Plain",
                                                         "icon": None}
    assert enrich.parse_meta("<html></html>", "https://x.com/") == {"image": None, "description": None, "icon": None}


class FakeResponse:
    def __init__(self, body, content_type="text/html; charset=utf-8", url="https://example.com/post/1"):
        self.body, self.headers, self.url, self.encoding = body, {"Content-Type": content_type}, url, "utf-8"
        self.read = 0

    def raise_for_status(self):
        pass

    def iter_content(self, size):
        for i in range(0, len(self.body), size):
            self.read += size
            yield self.body[i:i + size]

    def close(self):
        pass


def test_fetch_meta_reads_head_only_with_cap(monkeypatch):
    calls = {}
    body = PAGE.encode() + b"x" * 2_000_000
    response = FakeResponse(body)

    def get(url, **kw):
        calls.update(kw, url=url)
        return response

    monkeypatch.setattr(enrich.requests, "get", get)
    meta = enrich.fetch_meta("https://example.com/post/1", is_public=lambda u: True)

    assert meta["image"] == "https://example.com/img/cover.png"
    assert response.read <= enrich.MAX_BYTES
    assert calls["stream"] is True and calls["timeout"] == enrich.TIMEOUT
    assert "DailyBrief" in calls["headers"]["User-Agent"]


def test_fetch_meta_misses_never_raise(monkeypatch):
    def boom(url, **kw):
        raise enrich.requests.ConnectionError("down")

    monkeypatch.setattr(enrich.requests, "get", boom)
    assert enrich.fetch_meta("https://example.com/a", is_public=lambda u: True) is None

    monkeypatch.setattr(enrich.requests, "get", lambda url, **kw: FakeResponse(b"%PDF", "application/pdf"))
    assert enrich.fetch_meta("https://example.com/a.pdf", is_public=lambda u: True) is None

    monkeypatch.setattr(enrich.requests, "get", lambda url, **kw: 1 / 0)
    assert enrich.fetch_meta("http://10.0.0.1/", is_public=lambda u: False) is None
    assert enrich.fetch_meta("javascript:alert(1)", is_public=lambda u: True) is None


def entry(days_ago, image="https://e.com/i.png"):
    return {"fetched": date.fromordinal(TODAY.toordinal() - days_ago).isoformat(), "image": image,
            "description": None, "icon": None}


def test_cache_freshness_rules():
    assert enrich.is_fresh(entry(29), TODAY)
    assert not enrich.is_fresh(entry(31), TODAY)
    assert enrich.is_fresh(entry(6, image=None), TODAY)
    assert not enrich.is_fresh(entry(8, image=None), TODAY)


def test_cache_load_save_prunes(tmp_path):
    path = tmp_path / "og-cache.json"
    enrich.save_cache(path, {"https://a": entry(1), "https://old": entry(40)}, TODAY)

    assert list(enrich.load_cache(path)) == ["https://a"]
    path.write_text("{broken")
    assert enrich.load_cache(path) == {}
    assert enrich.load_cache(tmp_path / "missing.json") == {}


def art(link, image=None, **kw):
    return {"title": "T", "link": link, "summary": "", "image": image, "feed": "https://f.com/rss", **kw}


def test_enrich_fills_missing_images_and_uses_cache():
    fetched = []

    def fetch(url):
        fetched.append(url)
        return {"image": f"{url}/og.png", "description": "D", "icon": f"{url}/icon.png"}

    has_image = art("https://a.com/1", image="https://a.com/feed.png")
    cached = art("https://b.com/1")
    missing = art("https://c.com/1")
    dup = art("https://c.com/1")
    hn_comments = art("https://news.ycombinator.com/item?id=1", feed="https://hnrss.org/newest")
    cache = {"https://b.com/1": {"fetched": TODAY.isoformat(), "image": None, "description": None,
                                 "icon": "https://b.com/i.png"}}

    stats = enrich.enrich([has_image, cached, missing, dup, hn_comments], cache, TODAY, fetch=fetch)

    assert fetched == ["https://c.com/1"]
    assert has_image["image"] == "https://a.com/feed.png" and "icon" not in has_image
    assert missing["image"] == "https://c.com/1/og.png" and dup["image"] == missing["image"]
    assert missing["og_description"] == "D"
    assert cached["image"] is None and cached["icon"] == "https://b.com/i.png"
    assert cache["https://c.com/1"]["fetched"] == TODAY.isoformat()
    assert stats == {"fetched": 1, "cached": 1, "og_images": 2}


def test_enrich_fetches_hn_items_for_description_and_records_misses():
    hn = art("https://github.com/x/y", image="https://gh.com/i.png", feed="https://hnrss.org/newest")
    gone = art("https://gone.com/1")
    cache = {}

    enrich.enrich([hn, gone], cache, TODAY, fetch=lambda url: {"image": None, "description": "Repo", "icon": None}
                  if "github" in url else None)

    assert hn["og_description"] == "Repo" and hn["image"] == "https://gh.com/i.png"
    assert cache["https://gone.com/1"] == {"fetched": TODAY.isoformat(), "image": None, "description": None,
                                           "icon": None}


def test_enrich_survives_a_fetch_that_raises():
    def fetch(url):
        raise RuntimeError("boom")

    article = art("https://a.com/1")
    cache = {}

    enrich.enrich([article], cache, TODAY, fetch=fetch)

    assert article["image"] is None and cache["https://a.com/1"]["image"] is None


def test_icon_falls_back_to_site_favicon():
    found = art("https://www.blog.dev/post")
    blocked = art("https://blocked.dev/post")
    plain_http = art("http://old.dev/post")

    enrich.enrich([found, blocked, plain_http], {}, TODAY,
                  fetch=lambda url: {"image": None, "description": None, "icon": None} if "blog" in url else None)

    assert found["icon"] == "https://www.blog.dev/favicon.ico"
    assert blocked["icon"] == "https://blocked.dev/favicon.ico"
    assert "icon" not in plain_http
