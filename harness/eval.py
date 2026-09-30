"""P7 evals: identical small tasks run raw vs harnessed, metrics collected honestly.

The comparison holds the agent binary constant and varies only the scaffolding:
raw = one headless agent call in a throwaway copy of the fixture; harnessed =
the same call inside `init -> task start -> run -> verify`. Ground truth is an
acceptance test suite (`test_graded/`) the agent never sees — it is copied in
only after the agent finishes, so `graded_pass` measures the outcome, not the
agent's ability to game a visible test.

Cost is wall-clock seconds: token metering is agent-vendor-specific and would
compare incommensurable numbers (plan §7 P7 lists cost/task; we ship the
honest subset). Codex needs a workspace-write sandbox and Claude runs under
acceptEdits — same as the production adapters (harness/agents.py).
"""

import html
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

from harness.agents import AGENTS, agent_prompt, build_argv
from harness.gitops import changed_files
from harness.policy import die, hit
from harness.shellx import git, sh

VARIANTS = ("raw", "harnessed")
EVALS_DIR = "evals"


def load_tasks(r: Path) -> list[dict]:
    p = r / EVALS_DIR / "tasks.json"
    if not p.exists():
        die(f"no corpus: {p} (missing evals/tasks.json)")
    return json.loads(p.read_text())["tasks"]


def _score_cmds(stack: str) -> tuple[str, str]:
    if stack == "python":
        return "uv run pytest -q test_graded", "uv run pytest -q"
    return "npm install --prefer-offline --no-audit --no-fund && npx tsc && node --test test_graded/graded.test.ts", \
           "npm install --prefer-offline --no-audit --no-fund && npm test"


def _fake_agent(dirs: Path) -> dict[str, str]:
    bin_dir = dirs / "bin"
    bin_dir.mkdir()
    for name in AGENTS:
        p = bin_dir / name
        p.write_text("#!/bin/sh\nexit 0\n")
        p.chmod(0o755)
    return {**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}"}


def _fresh_fixture(src: Path, dirs: Path) -> Path:
    wd = dirs / "wd"
    shutil.copytree(src, wd, ignore=shutil.ignore_patterns("test_graded", "node_modules", ".venv"))
    git(wd, "init", "-q", "-b", "main")
    git(wd, "add", "-A")
    git(wd, "-c", "user.email=e@eval", "-c", "user.name=eval", "commit", "-qm", "fixture base")
    return wd


def _run_agent(agent: str, wd: Path, goal: str, accept: list[str], gates: list[str],
               env: dict[str, str] | None) -> tuple[int, float, str]:
    prompt = (agent_prompt({"goal": goal, "accept": accept, "gates": {g: {"cmd": g} for g in gates}})
              if gates else
              "Goal: " + goal + "\nAcceptance criteria:\n" + "\n".join(f"- {x}" for x in accept) +
              "\nFirst write a short plan, then implement. Before finishing, make sure the existing test command still passes.")
    rc, out, secs = sh(build_argv(agent, prompt), str(wd), timeout=1800, env=env)
    rec_extra = out[-300:] if rc else ""
    return rc, secs, rec_extra


def _grade(wd: Path, task: dict, fixture: Path) -> tuple[bool, int, str]:
    grade_cmd = _score_cmds(task["stack"])[0]
    if (wd / "test_graded").exists():
        shutil.rmtree(wd / "test_graded")
    shutil.copytree(fixture / "test_graded", wd / "test_graded")
    if task["stack"] != "python":
        (wd / "tsconfig.json").write_text(json.dumps({
            "compilerOptions": {"target": "ES2022", "module": "commonjs", "strict": True,
                                "rootDir": ".", "outDir": "dist", "esModuleInterop": True,
                                "moduleDetection": "force"},
            "include": ["src", "tests", "test_graded"]}) + "\n")
    rc, out, _ = sh(grade_cmd, str(wd), timeout=900)
    return rc == 0, rc, out[-600:]


def _harness_cli(repo: Path, *args: str) -> tuple[int, str]:
    rc, out, _ = sh([sys.executable, "-m", "harness", "--repo", str(repo), *args],
                    cwd=str(repo), env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parent.parent)})
    return rc, out


def _review_note(vout: str) -> str:
    tail = vout.split("independent-review")[-1] if "independent-review" in vout else vout
    return tail[-300:]


def run_one(task: dict, agent: str, variant: str, dry: bool, keep: bool) -> dict:
    """One eval: raw or harnessed. Honesty rules enforced here:
    - the graded suite lives in a separate mkdtemp dir (unpredictable sibling
      paths defeat an agent that tries to peek at the answer key),
    - harnessed runs `--risk medium` exactly like production (init's verification
     .json marks typecheck/e2e medium; the medium slice of discovered gates +
      independent review is what a real task would get),
    - `wall` is the WHOLE pipeline cost per variant, not just the agent call."""
    root = Path(__file__).resolve().parent.parent
    src = root / EVALS_DIR / "fixtures" / task["id"]
    if not src.is_dir():
        die(f"missing fixture for {task['id']}: {src}")
    dirs = Path(tempfile.mkdtemp(prefix=f"eval-{task['id']}-{variant}-"))
    key = Path(tempfile.mkdtemp(prefix="evalkey-"))  # answer key: no predictable path
    try:
        shutil.copytree(src, key / "fixture", ignore=shutil.ignore_patterns("node_modules", ".venv"))
        wd = _fresh_fixture(src, dirs)
        env = _fake_agent(dirs) if dry else None
        agent_cmd = _score_cmds(task["stack"])[1]
        allowed = [task["module"], "tests/**"]
        accept_args: list[str] = []
        for x in task["accept"]:
            accept_args += ["--accept", x]

        rec: dict = {"ts": int(time.time()), "task": task["id"], "stack": task["stack"],
                     "agent": "fake" if dry else agent, "variant": variant, "dry": dry}
        t0 = time.time()
        if variant == "harnessed":
            rc, _ = _harness_cli(wd, "init")
            if rc:
                rec["init_failed"] = True
            _harness_cli(wd, "task", "start", task["id"], "--goal", task["goal"], *accept_args,
                         "--allow", task["module"], "--risk", "medium")
            tcon = json.loads((wd / ".ai-engineering" / "tasks" / f"{task['id']}.json").read_text())
            awd = Path(tcon["worktree"])
            rec["agent_rc"], rec["agent_wall"], rec["agent_tail"] = _run_agent(
                agent, awd, task["goal"], task["accept"], [agent_cmd], env)
            _, vout = _harness_cli(wd, "verify", task["id"])
            rec["verdict"] = "PASS" if "Verdict: PASS" in vout else ("FAIL" if "Verdict:" in vout else "ERROR")
            rec["review_note"] = "" if rec["verdict"] == "PASS" else _review_note(vout)
            changed = changed_files(awd, tcon["base"])
            target = awd
        else:
            base = git(wd, "rev-parse", "HEAD")[1]
            rec["agent_rc"], rec["agent_wall"], rec["agent_tail"] = _run_agent(
                agent, wd, task["goal"], task["accept"], [agent_cmd], env)
            changed = changed_files(wd, base)  # diff-vs-base includes agent commits
            rec["verdict"] = None
            target = wd
        rec["wall"] = round(time.time() - t0, 1)
        rec["scope_violations"] = sum(1 for f in changed if not hit(f, allowed))
        ok, grc, gout = _grade(target, task, key / "fixture")
        rec["graded_pass"] = ok
        rec["grade_rc"] = grc
        if not ok:
            rec["grade_tail"] = gout
        if keep:
            rec["kept"] = str(dirs)
        else:
            shutil.rmtree(dirs, ignore_errors=True)
        return rec
    finally:
        shutil.rmtree(key, ignore_errors=True)


def cmd_eval(a) -> int:
    r = Path(a.repo).resolve()
    if a.ev == "list":
        rows = load_tasks(r)
        print(f"{'task':<14} {'stack':<12} module")
        for t in rows:
            print(f"{t['id']:<14} {t['stack']:<12} {t['module']}")
        print(f"\n{len(rows)} tasks x agents {', '.join(AGENTS)} x variants {', '.join(VARIANTS)}")
        return 0
    if a.ev == "run":
        rows = [t for t in load_tasks(r) if not a.task or t["id"] == a.task]
        if a.task and not rows:
            die(f"no such eval task: {a.task}")
        agents = AGENTS if a.agent == "all" else (a.agent,)
        variants = VARIANTS if a.variant == "all" else (a.variant,)
        out_path = r / EVALS_DIR / "results.jsonl"
        with out_path.open("a") as f:
            for t in rows:
                for ag in agents:
                    for v in variants:
                        rec = run_one(t, ag, v, dry=a.dry, keep=a.keep)
                        f.write(json.dumps(rec) + "\n")
                        f.flush()
                        print(f"{t['id']:<14} {rec['agent']:<7} {v:<10} graded={'PASS' if rec['graded_pass'] else 'FAIL'} "
                              f"gates={rec.get('verdict') or 'n/a':<8} scope={rec['scope_violations']} wall={rec['wall']}s")
        print(f"\nresults appended: {out_path}")
        return 0
    if a.ev == "report":
        rows = _read_results(r)
        html_out = render_report(rows)
        p = r / EVALS_DIR / "report.html"
        p.write_text(html_out)
        print(f"report: {p} ({len(rows)} runs)")
        return 0
    die(f"unknown eval subcommand: {a.ev}")


def _read_results(r: Path) -> list[dict]:
    p = r / EVALS_DIR / "results.jsonl"
    if not p.exists():
        die("no results yet; run `harness eval run --dry` first")
    return [json.loads(line) for line in p.read_text().splitlines() if line.strip()]


def render_report(rows: list[dict]) -> str:
    e = html.escape
    groups: dict[tuple[str, str], dict[str, list[dict]]] = {}
    for rec in rows:
        groups.setdefault((f"{rec['agent']}/{rec['stack']}", rec["task"]), {}).setdefault(rec["variant"], []).append(rec)
    head = ("<!doctype html><meta charset=utf-8><meta http-equiv='Content-Security-Policy' "
            "content=\"default-src 'none'; style-src 'unsafe-inline'\"><title>Harness evals</title>"
            "<style>body{font:14px system-ui;max-width:960px;margin:2rem auto}table{border-collapse:collapse}"
            "td,th{border:1px solid #ccc;padding:4px 8px}.pass{color:#070}.fail{color:#a00}</style>"
            "<h1>raw vs harnessed — eval report</h1>")
    body = []
    for key in sorted(groups):
        combo, task = key
        body.append(f"<h2>{e(combo)} — {e(task)}</h2><table><tr><th>variant</th><th>n</th>"
                    "<th>graded pass</th><th>first-pass gates</th><th>scope violations</th><th>mean wall (s)</th><th>reviewer FAIL notes</th></tr>")
        for v in VARIANTS:
            recs = groups[key].get(v, [])
            if not recs:
                continue
            graded = sum(1 for x in recs if x.get("graded_pass"))
            fp = sum(1 for x in recs if x.get("verdict") == "PASS")
            gates_cell = "—" if all(x.get("verdict") is None for x in recs) else f"{fp}/{len(recs)}"
            viol = sum(x.get("scope_violations", 0) for x in recs)
            wall = round(sum(x.get("wall", 0) for x in recs) / len(recs), 1)
            notes = "; ".join(e(str(x.get("review_note", ""))[:80]) for x in recs if x.get("review_note"))
            cls = "pass" if graded == len(recs) else "fail"
            body.append(f"<tr><td>{e(v)}</td><td>{len(recs)}</td><td class={cls}>{graded}/{len(recs)}</td>"
                        f"<td>{gates_cell}</td><td>{viol}</td><td>{wall}</td><td>{notes or '—'}</td></tr>")
        body.append("</table>")
    return head + "".join(body) + f"<p>{len(rows)} runs total.</p>"
