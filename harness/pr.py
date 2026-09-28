"""PR step: gated on a PASS verdict; commits worktree, pushes, opens via gh."""

from harness.contract import load_task
from harness.policy import AE, die, jload
from harness.shellx import git, sh


def cmd_pr(a) -> int:
    r, c = load_task(a)
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
    return sh(["gh", "pr", "create", "--title", c["goal"], "--body", body, "--head", c["branch"]], wt)[0]
