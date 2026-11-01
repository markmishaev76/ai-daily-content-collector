import pytest

from src import takes


def load(tmp_path, text):
    path = tmp_path / "takes.yaml"
    path.write_text(text)
    return takes.load(path)


def test_missing_or_empty_file_means_no_takes(tmp_path):
    assert takes.load(tmp_path / "takes.yaml") == {}
    assert load(tmp_path, "# Mark's takes\n") == {}


def test_dates_map_to_plain_text_with_whitespace_collapsed(tmp_path):
    loaded = load(tmp_path, '2026-11-01: "Worth reading: the fix is small."\n'
                            "'2026-10-31': >\n  Two lines\n  folded.\n")

    assert loaded == {"2026-11-01": "Worth reading: the fix is small.", "2026-10-31": "Two lines folded."}


@pytest.mark.parametrize("text", ["2026-11-01: [unclosed", "- a list\n", "not-a-date: hi\n", "2026-13-01: hi\n",
                                  "2026-11-01: 42\n", "2026-11-01: ''\n", f"2026-11-01: {'x' * 401}\n",
                                  "2026-11-01:\n  nested: map\n"])
def test_invalid_file_raises_naming_it(tmp_path, text):
    with pytest.raises(ValueError, match="takes.yaml"):
        load(tmp_path, text)


def test_four_hundred_characters_is_fine(tmp_path):
    assert len(load(tmp_path, f"2026-11-01: {'x' * 400}\n")["2026-11-01"]) == 400
