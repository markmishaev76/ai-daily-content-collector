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


NOW = datetime(2026, 10, 23, 3, 0, tzinfo=timezone.utc)


def run(tmp_path, feed, fetch_medium=lambda url: []):
    out = tmp_path / "public"
    code = build_site.main(out_dir=out, config=CONFIG, aggregator=FakeAggregator(feed),
                           fetch_medium=fetch_medium, data_path=tmp_path / "medium.json",
                           posts_dir=tmp_path / "posts", about_path=tmp_path / "about.md",
                           history_path=tmp_path / "lead-history.json", pinned_path=tmp_path / "pinned.yaml",
                           now=NOW)
    return code, out


def lead_block(out):
    html = (out / "index.html").read_text()
    start = html.index('class="lead')
    return html[start:html.index("<!-- /lead -->", start)], html


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
    raw, feed = build_site.fetch_feed(CONFIG, FakeAggregator({"T": [article(i) for i in range(8)]}))

    assert len(raw["T"]) == 8
    assert len(feed["T"]) == 5


def test_lead_uses_articles_below_cut_and_writes_history(tmp_path):
    items = [article(i) for i in range(7)] + [dict(article(7), title="Patch now: CVE-2026-109618")]

    code, out = run(tmp_path, {"T": items})
    lead, html = lead_block(out)
    history = json.loads((tmp_path / "lead-history.json").read_text())

    assert code == 0
    assert "CVE-2026-109618" in lead
    assert html.count("Patch now: CVE-2026-109618") == 1
    assert [(e["date"], e["url"], e["section"]) for e in history] == [("2026-10-23", "https://example.com/7", "T")]
    assert "CVE-2026-109618" in history[0]["key_tokens"]


def test_pinned_lead_through_build(tmp_path):
    (tmp_path / "pinned.yaml").write_text("url: https://example.com/2\nnote: Worth it\nuntil: 2026-10-23\n")

    code, out = run(tmp_path, {"T": [article(i) for i in range(4)]})
    lead, _ = lead_block(out)

    assert code == 0
    assert "A2" in lead and "Worth it" in lead


def test_invalid_pinned_fails_build(tmp_path, caplog):
    (tmp_path / "pinned.yaml").write_text("url: javascript:alert(1)\nuntil: 2026-10-30\n")

    code, out = run(tmp_path, {"T": [article(1)]})

    assert code == 1
    assert not (out / "index.html").exists()
    assert not (tmp_path / "lead-history.json").exists()
    assert "pinned.yaml" in caplog.text
