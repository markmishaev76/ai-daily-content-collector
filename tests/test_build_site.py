import json
from datetime import datetime, timezone

import build_site


class FakeAggregator:
    def __init__(self, feed):
        self.feed = feed

    def aggregate_content(self, topics):
        return self.feed


def article(n):
    return {"title": f"A{n}", "link": f"https://example.com/{n}", "summary": "",
            "published": datetime(2026, 10, 22, tzinfo=timezone.utc), "source": "S"}


CONFIG = {"topics": [{"name": "T", "sources": []}], "brief": {"max_articles_per_topic": 5}}


def run(tmp_path, feed, fetch_medium=lambda url: []):
    out = tmp_path / "public"
    code = build_site.main(out_dir=out, config=CONFIG, aggregator=FakeAggregator(feed),
                           fetch_medium=fetch_medium, data_path=tmp_path / "medium.json",
                           posts_dir=tmp_path / "posts", about_path=tmp_path / "about.md")
    return code, out


def test_zero_articles_exits_1_and_writes_nothing(tmp_path):
    code, out = run(tmp_path, {"T": []})

    assert code == 1
    assert not (out / "index.html").exists()


def test_medium_failure_keeps_saved_file(tmp_path):
    saved = [{"title": "Kept", "url": "https://medium.com/p/1", "date": "2025-01-01", "source": "medium"}]
    (tmp_path / "medium.json").write_text(json.dumps(saved))
    before = (tmp_path / "medium.json").read_text()

    code, out = run(tmp_path, {"T": [article(1)]}, fetch_medium=lambda url: None)

    assert code == 0
    assert (tmp_path / "medium.json").read_text() == before
    assert "Kept" in (out / "index.html").read_text()


def test_cuts_to_max_per_topic():
    feed = build_site.select_feed(CONFIG, FakeAggregator({"T": [article(i) for i in range(8)]}))

    assert len(feed["T"]) == 5
