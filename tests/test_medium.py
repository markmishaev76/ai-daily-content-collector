import requests

from src import medium


def post(url, title="T", date="2026-01-01"):
    return {"title": title, "url": url, "date": date, "source": "medium"}


def test_merge_keeps_posts_missing_from_feed():
    saved = [post("a", date="2025-01-01"), post("b", date="2025-06-01")]
    fetched = [post("b", date="2025-06-01"), post("c", date="2026-01-01")]

    merged = medium.merge_posts(saved, fetched)

    assert [p["url"] for p in merged] == ["c", "b", "a"]


def test_merge_fetched_wins_on_same_url():
    merged = medium.merge_posts([post("a", title="Old")], [post("a", title="New")])

    assert merged == [post("a", title="New")]


def test_merge_sorts_newest_first_undated_last():
    posts = [post("old", date="2023-08-06"), post("none", date=None), post("new", date="2026-04-17")]

    merged = medium.merge_posts(posts, [])

    assert [p["url"] for p in merged] == ["new", "old", "none"]


def test_fetch_returns_none_on_http_error(monkeypatch):
    def boom(*args, **kwargs):
        raise requests.ConnectionError("down")

    monkeypatch.setattr(medium.requests, "get", boom)

    assert medium.fetch_medium_posts("https://medium.com/feed/@x") is None


def test_save_reports_unchanged(tmp_path):
    path = tmp_path / "medium-posts.json"
    posts = [post("a")]

    assert medium.save(path, posts) is True
    assert medium.save(path, posts) is False
    assert medium.load_saved(path) == posts
