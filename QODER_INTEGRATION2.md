# Qoder Integration Report v2 — mission: P7 live matrix → v1.0 ship

Written 2026-09-30 02:15 Europe/Brussels. Supersedes QODER_INTEGRATION.md (v1,
still valid for posture/history). Restart a fresh Qoder conversation on
`/home/kilisan/harness` with this file as the entry point: state, new tools,
the end-state environment spec, and the remaining plan with week numbers.

## 1. Where the project stands (verified, not remembered)

- `main` == pushed @ `1593ff9` — §9 DoD closeout merged (`3aa83f9`, merge
  commit documents the reviewer-quota exception), ROADMAP honesty pass ticked,
  readiness 80/100, `scan --fail-under 70` exits 0.
- Branch `harness/p7-evals` (worktree `~/.harness-worktrees/harness-p7-evals`,
  tip = review-fix commit) — being verified+merged by the session that writes
  this file (see §5).
- P7 tooling landed: `harness eval list|run|report`, 6-task × 2-stack corpus
  under `evals/`, hidden `test_graded` suites as ground truth, offline fake-agent
  proof + XSS-safe CSP report. A substitute local review (cloud reviewer was
  quota-dead) found 6 defects — all fixed in that branch: no more verdict
  gaming (`--risk medium` real review in-loop), unpredictable answer-key path,
  full-pipeline wall cost, commit-proof scope baseline, fresh grade copies,
  honest n/a gates for raw.
- Posture unchanged (operator directive 2026-09-29, reaffirmed):
  `.qoder/settings.json` = `bypass_permissions` + blanket allow, **no hooks, no
  deny lines**. Enforcement narrative = verify-scope + evidence, not
  pre-execution blocking.

## 2. What was installed into Qoder this session

| Artifact | Path | Status |
|---|---|---|
| evals skill | `.qoder/skills/harness-evals/SKILL.md` | `[Enabled]` |
| release skill | `.qoder/skills/harness-release/SKILL.md` | `[Enabled]` |
| flake skill | `.qoder/skills/harness-test-flakes/SKILL.md` | `[Enabled]` |
| eval command | `.qoder/commands/harness-eval.md` | `[Enabled]` |
| ship command | `.qoder/commands/harness-ship.md` | `[Enabled]` |
| handoff command | `.qoder/commands/harness-handoff.md` | `[Enabled]` |
| (v1, unchanged) | `harness` skill, `harness-status/-verify/-next` | `[Enabled]` |

Verified via `qoder skills list` from inside the project. NOT yet exercised:
the three new commands (first live use is the restart session — report drift
back into the skill files if found).

## 3. End-state machine environment (technically outlined, pinned)

Goal: a fresh Omarchy/Arch box runs the whole pipeline with one block, and the
pinned versions are exactly what this repo's gates were proven against tonight.

### 3.1 Toolchain layer (mise + uv + npm)

```sh
# mise pins (machine-level; .config/mise/config.toml equivalent)
mise use -g python@3.14.5 nodejs@24.21.0
# repo python env — versions come from uv.lock, do not hand-edit
cd ~/harness && uv sync --frozen          # venv: python 3.13.13, fastapi/uvicorn,
                                          # pytest/ruff/mypy, types-PyYAML (dev group)
# web app
cd ~/harness/web && npm ci --no-audit --no-fund
npx playwright install chromium           # global browser store; Omarchy prints a
                                          # benign "OS not supported → ubuntu24
                                          # fallback" warning — it works
```

Verified pins tonight: `uv 0.11.14`, `node v24.21.0` (web runtime; mise default
`python 3.14.5` is for system scripts, repo venv is 3.13.13 — pytest picks the
venv automatically), `playwright 1.60.0`, `typescript 5.9.3`.

### 3.2 AI layer (the agents harness itself drives)

```
qoder CLI 1.1.64          # host; settings posture §1; skills/commands §2
claude (Claude Code) 2.1.283  # adapters + independent-review gate + evals agent
codex-cli 0.159.1             # second eval agent (workspace-write sandbox)
gh 2.101.0                    # pr subcommands + CI; authed BoozeLee
```

Pinning rule: these four binaries are the eval surface — a version change
invalidates prior eval numbers; record versions in the report footer when the
matrix runs (`harness eval report` reads rows produced by these exact builds).

`uv tool install .` remains the documented user install path; `scripts/smoke.sh`
proves the CLI end-to-end via venv isolation because uv 0.11.x has no
`--tool-dir` (recorded in ROADMAP; revisit if uv adds isolation).

### 3.3 MCP / plugins

Still none needed — `gh` CLI covers the remote surface (v1 report conclusion
unchanged). Qoder plugin packaging (`.qoder-plugin/plugin.json`) remains
post-v1 backlog.

## 4. Operating knowledge (this machine, Auto Mode — earned the hard way)

- **Classifier framing:** direct `timeout 90 claude -p …` Bash calls are BLOCKED
  as arbitrary external connectivity. The same provider call inside a harness
  pipeline command (`harness verify`, `uv run python -m harness … eval run`)
  passes and executes. Drive all providers through harness verbs.
- **Quota window:** Claude Code session limit resets 02:00 Europe/Brussels.
  Provider-heavy batches after 02:15; a refusal lands in a row as
  `agent_rc=1` + "session limit" in `agent_tail` — note, never hammer.
- **Reviewer-down substitute:** a local Qoder sub-agent reviewing the diff is
  the documented fallback (it caught the 6 honesty defects above). Record it in
  the merge message; never silently skip the gate.
- **Flakes = contention:** parallel gates both running `cd web && npm ci` race
  on node_modules (symptoms: ERR_MODULE_NOT_FOUND, sidebar spec failure, empty
  main node_modules). Playbook in `harness-test-flakes` skill.
- **Never:** read `serve.token`; force-push; `git push origin main` outside the
  explicit-ask flow (standing hook denial from the Claude-Code layer still
  applies to this session's discipline).

## 5. Remaining plan with week numbers

W1 (tonight, 2026-09-30) — DONE except final bullets:
- [x] DoD closeout merged to main + pushed + Actions proof
- [ ] p7-evals verify PASS → merge → push → Actions (session in flight)

W2 (by 2026-10-04):
- [ ] Live eval matrix ≥10 rows (`harness eval run`, claude+codex × 6 tasks ×
      2 variants) + report numbers into README "proof it works" section +
      TECHNICAL_PLAN §7 P7 line. Kill criterion: if both providers' quotas
      can't produce ≥10 rows in 3 attempts, ship v1 with dry-run honesty proof
      + waive live numbers (record waiver explicitly).

W3 (by 2026-10-11):
- [ ] v1.0 ship: bump both version sites → `harness --version` proof →
      changelog from `cc27ff1..HEAD` → tag v1.0.0 + `gh release create`
      (explicit user ask required for tag/release).

Post-v1 (no deadline): Qoder adapter in `harness init` (emit
`.qoder/skills+commands+settings` exactly as §2, marker-idempotent — the
P5d-shaped phase), plugin packaging, Copilot/Cursor adapters, policy
enforcement CI, `.Codex` handoff formalization.

## 6. Definition of "done building" (unchanged, restated)

v1.0 tag + release exist, every §9 DoD box is checked with a linked proof
(done tonight), README quickstart verified on a stranger's machine
(`scripts/smoke.sh` = that block), and P7 has run live once — or the W2 kill
criterion above explicitly waived it. Anything past that is post-v1.

## 7. Restart procedure

```sh
cd ~/harness && qoder            # project settings/skills load from .qoder/
```
First message candidates: `/harness-eval` (W2 matrix), `/harness-status`
(state), `/harness-handoff` (refresh §.Codex/status.md after the merge).
