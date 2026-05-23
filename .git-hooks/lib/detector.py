from __future__ import annotations
import os
import subprocess


def detect_llm() -> str:
    """Return 'claude' or 'codex' based on active LLM environment."""
    for var in ("CLAUDE_MODEL", "ANTHROPIC_MODEL"):
        if os.environ.get(var):
            return "claude"
    if os.environ.get("CODEX_MODEL"):
        return "codex"
    try:
        ppid = os.getppid()
        result = subprocess.run(
            ["ps", "-p", str(ppid), "-o", "comm="],
            capture_output=True, text=True, timeout=5
        )
        name = result.stdout.strip().lower()
        if "codex" in name:
            return "codex"
        if "claude" in name:
            return "claude"
    except Exception:
        pass
    return "claude"


def red_team_command(prompt: str) -> list[str]:
    """Return the CLI command list to invoke the opposing LLM for red-teaming."""
    identity = detect_llm()
    if identity == "claude":
        return ["codex", "exec", prompt]
    return ["claude", "-p", prompt]
