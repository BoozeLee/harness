"""§9 DoD: the §1 smoke transcript, permanently.

Edit .env blocked, `git push --force` blocked, Bash `cat .env` blocked,
Edit src/calc.py allowed, all four events audited — plus the regression for
the escape found during Qoder hook verification: directory patterns
(".ssh/**", "secrets/**") are matched against the repo-relative path, so an
absolute path resolving ABOVE the repo used to slip through hit().
"""

import json
from pathlib import Path

from helpers import harness

from harness.policy import AE, hit


def _guard(pyrepo: Path, tool: str, **ti):
    event = json.dumps({"cwd": str(pyrepo), "tool_name": tool, "tool_input": ti})
    return harness(["guard"], pyrepo, inp=event)


def test_section1_transcript_reproduces(pyrepo: Path):
    harness(["init"], pyrepo)
    cases = [
        ("Edit", {"file_path": str(pyrepo / ".env")}, "deny"),
        ("Bash", {"command": "git push --force"}, "deny"),
        ("Bash", {"command": "cat .env"}, "deny"),
        ("Edit", {"file_path": str(pyrepo / "src" / "calc.py")}, "allow"),
    ]
    for tool, ti, want in cases:
        r = _guard(pyrepo, tool, **ti)
        if want == "deny":
            assert r.returncode == 2, (tool, ti, r.stdout, r.stderr)
            assert json.loads(r.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"
        else:
            assert r.returncode == 0 and r.stdout == "", (tool, ti, r.stdout)
    lines = [json.loads(x) for x in (pyrepo / AE / "audit.log").read_text().splitlines()]
    assert [l["decision"] for l in lines[-4:]] == ["deny", "deny", "deny", "allow"]


def test_directory_patterns_hit_above_the_repo(pyrepo: Path):
    harness(["init"], pyrepo)
    ssh_key = pyrepo.parent / "home-sibs" / ".ssh" / "id_ed25519"  # never_read: .ssh/**
    ssh_key.parent.mkdir(parents=True)
    ssh_key.write_text("private\n")
    r = _guard(pyrepo, "Read", file_path=str(ssh_key))
    assert r.returncode == 2
    assert "secret path" in json.loads(r.stdout)["hookSpecificOutput"]["permissionDecisionReason"]


def test_hit_directory_anchor_is_segment_bounded():
    assert hit("../../home-sibs/.ssh/config", [".ssh/**"])
    assert hit(".github/workflows/ci.yml", [".github/workflows/**"])
    assert hit("secrets/token.json", ["secrets/**"])
    assert not hit("src/.ssh_keys/x", [".ssh/**"])
    assert not hit("src/mysecrets/x", ["secrets/**"])
