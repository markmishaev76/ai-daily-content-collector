import pytest

from src import posts


def write(dir_, name, body):
    (dir_ / name).write_text(body)


def test_loads_post_with_front_matter(tmp_path):
    write(tmp_path, "2026-10-22-agent-identity.md",
          "---\ntitle: Agent identity\ndate: 2026-10-22\nsummary: Why agents need their own principal\n---\n\n## Heading\n\nBody.\n")

    [post] = posts.load_local_posts(tmp_path)

    assert post["title"] == "Agent identity"
    assert post["date"] == "2026-10-22"
    assert post["slug"] == "agent-identity"
    assert post["url"] == "blog/agent-identity/"
    assert post["summary"] == "Why agents need their own principal"
    assert post["source"] == "local"
    assert "<h2>Heading</h2>" in post["html"]


def test_rejects_bad_filename(tmp_path):
    write(tmp_path, "My Post.md", "---\ntitle: X\ndate: 2026-10-22\n---\nBody")

    with pytest.raises(ValueError, match="My Post.md"):
        posts.load_local_posts(tmp_path)


def test_rejects_missing_title(tmp_path):
    write(tmp_path, "2026-10-22-no-title.md", "---\ndate: 2026-10-22\n---\nBody")

    with pytest.raises(ValueError, match="2026-10-22-no-title.md"):
        posts.load_local_posts(tmp_path)


@pytest.mark.parametrize("front_matter", [
    "title: X\ndate: 2026-10-22 10:00",
    "title: X\ndate: Oct 22 2026",
    "- just\n- a list",
])
def test_rejects_malformed_front_matter_naming_file(tmp_path, front_matter):
    write(tmp_path, "2026-10-22-bad.md", f"---\n{front_matter}\n---\nBody")

    with pytest.raises(ValueError, match="2026-10-22-bad.md"):
        posts.load_local_posts(tmp_path)


def test_sorted_newest_first(tmp_path):
    write(tmp_path, "2026-01-01-old.md", "---\ntitle: Old\ndate: 2026-01-01\n---\nA")
    write(tmp_path, "2026-10-01-new.md", "---\ntitle: New\ndate: 2026-10-01\n---\nB")

    assert [p["slug"] for p in posts.load_local_posts(tmp_path)] == ["new", "old"]


def test_empty_dir_returns_empty_list(tmp_path):
    assert posts.load_local_posts(tmp_path) == []


def test_render_markdown_file(tmp_path):
    about = tmp_path / "about.md"
    about.write_text("I lead **security**.")

    assert posts.render_markdown_file(about) == "<p>I lead <strong>security</strong>.</p>"
