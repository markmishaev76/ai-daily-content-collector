import json
from datetime import date

import pytest

from src import story

TODAY = date(2026, 10, 23)


def entry(day, n=0):
    return {"date": day, "url": f"https://example.com/{n}", "title": f"T{n}", "section": "S", "key_tokens": ["t"]}


def test_history_missing_is_empty(tmp_path):
    assert story.load_history(tmp_path / "none.json") == []


def test_history_invalid_raises_naming_file(tmp_path):
    path = tmp_path / "lead-history.json"
    path.write_text("{not json")

    with pytest.raises(ValueError, match="lead-history.json"):
        story.load_history(path)
    path.write_text('{"a": 1}')
    with pytest.raises(ValueError, match="lead-history.json"):
        story.load_history(path)


def test_history_capped_and_written(tmp_path):
    path = tmp_path / "data" / "lead-history.json"
    history = [entry(f"2026-09-{d:02d}", d) for d in range(1, 31)]

    history = story.record_lead(history, TODAY, url="https://new.com/x", title="New", section="Eng",
                                key_tokens={"b", "a"})
    story.save_history(path, history)
    saved = json.loads(path.read_text())

    assert len(saved) == story.HISTORY_CAP == 30
    assert saved[0]["date"] == "2026-09-02"
    assert saved[-1] == {"date": "2026-10-23", "url": "https://new.com/x", "title": "New", "section": "Eng",
                         "key_tokens": ["a", "b"]}
    assert story.load_history(path) == saved


def test_record_replaces_same_date():
    history = [entry("2026-10-22", 1), entry("2026-10-23", 2)]

    history = story.record_lead(history, TODAY, url="https://example.com/3", title="T3", section=None,
                                key_tokens=set())

    assert [e["url"] for e in history] == ["https://example.com/1", "https://example.com/3"]


def write(tmp_path, text):
    path = tmp_path / "pinned.yaml"
    path.write_text(text)
    return path


def test_pinned_missing_or_empty_is_none(tmp_path):
    assert story.load_pinned(tmp_path / "pinned.yaml", TODAY) is None
    assert story.load_pinned(write(tmp_path, "# nothing pinned\n"), TODAY) is None


def test_pinned_valid(tmp_path):
    path = write(tmp_path, 'url: "https://example.com/pin"\ntitle: Pinned\nnote: Read this\nuntil: 2026-10-30\n')

    assert story.load_pinned(path, TODAY) == {"url": "https://example.com/pin", "title": "Pinned",
                                             "note": "Read this", "until": date(2026, 10, 30)}


def test_pinned_until_today_active_and_yesterday_expired(tmp_path):
    assert story.load_pinned(write(tmp_path, "url: https://e.com/p\nuntil: 2026-10-23\n"), TODAY)["title"] is None
    assert story.load_pinned(write(tmp_path, "url: https://e.com/p\nuntil: '2026-10-22'\n"), TODAY) is None


@pytest.mark.parametrize("text", [
    "until: 2026-10-30\n",
    "url: javascript:alert(1)\nuntil: 2026-10-30\n",
    "url: https://e.com/p\n",
    "url: https://e.com/p\nuntil: next week\n",
    "url: https://e.com/p\nuntil: 2026-10-30T10:00:00\n",
    "url: https://e.com/p\nuntil: 2026-10-30\ntitle: [a, b]\n",
    "url: https://e.com/p\nuntil: 2026-10-30\nuntill: 2026-11-01\n",
    "- just a list\n",
    "url: [unclosed\n",
])
def test_pinned_invalid_raises_naming_file(tmp_path, text):
    with pytest.raises(ValueError, match="pinned.yaml"):
        story.load_pinned(write(tmp_path, text), TODAY)
