---
description: Refresh the .Codex/status.md session handoff from live git/task/evidence state before ending a session.
---

Update `/home/kilisan/harness/.Codex/status.md` (untracked — never commit it)
from VERIFIED state only:

1. `git log --oneline -6` + `git status --short` + `gh run list --limit 2` —
   the Git-state paragraph must match reality, including unmerged branches
   under `.harness-worktrees/`.
2. `harness task list` — verdicts come from evidence files, not memory.
3. One "Done (verified, not just written)" bullet per landed change with its
   proof (run URL, test count, smoke transcript line).
4. Next-step paragraph: first unchecked ROADMAP.md box + any blockers
   (quota windows, pending user decisions).
5. Never write secrets, token values, or unverified claims into it.
