from __future__ import annotations
import re
import subprocess
from .models import CodeReviewResult, Finding, Severity


_FINDING_RE = re.compile(
    r"(?P<severity>CRITICAL|HIGH|MEDIUM|LOW|INFO)[:\s]+(?P<file>[^\s:]+)?[:\s]*(?P<desc>.+)",
    re.IGNORECASE,
)


def parse_findings(output: str) -> list[Finding]:
    findings = []
    for line in output.splitlines():
        m = _FINDING_RE.search(line)
        if m:
            findings.append(Finding(
                severity=Severity.parse(m.group("severity")),
                file=m.group("file") or "",
                description=m.group("desc").strip(),
            ))
    return findings


def run_code_review(upstream_sha: str, timeout: int) -> CodeReviewResult:
    try:
        result = subprocess.run(
            ["codex", "review", "--base", upstream_sha],
            capture_output=True, text=True, timeout=timeout,
        )
        output = result.stdout + result.stderr
        findings = parse_findings(output)
        return CodeReviewResult(findings=findings, raw_output=output)
    except subprocess.TimeoutExpired:
        return CodeReviewResult(timed_out=True, raw_output="[timed out]")
    except FileNotFoundError:
        return CodeReviewResult(error="codex not found on PATH", raw_output="")
    except Exception as e:
        return CodeReviewResult(error=str(e), raw_output="")
