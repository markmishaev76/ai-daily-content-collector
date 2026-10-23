import yaml


def steps():
    with open(".github/workflows/site.yml") as f:
        return yaml.safe_load(f)["jobs"]["build"]["steps"]


def index_of(command):
    return next(i for i, s in enumerate(steps()) if command in (s.get("run") or ""))


def test_main_builds_from_latest_history():
    sync = steps()[index_of("git pull --ff-only origin main")]

    assert sync["if"] == "github.ref == 'refs/heads/main'"
    assert index_of("git pull --ff-only origin main") < index_of("python build_site.py")


def test_commit_step_adds_history_on_main_only():
    commit = steps()[index_of("git add data/medium-posts.json")]

    assert "data/lead-history.json" in commit["run"]
    assert "data/og-cache.json" in commit["run"]
    assert commit["if"] == "github.ref == 'refs/heads/main'"


def test_pinned_file_triggers_build():
    with open(".github/workflows/site.yml") as f:
        workflow = yaml.safe_load(f)

    assert "pinned.yaml" in workflow[True]["push"]["paths"]
