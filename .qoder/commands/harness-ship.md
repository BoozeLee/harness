---
description: Prepare and cut the v1.0 release — bump, gates, changelog, tag, GitHub release (asks before irreversible steps).
---

Follow the `harness-release` skill:

1. Open/confirm the task: `harness task list` — a `v1-ship` contract must exist
   covering `pyproject.toml`, `harness/**`, `README.md`, `ROADMAP.md`.
2. Bump BOTH version sites, prove `harness --version` = `harness 1.0.0`.
3. Run `harness verify v1-ship` — everything green (reviewer included) before
   any tag discussion.
4. Assemble the changelog from `git log --oneline cc27ff1..HEAD`, final README
   quickstart pass via `bash scripts/smoke.sh` from a fresh /tmp clone.
5. Commit + push (standing directive). Then STOP and ask for explicit approval
   for `git tag v1.0.0` + `gh release create` — those are the irreversible steps.
