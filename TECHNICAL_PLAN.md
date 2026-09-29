# Harness — Start-to-Finish Technical Plan (frontend → backend, Omarchy/Arch)

Status: v1 plan. All "verified today" facts below were executed on this machine
(Omarchy 4.0.4, Hyprland 0.56.2) on 2026-09-28 against `/home/kilisan/harness/harness.py`.

---

## 0. What Harness is (analysis of the current app)

`harness.py` (322 lines, stdlib-only, Python 3.9+) is a local-first control plane that
turns a Git repo into a governed agentic dev environment. Lifecycle:

```
scan → init → task start → (task run) → verify → pr        (per-repo lifecycle)
                  ↳ ci (workflow) · policy push|pull|status (team standard)
```

| Command | Mechanism | State produced |
|---|---|---|
| `scan` | Heuristic stack/gate detection: package.json scripts, pyproject/requirements (pytest/ruff/mypy), Cargo.toml, go.mod, Makefile; protects `.env*`, `*.pem`, `secrets/**`, migration/infra/workflow dirs; scores agent-readiness /100; `--fail-under N` turns the score into a CI floor (exit 1 below N) | in-memory dict |
| `init` | Writes `.ai-engineering/{project,policy,verification}.json`, generates `CLAUDE.md` + `AGENTS.md` (never clobbers a hand-written AGENTS.md — writes `AGENTS.md.proposed` unless `--force`), merges allow/deny + a `PreToolUse` guard hook into `.claude/settings.json` | Git-tracked JSON |
| `guard` | Claude Code PreToolUse hook: reads event JSON on stdin, matches file paths against `never_read`/`protected` and commands against `never_commands`, NDJSON-audits every event, exits 2 to block | `.ai-engineering/audit.log` |
| `task start` | Creates isolated `git worktree` + branch `harness/<name>`, copies policy into it, builds a **contract**: goal, acceptance criteria, risk level → gate subset (`low` gates only run for `--risk low`), `allowed`/`protected` path patterns, base SHA | `.ai-engineering/tasks/<name>.json` |
| `task run` | Optional: headless agent inside the worktree — `claude -p "<plan+implement+verify prompt>" --permission-mode acceptEdits` or `codex exec --sandbox workspace-write` (`--agent claude|codex`, default claude) | agent edits |
| `verify` | Runs each gate command, computes changed-file scope from `git diff` + `git status --porcelain`, runs an independent `claude -p` reviewer against the diff (PASS/FAIL verdict), writes evidence | `.ai-engineering/evidence/<name>.json` + `.html` |
| `pr` | Subcommands: `create` (refuses unless evidence verdict is PASS; commits excluding harness meta-files, pushes branch, `gh pr create` with gate checklist as body), `view` (maps task → `harness/<name>` branch → PR number via `gh pr list --head`, then `gh pr view`), `status`/`list` (gh passthroughs) | GitHub PR |
| `policy push\|pull\|status` | Team bundle: `.ai-engineering/{policy,verification}.json` mirrored into a Git repo (path or URL, `--branch`). push commits+pushes only when content changed; pull overwrites local copies byte-exactly from the bundle; status exits 1 on drift (CI hook). Everything else stays local — `project.json` holds machine paths, tasks/evidence/audit are per-repo history | bundle-repo commit |
| `ci` | Writes `.github/workflows/harness.yml`: a `readiness` job (`harness scan --fail-under N`) and a `gates` job running this repo's own `verification.json` commands, with dep setup inferred from lockfiles (uv/npm/pnpm/yarn, root and depth-1 app dirs) plus `--setup`/`--install` for what inference cannot know. Re-running updates in place via the marker line; a hand-written workflow is only touched with `--force` | GitHub Actions workflow |

Design properties worth preserving as invariants:
- **Plain files in Git** as the only source of truth (inspectable via `git diff`, no lock-in).
- **Deny-by-default policy** enforced at the hook layer, independent of the agent's own permission system.
- **Completion contract**: done = all risk-appropriate gates pass + changes in scope + reviewer PASS; skipped review ≠ passed.
- **Evidence-first**: every verdict ships a human-readable HTML report.

## 0.1 Bugs and gaps found by running it (today)

1. **Fixed**: `sh()` used `.strip()` on combined stdout+stderr. `git status --porcelain`
   lines are significant at column 0 (` M path`), so the first line lost its leading
   space and `ln[3:]` truncated one path character (`src/calc.py` → `rc/calc.py`),
   producing false scope violations. Changed to `.rstrip("\r\n")` (harness.py:20-22).
2. **No `task update`**: the contract key is `allowed` (set once at `task start`);
   widening scope requires hand-editing JSON with knowledge of the internal key name.
3. **Untracked-noise in scope**: `__pycache__/` dirs count as "changed files" when no
   `.gitignore` entry exists; evidence `files` list gets polluted.
4. **`MultiEdit` in the WRITE set / hook matcher is dead**: Claude Code 2.1.283 merged
   MultiEdit into Edit (verified against hooks docs + installed binary). Harmless, remove.
5. **Guard blocks but can't explain richly**: exit-2 + stderr works, but the newer
   `hookSpecificOutput.permissionDecision` JSON on stdout gives `deny`/`ask`/`allow`
   with a structured reason surfaced to the model.
6. **No `--max-turns`**: documented but absent from `claude` 2.1.283 `--help`; do not
   build budget control on it. Use `--max-budget-usd` and `--allowedTools` instead.
7. **Never use `--bare`** with `task run`: it skips hooks, which would silently disable
   the guard.

## 1. Verified toolchain on this machine (all present, no further installs needed)

| Tool | Version | Role / note |
|---|---|---|
| python | 3.14.5 | harness runtime (claims 3.9+ compat; tests pin it) |
| git | 2.55.0 | worktrees, diff, scope |
| gh | 2.101.0 | `pr` step; already authed (HTTPS, scopes repo/workflow) |
| claude | 2.1.283 | guard-hook host + headless worker/reviewer; verified with `claude -p "reply with exactly: OK"` → OK |
| node/npm/bun | 26.9.0 / 11.19.1 / 1.3.14 | node gate detection + dashboard build |
| uv | 0.11.14 | venv/package management for the backend |
| cargo / go | 1.96.0 / 1.26.3 | rust/go stack gates |
| ruff / pytest | 0.15.13 / 9.0.3 | python gates |
| mypy | 2.1.0 | installed today via `omarchy pkg add mypy` — note: Arch package renamed from `python-mypy`; bare `mypy` is correct |
| playwright | 1.63.0 | chromium + headless shell already in `~/.cache/ms-playwright`; python API imports OK |
| hyprland | 0.56.2 | desktop; irrelevant to the CLI, relevant for *headed* browser verification (§7 P4) |

### Omarchy/Arch conventions used (from the omarchy skill, applied)
- Install with `omarchy pkg add <pkg>` (idempotent, `--needed`), AUR only via
  `omarchy pkg aur add` — not needed for any dependency in this plan.
- Never touch `/usr/share/omarchy/` (owned by the package, clobbered on `omarchy update`).
- `claude` here is a mise shim (`~/.local/bin/claude` →
  `~/.local/share/mise/installs/claude/2.1.283/claude`); the Omarchy repo also ships
  `omarchy/claude-code 2.1.283-1`. Keep mise (pinnable) or switch to the package — do
  not mix.
- Long-running dashboard = a **systemd user service** (not an Omarchy hook); Omarchy
  hooks (`omarchy hook install`) are only appropriate for desktop-event automations.

### Reproduce this setup on a fresh Omarchy box
```bash
omarchy pkg add git python uv nodejs npm go rust mypy ruff python-pytest python-playwright
# gh: extra/gh ; claude: mise install claude  OR  omarchy pkg add claude-code
npx playwright install chromium   # or rely on pip playwright + `playwright install`
gh auth login
```

### Smoke test executed (proof of the above)
Scratch repo `/tmp/harness-smoke` (git+pyproject: pytest/ruff/mypy):
`scan` → readiness 60/100, 3 gates detected; `init` → wrote 3 JSONs + CLAUDE.md +
settings.json; `guard` fed synthetic PreToolUse events: Edit `.env` blocked (rc 2),
`git push --force` blocked, Bash `cat .env` blocked, Edit `src/calc.py` allowed,
all 4 events audited; `task start sub --risk low --allow "src/**"` → worktree
`/tmp/.harness-worktrees/harness-smoke-sub`, 3 gates filtered correctly; edited worktree,
`verify sub` → unit ✓ lint ✓ typecheck ✓ scope (caught out-of-scope `tests/` before
widening `allowed`) ✓ → **verdict PASS**, evidence JSON+HTML rendered, rc=0.
`task run` and `pr` were not executed (live agent budget / needs a GitHub remote) —
their primitives (`claude -p`, `gh`) were verified individually.

---

## 2. Product target for "building the app"

V1 = the CLI core hardened into a real package **plus a local web dashboard** (read +
act, never a second source of truth), per README roadmap. Order of value:

1. P0 harden CLI (fix bugs found above) — CLI stays fully usable standalone.
2. P1–P3 server + runner + dashboard.
3. P4 browser-verification gate, P5 projects API (§7 revision), P5b gh pr adapter,
   P5c agent adapters (Codex/Copilot), P6 team policy sync,
   P7 evals (raw vs harnessed).

Non-goals for v1: hosted/multi-tenant product (README: review agent SDK commercial
terms first), auth beyond a local token, non-git VCS.

## 3. Architecture (end to end)

```
┌─────────────────────────────────────────────────────────────────┐
│ Presentation   React dashboard (Vite, TS strict) · CLI · TUI    │
│                evidence HTML (sandboxed iframe → native views)  │
├─────────────────────────────────────────────────────────────────┤
│ API            FastAPI on 127.0.0.1:8766 · bearer token · SSE   │
├─────────────────────────────────────────────────────────────────┤
│ Domain core    harness/engine: scan · contract · policy eval ·  │
│  (pure py)     gate runner · scope · reviewer · evidence · pr   │
├─────────────────────────────────────────────────────────────────┤
│ Runner         asyncio subprocess supervisor · per-worktree     │
│                serial lock · global agent concurrency cap ·     │
│                cancel via process-group kill · run history      │
├─────────────────────────────────────────────────────────────────┤
│ Adapters       git/gh · Claude Code (hooks/-p) · Codex ·        │
│                Copilot · Playwright                             │
├─────────────────────────────────────────────────────────────────┤
│ State          .ai-engineering/*.json (authoritative, in Git)   │
│                audit.log NDJSON · evidence/ · git worktrees     │
│                SQLite = rebuildable index/queue ONLY            │
└─────────────────────────────────────────────────────────────────┘
```

The rule that keeps this boring and safe: **only the domain core mutates files;
the API/UI/runner are shells over the core; the guard hook works even when no
server is running.** Uninstalling the dashboard must not strand a repo.

## 4. Backend plan (start → finish)

### 4.1 Packaging (P0)
- Restructure single file → package:
  `harness/{__init__,cli,scan,policy,guard,contract,verify,evidence,gitops,shutilx}.py`
  with `pyproject.toml` (requires-python ≥3.10, zero runtime deps for the core;
  `harness[server]` extra pulls FastAPI/uvicorn).
- Install editable with uv: `uv tool install --editable .` → `harness` on PATH
  (replaces `python3 harness.py`).
- Add `schema_version` to every JSON the tool writes; loader errors clearly on
  unknown-major versions (files are Git-tracked, forward migration must be explicit).
- Fix §0.1 items 2–5: `harness task update <name> --allow … --risk …`, `-z`-based
  porcelain parsing, ignore-list filtering, drop MultiEdit, guard JSON-deny.

### 4.2 API server (P1)
FastAPI app, uvicorn, **bind 127.0.0.1 only**, token file `.ai-engineering/serve.token`
(0600), all endpoints under `/api`. OpenAPI auto-served → frontend types generated.
Port 8766 (8765 is occupied on this machine by an unrelated local service — verified
2026-09-28; the port must be configurable anyway).

| Endpoint | Core call | Notes |
|---|---|---|
| `GET /api/scan` | `scan(repo)` | cached until repo HEAD moves |
| `POST /api/init` | `cmd_init` | returns created files, refuses if dirty unless `force` |
| `GET /api/policy` / `PUT /api/policy` | load/validate policy.json | PUT rewrites `.claude/settings.json` too; diff preview before apply |
| `GET /api/tasks` | list contracts+verdicts | joined view |
| `POST /api/tasks` | `cmd_start` | body: name/goal/accept/allow/risk |
| `PATCH /api/tasks/{n}` | contract update | the missing `task update` |
| `POST /api/tasks/{n}/run` | enqueue `claude -p` | 202 + run id; guarded by adapter capability check |
| `POST /api/tasks/{n}/verify` | enqueue gates+scope+review | 202 + SSE stream |
| `POST /api/tasks/{n}/pr` | `cmd_pr` | server-side re-check: verdict==PASS |
| `GET /api/evidence/{n}` | JSON | |
| `GET /api/evidence/{n}/html` | raw HTML | `Content-Security-Policy: sandbox`, served from files only, no path traversal (resolve under evidence dir) |
| `GET /api/audit?follow=&blocked=` | tail NDJSON | secret values never rendered; targets are shown as recorded (already redacted-ish) |
| `GET /api/runs` + `/api/runs/{id}/events` | SQLite index / SSE | stream of stdout chunks, gate results, status |
| `POST /api/runs/{id}/cancel` | process-group SIGKILL | |
| `GET /api/health` | adapter probe | `which claude/gh/node/playwright`, versions |

### 4.3 Runner (P2)
- `asyncio.create_subprocess_exec` per run, `start_new_session=True` (own PGID) so
  cancel kills the whole tree (claude spawns nested shells).
- Concurrency: semaphore — gates within one verify run sequentially (today's behavior),
  one run at a time per worktree (git index.lock), global `max_parallel_agents`
  (default 2; API rate limits, not CPU, are the constraint — verified: no documented
  local cap, hooks run in parallel, each tool call blocks on guard ≤600 s default).
- Every run persists: start/end, argv (with secrets scrubbed), exit code, output chunks
  (ring buffer + spool file), gate results. SQLite `runs`/`events` tables; rebuildable.

### 4.4 Agent adapters (P5) — contract verified against Claude Code 2.1.283 + docs
- `AgentAdapter` interface: `probe()`, `install_hooks(repo, policy)`,
  `headless(prompt, cwd, budget, allowed_tools)`, `review(diff, goal) -> Verdict`.
- Claude Code specifics the adapter must honor:
  - PreToolUse stdin fields `session_id, transcript_path, cwd, hook_event_name,
    tool_name, tool_input` (assumed exactly right — confirmed).
  - Exit 2 = block, stderr → model; JSON stdout `hookSpecificOutput.
    {hookEventName:"PreToolUse", permissionDecision:"deny"|"ask"|"allow",
    permissionDecisionReason}` preferred for `ask`; other nonzero = non-blocking error.
  - Matcher = case-sensitive regex/alternation over tool names; unknown names silently
    ignored (MultiEdit → remove).
  - `--permission-mode acceptEdits` valid (2.1.283 also has
    `auto|manual|dontAsk|bypassPermissions|plan|default`); `--output-format
    stream-json` for run streaming; `--allowedTools/--disallowedTools`,
    `--max-budget-usd` for cost control; `--session-id` for resumable audit joins.
  - `.claude/settings.json` supports hooks + `permissions.allow/deny` with
    `Bash(glob)` / gitignore-style `Read(./.env)` / `Edit(/src/**/*.ts)`; precedence
    managed > CLI args > local > project > user — init must warn if a user-level
    setting would override the project guard hook.
- Codex / Copilot adapters: same probe/install/headless surface with vendor-native
  hook equivalents (AGENTS.md conventions); until then README lists them as unbuilt.

## 5. Frontend plan

### Stack
Vite + React 19 + TypeScript strict, TanStack Query (server state only — client state
stays minimal), Tailwind. No Redux, no SSR. Build artifacts served by FastAPI's static
mount in dev via Vite proxy; prod = `harness dashboard` builds once into the package.

### Views (mapped to API)
1. **Readiness** — score/100 dial, detected gates table, protected paths, gaps
   ("No test command detected…"), `Init` action with file-diff preview.
2. **Task board** — cards per contract: risk chip, goal, acceptance list, gates subset,
   branch/worktree, latest verdict badge; New-task drawer (name/goal/accept[]/allow[]/risk).
3. **Run view** — live SSE: gate-by-gate ✓/✗ with expandable tail output, agent
   `stream-json` transcript (rendered as text, never HTML), cancel button, duration.
4. **Evidence report** — native React version of today's HTML (PASS/FAIL header,
   results, files, stat, review tail); keep iframe fallback while native matures.
5. **Policy editor** — editable protected/never_read/never_commands/ask lists,
   generated `.claude/settings.json` preview, apply = PUT (server re-runs the guard
   self-test before saving).
6. **Audit** — filterable (blocked-first), follow-live tail, JSON drilldown per event.
7. **Health** — adapter/tool probe table (§4.1 commands above; red = fix via
   `omarchy pkg add …`).

Design constraints: dark/light via `prefers-color-scheme` (matches existing evidence
HTML), keyboard-first (Hyprland users), every mutating action shows a confirm step
with the exact core call it maps to.

## 6. Security model
- Server loopback-only + bearer token; no CORS beyond the dashboard origin;
  token never in URLs.
- Guard remains the enforcement layer: UI compromise ≠ policy bypass (hook runs
  inside Claude, not via the API).
- Secret hygiene: API never returns `.env` contents; audit records targets only;
  run argv scrubbed via allowlist regex; `never_read` patterns mirrored server-side
  for any future file-browsing view.
- Reviewer/agent output is untrusted text (prompt-injection surface): rendered as
  plain text, CSP-sandboxed for legacy HTML evidence; never executed, never fed back
  into policy decisions.
- Path traversal: every file-serving endpoint resolves under a fixed root and
  rejects symlink escape (`Path.resolve()` prefix check).
- `never_commands` substring matching is bypassable (obfuscation, env tricks) —
  documented limitation; defense-in-depth = deny-by-default Claude permissions +
  worktree isolation + PR gate.

## 7. Roadmap — phases with acceptance criteria

P0 — **CLI hardening** (1–2 d) — exit today's failures from the tool itself:
  packaging (§4.1), strip-bug regression test, `task update/list`, `-z` parsing,
  guard JSON-deny, schema_version, pytest suite for `hit/scan/render/shell-quoting`,
  smoke = the §1 transcript re-run automatically in CI (a repo *inside* the harness:
  pyproject with pytest+ruff+mypy → all gates). **Done (2026-09-28).**

P1 — **API server** (2–3 d): endpoints read-only subset + health probe; OpenAPI;
  acceptance: `curl` drives scan→start→verify headlessly without the CLI.
  **Done (2026-09-28):** `harness serve` on 127.0.0.1:8766, bearer token, task create +
  verify endpoints, evidence JSON/HTML, audit; dashboard wired live (readiness 70/100,
  deny event visible in Audit); 26 tests green via `uv run pytest`.

P2 — **Runner + streaming** (3–4 d): SSE, cancel, queue, SQLite index;
  acceptance: kill a `task run` mid-flight, worktree stays clean, run row terminal.
  **Done (2026-09-29):** `harness/runner.py` — dedicated event-loop thread, global
  `--max-parallel` semaphore + per-worktree lock, PGID kill on cancel, line-streamed
  output into rebuildable `runs/events` SQLite journal; SSE `/api/runs/{id}/events`
  (loopback-public, ends on terminal status event); Run/Runs dashboard views with
  live gate chips; Playwright UAT: queued→running→succeeded PASS streamed;
  28 tests green (incl. cancel-orphan and SSE-completeness).

P3 — **Dashboard** (3–5 d): views 1–6; Playwright e2e suite *as the repo's own gate*;
  acceptance: a non-terminal user completes full lifecycle in browser incl. one
  guard-blocked action surfaced in Audit.
  **Kickoff (2026-09-29):** app-building tool researched and chosen: **shadcn/ui**
  (Radix base, nova preset) — best fit because it is copy-in components (matches the
  plain-files/git-diff ethos, no runtime lock-in), first-class Vite + Tailwind v4 +
  React 19 support, and 2026 consensus for React dashboards. Installed: `components.json`,
  14 primitives under `src/components/ui/`, Geist theme CSS, `@/*` alias.
  Remaining P3 steps: (1) port the 6 views to shadcn primitives, (2) working
  New-task dialog form (create → contract), (3) sonner toasts for run lifecycle,
  (4) `tests/e2e/` Playwright specs wired as a `playwright` gate in
  verification.json so the harness verifies its own dashboard.
  **Done (2026-09-29):** all 6 views on shadcn primitives (testids preserved), working
  New-task dialog, sonner toasts for run lifecycle + verify, `playwright` gate registered
  (dashboard.spec only, min_risk medium, to avoid nested verify-spawning recursion);
  worktree runs sync the serve token via `git rev-parse --git-common-dir`.

P4 — **Browser verification gate** (2–3 d): new gate type `e2e` = Playwright spec run
  against the worktree app; screenshots archived under evidence/ with hash links.
  Omarchy note: headless-shell works under Hyprland unchanged; *headed* runs need
  Wayland (`--ozone-platform-hint=auto`) — document, default headless.
  **Done (2026-09-29):** gates take optional `"type": "e2e"` (CLI `verify.py` and async
  `runner.py` both inject `HARNESS_GATE_E2E=1` via the subprocess env param — never a
  cmd-string prefix, so exact-cmd guard matching stays intact). `evidence.archive_shots`
  prunes `evidence/<task>/` per run, archives only images (never trace.zip) from
  `test-results/` for e2e gates, sha256-names them `<sha12>-<slug>.png`, caps 5 MiB/file
  and 25/gate; evidence JSON gains additive `shots` (schema stays 1, key absent when
  empty). Server serves shots at `/api/evidence/{name}/shots/{fname}` — public like SSE
  (browser `<img>` cannot send bearer; loopback-only posture) with strict filename regex +
  parent-dir check; the html route rewrites relative hrefs to that path under CSP sandbox.
  Playwright specs write passing-test screenshots explicitly (`screenshot:"on"` is
  in-memory-attachment-only, writes no files); headed mode gated behind `HARNESS_HEADED`
  with `--ozone-platform-hint=auto`. `harness init` auto-tags scan-detected e2e gates.
  Dogfood: p4smoke verify archived 8 shots, all hashes verified, curl checks green
  (shot 200 no-auth, traversal rejected, missing 404, html hrefs rewritten).

P5 — **Projects API** — **revised (2026-09-29):** per user directive this phase became the
  `GET /api/v1/projects` endpoint + Projects listing view; the adapter layer (the former
  P5) moves to P5b.
  **Done (2026-09-29):** first `/api/v1/`-versioned route — list envelope of projects bound
  to the server (today exactly one: the repo `create_app` received), composed live from
  `scan(repo)` + `_task_rows()` verdict counts (helper extracted from `/api/tasks`, now
  shared). Entry: `{name, root, initialized, stacks, gates, protected, ci, readiness,
  tasks:{total,pass,fail,unverified}}`; bearer-protected by the existing middleware.
  Frontend: Projects view (`/projects`, first sidebar entry) with `project-row/-name/
  -readiness` testids; e2e VIEWS table picks it up automatically (11/11 green). Existing
  `/api/*` paths untouched — no big-bang versioning.

P5b — **`harness pr` gh adapter** — **revised (2026-09-29):** per user directive P5b became
  the gh-backed project-operations adapter; the Codex adapter layer moves to P5c.
  **Done (2026-09-29):** `pr` is a subcommand group (`create|view|status|list`,
  harness/pr.py + cli.py). `create` keeps the PASS-evidence gate and now surfaces gh
  failures instead of swallowing them (`die("gh pr create failed:…")`). `view` maps
  task → `harness/<name>` → PR number via `gh pr list --head … --json number` then
  `gh pr view`; absent PR dies with a create hint. `status`/`list` are exit-code-
  propagating passthroughs. All gh calls are argv arrays through `sh()` (never shell
  strings); read-only ops run at repo root, create keeps worktree cwd. Tested fully
  offline: fake-`gh` PATH shim (argv log + canned outputs) + local bare origin —
  create pushes `harness/t` and the `pr create --title/--head` contract is asserted from
  the log (tests/test_pr.py, 5 tests; suite now 43 green, ruff+mypy clean). Breaking
  `harness pr <name>` → `harness pr create <name>` accepted (no external users, no
  back-compat shim per AGENTS.md). Live read-only check: real `harness pr status` against
  the authed remote works.

P5c — **Adapter layer** (1 wk): Codex CLI adapter + settings generators; acceptance:
  same task lifecycle through two different agents on the same repo.
  **Done (2026-09-29):** `harness/agents.py` holds the adapters — one shared contract
  prompt (`agent_prompt`) + per-agent argv (`build_argv`): claude
  `-p … --permission-mode acceptEdits`, codex `exec --sandbox workspace-write`
  (flags verified against installed codex-cli 0.158.0 `--help`; approval-on-request
  would stall a headless run). `task run --agent claude|codex` (default claude) via
  cmd_run; runner.agent_argv carries the agent into dashboard runs; the server takes
  an `AgentRun` body (422 unknown agent, 409 missing CLI) and `TOOLS` probes codex.
  Settings generator: `init` writes `AGENTS.md` for Codex (which has no hook surface)
  and never clobbers a hand-written one — `AGENTS.md.proposed` unless `--force`;
  `cmd_start` copies it into the worktree, `META_PREFIX` keeps it out of scope,
  `pr create` excludes it from the commit. Enforcement asymmetry is accepted:
  Claude gets the PreToolUse guard hook, Codex relies on AGENTS.md + its sandbox +
  verify's after-the-fact scope gate. Acceptance proved fully offline with fake
  claude/codex binaries on PATH (argv logged to $AGENT_LOG, each performs a typed
  in-scope edit): init→task start→task run→verify→PASS through **both** agents on
  the same repo (tests/test_agents.py, 6 tests; suite 49 green, ruff+mypy clean,
  e2e 11/11 unchanged). No real provider invocations (auto-mode: no data off the
  machine). Fix shipped alongside: cmd_run now prints nonempty agent output
  (previously swallowed).

P6 — **Team policy sync** (1 wk): policy bundles as Git repo + `harness policy push/pull`,
  CI `harness scan --fail-under <n>` and `harness verify` in GitHub Actions.
  **Done (2026-09-29):** `harness policy push|pull|status <remote> [--branch]`
  (harness/bundle.py) syncs the two shared files — `policy.json` + `verification.json` —
  through a Git repo (bare path or URL) cloned into a temp dir per call; push commits only
  on content change ("unchanged", no empty commits), pull overwrites byte-exactly, status
  exits 1 on drift so CI can enforce the team standard. `project.json`, tasks, evidence and
  audit.log are deliberately excluded (machine paths / per-repo history).
  `harness scan --fail-under N` turns the readiness score into a floor (exit 1 below N,
  still emits `--json`). `harness ci [--fail-under N] [--setup CMD] [--install CMD] [--force]`
  (harness/ci.py) writes `.github/workflows/harness.yml`: `readiness` job (install harness →
  `harness scan --fail-under`) and `gates` job running **the repo's own gate commands**, so
  CI and `harness verify` cannot drift. Deliberate deviation from the wording "…and
  `harness verify` in Actions": verify is contract- and worktree-bound (needs
  `.ai-engineering/tasks/<name>.json` + a base SHA) and a PR checkout has neither, so CI
  executes the gate set itself instead of faking a contract. Dep setup is inferred from
  lockfiles at the root and in depth-1 app dirs (uv → `pip install uv && uv sync --frozen`
  because runners lack uv; npm/pnpm/yarn per dir, node_modules skipped), `--setup` covers
  what inference can't know (Playwright browsers), `--install` covers private harness repos
  (default: `pip install .` when the repo houses harness, else `pip install
  git+${{ secrets.HARNESS_REPO }}` — the package is **not** on PyPI). Regeneration is
  marker-based; a hand-written workflow is only replaced with `--force`.
  Acceptance: tests/test_bundle.py 8 + tests/test_ci.py 12 + 2 floor tests in
  tests/test_scan.py, all offline against local bare repos; the emitted YAML is parsed with
  pyyaml (dev dep) and its steps asserted equal to `verification.json`. Dogfooded live:
  `harness ci` put this repo's workflow in place (readiness 70 → 80, floor 70 passes / 95
  fails), and push→status→re-push→drift→pull round-tripped against a local bundle repo,
  pull restoring exact bytes. Suite 71 green, ruff+mypy clean, e2e 11/11 unchanged.
  Not automated (deliberately): the generated workflow has no policy-drift job, because the
  bundle URL is team infrastructure harness does not store locally — a team that wants it adds
  one `- run: "harness policy status <bundle-url>"` step to the readiness job.
  The first real run of that workflow on GitHub (f3a176d) was the phase's best evidence: unit,
  lint and typecheck passed on the runner, and `gate playwright` failed one spec — the Runs
  view — because `.ai-engineering/serve.token` is gitignored, so on a clean checkout vite baked
  an empty token while `harness serve` minted its own: every authed /api call 401'd. The seven
  heading-only specs passed regardless (they assert h1 + no JS errors); the single
  data-dependent spec (empty-or-rows) was the one that could see it. Fixed in
  `web/playwright.config.ts`: `syncToken()` now mints the file (0600) when neither the local
  nor the main checkout has one, before either server starts, since serve reuses an existing
  token and vite reads it at config load. Reproduced and verified offline by moving the real
  token aside: 10/10 dashboard specs green with a minted token.

P7 — **Evals** (2 wk): N identical tasks run raw vs harnessed across ≥2 stacks;
  metrics: first-pass gate rate, scope violations, reviewer FAIL reasons, cost/task,
  wall-clock. Report generator ships as static HTML from the evidence schema.

Deferred (per README): hosted product / Review Agent SDK commercial terms.

## 8. Risks
| Risk | Mitigation |
|---|---|
| Claude Code contract drift (flags change: `--max-turns` already absent, MultiEdit gone) | adapter pins capability probe per version; CI runs against a pinned `claude-code` (mise-pinnable) |
| Guard blocks legit flows → users disable it | audit-first UX: every block shows the rule + one-click *propose contract amendment* (never silent allow) |
| `subprocess shell=True` on gate commands = injection surface if policy.json edited maliciously | gates run only from repo-tracked policy after `git diff` review; P2 adds argv-form gate specs (`cmd_list`) with string cmd deprecated |
| Parallel agents hit API rate limits mid-verify | global `max_parallel_agents`, run retry with backoff, streaming makes waiting visible |
| Evidence HTML becomes XSS sink | CSP sandbox now, native React renderer in P3 removes it |
| Worktree sprawl (`/tmp/.harness-worktrees`) | `harness task done/cleanup` lifecycle command + stale-run GC |

## 9. Definition of done for v1
Repo dogfoods harness: all gates pass, Playwright suite covers the dashboard,
`.github/workflows/harness.yml` (generated by `harness ci`) runs the readiness floor and the
same gate commands on every push/PR,
guard blocks reproduce the §1 transcript, `harness --help` works after
`uv tool install .`, and a fresh Omarchy machine is bootstrapped by the §3 command
block alone.
