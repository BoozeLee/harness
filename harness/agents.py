"""Agent adapters: the same contract lifecycle driven by different coding agents.

Enforcement asymmetry, stated honestly: Claude runs under the PreToolUse guard hook
(.claude/settings.json); Codex has no hook equivalent, so it relies on AGENTS.md rules
plus its workspace-write sandbox, with the scope gate in `harness verify` catching
violations after the fact.
"""

import json
import shutil
import subprocess
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType

from harness.policy import die


@dataclass(frozen=True)
class AgentSpec:
    binary: str
    argv: Callable[[str], list[str]]
    enforcement_tier: str
    description: str


AGENT_SPECS: Mapping[str, AgentSpec] = MappingProxyType({
    "claude": AgentSpec("claude", lambda prompt: ["claude", "-p", prompt, "--permission-mode", "acceptEdits"],
                        "guard-hook", "Claude Code with the PreToolUse guard hook."),
    "codex": AgentSpec("codex", lambda prompt: ["codex", "exec", "--sandbox", "workspace-write", prompt],
                       "sandbox+verify", "Codex with workspace-write sandbox and verify scope gate."),
})
AGENTS = tuple(AGENT_SPECS)


def agent_prompt(c) -> str:
    return (f"Goal: {c['goal']}\nAcceptance criteria:\n" + "\n".join(f"- {x}" for x in c["accept"]) +
            "\nFirst write a short plan, then implement. Do not touch protected paths. Before finishing, run: " +
            "; ".join(g["cmd"] for g in c["gates"].values()) + ". Do not claim completion while any fails.")


def build_argv(agent: str, prompt: str) -> list[str]:
    try:
        return AGENT_SPECS[agent].argv(prompt)
    except KeyError:
        die(f"unknown agent: {agent} (supported: {', '.join(AGENT_SPECS)})")


def cmd_agents(args) -> int:
    rows = []
    for name, spec in AGENT_SPECS.items():
        path = shutil.which(spec.binary)
        version = None
        if path:
            for flag in ("--version", "version"):
                try:
                    result = subprocess.run([path, flag], capture_output=True, text=True, timeout=5, check=False)
                except (OSError, subprocess.SubprocessError):
                    continue
                if result.returncode == 0:
                    lines = (result.stdout + result.stderr).strip().splitlines()
                    version = lines[0][:90] if lines else "present"
                    break
            if version is None:
                version = "present"
        rows.append({"name": name, "binary": spec.binary, "present": path is not None,
                     "version": version, "enforcement_tier": spec.enforcement_tier})
    if args.json:
        print(json.dumps(rows))
    else:
        print(f"{'NAME':<12} {'PRESENT':<8} {'VERSION':<24} ENFORCEMENT TIER")
        for row in rows:
            print(f"{row['name']:<12} {'yes' if row['present'] else 'no':<8} "
                  f"{(row['version'] or '-'):<24} {row['enforcement_tier']}")
    return 0
