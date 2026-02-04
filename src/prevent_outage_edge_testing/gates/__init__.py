# src/prevent_outage_edge_testing/gates/__init__.py
"""
Release Gates Module.

Defines 5 gates for edge service release validation:
1. Contract gate - Protocol invariants
2. Cache correctness gate - Hit/miss, headers, vary, TTL
3. Perf budget gate - p95/p99 within baseline + drift
4. Failure-mode gate - Timeouts/retries, circuit breaker
5. Observability gate - Required signals present
"""

from prevent_outage_edge_testing.gates.models import (
    Gate,
    GateResult,
    GateStatus,
    GateReport,
    CheckResult,
)
from prevent_outage_edge_testing.gates.definitions import (
    ContractGate,
    CacheCorrectnessGate,
    PerfBudgetGate,
    FailureModeGate,
    ObservabilityGate,
    ALL_GATES,
)
from prevent_outage_edge_testing.gates.runner import GateRunner
from prevent_outage_edge_testing.gates.reporter import ReportGenerator

__all__ = [
    "Gate",
    "GateResult",
    "GateStatus",
    "GateReport",
    "CheckResult",
    "ContractGate",
    "CacheCorrectnessGate",
    "PerfBudgetGate",
    "FailureModeGate",
    "ObservabilityGate",
    "ALL_GATES",
    "GateRunner",
    "ReportGenerator",
]
