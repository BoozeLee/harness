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
harness eval run --agent codex     # P7: raw-vs-harnessed corpus runs (list|run|report; --dry = offline)
```

- **Guard hook**: `harness guard` is registered as a Claude Code PreToolUse hook; it blocks writes to protected paths, reads of secrets, and forbidden commands (exit 2) and logs to `.ai-engineering/audit.log`.
- **Completion contract**: a task is done only when all gates for its risk level pass, changes stay in scope, and the reviewer returns `VERDICT: PASS` (skipped review counts as not passed).
- **Everything is plain JSON/Markdown** in Git: inspect with `git diff`, no lock-in.
- **`web/`** dashboard talks to `harness serve` (FastAPI on 127.0.0.1:8766, bearer token in
  `.ai-engineering/serve.token`); run `npm run dev` in `web/` after `cd web && npm install`.
  Verify/agent runs stream live over SSE (Runs view); `--max-parallel` caps concurrent runs.
  The CLI is fully usable without it.
- **Evals (P7)**: 6 small tasks (3 Python, 3 TypeScript) each run twice — raw agent
  call vs. the full `init → task start → run → verify` pipeline, same agent binary.
  Ground truth is a hidden acceptance suite the agent never sees. Live matrix
  (codex, 2026-09-30, 13 runs): **11/13 graded PASS** — only slugify failed, both
  variants, on the collapse-runs edge case (a real agent miss, not an env flake); scope violations raw=3 vs harnessed=4 (contract amended after the
  runner flagged them); first-pass gates read FAIL on every harnessed run because
  independent-review hits the provider session limit — recorded, not skipped. The
  claude half waits on the 07:00 (Brussels) quota window; regenerate with
  `harness eval run --agent all && harness eval report`.
- Not yet built (per the report's roadmap): hosted product. Review Agent SDK commercial terms before shipping one.

## License and network source (AGPL §13)

`harness-agent` is **AGPL-3.0-only** — see [`LICENSE`](LICENSE).

Exactly one command opens a socket: `harness serve`. It runs FastAPI on
`127.0.0.1:8766` by default (`--host` / `--port`) and authenticates
state-changing requests with the bearer token in `.ai-engineering/serve.token`.
Every other command in the table above is a local CLI: it reads and writes
files and never listens. `harness --version` prints the running version.

If you rebind `--host` away from loopback, or forward the port so someone else
can reach the API or the dashboard, remote users are interacting with your
build over a network and AGPL §13 applies. You must then offer those users the
Corresponding Source of *your* version from a network server at no charge,
through some standard or customary means of copying software.

The Corresponding Source for this work is public at no charge here:

    https://github.com/BoozeLee/harness

Check out the commit you built from on `main` to reproduce it exactly.
