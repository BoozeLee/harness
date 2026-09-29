"""Project operations on PRs via gh: create is gated on a PASS verdict;
view/status/list are read-only passthroughs."""

import json

from harness.contract import load_task
from harness.policy import AE, die, find_root, jload
from harness.shellx import git, sh


def cmd_pr(a) -> int:
    if a.prc in ("status", "list"):
        r = find_root(a.repo)
        if not r:
            die("run `harness init` first")
        return _gh(r, a.prc)
    r, c = load_task(a)
    if a.prc == "create":
        return _create(r, c)
    return _view(r, c)


def _gh(r, *args) -> int:
    rc, out, _ = sh(["gh", "pr", *args], str(r))
    if rc == 127:
        die("gh not installed or not on PATH")
    if out:
        print(out)
    return rc


def _create(r, c) -> int:
    ep = r / AE / "evidence" / f"{c['name']}.json"
    if not ep.exists() or jload(ep)["verdict"] != "PASS":
        die("no passing evidence; run `harness verify` first")
    wt = c["worktree"]
    git(wt, "add", "-A", f":!{AE}", ":!.claude", ":!CLAUDE.md")
    rc, out, _ = git(wt, "commit", "-m", f"{c['goal']}\n\nVerified by Harness ({c['name']}).")
    if rc and "nothing to commit" not in out and "nothing added to commit" not in out:
        die(out)
    rc, out, _ = git(wt, "push", "-u", "origin", c["branch"])
    if rc:
        die(out)
    ev = jload(ep)
    body = "\n".join(f"- {'PASS' if x['ok'] else 'FAIL'} {x['name']}" for x in ev["results"]) + f"\n\n{ev['stat']}"
    rc, out, _ = sh(["gh", "pr", "create", "--title", c["goal"], "--body", body, "--head", c["branch"]], wt)
    if rc:
        die(f"gh pr create failed:\n{out}")
    if out:
        print(out)
    return 0


def _view(r, c) -> int:
    rc, out, _ = sh(["gh", "pr", "list", "--head", c["branch"], "--json", "number"], str(r))
    if rc:
        die(f"gh pr list failed:\n{out}")
    try:
        prs = json.loads(out)
    except json.JSONDecodeError:
        die(f"unparseable gh output: {out[:200]}")
    if not prs:
        die(f"no PR for {c['branch']}; run `harness pr create {c['name']}`")
    return _gh(r, "view", str(prs[0]["number"]))
