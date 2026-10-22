from main import select_articles


def art(n):
    return {"title": f"Plain {n}", "link": f"https://example.com/{n}", "summary": "", "published": None, "source": "S"}


def test_article_below_cut_in_earlier_section_shows_in_later_section():
    first = [art(i) for i in range(9)]
    second = [art(8), art(100)]

    picked = select_articles({"First": first, "Second": second}, max_articles=8)

    assert [a["link"] for a in picked["First"]] == [f"https://example.com/{i}" for i in range(8)]
    assert "https://example.com/8" in [a["link"] for a in picked["Second"]]


def test_article_shown_in_earlier_section_not_repeated():
    picked = select_articles({"First": [art(1)], "Second": [art(1), art(2)]}, max_articles=8)

    assert [a["link"] for a in picked["Second"]] == ["https://example.com/2"]


def test_later_section_fills_cut_after_skipping_repeats():
    first = [art(i) for i in range(3)]
    second = [art(0), art(1)] + [art(i) for i in range(10, 20)]

    picked = select_articles({"First": first, "Second": second}, max_articles=8)

    assert len(picked["Second"]) == 8
    assert picked["Second"][0]["link"] == "https://example.com/10"
