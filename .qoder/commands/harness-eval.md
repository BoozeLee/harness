---
description: Run the P7 raw-vs-harnessed eval matrix (dry proof first, then live chunks) and print headline numbers.
---

Run the evals per the `harness-evals` skill:

1. `harness eval run --dry --task wordcount` — offline plumbing proof. Stop if
   this fails; fix the runner before spending quota.
2. Check quota window: `TZ=Europe/Brussels date`. Before 02:15 local, ask the
   user whether to wait (do not run the live matrix on a dead quota).
3. Live matrix, one task at a time:
   `harness eval run --task <id>` for wordcount, dedup, movavg, queryparams,
   slugify, rangeexpand. Record each task's rows as they land.
4. `harness eval report` and summarize in chat: graded_pass raw vs harnessed
   per agent/stack, scope violations, mean wall. Do not commit report.html.
5. If ≥10 live rows: propose the README + TECHNICAL_PLAN §7 numbers edit as a
   commit on main (push only when the user asks).
