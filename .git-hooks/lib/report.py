from __future__ import annotations
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from .models import CodeReviewResult, RedTeamResult

_REPORTS_DIR = Path.home() / ".git-hooks" / "reports"

import re as _re

def _safe(s: str) -> str:
    """Strip everything except alphanumerics, dash, underscore — prevents path traversal."""
    return _re.sub(r"[^a-zA-Z0-9_\-]", "-", s)[:64]



def write_report(
    repo: str,
    branch: str,
    push_sha: str,
    elapsed: float,
    blocked: bool,
    block_reason: str,
    code_review: Optional[CodeReviewResult],
    rt_change: Optional[RedTeamResult],
    rt_drift: Optional[RedTeamResult],
    skipped: bool = False,
) -> Path:
    _REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    safe_repo = _safe(repo)
    safe_branch = _safe(branch)
    filename = f"{ts}-{safe_repo}-{safe_branch}.md"
    path = _REPORTS_DIR / filename

    status = "[SKIPPED]" if skipped else ("BLOCKED" if blocked else "PASSED")
    lines = [
        f"# Pre-Push Review Report",
        f"",
        f"| Field | Value |",
        f"|-------|-------|",
        f"| Repo | {repo} |",
        f"| Branch | {branch} |",
        f"| SHA | {push_sha} |",
        f"| Timestamp | {ts} |",
        f"| Elapsed | {elapsed:.1f}s |",
        f"| **Status** | **{status}** |",
        f"",
    ]

    if blocked and block_reason:
        lines += [f"## Block Reason", f"", f"{block_reason}", f""]

    # Code review section
    lines += [f"## Code Review Findings", f""]
    if code_review is None:
        lines += ["_(not run)_", ""]
    elif code_review.timed_out:
        lines += ["**TIMED OUT** — treated as blocking.", ""]
    elif code_review.error:
        lines += [f"**ERROR**: {code_review.error}", ""]
    elif not code_review.findings:
        lines += ["No findings.", ""]
    else:
        lines += ["| Severity | File | Description |", "|----------|------|-------------|"]
        for f in sorted(code_review.findings, key=lambda x: -x.severity):
            lines.append(f"| {f.severity} | {f.file} | {f.description} |")
        lines.append("")

    # Red-team sections
    for rt, title in [(rt_change, "Red-Team Pass 1 — Change-Level"), (rt_drift, "Red-Team Pass 2 — Layered Drift")]:
        lines += [f"## {title}", ""]
        if rt is None:
            lines += ["_(not run — no .md files changed)_", ""]
            continue
        if rt.timed_out:
            lines += ["**TIMED OUT** — treated as blocking.", ""]
            continue
        if rt.error:
            lines += [f"**ERROR**: {rt.error}", ""]
            continue
        lines += [
            f"**Severity:** {rt.severity}",
            f"**Summary:** {rt.summary}",
        ]
        if rt.compaction_cycles is not None:
            lines.append(f"**Compaction Cycles:** {rt.compaction_cycles}")
        lines += ["", "### Raw Output", "```", rt.raw_output[:4000], "```", ""]

    path.write_text("\n".join(lines))
    return path


def print_terminal_summary(
    blocked: bool,
    block_reason: str,
    code_review: Optional[CodeReviewResult],
    rt_change: Optional[RedTeamResult],
    rt_drift: Optional[RedTeamResult],
    report_path: Path,
    skipped: bool = False,
) -> None:
    status = "[SKIPPED]" if skipped else ("BLOCKED" if blocked else "PASSED")
    cr_summary = "n/a"
    if code_review:
        if code_review.timed_out:
            cr_summary = "TIMEOUT"
        elif code_review.error:
            cr_summary = f"ERROR: {code_review.error}"
        else:
            counts = {}
            for f in code_review.findings:
                counts[str(f.severity)] = counts.get(str(f.severity), 0) + 1
            cr_summary = " ".join(f"{v} {k}" for k, v in sorted(counts.items(), reverse=True)) or "clean"

    def _rt_summary(rt: Optional[RedTeamResult]) -> str:
        if rt is None:
            return "n/a"
        if rt.timed_out:
            return "TIMEOUT"
        if rt.error:
            return f"ERROR"
        s = str(rt.severity)
        if rt.compaction_cycles is not None:
            s += f" (compaction: {rt.compaction_cycles} cycles)"
        return s

    print("", file=sys.stderr)
    print("─── Pre-Push Review ─────────────────────────────", file=sys.stderr)
    print(f"  Status : {status}", file=sys.stderr)
    if blocked and block_reason:
        print(f"  Reason : {block_reason}", file=sys.stderr)
    print(f"  Code   : {cr_summary}", file=sys.stderr)
    print(f"  RT P1  : {_rt_summary(rt_change)}", file=sys.stderr)
    print(f"  RT P2  : {_rt_summary(rt_drift)}", file=sys.stderr)
    print(f"  Report : {report_path}", file=sys.stderr)
    print("─────────────────────────────────────────────────", file=sys.stderr)
    print("", file=sys.stderr)
