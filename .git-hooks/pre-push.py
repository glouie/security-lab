#!/usr/bin/env python3
"""Pre-push adversarial review orchestrator."""
from __future__ import annotations
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

# lib/ is a sibling directory
sys.path.insert(0, str(Path(__file__).parent))

from lib.code_review import run_code_review
from lib.models import CodeReviewResult, RedTeamResult
from lib.red_team import load_instruction_stack, run_red_team_change, run_red_team_drift
from lib.report import print_terminal_summary, write_report


def _git(*args: str) -> str:
    return subprocess.check_output(["git"] + list(args), text=True).strip()


def _resolve_upstream(_local_branch: str) -> str:
    """Return the upstream SHA to diff against."""
    try:
        return _git("rev-parse", f"@{{u}}")
    except subprocess.CalledProcessError:
        pass
    for fallback in ("main", "master"):
        try:
            return _git("rev-parse", fallback)
        except subprocess.CalledProcessError:
            pass
    return _git("rev-parse", "HEAD~1")


def _diff_stats(upstream: str) -> tuple[int, int]:
    """Return (file_count, line_count) of changes since upstream."""
    try:
        stat = _git("diff", "--stat", upstream)
        lines = stat.splitlines()
        if lines:
            last = lines[-1]
            parts = last.split(",")
            file_count = int(parts[0].split()[0]) if parts else 0
            changed = sum(int(p.split()[0]) for p in parts[1:] if p.split()) if len(parts) > 1 else 0
            return file_count, changed
    except Exception:
        pass
    return 1, 50


def _md_diff(upstream: str) -> str:
    """Return unified diff of .md files only."""
    try:
        return _git("diff", upstream, "--", "*.md")
    except subprocess.CalledProcessError:
        return ""


def _compute_timeout(diff_files: int, diff_lines: int) -> int:
    # Base 120s + 5s per file + 1s per 10 lines, capped at 600s.
    # Override entirely with REVIEW_TIMEOUT env var (seconds).
    env_override = os.environ.get("REVIEW_TIMEOUT")
    if env_override:
        return int(env_override)
    return min(120 + (diff_files * 5) + (diff_lines // 10), 600)


def main() -> int:
    if os.environ.get("SKIP_REVIEW"):
        repo = Path(_git("rev-parse", "--show-toplevel")).name
        branch = _git("rev-parse", "--abbrev-ref", "HEAD")
        sha = _git("rev-parse", "HEAD")
        print("⚠  SKIP_REVIEW is set — adversarial review bypassed", file=sys.stderr)
        path = write_report(repo, branch, sha, 0.0, False, "", None, None, None, skipped=True)
        print_terminal_summary(False, "", None, None, None, path, skipped=True)
        return 0

    start = time.monotonic()

    repo = Path(_git("rev-parse", "--show-toplevel")).name
    branch = _git("rev-parse", "--abbrev-ref", "HEAD")
    push_sha = _git("rev-parse", "HEAD")
    repo_root = Path(_git("rev-parse", "--show-toplevel"))

    upstream = _resolve_upstream(branch)
    diff_files, diff_lines = _diff_stats(upstream)
    timeout = _compute_timeout(diff_files, diff_lines)

    print(f"⏱  Review timeout: {timeout}s (set REVIEW_TIMEOUT=<secs> to override)", file=sys.stderr)

    md_diff = _md_diff(upstream)
    has_md = bool(md_diff.strip())

    # Snapshot instruction stack before workers start — avoids race if push adds agent .md files
    instruction_stack = load_instruction_stack(repo_root) if has_md else ""

    futures: dict = {}
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures["code_review"] = pool.submit(run_code_review, upstream, timeout)
        if has_md:
            futures["rt_change"] = pool.submit(run_red_team_change, md_diff, timeout)
            futures["rt_drift"] = pool.submit(run_red_team_drift, md_diff, instruction_stack, timeout)
        results = {k: f.result() for k, f in futures.items()}

    code_review: CodeReviewResult | None = results.get("code_review")
    rt_change: RedTeamResult | None = results.get("rt_change")
    rt_drift: RedTeamResult | None = results.get("rt_drift")

    # Emit warnings for non-blocking timeouts/errors
    if code_review and (code_review.timed_out or code_review.error) and not code_review.blocks:
        print(f"⚠  Code review {'timed out' if code_review.timed_out else 'errored'} — warnings only (set REVIEW_BLOCK_ON_TIMEOUT=1 to block)", file=sys.stderr)
    for rt in [rt_change, rt_drift]:
        if rt and (rt.timed_out or rt.error) and not rt.blocks:
            print(f"⚠  Red-team ({rt.pass_name}) {'timed out' if rt.timed_out else 'errored'} — warnings only", file=sys.stderr)

    # Determine block
    blocked = False
    block_reasons = []
    if code_review and code_review.blocks:
        if code_review.timed_out:
            block_reasons.append("code review timed out (fail-safe)")
        elif code_review.error:
            block_reasons.append(f"code review error: {code_review.error}")
        else:
            high_plus = [f for f in code_review.findings if f.severity.value >= 3]
            block_reasons.append(
                f"code review found {len(high_plus)} HIGH/CRITICAL finding(s)"
            )
        blocked = True
    for rt in [rt_change, rt_drift]:
        if rt and rt.blocks:
            if rt.timed_out:
                block_reasons.append(f"red-team ({rt.pass_name}) timed out (fail-safe)")
            elif rt.error:
                block_reasons.append(f"red-team ({rt.pass_name}) error: {rt.error}")
            elif rt.severity.value >= 3:
                block_reasons.append(f"red-team ({rt.pass_name}) severity {rt.severity}")
            elif rt.compaction_cycles is not None and rt.compaction_cycles <= 2:
                block_reasons.append(
                    f"red-team ({rt.pass_name}) compaction vulnerability: {rt.compaction_cycles} cycles"
                )
            blocked = True

    block_reason = "; ".join(block_reasons)
    elapsed = time.monotonic() - start

    report_path = write_report(
        repo, branch, push_sha, elapsed,
        blocked, block_reason,
        code_review, rt_change, rt_drift,
    )
    print_terminal_summary(blocked, block_reason, code_review, rt_change, rt_drift, report_path)

    return 1 if blocked else 0


if __name__ == "__main__":
    sys.exit(main())