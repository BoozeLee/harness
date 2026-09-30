---
name: harness-release
description: Ship Harness v1.0 — version bump, changelog from commit history, tag + GitHub release. Use for release, ship, version bump, or tag questions.
---

# Harness release (v1.0 ship)

Repo: /home/kilisan/harness, remote origin = BoozeLee/harness (private, gh authed).
`main` must stay releasable; Actions green is the acceptance signal.

## Steps (only on explicit user ask for tag/release — merge+push per standing directive)

1. Version bump — BOTH places or `--version` lies:
   - `pyproject.toml` `version = "1.0.0"`
   - `harness/__init__.py` `__version__ = "1.0.0"`
   Proof: `harness --version` prints `harness 1.0.0` (dev install is editable; if it
   still prints 0.2.0, the venv/entry point is stale — `uv run harness --version`).
2. Gates before anything else: `harness verify <release-task>` (open a task
   `v1-ship` first, allow `pyproject.toml harness/** README.md ROADMAP.md TECHNICAL_PLAN.md`).
3. Changelog: assemble from the history chain
   `git log --oneline cc27ff1..HEAD` — phases P0–P7 + DoD closeout.
4. README final pass: quickstart block verified by `bash scripts/smoke.sh`
   (that script IS the §3 command block; it passed end-to-end from a clean
   /tmp clone on 2026-09-29).
5. `git tag -a v1.0.0 -m "v1.0.0 — §9 DoD complete, P7 numbers in" && git push origin v1.0.0`
   then `gh release create v1.0.0 --title "Harness v1.0.0" --notes-file <changelog>`.
6. Tick the "v1.0 ship" boxes in ROADMAP.md with the run/tag proofs.

## Rules

- Never force-push; never delete tags locally after pushing.
- Tagging is irreversible-ish (public-ish, shared state): confirm with the user
  unless they explicitly said "ship it".
- If Actions fails on the tag commit, fix forward with a new commit — never rebase
  pushed history.
