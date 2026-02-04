# src/prevent_outage_edge_testing/gates/runner.py
"""
Gate runner - executes gates and collects results.
"""

import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from prevent_outage_edge_testing.gates.models import (
    Gate,
    GateResult,
    GateStatus,
    GateReport,
)
from prevent_outage_edge_testing.gates.definitions import ALL_GATES


class GateRunner:
    """Runs release gates and produces a report."""
    
    def __init__(
        self,
        gates: Optional[list[Gate]] = None,
        test_dir: Optional[Path] = None,
        baseline_file: Optional[Path] = None,
    ):
        self.gates = gates or ALL_GATES
        self.test_dir = test_dir or Path(".poet/generated_tests")
        self.baseline_file = baseline_file
    
    def run_gate(self, gate: Gate, context: dict[str, Any]) -> GateResult:
        """Run a single gate."""
        try:
            return gate.run(context)
        except Exception as e:
            return GateResult(
                gate_id=gate.id,
                gate_name=gate.name,
                status=GateStatus.ERROR,
                error=str(e),
            )
    
    def run_all(
        self,
        gate_ids: Optional[list[str]] = None,
        fail_fast: bool = False,
    ) -> GateReport:
        """
        Run all gates (or specified subset) and return a report.
        
        Args:
            gate_ids: Optional list of gate IDs to run. If None, runs all gates.
            fail_fast: If True, stop on first gate failure.
        
        Returns:
            GateReport with results from all gates.
        """
        start = time.perf_counter()
        timestamp = datetime.now()
        
        # Filter gates if specific IDs requested
        gates_to_run = self.gates
        if gate_ids:
            gates_to_run = [g for g in self.gates if g.id in gate_ids]
        
        # Build context
        context = {
            "test_dir": self.test_dir,
            "baseline_file": self.baseline_file,
            "timestamp": timestamp,
        }
        
        # Run each gate
        results: list[GateResult] = []
        for gate in gates_to_run:
            result = self.run_gate(gate, context)
            results.append(result)
            
            if fail_fast and result.status == GateStatus.FAILED:
                break
        
        # Determine overall status
        if any(r.status == GateStatus.ERROR for r in results):
            overall = GateStatus.ERROR
        elif any(r.status == GateStatus.FAILED for r in results):
            overall = GateStatus.FAILED
        elif all(r.status == GateStatus.SKIPPED for r in results):
            overall = GateStatus.SKIPPED
        else:
            overall = GateStatus.PASSED
        
        total_duration = (time.perf_counter() - start) * 1000
        
        return GateReport(
            timestamp=timestamp,
            overall_status=overall,
            gates=results,
            total_duration_ms=total_duration,
            metadata={
                "test_dir": str(self.test_dir),
                "baseline_file": str(self.baseline_file) if self.baseline_file else None,
                "gates_requested": gate_ids,
                "fail_fast": fail_fast,
            },
        )
    
    def run_single(self, gate_id: str) -> GateResult:
        """Run a single gate by ID."""
        for gate in self.gates:
            if gate.id == gate_id:
                context = {
                    "test_dir": self.test_dir,
                    "baseline_file": self.baseline_file,
                }
                return self.run_gate(gate, context)
        
        return GateResult(
            gate_id=gate_id,
            gate_name="Unknown",
            status=GateStatus.ERROR,
            error=f"Gate not found: {gate_id}",
        )
    
    @staticmethod
    def available_gates() -> list[dict[str, str]]:
        """List available gates."""
        return [
            {
                "id": g.id,
                "name": g.name,
                "description": g.description,
                "required": g.required,
            }
            for g in ALL_GATES
        ]
