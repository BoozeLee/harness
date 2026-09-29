---
description: Verify a Harness task contract through all its gates and report the evidence verdict. Usage: /harness-verify <task>
---

Argument: the task name (first `$ARGUMENTS` word; if missing, list contracts
with `harness task list` and ask which one).

1. `harness verify $ARGUMENTS` from the repo root — it runs the gates for the
   contract's risk level, the scope check, and the reviewer, then writes
   `.ai-engineering/evidence/<task>.json`.
2. Read the evidence JSON (safe to read; it is plain JSON) and report: verdict,
   each gate's pass/fail, changed-files vs allowed scope.
3. On FAIL: quote the failing gate's output tail and stop — do not loosen the
   contract or skip a gate without being told to.
4. On PASS: state that `harness pr create $ARGUMENTS` is unblocked (do not run
   it unless asked).
