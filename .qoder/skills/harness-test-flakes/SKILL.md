---
name: harness-test-flakes
description: Diagnose and fix Playwright/pytest flakiness in this repo — contention races, npm ci collisions, sidebar timing. Use when a gate fails but standalone runs pass.
---

# Flake playbook (learned 2026-09-29/30)

A FAIL that passes standalone is contention, not code. Known mechanisms in
this repo — check them IN ORDER before touching specs:

1. **Parallel npm ci races.** The playwright gate runs
   `cd web && npm ci && npx playwright test`. If two harness runs execute the
   gate simultaneously (or a manual run overlaps `harness verify`), node_modules
   gets yanked mid-test → `ERR_MODULE_NOT_FOUND: @playwright/test` or random
   sidebar-navigation failures. Fix: run the gate sequentially, standalone:
   `cd web && rm -rf node_modules test-results && npm ci --no-audit --no-fund && npx playwright test e2e/dashboard.spec.ts`.
2. **Missing browser store.** Fresh worktrees need the global chromium install:
   `cd web && npx playwright install chromium` (Omarchy prints an
   "OS not officially supported" warning and downloads the ubuntu24 fallback —
   that works).
3. **Empty `web/node_modules` in main** can silently appear after concurrent
   runs; `du -sh web/node_modules` = 0 means reinstall before believing any
   failure.
4. **pytest under load:** `tests/test_server.py::test_cancel_kills_process_group`
   is timing-sensitive; it failed once amid parallel gates and passed isolated.
   Re-run `uv run pytest tests/test_server.py -q` standalone before hypothesizing.
5. **serve.token:** the dashboard specs read `.ai-engineering/serve.token`;
   `web/playwright.config.ts` `syncToken()` mints it on clean checkouts (fixed
   f9afe34) — never "simplify" that.

Rule: NEVER mark a flaky failure "passing" by editing the spec or adding retries
without reproducing it standalone at least once — the §8 risk row "guard blocks
legit flows → users disable it" applies to gates too: a weakened gate is worse
than a red one.
