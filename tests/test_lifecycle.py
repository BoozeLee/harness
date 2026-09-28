import json
from pathlib import Path

from helpers import harness


def load(p: Path) -> dict:
    return json.loads(p.read_text())


def test_scan_json_is_versioned(pyrepo: Path):
    p = harness(["scan", "--json"], pyrepo)
    assert p.returncode == 0
    j = json.loads(p.stdout)
    assert j["schema_version"] == 1
    assert "unit" in j["gates"]


def test_init_writes_state_and_guard_hook(pyrepo: Path):
    p = harness(["init"], pyrepo)
    assert p.returncode == 0
    for f in ("project.json", "policy.json", "verification.json"):
        assert (pyrepo / ".ai-engineering" / f).exists(), f
    st = load(pyrepo / ".claude" / "settings.json")
    assert "schema_version" not in st  # settings.json is Claude's file, not ours
    assert any("guard" in json.dumps(h) for h in st["hooks"]["PreToolUse"])
    assert (pyrepo / "CLAUDE.md").exists()


def _guard(pyrepo: Path, tool: str, **ti):
    event = json.dumps({"cwd": str(pyrepo), "tool_name": tool, "tool_input": ti})
    return harness(["guard"], pyrepo, inp=event)


def test_guard_deny_ask_allow_channels(pyrepo: Path):
    harness(["init"], pyrepo)
    denied = _guard(pyrepo, "Edit", file_path=str(pyrepo / ".env"))
    assert denied.returncode == 2
    assert json.loads(denied.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"
    asked = _guard(pyrepo, "Bash", command="git push -u origin x")
    assert asked.returncode == 0
    assert json.loads(asked.stdout)["hookSpecificOutput"]["permissionDecision"] == "ask"
    allowed = _guard(pyrepo, "Edit", file_path=str(pyrepo / "src" / "calc.py"))
    assert allowed.returncode == 0 and allowed.stdout == ""
    lines = [json.loads(x) for x in (pyrepo / ".ai-engineering" / "audit.log").read_text().splitlines()]
    assert [l["decision"] for l in lines][-3:] == ["deny", "ask", "allow"]


def test_full_lifecycle_with_scope_and_artifacts(pyrepo: Path):
    harness(["init"], pyrepo)
    started = harness(["task", "start", "t", "--goal", "g", "--risk", "low",
                       "--allow", "src/**"], pyrepo)
    assert started.returncode == 0
    assert "unit, lint, typecheck" in started.stdout
    c = load(pyrepo / ".ai-engineering" / "tasks" / "t.json")
    wt = Path(c["worktree"])
    assert c["allowed"] == ["src/**"] and c["review"] is False

    (wt / "src" / "calc.py").write_text(
        "def add(a: int, b: int) -> int:\n    return a + b\n\n\n"
        "def subtract(a: int, b: int) -> int:\n    return a - b\n")
    (wt / "src" / "__pycache__").mkdir(exist_ok=True)
    (wt / "src" / "__pycache__" / "junk.pyc").write_text("")

    v = harness(["verify", "t"], pyrepo)
    assert v.returncode == 0, v.stdout + v.stderr
    ev = load(pyrepo / ".ai-engineering" / "evidence" / "t.json")
    assert ev["verdict"] == "PASS"
    assert "src/calc.py" in ev["files"]
    assert not any("__pycache__" in f for f in ev["files"])

    u = harness(["task", "update", "t", "--allow", "docs/**"], pyrepo)
    assert u.returncode == 0
    v2 = harness(["verify", "t"], pyrepo)
    assert v2.returncode == 1
    ev2 = load(pyrepo / ".ai-engineering" / "evidence" / "t.json")
    assert ev2["verdict"] == "FAIL"
    assert "violations: src/calc.py" in next(r["tail"] for r in ev2["results"] if r["name"] == "scope")

    ls = harness(["task", "list"], pyrepo)
    assert "t" in ls.stdout and "FAIL" in ls.stdout

    refused = harness(["pr", "t"], pyrepo)
    assert refused.returncode == 1 and "no passing evidence" in refused.stderr
