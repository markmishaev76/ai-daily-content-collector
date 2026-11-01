import re
from datetime import date, datetime, timezone

import pytest
import requests

from src import events

NOW = datetime(2026, 11, 1, 8, 0, tzinfo=timezone.utc)
TODAY = NOW.date()
CONFIG = {"events": {"horizon_days": 90, "closing_days": 7,
                     "topics": ["security", "devops", "general"],
                     "topic_categories": {"security": "security", "devops": "platform"},
                     "keywords": {"ai": ["AI", "LLM", "agentic", "MCP"], "security": ["security", "BSides", "OAuth"],
                                  "platform": ["KubeCon", "DevOps", "cloud"], "leadership": ["LeadDev"]}}}


def ms(d):
    return int(datetime(d.year, d.month, d.day, tzinfo=timezone.utc).timestamp() * 1000)


def cfp(name="AI Engineer Summit", until=date(2026, 11, 5), start=date(2027, 2, 10), end=None, location="Berlin (Germany)",
        link="https://cfp.example.com/ai"):
    return {"link": link, "untilDate": ms(until),
            "conf": {"name": name, "date": [ms(start)] + ([ms(end)] if end else []), "hyperlink": "https://ai.example.com",
                     "location": location, "status": "open"}}


def conf(name="KubeCon Europe", start="2026-12-01", end="2026-12-03", city="Amsterdam", country="Netherlands",
         online=False, cfp_url=None, cfp_end=None, url="https://kubecon.example.com"):
    out = {"name": name, "url": url, "startDate": start, "endDate": end, "city": city, "country": country, "online": online}
    if cfp_url:
        out.update(cfpUrl=cfp_url, cfpEndDate=cfp_end)
    return out


class Response:
    def __init__(self, status=200, body=None):
        self.status_code, self.body = status, body

    def json(self):
        if isinstance(self.body, Exception):
            raise self.body
        return self.body


def fake_get(cfps=None, confs=None):
    confs = confs or {}

    def get(url, **kw):
        if "developers.events" in url:
            if isinstance(cfps, Exception):
                raise cfps
            return cfps if isinstance(cfps, Response) else Response(200, cfps or [])
        year, topic = re.search(r"/conferences/(\d{4})/(\w+)\.json", url).groups()
        body = confs.get((int(year), topic), [])
        return body if isinstance(body, Response) else Response(200, body)
    return get


# Settings

def test_settings_defaults_and_absent():
    assert events.settings({}) is None
    s = events.settings({"events": {}})
    assert s["horizon_days"] == 90 and s["closing_days"] == 7
    assert set(s["keywords"]) == {"ai", "security", "platform", "leadership"} and s["topics"]


@pytest.mark.parametrize("bad", [{"horizon_days": 0}, {"closing_days": "7"}, {"keywords": {"ai": "AI"}},
                                 {"keywords": {"fun": ["x"]}}, {"keywords": {"ai": [""]}}, {"topics": ["bad topic"]},
                                 {"topic_categories": {"security": "nope"}}, {"extra": 1}, ["x"]])
def test_settings_invalid_raise_naming_config(bad):
    with pytest.raises(ValueError, match="config.yaml: events"):
        events.settings({"events": bad})


# Parsing and relevance

def test_open_cfps_parsed_and_closed_ones_dropped():
    s = events.settings(CONFIG)
    data = [cfp(), cfp("Old AI Conf", until=date(2026, 10, 31)), cfp("Closes Today AI", until=TODAY),
            cfp("AI Online Day", location="Online"), {"broken": True}]

    parsed = events.parse_cfps(data, TODAY)

    assert [e["name"] for e in parsed] == ["AI Engineer Summit", "Closes Today AI", "AI Online Day"]
    e = parsed[0]
    assert (e["cfp_end"], e["start"], e["end"], e["year"]) == (date(2026, 11, 5), date(2027, 2, 10), date(2027, 2, 10), 2027)
    assert e["cfp_url"] == "https://cfp.example.com/ai" and e["url"] == "https://ai.example.com"
    assert e["location"] == "Berlin (Germany)" and e["online"] is False and parsed[2]["online"] is True
    assert s


def test_conference_files_parsed():
    parsed = events.parse_conferences([conf(), conf("BSides Online", city=None, country=None, online=True,
                                                    cfp_url="https://b.example.com/cfp", cfp_end="2026-11-20"),
                                       {"name": "No dates"}], "security")

    assert [e["name"] for e in parsed] == ["KubeCon Europe", "BSides Online"]
    assert parsed[0]["location"] == "Amsterdam, Netherlands" and parsed[0]["start"] == date(2026, 12, 1)
    assert parsed[1]["location"] == "Online" and parsed[1]["online"] and parsed[1]["cfp_end"] == date(2026, 11, 20)
    assert parsed[0]["topic"] == "security"


@pytest.mark.parametrize("name,topic,cats", [
    ("AI Engineer Summit", "general", {"ai"}),
    ("Agentic Systems Day", "general", {"ai"}),
    ("MCP Dev Summit", None, {"ai"}),
    ("BSides Tel Aviv", None, {"security"}),
    ("PyCon", "security", {"security"}),             # the topic file counts
    ("DevOpsDays Berlin", "devops", {"platform"}),
    ("Cloud and AI Summit", None, {"ai", "platform"}),
    ("LeadDev London", None, {"leadership"}),
    ("FAIRtech Expo", "general", set()),            # whole words only
    ("JSConf", "general", set()),
])
def test_categories(name, topic, cats):
    assert events.categories(name, topic, events.settings(CONFIG)) == cats


# Collect: merge, sort, failures

def test_collect_merges_sorts_and_splits():
    cfps = [cfp("AI Engineer Summit 2027", until=date(2026, 11, 20), start=date(2027, 2, 10)),
            cfp("KubeCon Europe", until=date(2026, 11, 3), start=date(2026, 12, 1), end=date(2026, 12, 3),
                link="https://kubecon.example.com/cfp"),
            cfp("Knitting Conf", until=date(2026, 11, 4))]
    confs = {(2026, "devops"): [conf()],
             (2026, "general"): [conf("Cloud Summit", start="2026-11-10", end="2026-11-10"),
                                 conf("Cloud Far Away", start="2027-03-01", end="2027-03-02"),
                                 conf("Cloud Past", start="2026-10-01", end="2026-10-02")],
             (2027, "general"): [conf("AI Engineer Summit", start="2027-02-10", end="2027-02-11", url="https://ai.example.com")]}

    data, counts = events.collect(CONFIG, NOW, get=fake_get(cfps, confs))

    assert [e["name"] for e in data["cfps"]] == ["KubeCon Europe", "AI Engineer Summit 2027"]
    assert [e["name"] for e in data["upcoming"]] == ["Cloud Summit", "KubeCon Europe"]
    kube = data["cfps"][0]
    assert kube["cfp_url"] == "https://kubecon.example.com/cfp" and kube["closing_soon"] and kube["days_left"] == 2
    assert not data["cfps"][1]["closing_soon"]
    assert sum(1 for e in data["cfps"] if e["name"].startswith("AI Engineer")) == 1
    assert counts["developers.events"] == 3 and counts["conference-data"] == 5


def test_one_source_failing_keeps_the_other(caplog):
    data, counts = events.collect(CONFIG, NOW, get=fake_get(requests.ConnectionError("down"),
                                                            {(2026, "devops"): [conf()]}))

    assert [e["name"] for e in data["upcoming"]] == ["KubeCon Europe"] and data["cfps"] == []
    assert counts["developers.events"] is None and "developers.events" in caplog.text


def test_bad_conference_file_is_skipped_with_warning(caplog):
    data, counts = events.collect(CONFIG, NOW, get=fake_get([cfp()], {(2026, "devops"): Response(404),
                                                                      (2026, "security"): Response(200, {"x": 1})}))

    assert [e["name"] for e in data["cfps"]] == ["AI Engineer Summit"]
    assert "2026/devops" in caplog.text and "2026/security" in caplog.text


def test_everything_failing_gives_empty_lists():
    data, counts = events.collect(CONFIG, NOW, get=fake_get(Response(500), {(y, t): Response(500) for y in (2026, 2027)
                                                                           for t in ("security", "devops", "general")}))

    assert data == {"cfps": [], "upcoming": []} and counts == {"developers.events": None, "conference-data": None}


# Calendar feed

def unfold(text):
    assert "\r\n" in text and "\n" not in text.replace("\r\n", "")
    return text.replace("\r\n ", "").split("\r\n")


def test_ics_is_valid_rfc5545():
    long_name = "Conférence Internationale sur la Sécurité, l'Identité; et les Agents " * 2
    cfps = [{"name": long_name.strip(), "year": 2027, "cfp_end": date(2026, 11, 5), "cfp_url": "https://cfp.example.com/a?x=1,2",
             "url": "https://conf.example.com", "location": "Paris, France", "start": date(2027, 2, 10), "end": date(2027, 2, 11),
             "online": False},
            {"name": "BSides", "year": 2026, "cfp_end": date(2026, 11, 20), "cfp_url": "https://b.example.com", "url": None,
             "location": "Online", "start": date(2026, 12, 1), "end": date(2026, 12, 1), "online": True}]

    text = events.ics(cfps, NOW)

    raw_lines = text.split("\r\n")
    assert text.endswith("\r\n") and all(len(line.encode("utf-8")) <= 75 for line in raw_lines)
    lines = unfold(text)
    assert lines[0] == "BEGIN:VCALENDAR" and lines[-2] == "END:VCALENDAR" and lines[-1] == ""
    assert "VERSION:2.0" in lines and any(line.startswith("PRODID:") for line in lines)
    assert lines.count("BEGIN:VEVENT") == 2 == lines.count("END:VEVENT")
    first = lines[lines.index("BEGIN:VEVENT"):lines.index("END:VEVENT")]
    props = dict(line.split(":", 1) for line in first)
    assert props["DTSTART;VALUE=DATE"] == "20261105" and props["DTEND;VALUE=DATE"] == "20261106"
    assert props["DTSTAMP"] == "20261101T080000Z"
    assert props["SUMMARY"].startswith("CFP closes: Conférence Internationale sur la Sécurité\\, l'Identité\\; et")
    assert props["URL"] == "https://cfp.example.com/a?x=1,2"
    assert "Paris\\, France" in props["DESCRIPTION"] and "https://conf.example.com" in props["DESCRIPTION"]
    assert re.fullmatch(r"cfp-[a-z0-9-]+-2027@thedailybrief\.dev", props["UID"])


def test_ics_uids_stable_when_deadline_moves():
    base = {"name": "BSides Tel Aviv", "year": 2026, "cfp_url": "https://b.example.com", "url": None, "location": "Online",
            "start": date(2026, 12, 1), "end": date(2026, 12, 1), "online": True}
    uid = lambda text: next(line for line in unfold(text) if line.startswith("UID:"))

    assert uid(events.ics([dict(base, cfp_end=date(2026, 11, 5))], NOW)) == \
        uid(events.ics([dict(base, cfp_end=date(2026, 11, 9))], NOW.replace(day=2)))


def test_ics_empty_calendar_is_still_valid():
    lines = unfold(events.ics([], NOW))

    assert lines[0] == "BEGIN:VCALENDAR" and "END:VCALENDAR" in lines and "BEGIN:VEVENT" not in lines


def test_cfp_closing_after_the_conference_is_dropped():
    cfps = [cfp("AI Late Deadline", until=date(2026, 12, 31), start=date(2026, 11, 28)), cfp()]

    data, _ = events.collect(CONFIG, NOW, get=fake_get(cfps))

    assert [e["name"] for e in data["cfps"]] == ["AI Engineer Summit"]
