# Harness

Local-first control plane that turns a normal Git repo into a governed, verifiable agentic dev environment. Stdlib-only Python core, packaged: install with `uv tool install .` (or `uv tool install --editable .` in this repo) and use `harness --help`.

```
harness scan                       # agent-readiness score, detected gates, protected paths
harness scan --fail-under 70       # same score as a CI floor: exits 1 when readiness is below N
harness init                       # writes .ai-engineering/{project,policy,verification}.json,
                                   # CLAUDE.md + AGENTS.md, .claude/settings.json (allow/deny + guard hook)
harness ci                         # writes .github/workflows/harness.yml: readiness floor + this repo's gates
harness policy push <bundle-repo>  # publish policy.json + verification.json to a shared Git repo
harness policy status <bundle-repo>  # exits 1 when the local bundle differs from the team's
harness task start invites --goal "Add team invitations" --accept "expired invite is rejected" --risk high
harness task update invites --allow "src/**" --allow "tests/**"   # amend a contract
harness task list                  # contracts with risk, branch, latest verdict
harness task run invites --agent codex  # headless agent inside the worktree (claude|codex, optional)
harness verify invites             # runs every gate + scope check + independent review -> evidence HTML
harness pr create invites          # refuses unless evidence verdict is PASS
harness serve --port 8766          # local API + runner + dashboard backend (uv sync --extra server)
```

- **Guard hook**: `harness guard` is registered as a Claude Code PreToolUse hook; it blocks writes to protected paths, reads of secrets, and forbidden commands (exit 2) and logs to `.ai-engineering/audit.log`.
- **Completion contract**: a task is done only when all gates for its risk level pass, changes stay in scope, and the reviewer returns `VERDICT: PASS` (skipped review counts as not passed).
- **Everything is plain JSON/Markdown** in Git: inspect with `git diff`, no lock-in.
- **`web/`** dashboard talks to `harness serve` (FastAPI on 127.0.0.1:8766, bearer token in
  `.ai-engineering/serve.token`); run `npm run dev` in `web/` after `cd web && npm install`.
  Verify/agent runs stream live over SSE (Runs view); `--max-parallel` caps concurrent runs.
  The CLI is fully usable without it.
- Not yet built (per the report's roadmap): evals comparing raw vs. harnessed runs. Review Agent SDK commercial terms before shipping a hosted product.
