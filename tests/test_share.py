import xml.etree.ElementTree as ET

import pytest
from PIL import Image

from src import share_card, site_builder
from tests.test_brief_pages import NOW, build, item, page, past


def test_card_is_a_1200_by_627_png(tmp_path):
    out = tmp_path / "card.png"

    share_card.render(out, "A headline", "Story of the day · Thu, Oct 22", take="My take.", color="#5a4fcf")

    with Image.open(out) as img:
        assert img.format == "PNG" and img.size == (1200, 627)


def test_long_titles_wrap_to_at_most_four_lines_with_ellipsis():
    lines = share_card.wrap("word " * 200, share_card.font("bold", 60), 1000, 4)

    assert len(lines) == 4 and lines[-1].endswith("…")
    assert all(share_card.font("bold", 60).getlength(line) <= 1000 for line in lines)


def test_card_renders_without_take_or_title(tmp_path):
    share_card.render(tmp_path / "card.png", "", "The Daily Brief")

    assert (tmp_path / "card.png").stat().st_size > 0


def test_card_rejects_bad_color(tmp_path):
    with pytest.raises(ValueError):
        share_card.render(tmp_path / "card.png", "T", "K", color="red; drop")


def snap_with_take():
    snap = past(day="2026-10-22", sections=[
        {"name": "Topic", "cards": [item("First card", source="The Register")], "more": []},
        {"name": "Other", "cards": [item("Second card")], "more": []},
        {"name": "Third", "cards": [], "more": [item("Row only")]}])
    snap["lead"]["take"] = "This matters for agents."
    return snap


def test_linkedin_text_has_lead_take_picks_and_permalink():
    text = site_builder.linkedin_text(snap_with_take(), "https://thedailybrief.dev/brief/2026-10-22/")

    assert text.startswith("The Daily Brief · Thursday, October 22\n")
    assert "Story of the day: Past lead\nThis matters for agents.\nhttps://example.com/pastlead" in text
    assert "• First card (The Register) https://example.com/firstcard" in text
    assert "• Second card (Src)" in text and "Row only" not in text
    assert text.rstrip().endswith("Full brief: https://thedailybrief.dev/brief/2026-10-22/")


def test_linkedin_text_without_lead_lists_picks_only():
    snap = dict(snap_with_take(), lead=None)

    text = site_builder.linkedin_text(snap, "https://thedailybrief.dev/brief/2026-10-22/")

    assert "Story of the day" not in text and "• First card" in text


def test_brief_pages_get_copy_button_share_image_and_lead_title(tmp_path):
    build(tmp_path, briefs={"2026-10-21": past()})

    html = page(tmp_path, "2026-10-21")
    assert 'class="copy-share"' in html and "Story of the day: Past lead" in html
    assert 'og:image" content="https://thedailybrief.dev/share/2026-10-21.png"' in html
    assert 'og:title" content="Past lead · The Daily Brief"' in html
    assert (tmp_path / "share" / "2026-10-21.png").exists()
    assert (tmp_path / "share" / "2026-10-22.png").exists()
    assert 'og:image" content="https://thedailybrief.dev/share/2026-10-22.png"' in page(tmp_path, "2026-10-22")
    front = page(tmp_path)
    assert 'og:image" content="https://thedailybrief.dev/static/share.png"' in front
    assert 'class="copy-share"' in front and "Full brief: https://thedailybrief.dev/brief/2026-10-22/" in front


def test_other_pages_keep_static_share_image(tmp_path):
    build(tmp_path)

    assert 'og:image" content="https://thedailybrief.dev/static/share.png"' in (tmp_path / "about/index.html").read_text()


def test_brief_feed_lists_kept_days_newest_first(tmp_path):
    build(tmp_path, briefs={"2026-10-21": past(), "2026-10-01": past("2026-10-01")})

    channel = ET.parse(tmp_path / "brief.xml").getroot().find("channel")
    items = channel.findall("item")
    assert [i.find("link").text for i in items] == ["https://thedailybrief.dev/brief/2026-10-22/",
                                                    "https://thedailybrief.dev/brief/2026-10-21/"]
    assert items[1].find("title").text == "Wed, Oct 21: Past lead"
    assert items[1].find("guid").text == items[1].find("link").text
    description = items[1].find("description").text
    assert '<a href="https://example.com/pastlead">Past lead</a>' in description
    assert "Past card" in description and "Topic" in description
    assert 'href="brief.xml"' in page(tmp_path)


def test_brief_feed_escapes_titles(tmp_path):
    build(tmp_path, briefs={"2026-10-21": past(lead_title="<script>x</script> & co")})

    description = ET.parse(tmp_path / "brief.xml").getroot().find("channel/item[2]/description").text
    assert "<script>" not in description and "&lt;script&gt;" in description


def test_newsletter_form_only_when_configured(tmp_path):
    build(tmp_path)
    assert "buttondown" not in page(tmp_path)

    build(tmp_path, newsletter="markmishaev")
    html = page(tmp_path)
    assert 'action="https://buttondown.com/api/emails/embed-subscribe/markmishaev"' in html
    assert 'type="email"' in html and 'name="email"' in html
    assert "buttondown" in (tmp_path / "about/index.html").read_text()


@pytest.mark.parametrize("bad", ["a b", "x/../y", "<u>", 42])
def test_newsletter_username_validated(bad):
    with pytest.raises(ValueError):
        site_builder.newsletter_user({"newsletter": {"buttondown": bad}})


def test_newsletter_user_absent_null_or_blank_is_none():
    assert site_builder.newsletter_user({}) is None
    assert site_builder.newsletter_user({"newsletter": {"buttondown": None}}) is None
    assert site_builder.newsletter_user({"newsletter": {"buttondown": ""}}) is None
    assert site_builder.newsletter_user({"newsletter": {"buttondown": "markmishaev"}}) == "markmishaev"
