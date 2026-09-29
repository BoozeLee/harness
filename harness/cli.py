"""Argparse surface. Exit codes: 0 ok, 1 policy/contract failure or die(), 2 reserved for guard block."""

import argparse
import sys

from harness import __version__
from harness.agents import AGENTS
from harness.contract import cmd_list, cmd_run, cmd_start, cmd_update
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
    x.set_defaults(f=cmd_scan)

    x = s.add_parser("init", help="write .ai-engineering/, CLAUDE.md, AGENTS.md and .claude/settings.json")
    x.add_argument("--force", action="store_true")
    x.set_defaults(f=cmd_init)

    s.add_parser("guard", help=argparse.SUPPRESS).set_defaults(f=cmd_guard)

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
