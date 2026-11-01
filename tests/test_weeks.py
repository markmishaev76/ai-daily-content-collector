import json
from datetime import date

import pytest

from src import weeks

CONFIG = {"topics": [{"name": "Security", "weight": 1.5, "sources": []}, {"name": "Platform", "weight": 0.75, "sources": []}]}
SUNDAY = date(2026, 11, 1)


def item(title, link, source="Src", **kw):
    return dict({"title": title, "link": link, "source": source, "excerpt": "", "date": "Oct 30", "domain": ""}, **kw)


def snap(day, lead=None, security=(), platform=()):
    return {"date": day, "pulse": [],
            "lead": {"title": lead[0], "link": lead[1], "source": "Lead src", "section": "Security", "labels": []}
            if lead else None,
            "sections": [{"name": "Security", "cards": list(security), "more": []},
                         {"name": "Platform", "cards": list(platform), "more": []}]}


def week_of(**days):
    return {f"2026-{k[1:3]}-{k[4:]}": v for k, v in days.items()}


def test_week_ids_and_days():
    assert weeks.week_id(SUNDAY) == "2026-W44"
    assert weeks.week_id(date(2027, 1, 1)) == "2026-W53"
    assert weeks.week_dates(SUNDAY) == [date(2026, 10, 26 + n) if n < 6 else date(2026, 11, 1) for n in range(7)]


def test_week_has_seven_days_with_leads_and_takes():
    snaps = {"2026-10-26": snap("2026-10-26", ("Mon lead", "https://e.com/mon")),
             "2026-11-01": dict(snap("2026-11-01", ("Sun lead", "https://e.com/sun")))}
    snaps["2026-11-01"]["lead"]["take"] = "My take"

    week = weeks.build_week(snaps, SUNDAY, CONFIG)

    assert week["week"] == "2026-W44" and (week["start"], week["end"]) == ("2026-10-26", "2026-11-01")
    assert [d["date"] for d in week["days"]] == [f"2026-10-{d}" for d in range(26, 32)] + ["2026-11-01"]
    assert week["days"][0]["lead"]["title"] == "Mon lead" and week["days"][1]["lead"] is None
    assert week["days"][6]["lead"]["take"] == "My take" and week["preview"] is False


def test_top_ranked_by_coverage_then_score_then_section_weight_one_per_cluster_no_leads():
    snaps = {
        "2026-10-27": snap("2026-10-27", ("PHP2Shell flaw patched CVE-2026-10001", "https://lead.com/php"),
                           security=[item("Big breach at Acme Corp exposes customer records", "https://a.com/1",
                                          score=5.0, coverage=1),
                                     item("PHP2Shell exploited CVE-2026-10001", "https://b.com/php", score=50.0, coverage=4),
                                     item("Quiet security tip", "https://c.com/tip", score=9.0, coverage=1)],
                           platform=[item("Kubernetes 1.40 released", "https://k.com/140", score=9.0, coverage=1)]),
        "2026-10-29": snap("2026-10-29",
                           security=[item("Acme Corp breach exposes customer records, says report", "https://d.com/acme",
                                          score=3.0)],
                           platform=[item("Old snapshot item without signals", "https://o.com/x")]),
    }

    top = weeks.build_week(snaps, SUNDAY, CONFIG)["top"]

    titles = [t["title"] for t in top]
    assert titles[0] == "Big breach at Acme Corp exposes customer records"        # 2 domains across the week
    assert top[0]["coverage"] == 2 and top[0]["date"] == "2026-10-27"
    assert titles[1:] == ["Quiet security tip", "Kubernetes 1.40 released", "Old snapshot item without signals"]
    assert not any("PHP2Shell" in t for t in titles)                             # the lead's story is excluded
    assert top[0]["section"] == "Security" and top[0]["source"] == "Src"


def test_top_is_capped_at_ten():
    many = [item(f"Alpha{n} beta{n} gamma{n}", f"https://e{n}.com/x", score=float(n)) for n in range(15)]

    assert len(weeks.build_week({"2026-10-28": snap("2026-10-28", security=many)}, SUNDAY, CONFIG)["top"]) == 10


def test_preview_only_covers_days_so_far():
    week = weeks.build_week({"2026-10-28": snap("2026-10-28", ("Wed lead", "https://e.com/w"))}, date(2026, 10, 28),
                            CONFIG, preview=True)

    assert week["preview"] is True and [d["date"] for d in week["days"]] == ["2026-10-26", "2026-10-27", "2026-10-28"]


def test_plain_text_for_linkedin():
    snaps = {"2026-10-26": snap("2026-10-26", ("Mon lead", "https://e.com/mon"),
                                security=[item("Top one", "https://t.com/1", score=1.0)])}
    week = weeks.build_week(snaps, SUNDAY, CONFIG)

    text = weeks.plain_text(week, "https://thedailybrief.dev/week/2026-W44/")

    assert text.startswith("The Daily Brief · week in review, Oct 26 – Nov 1, 2026\n")
    assert "Stories of the day:\n1. Mon Oct 26: Mon lead https://e.com/mon\n" in text
    assert "Top of the week:\n1. Top one https://t.com/1\n" in text
    assert text.rstrip().endswith("https://thedailybrief.dev/week/2026-W44/")
    assert "Tue Oct 27" not in text


def test_save_load_prune(tmp_path):
    d = tmp_path / "weeks"
    for n in range(36, 46):
        weeks.save(d, {"week": f"2026-W{n}", "start": "2026-01-01", "end": "2026-01-07", "days": [], "top": [],
                       "preview": False})
    (d / "notes.txt").write_text("keep")

    weeks.prune(d, keep=8)
    loaded = weeks.load(d)

    assert sorted(loaded) == [f"2026-W{n}" for n in range(38, 46)] and (d / "notes.txt").exists()


def test_missing_dir_is_empty(tmp_path):
    assert weeks.load(tmp_path / "weeks") == {}


@pytest.mark.parametrize("body", ["{bad", "[]", {"week": "2026-W40"}, {"week": "2026-W41", "start": "x", "end": "y",
                                                                     "days": [], "top": []},
                                  {"week": "2026-W40", "start": "2026-01-01", "end": "2026-01-07", "days": "x", "top": []},
                                  {"week": "2026-W40", "start": "2026-01-01", "end": "2026-01-07", "days": [],
                                   "top": [{"link": "x"}]}])
def test_corrupt_week_raises_naming_file(tmp_path, body):
    d = tmp_path / "weeks"
    d.mkdir()
    (d / "2026-W40.json").write_text(body if isinstance(body, str) else json.dumps(body))

    with pytest.raises(ValueError, match=r"weeks/2026-W40\.json"):
        weeks.load(d)


def test_items_without_saved_score_fall_back_to_theme_keywords():
    snaps = {"2026-10-28": snap("2026-10-28", security=[item("Aardvark news", "https://a.com/1"),
                                                        item("MCP server prompt injection found", "https://m.com/1")])}

    top = weeks.build_week(snaps, SUNDAY, CONFIG)["top"]

    assert [t["title"] for t in top] == ["MCP server prompt injection found", "Aardvark news"]
