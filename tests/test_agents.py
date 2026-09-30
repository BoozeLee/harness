"""P5c acceptance: the same contract lifecycle through two different agents.

Fake `claude`/`codex` binaries on PATH stand in for real agents (no API calls): they log
argv and make a typed edit inside the allowed scope, so the full start -> run -> verify
loop must reach PASS identically for both adapters.
"""

import json
import os
from pathlib import Path

from helpers import harness

from harness.agents import AGENT_SPECS, AGENTS, build_argv

AGENT_SCRIPT = """#!/bin/sh
echo %s >> "$AGENT_LOG"
printf '%%s\\n' "$@" >> "$AGENT_LOG"
mkdir -p src && printf 'def made_by_%s() -> None:\\n    pass\\n' > src/made.py
echo ran-%s
"""


def agent_env(tmp_path: Path) -> dict:
    bin_dir = tmp_path / "agentbin"
    bin_dir.mkdir(exist_ok=True)
    for name in ("claude", "codex"):
        p = bin_dir / name
        p.write_text(AGENT_SCRIPT % (name, name, name))
        p.chmod(0o755)
    return {"PATH": f"{bin_dir}:{os.environ['PATH']}", "AGENT_LOG": str(tmp_path / "agents.log")}


def agent_log(tmp_path: Path) -> list[str]:
    p = tmp_path / "agents.log"
    return p.read_text().splitlines() if p.exists() else []


def _init_and_start(pyrepo: Path, env: dict):
    assert harness(["init"], pyrepo, env=env).returncode == 0
    p = harness(["task", "start", "t", "--goal", "stub fn", "--risk", "low", "--allow", "src/**"], pyrepo, env=env)
    assert p.returncode == 0


def _lifecycle_through(agent: str, tmp_path: Path, pyrepo: Path):
    env = agent_env(tmp_path)
    _init_and_start(pyrepo, env)
    r = harness(["task", "run", "t", "--agent", agent], pyrepo, env=env)
    assert r.returncode == 0, r.stdout + r.stderr
    assert f"ran-{agent}" in r.stdout
    wt = Path(json.loads((pyrepo / ".ai-engineering" / "tasks" / "t.json").read_text())["worktree"])
    assert (wt / "src" / "made.py").exists()
    v = harness(["verify", "t"], pyrepo, env=env)
    assert v.returncode == 0, v.stdout + v.stderr
    ev = json.loads((pyrepo / ".ai-engineering" / "evidence" / "t.json").read_text())
    assert ev["verdict"] == "PASS"


def test_claude_lifecycle(tmp_path: Path, pyrepo: Path):
    _lifecycle_through("claude", tmp_path, pyrepo)
    lines = agent_log(tmp_path)
    assert lines[0] == "claude" and "--permission-mode" in lines and "acceptEdits" in lines


def test_codex_lifecycle(tmp_path: Path, pyrepo: Path):
    _lifecycle_through("codex", tmp_path, pyrepo)
    lines = agent_log(tmp_path)
    assert lines[0] == "codex" and "exec" in lines and "--sandbox" in lines and "workspace-write" in lines


def test_run_defaults_to_claude(tmp_path: Path, pyrepo: Path):
    env = agent_env(tmp_path)
    _init_and_start(pyrepo, env)
    assert harness(["task", "run", "t"], pyrepo, env=env).returncode == 0
    assert agent_log(tmp_path)[0] == "claude"


def test_unknown_agent_rejected_by_argparse(tmp_path: Path, pyrepo: Path):
    env = agent_env(tmp_path)
    _init_and_start(pyrepo, env)
    assert harness(["task", "run", "t", "--agent", "copilot"], pyrepo, env=env).returncode == 2


def test_init_writes_agents_md_and_copies_to_worktree(tmp_path: Path, pyrepo: Path):
    env = agent_env(tmp_path)
    _init_and_start(pyrepo, env)
    rules = (pyrepo / "AGENTS.md").read_text()
    assert "# Project rules" in rules and "Verify before claiming done" in rules
    wt = Path(json.loads((pyrepo / ".ai-engineering" / "tasks" / "t.json").read_text())["worktree"])
    assert (wt / "AGENTS.md").exists()


def test_existing_agents_md_is_never_clobbered(tmp_path: Path, pyrepo: Path):
    (pyrepo / "AGENTS.md").write_text("# hand-written\n")
    assert harness(["init"], pyrepo).returncode == 0
    assert (pyrepo / "AGENTS.md").read_text() == "# hand-written\n"
    assert (pyrepo / "AGENTS.md.proposed").exists()


def test_registry_argv_contract():
    prompt = "prompt-bytes"
    for name, spec in AGENT_SPECS.items():
        argv = build_argv(name, prompt)
        assert argv == spec.argv(prompt)
        if spec.enforcement_tier == "guard-hook":
            assert argv == [spec.binary, "-p", prompt, "--permission-mode", "acceptEdits"]
        elif spec.enforcement_tier == "sandbox+verify":
            assert argv == [spec.binary, "exec", "--sandbox", "workspace-write", prompt]
    assert AGENTS == tuple(AGENT_SPECS)


def test_unknown_agent_lists_registry_keys(capsys):
    import pytest
    with pytest.raises(SystemExit) as exc:
        build_argv("missing", "prompt")
    assert exc.value.code == 1
    assert f"unknown agent: missing (supported: {', '.join(AGENT_SPECS)})" in capsys.readouterr().err


def test_agents_json_probes_fake_path(tmp_path: Path, pyrepo: Path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    spec_names = list(AGENT_SPECS)
    present = AGENT_SPECS[spec_names[0]]
    shim = bin_dir / present.binary
    shim.write_text("#!/bin/sh\nprintf 'fake-agent 1.0\\n'\n")
    shim.chmod(0o755)
    env = {"PATH": f"{bin_dir}:/usr/bin:/bin"}
    proc = harness(["agents", "--json"], pyrepo, env=env)
    assert proc.returncode == 0, proc.stderr
    rows = json.loads(proc.stdout)
    by_name = {row["name"]: row for row in rows}
    assert by_name[spec_names[0]]["present"] is True
    assert by_name[spec_names[0]]["version"] == "fake-agent 1.0"
    assert by_name[spec_names[1]]["present"] is False
