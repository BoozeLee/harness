"""Claude Code PreToolUse hook. Contract verified against 2.1.283: JSON event on
stdin; deny = JSON decision on stdout AND exit 2 with stderr reason (the exit code
is the guaranteed channel on every version; the JSON gives richer reason text)."""

import json
import os
import sys
from pathlib import Path

from harness.policy import AE, audit, evaluate, find_root, jload


def _decision_output(kind: str, why: str) -> str:
    return json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                              "permissionDecision": kind,
                                              "permissionDecisionReason": f"Harness policy: {why}"}})


def cmd_guard(a) -> int:
    try:
        ev = json.load(sys.stdin)
    except (ValueError, UnicodeDecodeError):
        return 0
    cwd = Path(ev.get("cwd") or os.getcwd())
    root = find_root(cwd)
    if not root:
        return 0
    pol = jload(root / AE / "policy.json")
    ti = ev.get("tool_input") or {}
    tool = ev.get("tool_name", "")
    decision, why = evaluate(pol, cwd, root, tool, ti)
    audit(root, tool, ti.get("file_path") or ti.get("path") or ti.get("command"), decision, why)
    if decision == "deny":
        print(_decision_output("deny", why), flush=True)
        print(f"Harness policy blocked this action: {why}.", file=sys.stderr)
        return 2
    if decision == "ask":
        print(_decision_output("ask", why), flush=True)
    return 0
