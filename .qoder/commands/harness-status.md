---
description: Report Harness repo standing - readiness score, open tasks, branch/remote sync, last CI result.
---

Gather this repo's current standing and report it compactly (no recommendations
unless something is red):

1. `harness scan` — readiness score and gate list.
2. `harness task list` — contracts with risk and latest verdict.
3. `git status --short` and `git log --oneline -3`; compare `main` vs
   `origin/main` (`git rev-parse main origin/main`).
4. `gh run list --branch main --limit 3` — latest Actions result (skip if gh
   unauthenticated; say so).

End with the single next step the roadmap implies (TECHNICAL_PLAN.md §7 /
.Codex/status.md "Next step").
