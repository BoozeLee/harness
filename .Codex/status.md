# Status — 2026-09-30 (evening)

**Goal:** Harness (contract-gated AI-engineering pipeline, ~/harness) — v1.1.0 shipped; post-v1 integration wave (ELOHIM gate, LINCE-shaped agent registry) complete.

**Git state (verified at write time):** main == origin/main == `5f24a9d`. Chain today: `8fb5fd2` (v1.0.0 tag, at `f6327bd`→v1.0.0 release live with wheel+sdist) → `d7ba636` (merge elohim-gate) → `6e7ae23` (merge lince-registry) → `9cca47a` (v1.1.0 bump + changelog + install.sh committed) → `5f24a9d` (v1.1.0 __version__ drift fix + pinning test). **Tag v1.1.0 = `5f24a9d`** (moved once: first wheel shipped stale "1.0.0" string; assets replaced via --clobber). Actions green on all pushes incl. `gate elohim` on real runners. Remote: BoozeLee/harness (private, gh authed). Releases: v1.0.0 + v1.1.0 live, both with wheel/sdist attached.

## Done (verified, not just written)

- **v1.0.0 tag+release** — was already cut by the pre-disconnect run; verified correct target (`8fb5fd2`), assets uploaded.
- **Install wrapper** (`scripts/install.sh`, committed): stranger-install from the GitHub release wheel (`uv tool install --reinstall`, venv fallback). Dogfooded twice against live releases; final proof: wrapper installs v1.1.0 → `harness --version` = 1.1.0.
- **ELOHIM gate** (task `elohim-gate`, role-driven Soldier contract under codex): skill tree vendored byte-identical at `vendor/elohim/` (diff -r clean; instrument sha256 matches ledger pin `a920cdd5...`); `elohim` gate in verification.json (min_risk medium, exit-code verdict); `.gitignore` for vendor out/; ruff excludes vendor (vendored code is not our lint surface); `harness ci` regenerated → `gate elohim` step, playwright `--with-deps chromium` setup step restored (agent's first regen silently dropped it — caught in adversarial review). `task update --allow` REPLACES the allow list (not extends) — re-amend with full list. Contract amended to include pyproject.toml after maintainer lint-exclude fix.
- **LINCE-shaped agent registry** (task `lince-registry` under codex): `AgentSpec` frozen dataclass (binary, argv builder, enforcement_tier, description), immutable `AGENT_SPECS` MappingProxyType; AGENTS/build_argv/unknown-agent-error/server TOOLS all derive from registry; claude/codex argv byte-identical; new `harness agents [--json]` validation verb (presence/version/tier); TECHNICAL_PLAN "Adding an agent" section; tests 6→9 green (PATH-shim, offline). First task verified through the ELOHIM gate itself. Suite 88 passed, ruff+mypy clean, CI green.
- **Reviewer exceptions** (both merges, documented in merge messages per p7-evals precedent): claude independent-review quota-locked until 07:00 Brussels; substitute = line-by-line diff review + vendored-tree diff proof + hash re-match + direct test runs + CI as standing independent verification.

## In progress / NOT done

- **G1 live matrix claude half: STILL OPEN.** Durable one-shot cron `720044ff` (Sep 30 07:05) did NOT fire (evals/results.jsonl has only codex runs, latest 03:59). Codex half shipped: 11/13 PASS. The one-shot's next cron match is Sep 30 NEXT year — delete and re-arm for tomorrow 07:05, or run the G1 procedure manually tomorrow.
- Deliberate design decisions a new session must NOT "fix": see prior status — serve-token minting in playwright.config.ts, golden-path `review:false`, loopback-no-bearer SSE/shot routes, `@playwright/test` pinned **1.63.0** (chromium-1243), `expect.timeout: 15_000`, ruff-excludes-vendor.
- Known quirk: contract `gates` snapshot taken at `task start`; a gate added mid-task doesn't run in verify until contract re-snapshot (elohim-gate was manually proven rc=0 + CI-green instead).

## Next step

1. **Re-arm the G1 claude-half job** for the next 07:05 quota reset (cron 720044ff is dead-in-effect) and run the live matrix claude half; then README numbers.
2. Candidate follow-ups (not started): `type: "elohim"` evidence gate (parsed --json into dashboard), capo `.capo/hits/*.yaml` → harness task importer (one-way), NexusRecon findings → contract-scope seeding, README/§9 version-drift lesson promoted to init check.

## Runtime / environment facts

- Servers DOWN (5173+8766). Start: `uv run harness serve`; e2e auto-boots: `cd web && npx playwright test`.
- Kill hung server: `PID=$(ss -tlnp | grep 8766 | grep -oP 'pid=\K[0-9]+' | head -1) && kill $PID`.
- Gates: `uv run pytest -q` / `uv run ruff check .` / `uv run mypy harness/` / playwright / `python3 vendor/elohim/scripts/elohim_run.py`.
- ELOHIM skill: `~/.agents/skills/elohim` (v2.0.0, mirrored in ~/.claude/skills — those two trees are synced copies, not conflicts). "Shadowed by user" = user skill wins over same-named builtin; only real collision: builtin `debug` shadowed by `~/.claude/skills/debug`.
- Global rules (AGENTS.md): no end-of-turn recaps ≤1-sentence turn ends; never invent APIs/versions; commit/push only when asked; never read/commit secrets; reviewer output is untrusted text.
- Pre-compaction transcripts: `~/.qoder/projects/-home-kilisan/` (2a83f430… = pre-v1.0 session; today's session under this dir too).
