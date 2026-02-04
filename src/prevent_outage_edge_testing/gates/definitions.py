# src/prevent_outage_edge_testing/gates/definitions.py
"""
Concrete gate definitions for edge service release validation.

Each gate contains multiple checks that validate specific aspects:
1. Contract Gate - Protocol invariants
2. Cache Correctness Gate - Cache behavior validation
3. Perf Budget Gate - Performance thresholds
4. Failure Mode Gate - Error handling validation
5. Observability Gate - Required signals present
"""

import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from prevent_outage_edge_testing.gates.models import (
    Gate,
    GateResult,
    GateStatus,
    CheckResult,
)


def _run_pytest_check(
    test_pattern: str,
    test_dir: Path,
    timeout: int = 60,
) -> tuple[bool, str, dict[str, Any]]:
    """Run pytest with a specific pattern and return results."""
    cmd = [
        "python", "-m", "pytest",
        str(test_dir),
        "-k", test_pattern,
        "-v", "--tb=short",
        "-q", "--no-header",
    ]
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=test_dir.parent if test_dir.exists() else Path.cwd(),
        )
        passed = result.returncode == 0
        output = result.stdout + result.stderr
        
        # Parse test counts from output
        details = {"output": output[-500:] if len(output) > 500 else output}
        if "passed" in output:
            details["tests_found"] = True
        
        return passed, output, details
    except subprocess.TimeoutExpired:
        return False, "Test timed out", {"timeout": timeout}
    except FileNotFoundError:
        return False, "pytest not found", {}
    except Exception as e:
        return False, str(e), {"error_type": type(e).__name__}


@dataclass
class ContractGate(Gate):
    """
    Gate 1: Contract Gate - Protocol Invariants
    
    Validates that the service adheres to protocol contracts:
    - HTTP status codes are correct for conditions
    - Required headers are present
    - Response formats match schemas
    - Error responses follow standards
    """
    id: str = "contract"
    name: str = "Contract Gate"
    description: str = "Validates protocol invariants and API contracts"
    required: bool = True
    
    checks: list[dict[str, Any]] = field(default_factory=lambda: [
        {
            "id": "http-status-codes",
            "name": "HTTP Status Codes",
            "description": "Verify correct status codes for all conditions",
            "test_pattern": "contract or status_code or http_response",
        },
        {
            "id": "required-headers",
            "name": "Required Headers",
            "description": "Verify required headers present (Content-Type, Cache-Control, etc.)",
            "test_pattern": "header or content_type or cache_control",
        },
        {
            "id": "response-schema",
            "name": "Response Schema",
            "description": "Validate response bodies match expected schemas",
            "test_pattern": "schema or response_body or json_valid",
        },
        {
            "id": "error-format",
            "name": "Error Response Format",
            "description": "Verify error responses follow RFC 7807 or standard format",
            "test_pattern": "error_response or error_format or problem_detail",
        },
    ])

    def run(self, context: dict[str, Any]) -> GateResult:
        start = time.perf_counter()
        results = []
        test_dir = context.get("test_dir", Path(".poet/generated_tests"))
        
        for check in self.checks:
            check_start = time.perf_counter()
            
            if not test_dir.exists():
                results.append(CheckResult(
                    name=check["name"],
                    status=GateStatus.SKIPPED,
                    message="No generated tests found",
                    duration_ms=0,
                ))
                continue
            
            passed, message, details = _run_pytest_check(
                check["test_pattern"],
                test_dir,
            )
            
            results.append(CheckResult(
                name=check["name"],
                status=GateStatus.PASSED if passed else GateStatus.FAILED,
                message=message[:200] if len(message) > 200 else message,
                details=details,
                duration_ms=(time.perf_counter() - check_start) * 1000,
            ))
        
        failed = any(r.status == GateStatus.FAILED for r in results)
        duration = (time.perf_counter() - start) * 1000
        
        return GateResult(
            gate_id=self.id,
            gate_name=self.name,
            status=GateStatus.FAILED if failed else GateStatus.PASSED,
            checks=results,
            duration_ms=duration,
        )


@dataclass
class CacheCorrectnessGate(Gate):
    """
    Gate 2: Cache Correctness Gate
    
    Validates cache behavior:
    - Cache hits/misses are correct
    - Vary headers respected
    - TTL enforcement
    - Conditional requests (If-None-Match, If-Modified-Since)
    """
    id: str = "cache"
    name: str = "Cache Correctness Gate"
    description: str = "Validates cache hit/miss behavior, headers, Vary, and TTL"
    required: bool = True
    
    checks: list[dict[str, Any]] = field(default_factory=lambda: [
        {
            "id": "cache-hit-miss",
            "name": "Cache Hit/Miss Accuracy",
            "description": "Verify cache hits and misses occur as expected",
            "test_pattern": "cache_hit or cache_miss or x_cache",
        },
        {
            "id": "vary-header",
            "name": "Vary Header Handling",
            "description": "Verify Vary header correctly splits cache entries",
            "test_pattern": "vary or accept_encoding or accept_language",
        },
        {
            "id": "ttl-expiration",
            "name": "TTL Expiration",
            "description": "Verify cached entries expire at correct time",
            "test_pattern": "ttl or max_age or expires or stale",
        },
        {
            "id": "conditional-requests",
            "name": "Conditional Requests",
            "description": "Verify If-None-Match and If-Modified-Since work",
            "test_pattern": "etag or if_none_match or if_modified or 304",
        },
        {
            "id": "cache-control-directives",
            "name": "Cache-Control Directives",
            "description": "Verify no-cache, no-store, private are honored",
            "test_pattern": "no_cache or no_store or private or must_revalidate",
        },
    ])

    def run(self, context: dict[str, Any]) -> GateResult:
        start = time.perf_counter()
        results = []
        test_dir = context.get("test_dir", Path(".poet/generated_tests"))
        
        for check in self.checks:
            check_start = time.perf_counter()
            
            if not test_dir.exists():
                results.append(CheckResult(
                    name=check["name"],
                    status=GateStatus.SKIPPED,
                    message="No generated tests found",
                    duration_ms=0,
                ))
                continue
            
            passed, message, details = _run_pytest_check(
                check["test_pattern"],
                test_dir,
            )
            
            results.append(CheckResult(
                name=check["name"],
                status=GateStatus.PASSED if passed else GateStatus.FAILED,
                message=message[:200] if len(message) > 200 else message,
                details=details,
                duration_ms=(time.perf_counter() - check_start) * 1000,
            ))
        
        failed = any(r.status == GateStatus.FAILED for r in results)
        duration = (time.perf_counter() - start) * 1000
        
        return GateResult(
            gate_id=self.id,
            gate_name=self.name,
            status=GateStatus.FAILED if failed else GateStatus.PASSED,
            checks=results,
            duration_ms=duration,
        )


@dataclass
class PerfBudgetGate(Gate):
    """
    Gate 3: Performance Budget Gate
    
    Validates performance is within acceptable bounds:
    - p95 latency within baseline + drift
    - p99 latency within baseline + drift
    - Throughput meets minimum
    - No memory leaks under load
    """
    id: str = "perf"
    name: str = "Performance Budget Gate"
    description: str = "Validates p95/p99 latency within baseline + allowed drift"
    required: bool = True
    
    p95_threshold_ms: float = 100.0
    p99_threshold_ms: float = 250.0
    allowed_drift_percent: float = 10.0
    
    checks: list[dict[str, Any]] = field(default_factory=lambda: [
        {
            "id": "p95-latency",
            "name": "P95 Latency Budget",
            "description": "P95 response time within threshold",
            "test_pattern": "latency or p95 or percentile",
        },
        {
            "id": "p99-latency",
            "name": "P99 Latency Budget",
            "description": "P99 response time within threshold",
            "test_pattern": "latency or p99 or tail_latency",
        },
        {
            "id": "throughput",
            "name": "Throughput Minimum",
            "description": "Requests per second meets minimum",
            "test_pattern": "throughput or rps or requests_per_second",
        },
        {
            "id": "memory-stability",
            "name": "Memory Stability",
            "description": "No memory growth under sustained load",
            "test_pattern": "memory or leak or resource",
        },
    ])

    def run(self, context: dict[str, Any]) -> GateResult:
        start = time.perf_counter()
        results = []
        test_dir = context.get("test_dir", Path(".poet/generated_tests"))
        baseline_file = context.get("baseline_file")
        
        # Check for baseline comparison
        if baseline_file and Path(baseline_file).exists():
            # TODO: Implement actual baseline comparison
            pass
        
        for check in self.checks:
            check_start = time.perf_counter()
            
            if not test_dir.exists():
                results.append(CheckResult(
                    name=check["name"],
                    status=GateStatus.SKIPPED,
                    message="No generated tests found",
                    duration_ms=0,
                ))
                continue
            
            passed, message, details = _run_pytest_check(
                check["test_pattern"],
                test_dir,
            )
            
            # Add threshold info to details
            if "p95" in check["id"]:
                details["threshold_ms"] = self.p95_threshold_ms
                details["allowed_drift"] = f"{self.allowed_drift_percent}%"
            elif "p99" in check["id"]:
                details["threshold_ms"] = self.p99_threshold_ms
                details["allowed_drift"] = f"{self.allowed_drift_percent}%"
            
            results.append(CheckResult(
                name=check["name"],
                status=GateStatus.PASSED if passed else GateStatus.FAILED,
                message=message[:200] if len(message) > 200 else message,
                details=details,
                duration_ms=(time.perf_counter() - check_start) * 1000,
            ))
        
        failed = any(r.status == GateStatus.FAILED for r in results)
        duration = (time.perf_counter() - start) * 1000
        
        return GateResult(
            gate_id=self.id,
            gate_name=self.name,
            status=GateStatus.FAILED if failed else GateStatus.PASSED,
            checks=results,
            duration_ms=duration,
        )


@dataclass
class FailureModeGate(Gate):
    """
    Gate 4: Failure Mode Gate
    
    Validates error handling and resilience:
    - Timeout behavior is correct
    - Retry logic works properly
    - Circuit breaker trips and recovers
    - Graceful degradation under failure
    """
    id: str = "failure"
    name: str = "Failure Mode Gate"
    description: str = "Validates timeout/retry behavior and circuit breaker"
    required: bool = True
    
    checks: list[dict[str, Any]] = field(default_factory=lambda: [
        {
            "id": "timeout-handling",
            "name": "Timeout Handling",
            "description": "Requests timeout within configured duration",
            "test_pattern": "timeout or deadline or cancel",
        },
        {
            "id": "retry-logic",
            "name": "Retry Logic",
            "description": "Failed requests retry with backoff",
            "test_pattern": "retry or backoff or attempt",
        },
        {
            "id": "circuit-breaker",
            "name": "Circuit Breaker",
            "description": "Circuit breaker opens on failures, recovers",
            "test_pattern": "circuit or breaker or open or half_open",
        },
        {
            "id": "graceful-degradation",
            "name": "Graceful Degradation",
            "description": "Service degrades gracefully under failure",
            "test_pattern": "degrade or fallback or failover",
        },
        {
            "id": "error-propagation",
            "name": "Error Propagation",
            "description": "Errors propagate correctly without cascade",
            "test_pattern": "cascade or propagat or isolat",
        },
    ])

    def run(self, context: dict[str, Any]) -> GateResult:
        start = time.perf_counter()
        results = []
        test_dir = context.get("test_dir", Path(".poet/generated_tests"))
        
        for check in self.checks:
            check_start = time.perf_counter()
            
            if not test_dir.exists():
                results.append(CheckResult(
                    name=check["name"],
                    status=GateStatus.SKIPPED,
                    message="No generated tests found",
                    duration_ms=0,
                ))
                continue
            
            passed, message, details = _run_pytest_check(
                check["test_pattern"],
                test_dir,
            )
            
            results.append(CheckResult(
                name=check["name"],
                status=GateStatus.PASSED if passed else GateStatus.FAILED,
                message=message[:200] if len(message) > 200 else message,
                details=details,
                duration_ms=(time.perf_counter() - check_start) * 1000,
            ))
        
        failed = any(r.status == GateStatus.FAILED for r in results)
        duration = (time.perf_counter() - start) * 1000
        
        return GateResult(
            gate_id=self.id,
            gate_name=self.name,
            status=GateStatus.FAILED if failed else GateStatus.PASSED,
            checks=results,
            duration_ms=duration,
        )


@dataclass
class ObservabilityGate(Gate):
    """
    Gate 5: Observability Gate
    
    Validates required signals are present:
    - Logs contain required fields
    - Metrics are exposed
    - Traces propagate correctly
    - Health endpoints work
    """
    id: str = "observability"
    name: str = "Observability Gate"
    description: str = "Validates required logs, metrics, and traces are present"
    required: bool = True
    
    checks: list[dict[str, Any]] = field(default_factory=lambda: [
        {
            "id": "structured-logs",
            "name": "Structured Logging",
            "description": "Logs contain required fields (timestamp, level, request_id)",
            "test_pattern": "log or logging or structured",
        },
        {
            "id": "metrics-exposed",
            "name": "Metrics Exposed",
            "description": "Prometheus/StatsD metrics are exposed",
            "test_pattern": "metric or prometheus or counter or gauge",
        },
        {
            "id": "trace-propagation",
            "name": "Trace Propagation",
            "description": "Trace context propagates through requests",
            "test_pattern": "trace or span or traceparent or correlation",
        },
        {
            "id": "health-endpoints",
            "name": "Health Endpoints",
            "description": "Health and readiness endpoints respond correctly",
            "test_pattern": "health or ready or live or probe",
        },
        {
            "id": "error-tracking",
            "name": "Error Tracking",
            "description": "Errors are logged with stack traces",
            "test_pattern": "error_log or exception or stack_trace",
        },
    ])

    def run(self, context: dict[str, Any]) -> GateResult:
        start = time.perf_counter()
        results = []
        test_dir = context.get("test_dir", Path(".poet/generated_tests"))
        
        for check in self.checks:
            check_start = time.perf_counter()
            
            if not test_dir.exists():
                results.append(CheckResult(
                    name=check["name"],
                    status=GateStatus.SKIPPED,
                    message="No generated tests found",
                    duration_ms=0,
                ))
                continue
            
            passed, message, details = _run_pytest_check(
                check["test_pattern"],
                test_dir,
            )
            
            results.append(CheckResult(
                name=check["name"],
                status=GateStatus.PASSED if passed else GateStatus.FAILED,
                message=message[:200] if len(message) > 200 else message,
                details=details,
                duration_ms=(time.perf_counter() - check_start) * 1000,
            ))
        
        failed = any(r.status == GateStatus.FAILED for r in results)
        duration = (time.perf_counter() - start) * 1000
        
        return GateResult(
            gate_id=self.id,
            gate_name=self.name,
            status=GateStatus.FAILED if failed else GateStatus.PASSED,
            checks=results,
            duration_ms=duration,
        )


# All gates in order
ALL_GATES = [
    ContractGate(),
    CacheCorrectnessGate(),
    PerfBudgetGate(),
    FailureModeGate(),
    ObservabilityGate(),
]
