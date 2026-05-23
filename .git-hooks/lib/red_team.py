from __future__ import annotations
import re
import subprocess
from pathlib import Path
from .detector import red_team_command
from .models import RedTeamResult, Severity

_SEVERITY_RE = re.compile(r"^SEVERITY:\s*(\w+)", re.MULTILINE)
_SUMMARY_RE = re.compile(r"^SUMMARY:\s*(.+)", re.MULTILINE)
_COMPACTION_RE = re.compile(r"^COMPACTION_CYCLES:\s*(\d+)", re.MULTILINE)

_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


def _load_instruction_stack(repo_root: Path) -> str:
    parts = []
    for path in [
        Path.home() / ".claude" / "CLAUDE.md",
        repo_root / "CLAUDE.md",
        *sorted((repo_root / "agents").glob("*.md")),
        repo_root / "SKILL.md",
    ]:
        if path.exists():
            parts.append(f"=== {path} ===\n{path.read_text()}")
    return "\n\n".join(parts)


def _parse_result(output: str, pass_name: str) -> RedTeamResult:
    sev_m = _SEVERITY_RE.search(output)
    sum_m = _SUMMARY_RE.search(output)
    comp_m = _COMPACTION_RE.search(output)
    return RedTeamResult(
        pass_name=pass_name,
        severity=Severity.parse(sev_m.group(1)) if sev_m else Severity.MEDIUM,
        compaction_cycles=int(comp_m.group(1)) if comp_m else None,
        summary=sum_m.group(1).strip() if sum_m else "",
        raw_output=output,
    )


def _run_prompt(prompt: str, timeout: int) -> tuple[str, bool, str | None]:
    """Returns (output, timed_out, error)."""
    cmd = red_team_command(prompt)
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return result.stdout + result.stderr, False, None
    except subprocess.TimeoutExpired:
        return "[timed out]", True, None
    except FileNotFoundError:
        return "", False, f"{cmd[0]} not found on PATH"
    except Exception as e:
        return "", False, str(e)


def run_red_team_change(diff: str, timeout: int) -> RedTeamResult:
    template = (_PROMPTS_DIR / "red_team_change.txt").read_text()
    prompt = template.replace("{diff}", diff)
    output, timed_out, error = _run_prompt(prompt, timeout)
    if timed_out:
        return RedTeamResult(pass_name="change", timed_out=True, raw_output=output)
    if error:
        return RedTeamResult(pass_name="change", error=error)
    return _parse_result(output, "change")


def load_instruction_stack(repo_root: Path) -> str:
    """Snapshot instruction stack — call before workers launch to avoid race with push."""
    return _load_instruction_stack(repo_root)


def run_red_team_drift(diff: str, instruction_stack: str, timeout: int) -> RedTeamResult:
    template = (_PROMPTS_DIR / "red_team_drift.txt").read_text()
    prompt = template.replace("{instruction_stack}", instruction_stack).replace("{diff}", diff)
    output, timed_out, error = _run_prompt(prompt, timeout)
    if timed_out:
        return RedTeamResult(pass_name="drift", timed_out=True, raw_output=output)
    if error:
        return RedTeamResult(pass_name="drift", error=error)
    return _parse_result(output, "drift")
