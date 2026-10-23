import pytest

from src import hn

SUMMARY = "Article URL: https://x.dev/a\nComments URL: https://news.ycombinator.com/item?id=1\nPoints: 12\n# Comments: 3"


def test_counts_and_detection():
    assert hn.hn_counts(SUMMARY) == (12, 3)
    assert hn.hn_counts(None) == (0, 0)
    assert hn.is_hn_item({"feed": "https://hnrss.org/newest?q=MCP", "link": "https://x.dev/a"})
    assert hn.is_hn_item({"feed": "", "link": "https://news.ycombinator.com/item?id=1"})
    assert not hn.is_hn_item({"feed": "https://x.dev/feed", "link": "https://x.dev/a"})
    assert not hn.is_hn_item({"feed": "https://nothnrss.org/x", "link": "https://x.dev/a"})


def test_min_points_validated():
    assert hn.min_points({"story": {"section_min_hn_points": 10}}, "section_min_hn_points") == 10
    assert hn.min_points({}, "section_min_hn_points") == 0
    for bad in ("ten", -1, True, 2.5):
        with pytest.raises(ValueError, match="config.yaml: story.section_min_hn_points"):
            hn.min_points({"story": {"section_min_hn_points": bad}}, "section_min_hn_points")
