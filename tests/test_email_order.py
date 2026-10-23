import re

import yaml

from src.email_sender import EmailSender


def test_email_sections_follow_config_order(monkeypatch):
    for name in ("EMAIL_FROM", "EMAIL_TO", "EMAIL_PASSWORD"):
        monkeypatch.setenv(name, "x@example.com")
    with open("config.yaml") as f:
        names = [t["name"] for t in yaml.safe_load(f)["topics"]]
    feed = {name: [{"title": f"Story {i}", "link": f"https://example.com/{i}", "summary": "",
                    "published": None, "source": "S"}] for i, name in enumerate(names)}

    html = EmailSender().create_html_email(feed)

    assert re.findall(r"<h2>(.*?)</h2>", html) == [n.replace("&", "&amp;") for n in names]
    assert names[0] == "AI-Assisted Engineering"
    assert "Story of the day" not in html
