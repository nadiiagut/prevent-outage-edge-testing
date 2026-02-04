# src/prevent_outage_edge_testing/gates/models.py
"""
Data models for release gates.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional


class GateStatus(str, Enum):
    """Status of a gate check."""
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"


@dataclass
class CheckResult:
    """Result of a single check within a gate."""
    name: str
    status: GateStatus
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status.value,
            "message": self.message,
            "details": self.details,
            "duration_ms": self.duration_ms,
        }


@dataclass
class GateResult:
    """Result of running a complete gate."""
    gate_id: str
    gate_name: str
    status: GateStatus
    checks: list[CheckResult] = field(default_factory=list)
    duration_ms: float = 0.0
    error: Optional[str] = None

    @property
    def passed_count(self) -> int:
        return sum(1 for c in self.checks if c.status == GateStatus.PASSED)

    @property
    def failed_count(self) -> int:
        return sum(1 for c in self.checks if c.status == GateStatus.FAILED)

    @property
    def skipped_count(self) -> int:
        return sum(1 for c in self.checks if c.status == GateStatus.SKIPPED)

    def to_dict(self) -> dict[str, Any]:
        return {
            "gate_id": self.gate_id,
            "gate_name": self.gate_name,
            "status": self.status.value,
            "checks": [c.to_dict() for c in self.checks],
            "passed": self.passed_count,
            "failed": self.failed_count,
            "skipped": self.skipped_count,
            "duration_ms": self.duration_ms,
            "error": self.error,
        }


@dataclass
class GateReport:
    """Complete report from running all gates."""
    timestamp: datetime
    overall_status: GateStatus
    gates: list[GateResult] = field(default_factory=list)
    total_duration_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def passed_gates(self) -> int:
        return sum(1 for g in self.gates if g.status == GateStatus.PASSED)

    @property
    def failed_gates(self) -> int:
        return sum(1 for g in self.gates if g.status == GateStatus.FAILED)

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "overall_status": self.overall_status.value,
            "summary": {
                "total_gates": len(self.gates),
                "passed": self.passed_gates,
                "failed": self.failed_gates,
                "total_duration_ms": self.total_duration_ms,
            },
            "gates": [g.to_dict() for g in self.gates],
            "metadata": self.metadata,
        }


@dataclass
class Gate:
    """Base gate definition."""
    id: str
    name: str
    description: str
    checks: list[dict[str, Any]] = field(default_factory=list)
    required: bool = True

    def run(self, context: dict[str, Any]) -> GateResult:
        """Run all checks in this gate. Override in subclasses."""
        raise NotImplementedError("Subclasses must implement run()")
