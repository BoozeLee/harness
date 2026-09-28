"""Verification: run gates, check scope, request independent review, emit evidence."""

import shutil
import time

from harness.contract import load_task
from harness.evidence import write as write_evidence
from harness.gitops import changed_files
from harness.policy import hit
from harness.shellx import git, sh


def review(c: dict):
    if not shutil.which("claude"):
        return None, "claude CLI unavailable; review skipped"
    d = git(c["worktree"], "diff", c["base"])[1][:40000]
    p = ("You are an independent code reviewer. Review this diff against the goal and acceptance criteria. "
         f"Goal: {c['goal']}\nCriteria: {c['accept']}\nList concrete defects only. End with 'VERDICT: PASS' or 'VERDICT: FAIL'.\n\n{d}")
    rc, out, _ = sh(["claude", "-p", p], c["worktree"], timeout=900)
    return ("VERDICT: PASS" in out and rc == 0), out[-1500:]


def cmd_verify(a) -> int:
    r, c = load_task(a)
    wt = c["worktree"]
    res = []
    for k, g in c["gates"].items():
        rc, out, t = sh(g["cmd"], wt)
        res.append({"name": k, "cmd": g["cmd"], "ok": rc == 0, "secs": t, "tail": out[-1200:], "required": True})
    ch = changed_files(wt, c["base"])
    bad = [f for f in ch if hit(f, c["protected"]) or not hit(f, c["allowed"])]
    res.append({"name": "scope", "cmd": "changed files within contract", "ok": not bad, "secs": 0,
                "tail": ("violations: " + ", ".join(bad)) if bad else f"{len(ch)} files in scope",
                "required": True})
    if c["review"]:
        ok, out = review(c)
        res.append({"name": "independent-review", "cmd": "claude -p reviewer", "ok": bool(ok), "secs": 0,
                    "tail": out, "required": True, "skipped": ok is None})
    stat = git(wt, "diff", "--shortstat", c["base"])[1]
    ok = all(x["ok"] for x in res if x["required"])
    ev = {"task": c["name"], "goal": c["goal"], "accept": c["accept"], "results": res, "files": ch,
          "stat": stat, "verdict": "PASS" if ok else "FAIL", "time": int(time.time())}
    hp = write_evidence(r, ev)[1]
    for x in res:
        print(f"{'PASS' if x['ok'] else 'FAIL':<5} {x['name']:<20} {x['secs']}s")
    print(f"\nVerdict: {ev['verdict']}   ({stat or 'no diff'})")
    print(f"Report : {hp}")
    return 0 if ok else 1
