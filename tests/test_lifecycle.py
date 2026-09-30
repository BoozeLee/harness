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
    assert [ev["decision"] for ev in lines][-3:] == ["deny", "ask", "allow"]


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
    assert "shots" not in ev  # no e2e-typed gate → byte-identical to pre-P4 evidence
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

    refused = harness(["pr", "create", "t"], pyrepo)
    assert refused.returncode == 1 and "no passing evidence" in refused.stderr


def test_e2e_gate_archives_shots_via_cli(pyrepo: Path):
    import hashlib

    harness(["init"], pyrepo)
    vf = pyrepo / ".ai-engineering" / "verification.json"
    v = load(vf)
    # cmd asserts the env plumbing: an e2e-typed gate must run with HARNESS_GATE_E2E=1
    v["gates"]["browser"] = {"cmd": 'test "$HARNESS_GATE_E2E" = 1 && mkdir -p web/test-results/demo-a '
                                    "&& head -c 64 /dev/urandom > web/test-results/demo-a/test-passed-1.png",
                             "min_risk": "low", "type": "e2e"}
    vf.write_text(json.dumps(v, indent=2) + "\n")

    started = harness(["task", "start", "et", "--goal", "g", "--risk", "low", "--allow", "src/**"], pyrepo)
    assert started.returncode == 0, started.stdout + started.stderr
    c = load(pyrepo / ".ai-engineering" / "tasks" / "et.json")
    assert c["gates"]["browser"]["type"] == "e2e"  # type survives contract copying

    Path(c["worktree"], "src", "calc.py").write_text(
        "def add(a: int, b: int) -> int:\n    return a + b\n\n\n"
        "def mul(a: int, b: int) -> int:\n    return a * b\n")
    done = harness(["verify", "et"], pyrepo)
    assert done.returncode == 0, done.stdout + done.stderr

    ev = load(pyrepo / ".ai-engineering" / "evidence" / "et.json")
    assert ev["verdict"] == "PASS"
    assert len(ev["shots"]) == 1
    shot = ev["shots"][0]
    dest = pyrepo / ".ai-engineering" / "evidence" / "et" / shot["file"]
    assert hashlib.sha256(dest.read_bytes()).hexdigest() == shot["sha256"]
    assert "test-results" not in " ".join(ev["files"])  # artifacts stay out of scope


def test_verify_stat_names_untracked_agent_work(pyrepo: Path):
    """Adoption defect (gitcrate): an agent that only adds new files produced a
    PASS verdict printed as '(no diff)' — git diff never sees untracked paths."""
    harness(["init"], pyrepo)
    started = harness(["task", "start", "un", "--goal", "g", "--risk", "low",
                       "--allow", "pytest.ini"], pyrepo)
    assert started.returncode == 0
    c = load(pyrepo / ".ai-engineering" / "tasks" / "un.json")
    wt = Path(c["worktree"])
    (wt / "pytest.ini").write_text("[pytest]\ntestpaths = tests\n")

    v = harness(["verify", "un"], pyrepo)
    assert v.returncode == 0, v.stdout + v.stderr
    ev = load(pyrepo / ".ai-engineering" / "evidence" / "un.json")
    assert "1 untracked file(s) added" in ev["stat"]
    assert "no diff" not in v.stdout
