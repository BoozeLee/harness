"""Agent adapters: the same contract lifecycle driven by different coding agents.

Enforcement asymmetry, stated honestly: Claude runs under the PreToolUse guard hook
(.claude/settings.json); Codex has no hook equivalent, so it relies on AGENTS.md rules
plus its workspace-write sandbox, with the scope gate in `harness verify` catching
violations after the fact.
"""

from harness.policy import die

AGENTS = ("claude", "codex")


def agent_prompt(c) -> str:
    return (f"Goal: {c['goal']}\nAcceptance criteria:\n" + "\n".join(f"- {x}" for x in c["accept"]) +
            "\nFirst write a short plan, then implement. Do not touch protected paths. Before finishing, run: " +
            "; ".join(g["cmd"] for g in c["gates"].values()) + ". Do not claim completion while any fails.")


def build_argv(agent: str, prompt: str) -> list:
    if agent == "claude":
        return ["claude", "-p", prompt, "--permission-mode", "acceptEdits"]
    if agent == "codex":
        # approval-on-request would stall a headless run; workspace-write is the automation mode
        return ["codex", "exec", "--sandbox", "workspace-write", prompt]
    die(f"unknown agent: {agent} (supported: {', '.join(AGENTS)})")
