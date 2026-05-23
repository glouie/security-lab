from __future__ import annotations
import os
from dataclasses import dataclass, field
from enum import IntEnum
from typing import List, Optional

# Set REVIEW_BLOCK_ON_TIMEOUT=1 to re-enable strict fail-safe (e.g. in CI).
# Default: timeout warns but does not block.
BLOCK_ON_TIMEOUT = os.environ.get("REVIEW_BLOCK_ON_TIMEOUT", "0") == "1"


class Severity(IntEnum):
    INFO = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4

    @classmethod
    def parse(cls, text: str) -> "Severity":
        mapping = {
            "critical": cls.CRITICAL,
            "high": cls.HIGH,
            "medium": cls.MEDIUM,
            "low": cls.LOW,
            "info": cls.INFO,
        }
        return mapping.get(text.strip().lower(), cls.MEDIUM)

    def __str__(self) -> str:
        return self.name


@dataclass
class Finding:
    severity: Severity
    file: str
    description: str


@dataclass
class CodeReviewResult:
    findings: List[Finding] = field(default_factory=list)
    raw_output: str = ""
    timed_out: bool = False
    error: Optional[str] = None

    @property
    def max_severity(self) -> Optional[Severity]:
        return max((f.severity for f in self.findings), default=None)

    @property
    def blocks(self) -> bool:
        # Timeout/error only block when strict mode is enabled (e.g. CI).
        # Locally they warn and let the push through.
        if self.timed_out or self.error:
            return BLOCK_ON_TIMEOUT
        return any(f.severity >= Severity.HIGH for f in self.findings)


@dataclass
class RedTeamResult:
    pass_name: str  # "change" or "drift"
    severity: Severity = Severity.INFO
    compaction_cycles: Optional[int] = None
    summary: str = ""
    raw_output: str = ""
    timed_out: bool = False
    error: Optional[str] = None

    @property
    def blocks(self) -> bool:
        # Timeout/error only block in strict mode.
        if self.timed_out or self.error:
            return BLOCK_ON_TIMEOUT
        if self.severity >= Severity.HIGH:
            return True
        # Missing compaction cycles treated as unknown — only block in strict mode.
        if self.pass_name == "drift" and self.compaction_cycles is None:
            return BLOCK_ON_TIMEOUT
        if self.compaction_cycles is not None and self.compaction_cycles <= 2:
            return True
        return False