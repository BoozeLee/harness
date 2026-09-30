# Harness Roadmap — from here to done

Checklist ledger of every remaining step to v1.0 and beyond. Source of truth
for "what's next": the first unchecked box in the earliest open phase. Ground:
TECHNICAL_PLAN.md §7 (phase acceptance criteria) and §9 (v1 DoD) — this file
turns those into tickable items; don't check a box without its proof.

Legend: `[x]` done & verified · `[ ]` open · `→` blocked on a user decision

## P0–P6 — foundation (DONE)

- [x] P0 CLI hardening + packaging + web scaffold
- [x] P1 FastAPI serve + frontend wired (bearer token posture)
- [x] P2 async runner + SSE streaming + diff review
- [x] P3 dashboard (6 views, shadcn) + playwright gate
- [x] P4 e2e gate + evidence shots
- [x] P5 projects API · P5b `harness pr` gh-adapter · P5c claude+codex adapters
- [x] P6 policy bundle push/pull/status + `scan --fail-under` + `harness ci`
      (generated workflow, green on real runner: run 36621438640)
- [x] Qoder integration: project skill, 3 commands, AGENTS.md, bypass_permissions
      session posture (`a2bc2e4`; see QODER_INTEGRATION.md)

## v1 DoD closeout (TECHNICAL_PLAN §9) — W1, all offline (~6-8h)

- [x] **Push integration commit** — `a2bc2e4` pushed; Actions run 36633480413
      success: https://github.com/BoozeLee/harness/actions/runs/36633480413
- [x] **Guard transcript test** — pytest reproducing the §1 story end to end:
      a fake agent session whose `Read .env` / forbidden `Bash` events go
      through `cmd_guard` stdin and get exit-2 + audit.log lines. §8 risk row
      "Guard blocks legit flows → users disable it" gets its counterweight test
      too: an in-scope edit passes untouched. Proof: new tests green, suite ≥73.
      → landed on branch `harness/dod-closeout` (tests/test_guard_transcript.py
      + `hit()` outside-repo fix; merged 3aa83f9, Actions to confirm).
- [x] **Install smoke** — clean install of the package in a throwaway venv
      (`uv venv && uv pip install <repo>`; `uv tool install` has no `--tool-dir`
      in 0.11.x) → `harness --help` + `harness scan` on a scratch repo.
      Automated as scripts/smoke.sh + tests/test_build.py (wheel entry point).
      Proof: `bash scripts/smoke.sh` → "smoke ok" from a fresh clone (2026-09-29);
      merged 3aa83f9. Reviewer gate: documented exception (Claude quota, see merge commit).
- [x] **Fresh-machine checklist** — run TECHNICAL_PLAN §3 command block verbatim
      on a clean clone in /tmp; fix every step that needed unstated knowledge
      (the serve.token mint was exactly this class of bug). Proof: scripts/smoke.sh
      IS the block, ran green end to end from /tmp/harness-checklist-clone
      (scan→init→ci→policy push/status→task→verify PASS→serve --help);
      unstated knowledge found & fixed: readiness floors are repo-dependent
      (bare python repo scores 30→40, not ≥60). Merged 3aa83f9.
- [x] **ROADMAP honesty pass** — this section Done (merge 3aa83f9 + tick commit);
      readiness floor held: `harness scan --fail-under 70` exits 0 on main.

## P7 — Evals: raw vs harnessed (W2–W3)

→ **Unblocked: operator lifted the off-machine rule 2026-09-30** — live provider
runs are authorized for this corpus only (small synthetic utils, no repo data).

- [x] Corpus: 6 small tasks × 2 stacks (python ×3, typescript ×3), same task run
      both ways; hidden `test_graded` suites are the ground truth.
      Proof: `evals/tasks.json` + `evals/fixtures/` + `harness eval list` green.
- [x] Runner: `harness eval run` — raw vs `init→task start→run→verify` in
      throwaway repos, fake agent with `--dry` (fully offline); collects per-run
      graded_pass, first-pass gate verdict, scope violations, wall-clock cost.
      Proof: tests/test_eval.py (5 offline tests). Honest finding encoded in a
      test: a do-nothing agent reaches gates=PASS + empty diff → the corpus's
      visible gates are weak by design; `graded_pass` is the real signal.
- [x] Report: `harness eval report` → static CSP-sandboxed HTML from
      results.jsonl, grouped agent/stack × task × variant.
      Proof: test_report_groups_and_escapes (incl. XSS escape assertion).
- [x] **Live matrix (codex half)**: 13 real provider runs 2026-09-30 — 11/13 graded
      PASS (only slugify failed, both variants, a genuine agent miss), scope
      violations raw=3 vs harnessed=4, every harnessed gates=FAIL attributable to the
      independent-review session limit — recorded in each run's review_note, not
      skipped. ≥10-row bar met on attempt 1. The live runs immediately earned their
      keep: they exposed the TS grading-env defect (fixed 0f5c1da: @types/node +
      moduleDetection:force + explicit test paths; the first 6 TS rows were pruned as
      env-corrupted, not agent results).
      Proof: evals/results.jsonl + `harness eval report` (artifacts gitignored by
      design; numbers land in README — a tracked generated file would drift).
- [ ] **Claude half**: same matrix through `--agent claude` after the session-limit
      window (reset announced 07:00 Europe/Brussels 2026-09-30); if 3 attempts yield
      <10 rows, ship v1 on the codex matrix + dry-run honesty proof and note the
      single-agent caveat in the README block.
- [x] README + TECHNICAL_PLAN §7 P7 Done note with the numbers (README evals block;
      claude caveat stated there until its half runs).

## v1.0 ship (end of W3)

- [ ] Version bump to `1.0.0` in pyproject + `harness --version` proof.
- [ ] GitHub release: tag v1.0.0, changelog assembled from the history chain
      (cc27ff1→HEAD), install instructions smoke-tested per DoD.
- [ ] README final pass: one-command quickstart (`uv tool install .` → scan →
      init → task start) verified line by line on a clean repo.

## Post-v1 backlog (no order implied)

- [ ] **Qoder adapter in `harness init`** — emit `.qoder/settings.json`
      (bypass posture + skill + 3 commands, all marker-based/idempotent) next to
      the existing CLAUDE.md/.claude generation, so onboarded repos get the same
      friction-free Qoder environment for free. Natural next code phase.
- [ ] Guard hardening: `hit()` matched repo-relative only — absolute
      outside-root reads (`~/.ssh`) slipped `never_read` (found during Qoder
      verification). Fixed on branch `harness/dod-closeout` (segment-bounded
      directory anchor + tests/test_guard_transcript.py); merged 3aa83f9.
- [ ] `.Codex/` convention: promote the session-handoff format to a supported
      `harness handoff` output (or drop it — duplicate of evidence+task list).
- [ ] Copilot/Cursor adapters (TECHNICAL_PLAN explicitly "not yet built").
- [ ] Team policy **enforcement**: `policy status` as a required CI check once
      a real bundle URL exists (workflow note in §7 P6 says how).
- [ ] Hosted product / Review Agent SDK commercial terms — research task, not code.
- [ ] Qoder plugin packaging (`.qoder-plugin/plugin.json` + `qoder plugins validate`)
      for cross-repo install of the harness skill/commands.

## Definition of "done building" for this project

v1.0 release exists (tag + GitHub release), every §9 DoD box above is checked
with a linked proof, README quickstart works verbatim on a stranger's machine,
and P7 has run once — or the user explicitly waived P7. Anything past that is
post-v1 by definition.
