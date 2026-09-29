"""Team policy bundle sync, proven offline against a local bare bundle repo."""

import json
from pathlib import Path

from helpers import gcmd, harness

GIT_ID = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
          "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}


def bundle_repo(tmp_path: Path) -> Path:
    b = tmp_path / "policy-bundle.git"
    gcmd(tmp_path, "init", "--bare", "-b", "main", str(b))
    return b


def init_repo(tmp_path: Path, name: str = "app") -> Path:
    """Minimal initialized harness repo (python stack), as a team member would have it."""
    r = tmp_path / name
    r.mkdir()
    (r / "pyproject.toml").write_text(f'[project]\nname="{name}"\nversion="0.1.0"\n')
    (r / "tests").mkdir()
    gcmd(r, "init", "-q", "-b", "main")
    gcmd(r, "add", "-A")
    gcmd(r, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "i")
    assert harness(["init"], r).returncode == 0
    return r


def push(r: Path, b: Path):
    return harness(["policy", "push", str(b)], r, env=GIT_ID)


def test_push_then_status_in_sync(tmp_path: Path):
    r, b = init_repo(tmp_path), bundle_repo(tmp_path)
    p = push(r, b)
    assert p.returncode == 0, p.stdout + p.stderr
    assert "Pushed" in p.stdout
    s = harness(["policy", "status", str(b)], r)
    assert s.returncode == 0, s.stdout + s.stderr
    assert "In sync" in s.stdout


def test_bundle_carries_only_shared_state(tmp_path: Path):
    r, b = init_repo(tmp_path), bundle_repo(tmp_path)
    assert push(r, b).returncode == 0
    files = gcmd(b, "ls-tree", "-r", "--name-only", "main").stdout.split()
    assert files == [".ai-engineering/policy.json", ".ai-engineering/verification.json"]


def test_push_is_idempotent(tmp_path: Path):
    r, b = init_repo(tmp_path), bundle_repo(tmp_path)
    assert push(r, b).returncode == 0
    second = push(r, b)
    assert second.returncode == 0 and "unchanged" in second.stdout
    assert gcmd(b, "rev-list", "--count", "main").stdout.strip() == "1"


def test_status_detects_local_drift(tmp_path: Path):
    r, b = init_repo(tmp_path), bundle_repo(tmp_path)
    assert push(r, b).returncode == 0
    v = r / ".ai-engineering" / "verification.json"
    v.write_text(v.read_text().replace('"review": true', '"review": false'))
    s = harness(["policy", "status", str(b)], r)
    assert s.returncode == 1
    assert "DRIFT" in s.stdout and "verification.json" in s.stdout


def test_pull_propagates_the_team_standard(tmp_path: Path):
    r, b = init_repo(tmp_path), bundle_repo(tmp_path)
    pol = r / ".ai-engineering" / "policy.json"
    data = json.loads(pol.read_text())
    data["protected"] = data["protected"] + ["infra/prod/**"]
    pol.write_text(json.dumps(data, indent=2) + "\n")
    assert push(r, b).returncode == 0

    peer = init_repo(tmp_path, "peer")
    pulled = harness(["policy", "pull", str(b)], peer)
    assert pulled.returncode == 0, pulled.stdout + pulled.stderr
    assert "policy.json" in pulled.stdout
    assert (peer / ".ai-engineering" / "policy.json").read_text() == pol.read_text()
    assert "nothing" in harness(["policy", "pull", str(b)], peer).stdout


def test_pull_from_repo_without_bundle_fails(tmp_path: Path):
    r, b = init_repo(tmp_path), bundle_repo(tmp_path)
    p = harness(["policy", "pull", str(b)], r)
    assert p.returncode == 1
    assert "policy push" in p.stdout + p.stderr


def test_push_without_init_fails(tmp_path: Path):
    r = tmp_path / "raw"
    r.mkdir()
    gcmd(r, "init", "-q", "-b", "main")
    (r / "f").write_text("x")
    gcmd(r, "add", "-A")
    gcmd(r, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "i")
    p = harness(["policy", "push", str(bundle_repo(tmp_path))], r, env=GIT_ID)
    assert p.returncode == 1
    assert "harness init" in p.stdout + p.stderr


def test_unreachable_remote_is_reported(tmp_path: Path):
    r = init_repo(tmp_path)
    p = harness(["policy", "status", str(tmp_path / "nope.git")], r)
    assert p.returncode == 1
    assert "cannot clone" in p.stdout + p.stderr
