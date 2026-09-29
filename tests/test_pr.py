import json
import os
from pathlib import Path

from helpers import gcmd, harness

GH_SCRIPT = """#!/bin/sh
printf '%s\\n' "$@" >> "$FAKE_GH_LOG"
for a in "$@"; do
  if [ "$a" = list ]; then echo '{list_json}'; exit "${{FAKE_GH_RC:-0}}"; fi
done
echo fake-gh-ok
exit "${{FAKE_GH_RC:-0}}"
"""

GIT_ID = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}


def gh_env(tmp_path: Path, list_json: str = "[]", gh_rc: int = 0) -> dict:
    """PATH shim: a fake `gh` that logs argv one per line and echoes list_json for `gh pr list`."""
    bin_dir = tmp_path / "fakebin"
    bin_dir.mkdir(exist_ok=True)
    script = bin_dir / "gh"
    script.write_text(GH_SCRIPT.format(list_json=list_json))
    script.chmod(0o755)
    return {"PATH": f"{bin_dir}:{os.environ['PATH']}", "FAKE_GH_LOG": str(tmp_path / "gh.log"),
            "FAKE_GH_RC": str(gh_rc), **GIT_ID}


def log_lines(tmp_path: Path) -> list[str]:
    p = tmp_path / "gh.log"
    return p.read_text().splitlines() if p.exists() else []


def _start_task(pyrepo: Path, env: dict | None = None):
    harness(["init"], pyrepo)
    p = harness(["task", "start", "t", "--goal", "add mul", "--risk", "low", "--allow", "src/**"], pyrepo, env=env)
    assert p.returncode == 0


def test_pr_create_pushes_and_opens_pr(tmp_path: Path, pyrepo: Path):
    origin = tmp_path / "origin.git"
    gcmd(tmp_path, "init", "--bare", "-q", str(origin))
    gcmd(pyrepo, "remote", "add", "origin", str(origin))
    gcmd(pyrepo, "push", "-q", "-u", "origin", "main")
    env = gh_env(tmp_path)
    _start_task(pyrepo, env)
    wt = Path(json.loads((pyrepo / ".ai-engineering" / "tasks" / "t.json").read_text())["worktree"])
    (wt / "src" / "calc.py").write_text(
        "def add(a: int, b: int) -> int:\n    return a + b\n\n\n"
        "def mul(a: int, b: int) -> int:\n    return a * b\n")
    v = harness(["verify", "t"], pyrepo, env=env)
    assert v.returncode == 0, v.stdout + v.stderr

    p = harness(["pr", "create", "t"], pyrepo, env=env)
    assert p.returncode == 0, p.stdout + p.stderr
    assert "fake-gh-ok" in p.stdout
    lines = log_lines(tmp_path)
    assert lines[:2] == ["pr", "create"] and "--head" in lines and "harness/t" in lines and "add mul" in lines
    assert "refs/heads/harness/t" in gcmd(pyrepo, "ls-remote", "--heads", "origin").stdout


def test_pr_refuses_without_evidence_and_bogus_subcommand(tmp_path: Path, pyrepo: Path):
    harness(["init"], pyrepo)
    harness(["task", "start", "t", "--goal", "g", "--risk", "low", "--allow", "src/**"], pyrepo)
    refused = harness(["pr", "create", "t"], pyrepo)
    assert refused.returncode == 1 and "no passing evidence" in refused.stderr
    assert harness(["pr", "bogus"], pyrepo).returncode == 2


def test_pr_view_no_pr(tmp_path: Path, pyrepo: Path):
    _start_task(pyrepo)
    p = harness(["pr", "view", "t"], pyrepo, env=gh_env(tmp_path))
    assert p.returncode == 1 and "no PR for harness/t" in p.stderr


def test_pr_view_resolves_branch_to_number(tmp_path: Path, pyrepo: Path):
    _start_task(pyrepo)
    p = harness(["pr", "view", "t"], pyrepo, env=gh_env(tmp_path, list_json='[{"number":7}]'))
    assert p.returncode == 0 and "fake-gh-ok" in p.stdout
    lines = log_lines(tmp_path)
    assert "list" in lines and "view" in lines and "7" in lines


def test_pr_status_propagates_gh_exit_code(tmp_path: Path, pyrepo: Path):
    harness(["init"], pyrepo)
    p = harness(["pr", "status"], pyrepo, env=gh_env(tmp_path, gh_rc=3))
    assert p.returncode == 3 and "fake-gh-ok" in p.stdout
