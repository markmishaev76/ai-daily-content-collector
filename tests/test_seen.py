import json
from datetime import date

import pytest

from src import seen

TODAY = date(2026, 10, 25)


def art(url):
    return {"title": url, "link": url}


def test_load_missing_is_empty(tmp_path):
    assert seen.load(tmp_path / "seen.json") == {}


@pytest.mark.parametrize("text", ["{not json", "[]", '{"example.com/a": 3}', '{"example.com/a": "yesterday"}'])
def test_load_corrupt_fails_naming_file(tmp_path, text):
    path = tmp_path / "seen.json"
    path.write_text(text)

    with pytest.raises(ValueError, match="seen.json"):
        seen.load(path)


def test_unseen_drops_earlier_days_keeps_today_and_new():
    shown = {"example.com/old": "2026-10-24", "example.com/today": "2026-10-25"}
    feed = {"T": [art("https://www.example.com/old/"), art("http://example.com/today#x"), art("https://example.com/new")]}

    kept, skipped = seen.unseen(feed, shown, TODAY)

    assert [a["link"] for a in kept["T"]] == ["http://example.com/today#x", "https://example.com/new"]
    assert skipped == 1


def test_record_keeps_first_date_adds_new_and_prunes_after_14_days():
    shown = {"example.com/a": "2026-10-20", "example.com/stale": "2026-10-10", "example.com/edge": "2026-10-11"}

    out = seen.record(shown, ["https://example.com/a", "https://example.com/b/", "", "javascript:x"], TODAY)

    assert out == {"example.com/a": "2026-10-20", "example.com/b": "2026-10-25", "example.com/edge": "2026-10-11"}


def test_record_is_stable_for_repeat_builds_the_same_day():
    once = seen.record({}, ["https://example.com/a"], TODAY)

    assert seen.record(once, ["https://example.com/a"], TODAY) == once


def test_save_round_trip(tmp_path):
    path = tmp_path / "data" / "seen.json"
    seen.save(path, {"example.com/b": "2026-10-25", "example.com/a": "2026-10-24"})

    assert seen.load(path) == {"example.com/a": "2026-10-24", "example.com/b": "2026-10-25"}
    assert list(json.loads(path.read_text())) == ["example.com/a", "example.com/b"]
