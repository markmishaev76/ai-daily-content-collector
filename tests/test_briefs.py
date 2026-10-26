import json
from datetime import date

import pytest

from src import briefs

TODAY = date(2026, 10, 26)


def snap(day="2026-10-25", title="Story"):
    return {"date": day, "lead": None, "pulse": [],
            "sections": [{"name": "Leadership", "cards": [{"title": title, "link": "https://e.com/a"}], "more": []}]}


def write(directory, day, body):
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{day}.json").write_text(body if isinstance(body, str) else json.dumps(body))


def test_window_is_today_and_six_days_before():
    assert briefs.window(TODAY) == [date(2026, 10, d) for d in range(20, 27)]


def test_missing_directory_means_no_past_days(tmp_path):
    assert briefs.load(tmp_path / "briefs", TODAY) == {}


def test_load_returns_past_days_in_window_only(tmp_path):
    d = tmp_path / "briefs"
    for day in ("2026-10-19", "2026-10-20", "2026-10-25", "2026-10-26"):
        write(d, day, snap(day))
    write(d, "notes", "ignored")

    loaded = briefs.load(d, TODAY)

    assert sorted(loaded) == ["2026-10-20", "2026-10-25"]
    assert loaded["2026-10-25"]["sections"][0]["name"] == "Leadership"


@pytest.mark.parametrize("body", ["{not json", "[]", {"date": "2026-10-24"},
                                  dict(snap(), date="2026-10-24"),
                                  dict(snap(), sections=[{"name": 3, "cards": [], "more": []}]),
                                  dict(snap(), sections=[{"name": "A", "cards": [{"link": "x"}], "more": []}]),
                                  dict(snap(), lead="Story"), dict(snap(), pulse={"a": 1})])
def test_corrupt_or_invalid_snapshot_raises_naming_file(tmp_path, body):
    write(tmp_path / "briefs", "2026-10-25", body)

    with pytest.raises(ValueError, match=r"briefs/2026-10-25\.json"):
        briefs.load(tmp_path / "briefs", TODAY)


def test_corrupt_file_outside_window_is_ignored(tmp_path):
    write(tmp_path / "briefs", "2026-10-01", "{not json")

    assert briefs.load(tmp_path / "briefs", TODAY) == {}


def test_save_overwrites_today_and_leaves_other_days(tmp_path):
    d = tmp_path / "briefs"
    write(d, "2026-10-25", snap("2026-10-25", "Yesterday"))
    briefs.save(d, TODAY, snap("2026-10-26", "First build"))
    before = (d / "2026-10-25.json").read_text()

    briefs.save(d, TODAY, snap("2026-10-26", "Last build"))

    assert json.loads((d / "2026-10-26.json").read_text())["sections"][0]["cards"][0]["title"] == "Last build"
    assert (d / "2026-10-25.json").read_text() == before


def test_prune_keeps_seven_days(tmp_path):
    d = tmp_path / "briefs"
    for day in ("2026-10-18", "2026-10-19", "2026-10-20", "2026-10-26"):
        write(d, day, snap(day))
    (d / "README").write_text("keep me")

    briefs.prune(d, TODAY)

    assert sorted(p.name for p in d.iterdir()) == ["2026-10-20.json", "2026-10-26.json", "README"]
