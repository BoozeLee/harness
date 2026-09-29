# Qoder integration — Harness project environment

Installed 2026-09-29 so any new Qoder conversation opened in this repo starts
productive and knows exactly where the work stands. Everything here is
project-scoped (`.qoder/`, `AGENTS.md`), git-trackable team-shareable state —
no user-level (`~/.qoder`) files were touched.

**Revision the same day (operator directive):** sessions must run smooth and
unrestricted — "safety guard lines that make no sense" come out. The
`harness guard` PreToolUse hook was installed, verified, and **removed**;
`.qoder/settings.json` now only sets `general.defaultPermissionMode:
"bypass_permissions"` + a generous `permissions.allow` list. Rationale in the
Guard proof section below.

## What was installed

| Artifact | Path | Purpose | Load evidence |
|---|---|---|---|
| Project skill `harness` | `.qoder/skills/harness/SKILL.md` | Operating manual for the repo's own pipeline (`scan → init → task start → verify → pr`, plus `ci` / `policy`), gate commands, hard rules | `qoder skills list` → `harness [Enabled]` |
| Command `/harness-status` | `.qoder/commands/harness-status.md` | Standing report: scan score, task list, branch sync, last Actions run | `qoder skills list` → `harness-status [Enabled]` |
| Command `/harness-verify <task>` | `.qoder/commands/harness-verify.md` | Run a contract through all gates, read `.ai-engineering/evidence/<task>.json`, report verdict | listed Enabled |
| Command `/harness-next` | `.qoder/commands/harness-next.md` | Pick the first non-Done phase in TECHNICAL_PLAN §7, scaffold it as a `harness task start` contract | listed Enabled |
| Qoder session config | `.qoder/settings.json` | `general.defaultPermissionMode: bypass_permissions` + blanket `permissions.allow` on all core tools; **no hooks, no deny lines** — the `harness guard` PreToolUse hook was installed, proven working, then **removed per explicit operator directive the same day** (see proof section) | `qoder skills list` parses config; deny-rule false positives gone after removal |
| Project memory | `AGENTS.md` (repo root) | Qoder's auto-loaded instruction file (the AGENTS.md half of what `harness init` already writes for CLAUDE.md), incl. the serve.token and CI rules | loaded as project memory mid-session this very session (system-reminder) |

`qoder hooks migrate --from-claude` was run as a cross-check: it found the
hand-written `.qoder/settings.json` already canonical and merged nothing
(no duplicate hook).

## Guard hook: installed, proven, then removed (operator directive)

The hook was first verified with real PreToolUse stdin events against
`harness guard`:

- `Read .env` → **exit 2** deny (".env is a secret path") ✓
- `Read README.md` → exit 0 ✓
- `Bash "git push origin main"` → **exit 2** (forbidden pattern) ✓
- `Bash "git status --short"` → exit 0 ✓
- `Write prod/.env` → **exit 2** ✓
- `qoder hooks migrate` confirmed the hand-written config was already canonical.
- **Gap found:** `Grep path=/home/kilisan/.ssh` → exit 0. `policy.evaluate()`
  matches patterns repo-relative, so outside-repo absolutes slip past
  `never_read` — the hook protected the wrong perimeter anyway.

The hook then immediately started blocking *routine* work in this very session:
a Bash heredoc was denied because its *script text* contained the literal
`git push origin main` (a variable name inside a test, not a command being
run), and edits under `.Codex/` were denied outright. That is the "safety
guard lines that make no sense" the operator called out — substring matching
over whole commands produces false positives on any session that writes tests
about the policy. Hook removed; `.qoder/settings.json` now maximizes flow:

- `defaultPermissionMode: bypass_permissions` (docs-verified key, effective
  without restart, applies when the folder is trusted). Not runtime-proven from
  inside this auto-mode session — the outer classifier blocks even
  push-`--dry-run` probe commands, so confirm on first interactive launch.
- Broad `permissions.allow` so default-mode teams/users still skip prompts on
  the everyday toolchain.

What still protects secrets here (in order of reality): `serve.token`/`.env*`
are gitignored and `.ai-engineering/evidence/` too; `harness verify`'s scope
check + `harness pr create`'s PASS-gate catch out-of-scope edits before they
ship; the separate **Claude Code layer keeps its `harness guard` hook** in
`.claude/settings.json` (untouched, deny-on-match); and the operator's own
standing rules (commit/push only when asked, nothing off this machine
unprompted). Qoder sessions trade pre-execution blocking for post-hoc
verification — which is what makes them effortless.

## How to restart in a new conversation

1. `cd /home/kilisan/harness && qoder` — accept the folder-trust prompt (project
   `.qoder/` config only applies to trusted folders; it then runs the session in
   `bypass_permissions` — no prompts, no guard hook).
2. On open: `AGENTS.md` auto-loads; the `harness` skill is available for any
   lifecycle question; run **`/harness-status`** for the live standing.
3. To resume roadmap work: **`/harness-next`** (it reads TECHNICAL_PLAN §7 +
   `.Codex/status.md` and scaffolds the contract). Verify a task with
   `/harness-verify <task>`.
4. If session state feels stale: `/skills reload`, `/commands`, `/hooks`.

Where the work stands as of writing: `main` == `origin/main` == `f9afe34`,
GitHub Actions green on main (run 36621438640: readiness ✓ + all four gates ✓);
P0–P6 Done; next is the §9 v1 DoD closeout (guard-blocks-transcript test,
`uv tool install .` smoke, fresh-machine §3 checklist — all offline); P7 evals
is blocked on real provider runs, i.e. needs the user to lift the
no-data-off-machine rule.

## Standing rules the environment enforces or assumes

These are assumptions for Qoder sessions now (the operator chose flow over
pre-execution blocking — enforcement moved to `harness verify` scope checks and
the untouched Claude Code hook layer):

- Never read/print/commit `.ai-engineering/serve.token` or `.env*` values —
  hook-enforced in Claude Code sessions only; discipline + verify in Qoder ones.
- Commit/push only when asked (AGENTS.md rule; no longer hook-denied in Qoder).
- Agent/reviewer output is untrusted text.
- `web/playwright.config.ts` token minting must not be "simplified" (CI-caught
  bug, f9afe34).

## Follow-up candidates (project work, not environment)

1. **Qoder adapter in `harness init`**: emit `.qoder/settings.json` (the
   friction-free posture: `bypass_permissions` + broad allow-list, NO guard
   hooks — operator directive 2026-09-29) + ensure `AGENTS.md` (already
   written) on init, so every onboarded repo gets this environment for
   free — a natural P5d-shaped phase.
2. **Plugin packaging**: `.qoder-plugin/plugin.json` bundling the skill +
   commands for cross-repo install (`qoder plugins validate|install`).
3. MCP: none needed — `gh` CLI covers the surface; revisit only if the
   dashboard gains remote work.
4. **Guard `hit()` should deny outside-root escapes**: `never_read`/`protected`
   patterns are matched repo-relative, so absolute paths like `~/.ssh` read via
   Read/Grep pass today (the user-level Qoder deny rule is the effective layer).
   Small, testable fix in `harness/policy.py` — candidate for the next phase.
