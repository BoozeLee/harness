# Changelog

## v1.1.0 — 2026-09-30

Post-v1 integration wave, both features shipped through harness's own
contract-gated lifecycle with role-assigned agent prompts (Underboss plans,
Soldier executes, `harness verify` + CI adjudicate):

- **ELOHIM gate** (`6062579`, merge `d7ba636`): the ELOHIM measurement
  instrument (vendored under `vendor/elohim/`, byte-identical to the skill
  tree, instrument sha256 matches the ledger pin) becomes a verification gate
  whose contract is "read the exit code, not the prose": pin checksum, 16
  re-measured ledger facts, six numeric traps, residuals on every claim.
  Runs locally and in GitHub Actions identically (`gate elohim` green on
  runners since `d7ba636`). Vendored code is excluded from ruff. Caught and
  fixed during review: `harness ci` regeneration had silently dropped the
  CI playwright-setup step — restored, workflow diff confirmed minimal.
- **Declarative agent registry** (`68298e4`, merge `6e7ae23`): `harness/agents.py`
  now holds frozen `AgentSpec` records (binary, headless argv builder,
  enforcement tier, description) in an immutable `AGENT_SPECS` mapping,
  modeled on LINCE's agent-registration contract. `AGENTS`, `build_argv`,
  the unknown-agent error and the server `TOOLS` probe all derive from the
  registry; claude/codex argv unchanged byte for byte. New validation verb
  `harness agents [--json]` reports presence, version and enforcement tier
  per registered agent — the "adding an agent" procedure is documented in
  TECHNICAL_PLAN §"Adding an agent".
- **Release tooling**: `scripts/install.sh` — one-command stranger install from
  the GitHub release wheel (`uv tool install`, venv fallback); wheel + sdist
  attached to releases; `scripts/smoke.sh` green at every release.
- Tests: suite 6 → 9 in `tests/test_agents.py` (registry-pinned argv,
  PATH-shim presence probes, offline). First task ever verified through the
  ELOHIM gate itself: `lince-registry`.

## v1.0.0 — 2026-09-30

First stable release. Everything from the baseline (`cc27ff1`) to here:

- **P0 — CLI core + packaging** (`638df1b`, `fc9a0fb`): `harness scan/init/task/verify`
  over stdlib-only Python; versioned JSON state in `.ai-engineering/`; contract-gated
  scope checks; guard hook JSON channels; `harness-agent` wheel with console script;
  draft Vite+React+TS dashboard.
- **P1 — local server** (`b7348ea`): FastAPI on 127.0.0.1:8766 with bearer token,
  health/scan/policy/verification/tasks/evidence/audit endpoints, dashboard wired to
  the live API.
- **P2 — async runner** (`ede27e1`, `384ba62`): background agent runs with SSE
  streaming, cancel-by-PGID, sqlite journal, live Runs view, diff review (4 bugs
  fixed pre-commit).
- **P3 — real UI** (`aa60579`, `00eb7b9`, `e470ba9`): shadcn/ui across all six
  dashboard views, working New-task dialog, Playwright e2e suite as a self-verifying
  gate (`min_risk medium`), sonner run-lifecycle toasts.
- **P4 — evidence** (`bb10b50`): `e2e` gate type with hashed screenshot evidence,
  public loopback shots route, CSP-sandboxed HTML reports.
- **P5 — GitHub integration** (`d0b302b`, `e2fd50d`, `7511420`): `/api/v1/projects`;
  `harness pr create|view|status|list` wrapping `gh` behind the evidence gate; agent
  adapters driving claude (`-p --permission-mode acceptEdits`) and codex
  (`exec --sandbox workspace-write`) through the same lifecycle.
- **P6 — team layer + CI** (`f3a176d`, `f9afe34`): `harness policy push|pull|status`
  bundle sync through a Git remote, `scan --fail-under N` readiness floor,
  `harness ci` generating `.github/workflows/harness.yml` that runs the repo's own
  gates; clean-checkout serve-token mint so e2e auth works in CI.
- **DoD closeout** (`3aa83f9`, `1593ff9`): §1 guard-block transcript tests (including
  the outside-repo `hit()` anchor fix), automated install smoke (`scripts/smoke.sh`
  = the §3 fresh-machine checklist, green from clean clones), wheel/entry-point and
  README-drift tests.
- **P7 — evals** (`24555b2`, `0f5c1da`): `harness eval list|run|report` — 6-task
  python+TS corpus with hidden ground-truth suites, raw-vs-harnessed runner with
  offline `--dry` honesty proof, live codex matrix (13 runs, 11/13 graded PASS;
  numbers in README). Independent-review verdicts recorded per run, quota failures
  never skipped silently.

Known caveats shipped with: claude half of the live matrix pending a provider
session-limit window; `eval run` fake agent is POSIX-only (repo targets Linux/CI).
