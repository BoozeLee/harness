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

- [ ] **Push integration commit** — `git push origin main` (a2bc2e4 + whatever
      this lands), Actions green on the new main. Proof: run URL + success.
- [ ] **Guard transcript test** — pytest reproducing the §1 story end to end:
      a fake agent session whose `Read .env` / forbidden `Bash` events go
      through `cmd_guard` stdin and get exit-2 + audit.log lines. §8 risk row
      "Guard blocks legit flows → users disable it" gets its counterweight test
      too: an in-scope edit passes untouched. Proof: new tests green, suite ≥73.
- [ ] **Install smoke** — `uv tool install .` in a clean venv → `harness --help`
      + `harness scan` on a scratch repo. Automate as a pytest marked slow or a
      CI step. Proof: command transcript in the commit body.
- [ ] **Fresh-machine checklist** — run TECHNICAL_PLAN §3 command block verbatim
      on a clean clone in /tmp; fix every step that needed unstated knowledge
      (the serve.token mint was exactly this class of bug). Proof: doc diff or
      "no changes needed" note in §3.
- [ ] **ROADMAP honesty pass** — mark this whole section Done in one commit;
      readiness still ≥ floor (`harness scan --fail-under 70` exits 0).

## P7 — Evals: raw vs harnessed (W2–W3, needs a lift)

→ **Blocked on user decision:** real provider calls send task/diff data off this
machine. Lift the auto-mode rule, or park P7 and ship v1 without eval numbers.

- [ ] Corpus: ≥6 small tasks × 2 stacks (python repo + a TS repo), same task
      run both ways. Proof: fixtures under `evals/`, `harness eval list` shows them.
- [ ] Runner: `harness eval` — spawns raw `claude -p` vs `task start/run/verify`
      in throwaway bare-origin repos, collects per-run: first-pass gate rate,
      scope violations, reviewer FAIL reasons, cost, wall-clock.
- [ ] Report: static HTML from the evidence schema (dashboard pattern reused),
      checked-in last report as the README's "proof it works" artifact.
- [ ] README + TECHNICAL_PLAN §7 P7 Done note with the numbers.

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
- [ ] Guard hardening: `hit()` currently matches repo-relative only — absolute
      outside-root reads (`~/.ssh`) slip `never_read` (found during Qoder
      verification). Decide: canonicalize+escape-check vs leave to user-level
      deny rules; test either way.
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
