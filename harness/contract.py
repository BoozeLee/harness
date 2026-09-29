"""Task contracts: start/update/list and the optional headless agent run."""

import shutil
import time
from pathlib import Path

from harness.policy import AE, LVL, die, find_root, jload, jsave
from harness.shellx import git, sh


def tdir(r: Path) -> Path:
    return r / AE / "tasks"


def load_task(a) -> tuple:
    r = find_root(a.repo)
    if not r:
        die("run `harness init` first")
    p = tdir(r) / f"{a.name}.json"
    if not p.exists():
        die(f"no such task: {a.name}")
    return r, jload(p)


def cmd_start(a) -> int:
    r = find_root(a.repo)
    if not r:
        die("run `harness init` first")
    wt = r.parent / ".harness-worktrees" / f"{r.name}-{a.name}"
    br = f"harness/{a.name}"
    base = git(r, "rev-parse", "HEAD")[1]
    rc, out, _ = git(r, "worktree", "add", "-b", br, str(wt))
    if rc:
        die(out)
    for p in (AE, ".claude", "CLAUDE.md", "AGENTS.md"):
        s, d = r / p, wt / p
        if s.exists() and not d.exists():
            if s.is_dir():
                shutil.copytree(s, d, ignore=shutil.ignore_patterns("tasks", "evidence", "audit.log"))
            else:
                shutil.copy2(s, d)
    v = jload(r / AE / "verification.json")
    pol = jload(r / AE / "policy.json")
    gates = {k: g for k, g in v["gates"].items() if LVL[g["min_risk"]] <= LVL[a.risk]}
    con = {"name": a.name, "goal": a.goal, "accept": a.accept or [], "risk": a.risk, "branch": br,
           "worktree": str(wt), "base": base, "allowed": a.allow or ["**"], "protected": pol["protected"],
           "gates": gates, "review": v.get("review", True) and a.risk != "low", "created": int(time.time())}
    jsave(tdir(r) / f"{a.name}.json", con)
    print(f"Worktree : {wt}\nBranch   : {br}\nGates    : {', '.join(gates) or 'none (!)'}")
    print(f"Next     : harness task run {a.name}   |   harness verify {a.name}")
    return 0


def cmd_update(a) -> int:
    r, c = load_task(a)
    if a.goal:
        c["goal"] = a.goal
    if a.accept:
        c["accept"] = a.accept
    if a.allow:
        c["allowed"] = a.allow
    if a.risk and a.risk != c["risk"]:
        c["risk"] = a.risk
        v = jload(r / AE / "verification.json")
        c["gates"] = {k: g for k, g in v["gates"].items() if LVL[g["min_risk"]] <= LVL[a.risk]}
        c["review"] = v.get("review", True) and c["risk"] != "low"
    jsave(tdir(r) / f"{c['name']}.json", c)
    print(f"Updated  : {c['name']}\nRisk     : {c['risk']}\nGates    : {', '.join(c['gates']) or 'none (!)'}")
    print(f"Allowed  : {', '.join(c['allowed'])}")
    return 0


def cmd_list(a) -> int:
    r = find_root(a.repo)
    if not r:
        die("run `harness init` first")
    d = tdir(r)
    rows = []
    for p in sorted(d.glob("*.json")) if d.is_dir() else []:
        c = jload(p)
        ep = r / AE / "evidence" / f"{c['name']}.json"
        verdict = jload(ep)["verdict"] if ep.exists() else "unverified"
        rows.append(f"{c['name']:<20} {c['risk']:<7} {c['branch']:<28} {verdict}")
    if not rows:
        print("no tasks")
    for row in rows:
        print(row)
    return 0


def cmd_run(a) -> int:
    from harness.agents import agent_prompt, build_argv

    _, c = load_task(a)
    if not shutil.which(a.agent):
        die(f"`{a.agent}` CLI not found; work in the worktree manually, then `harness verify`.")
    rc, out, _ = sh(build_argv(a.agent, agent_prompt(c)), c["worktree"], timeout=3600)
    if out:
        print(out)
    return rc
