# Harness

Local-first control plane that turns a normal Git repo into a governed, verifiable agentic dev environment. Stdlib-only Python core, packaged: install with `uv tool install .` (or `uv tool install --editable .` in this repo) and use `harness --help`.

```
harness scan                       # agent-readiness score, detected gates, protected paths
harness init                       # writes .ai-engineering/{project,policy,verification}.json,
                                   # minimal CLAUDE.md, .claude/settings.json (allow/deny + guard hook)
harness task start invites --goal "Add team invitations" --accept "expired invite is rejected" --risk high
harness task update invites --allow "src/**" --allow "tests/**"   # amend a contract
harness task list                  # contracts with risk, branch, latest verdict
harness task run invites           # headless `claude -p` inside the isolated worktree (optional)
harness verify invites             # runs every gate + scope check + independent review -> evidence HTML
harness pr invites                 # refuses unless evidence verdict is PASS
```

- **Guard hook**: `harness guard` is registered as a Claude Code PreToolUse hook; it blocks writes to protected paths, reads of secrets, and forbidden commands (exit 2) and logs to `.ai-engineering/audit.log`.
- **Completion contract**: a task is done only when all gates for its risk level pass, changes stay in scope, and the reviewer returns `VERDICT: PASS` (skipped review counts as not passed).
- **Everything is plain JSON/Markdown** in Git: inspect with `git diff`, no lock-in.
- **`web/`** is a draft dashboard (Vite + React + TS) for the planned local API server
  (plan §4.2, phase P1); the CLI is fully usable without it.
- Not yet built (per the report's roadmap): browser verification, team policy sync, Codex/Copilot adapters, evals comparing raw vs. harnessed runs. Review Agent SDK commercial terms before shipping a hosted product.
