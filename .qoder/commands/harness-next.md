---
description: Start the next roadmap phase of TECHNICAL_PLAN.md as a governed Harness task. Usage: /harness-next
---

1. Read `TECHNICAL_PLAN.md` §7 (phase table) and `.Codex/status.md` "Next step"
   if present; pick the first phase not marked Done.
2. Restate in ≤5 lines: the phase, its acceptance criteria from the plan, and
   anything blocking it (e.g. real-provider phases need the user to lift the
   no-data-off-machine rule).
3. Scaffold it as a contract:
   `harness task start <phase-slug> --goal "…" --accept "…" --risk <low|medium|high>`
   — risk high only when it touches auth/CI/push behavior.
4. Propose the implementation outline inside the worktree
   (`.harness-worktrees/<phase-slug>/`) and wait for go-ahead before editing.
