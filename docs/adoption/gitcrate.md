# Adoption log: harness on a second real repo (gitcrate)

Run 2026-09-30, from a fresh clone of `/home/kilisan/gitcrate` (a messy personal
Python/utility repo, 1822 tracked files, unittest-style tests, no venv).
Harness 1.0.0 installed into a throwaway venv (`uv venv` + `uv pip install`) —
identical to a stranger's first step in the README. This is the proof the
product thesis works outside its own repo, plus the friction it exposed.

## What worked unmodified

- `harness --version` → 1.0.0 straight from the wheel.
- `harness scan`: detected the python stack and wrote an honest readiness score
  (40/100). `harness init` lifted it to 50/100 and produced
  `.ai-engineering/`, `CLAUDE.md`, `AGENTS.md`, `.claude/settings.json` without
  touching any repo file destructively.
- `harness task start pytest-noise … --risk low` → worktree + contract, exactly
  as in the dogfood lifecycle.
- The governed task itself: gitcrate's own TODO phase 1 ("stop the noise") —
  bare `python3 -m pytest -q` failed with 5 collection errors from orphaned
  `scripts/test_*.py`. One in-scope `pytest.ini` (`testpaths = tests`) fixed it:
  pytest 15/15 green, unittest discover still green, `harness verify` →
  **PASS (unit + scope)**. Real value, produced through the contract path.

## Friction → product defects (all fixed in harness on this landing)

1. **Generated CI guarantees an instant red build.** `harness ci` hardcoded
   `--fail-under 70`; gitcrate scores 50 even after `init`, so the readiness
   job would fail on the repo's very first push. A newcomer meeting a red
   Actions tab from our own generated workflow is churn-on-arrival.
   → `harness ci` now clamps the default floor to `min(70, measured)`, prints
   the clamp explicitly, and an explicit `--fail-under N` is never clamped
   (tests: `test_ci_clamps_default_floor_to_measured_readiness`,
   `test_ci_explicit_floor_is_never_clamped`).
2. **`Verdict: PASS (no diff)` lied.** An agent whose entire contribution is
   *new* files (the common case: a config, a module) is invisible to
   `git diff --shortstat base HEAD`, so the evidence and the console claimed no
   changes while the scope gate had just counted them.
   → verify.py + runner.py now render `N untracked file(s) added` in that state
   (test: `test_verify_stat_names_untracked_agent_work`).
3. **Gate detection is stack-shaped, not repo-shaped.** scan proposed
   `python3 -m pytest -q` because the repo is python+tests/, but this repo's
   working entry point is `python3 -m unittest discover -s tests`. The escape
   hatch existed and was one file: edit `.ai-engineering/verification.json`
   (the contract is plain JSON, `git diff`-reviewable — by design). Not fixed
   in code: guessing a repo's test runner is a false-precision problem; the
   right long-term answer is `harness init --gate unit "cmd"` sugar, tracked
   below, not heuristics that silently pick wrong.

## Known-benign observations

- Worktrees land at `<repo-parent>/.harness-worktrees/…` (here
  `/tmp/.harness-worktrees/…` for a /tmp clone). Correct by design — never
  inside the governed repo — worth a README note.
- `--risk low` skips independent review by contract semantics (low ⇒ no
  reviewer). Proven-correct behavior, but a first-time user needs the README
  risk table before they trust their own gates.
- `harness policy push` was not exercised here (needs a bundle remote;
  `scripts/smoke.sh` already covers it end to end).

## Verdict on the thesis

The lifecycle drove a real cleanup task in a foreign repo with zero harness-side
special-casing, the gates caught a genuine repo-wide breakage, and every piece
of friction found was either an instant fix in harness proper (2 shipped with
tests) or a documented design choice. Adoption is viable; the two code fixes are
what a stranger would have hit in their first ten minutes.

## Follow-ups (post-v1 backlog)

- `harness init --gate <name> "<cmd>"` sugar to set gate commands without
  hand-editing JSON.
- README risk-table paragraph (what low/medium/high actually gates) + worktree
  location note.
- Second adoption subject (mcp-regression-lab) to see if a node/TS repo finds
  different friction.
