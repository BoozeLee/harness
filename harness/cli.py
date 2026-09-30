"""Argparse surface. Exit codes: 0 ok, 1 policy/contract failure or die(), 2 reserved for guard block."""

import argparse
import sys

from harness import __version__
from harness.agents import AGENTS, cmd_agents
from harness.bundle import cmd_policy
from harness.ci import cmd_ci
from harness.contract import cmd_list, cmd_run, cmd_start, cmd_update
from harness.eval import VARIANTS, cmd_eval
from harness.guard import cmd_guard
from harness.policy import LVL, cmd_init
from harness.pr import cmd_pr
from harness.scan import cmd_scan
from harness.verify import cmd_verify


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="harness",
                                description="Local-first control plane that professionalizes how "
                                            "coding agents work on a repo: scan -> init -> task start "
                                            "-> (task run) -> verify -> pr.")
    p.add_argument("--version", action="version", version=f"harness {__version__}")
    p.add_argument("--repo", default=".")
    s = p.add_subparsers(dest="c", required=True)

    x = s.add_parser("scan", help="detect stacks, gates, protected paths; score agent-readiness")
    x.add_argument("--json", action="store_true")
    x.add_argument("--fail-under", type=int, metavar="N", help="exit 1 when readiness scores below N (CI gate)")
    x.set_defaults(f=cmd_scan)

    x = s.add_parser("init", help="write .ai-engineering/, CLAUDE.md, AGENTS.md and .claude/settings.json")
    x.add_argument("--force", action="store_true")
    x.set_defaults(f=cmd_init)

    s.add_parser("guard", help=argparse.SUPPRESS).set_defaults(f=cmd_guard)

    x = s.add_parser("agents", help="show supported agent binaries and enforcement tiers")
    x.add_argument("--json", action="store_true", help="machine-readable JSON output")
    x.set_defaults(f=cmd_agents)

    t = s.add_parser("task", help="manage contracts").add_subparsers(dest="t", required=True)
    x = t.add_parser("start")
    x.add_argument("name")
    x.add_argument("--goal", required=True)
    x.add_argument("--accept", action="append")
    x.add_argument("--allow", action="append")
    x.add_argument("--risk", choices=list(LVL), default="medium")
    x.set_defaults(f=cmd_start)
    x = t.add_parser("run", help="optional headless agent run inside the worktree")
    x.add_argument("name")
    x.add_argument("--agent", choices=list(AGENTS), default="claude")
    x.set_defaults(f=cmd_run)
    x = t.add_parser("update", help="amend a contract (goal/accept/allow/risk)")
    x.add_argument("name")
    x.add_argument("--goal")
    x.add_argument("--accept", action="append")
    x.add_argument("--allow", action="append")
    x.add_argument("--risk", choices=list(LVL))
    x.set_defaults(f=cmd_update)
    x = t.add_parser("list")
    x.set_defaults(f=cmd_list)

    x = s.add_parser("verify", help="run gates + scope + review, emit evidence")
    x.add_argument("name")
    x.set_defaults(f=cmd_verify)

    x = s.add_parser("pr", help="gh-backed PR operations for task branches")
    prs = x.add_subparsers(dest="prc", required=True)
    y = prs.add_parser("create", help="commit, push, gh pr create (requires PASS evidence)")
    y.add_argument("name")
    y = prs.add_parser("view", help="show the PR opened for the task branch")
    y.add_argument("name")
    prs.add_parser("status", help="gh pr status")
    prs.add_parser("list", help="gh pr list")
    x.set_defaults(f=cmd_pr)

    x = s.add_parser("policy", help="sync the team policy bundle (policy.json + verification.json) with a Git repo")
    ps = x.add_subparsers(dest="polc", required=True)
    for nm, hp in (("push", "publish local policy + gates to the bundle repo"),
                   ("pull", "adopt the bundle as the local team standard"),
                   ("status", "exit 1 when the local bundle differs from the remote")):
        y = ps.add_parser(nm, help=hp)
        y.add_argument("remote", help="bundle repo path or URL")
        y.add_argument("--branch", default="main")
    x.set_defaults(f=cmd_policy)

    x = s.add_parser("ci", help="generate .github/workflows/harness.yml (readiness floor + gates)")
    x.add_argument("--fail-under", type=int, metavar="N",
                   help="readiness floor in the workflow (default: min(70, the repo's measured score))")
    x.add_argument("--setup", action="append", metavar="CMD",
                   help="extra step the gates need before they can run (repeatable), e.g. "
                        '"cd web && npx playwright install --with-deps chromium"')
    x.add_argument("--install", metavar="CMD",
                   help="how CI installs the harness CLI (default: this repo when it is harness, "
                        "otherwise `pip install harness-agent`)")
    x.add_argument("--force", action="store_true", help="overwrite a hand-written workflow")
    x.set_defaults(f=cmd_ci)

    x = s.add_parser("eval", help="P7: run the raw-vs-harnessed corpus and report metrics")
    evs = x.add_subparsers(dest="ev", required=True)
    evs.add_parser("list", help="show the task matrix").set_defaults(f=cmd_eval)
    y = evs.add_parser("run", help="run evals (fake agent with --dry; provider calls otherwise)")
    y.add_argument("--task", help="only this task id")
    y.add_argument("--agent", choices=[*AGENTS, "all"], default="all")
    y.add_argument("--variant", choices=[*VARIANTS, "all"], default="all")
    y.add_argument("--dry", action="store_true", help="no provider calls: fake no-op agent, plumbing proof")
    y.add_argument("--keep", action="store_true", help="keep throwaway workdirs for post-mortem")
    y.set_defaults(f=cmd_eval)
    evs.add_parser("report", help="render evals/report.html from evals/results.jsonl").set_defaults(f=cmd_eval)


    x = s.add_parser("serve", help="local API server for the dashboard (needs server extra)")
    x.add_argument("--host", default="127.0.0.1")
    x.add_argument("--port", type=int, default=8766)
    x.add_argument("--max-parallel", type=int, default=2, help="concurrent agent/verify runs (plan §4.3)")
    x.set_defaults(f=_serve)

    a = p.parse_args(argv)
    return a.f(a) or 0


def _serve(a) -> int:
    try:
        from harness.server import cmd_serve
    except ImportError:
        from harness.policy import die
        die("fastapi/uvicorn missing; run `uv sync --extra server` or `uv tool install harness-agent --with fastapi --with uvicorn`")
    return cmd_serve(a)


if __name__ == "__main__":
    sys.exit(main())
