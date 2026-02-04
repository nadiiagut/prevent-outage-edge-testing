# latency_simulator.py
# Safe fallback simulator for latency data when privileged access unavailable.
"""
Generates realistic latency distributions for testing without DTrace/eBPF.

This simulator produces data that follows common latency patterns:
- Log-normal distribution (typical for most services)
- Bimodal distribution (cache hit/miss scenarios)
- With configurable tail latency characteristics

Usage:
    sim = LatencySimulator(p50_ms=10, p99_ms=100)
    latencies = sim.generate(n=1000)
    
    # Or use the collector interface matching privileged version
    collector = SimulatorLatencyCollector()
    with collector.trace():
        time.sleep(5)  # Simulates workload
    results = collector.get_results()
"""

import random
import math
import time
from dataclasses import dataclass, field
from typing import Optional
from contextlib import contextmanager


@dataclass
class LatencyResults:
    """Results from latency collection."""
    
    samples: list[float] = field(default_factory=list)
    start_time: float = 0.0
    end_time: float = 0.0
    syscall_breakdown: dict[str, list[float]] = field(default_factory=dict)
    
    def percentile(self, p: float) -> float:
        """Calculate percentile from samples."""
        if not self.samples:
            return 0.0
        sorted_samples = sorted(self.samples)
        idx = int(len(sorted_samples) * p / 100)
        return sorted_samples[min(idx, len(sorted_samples) - 1)]
    
    @property
    def p50(self) -> float:
        return self.percentile(50)
    
    @property
    def p95(self) -> float:
        return self.percentile(95)
    
    @property
    def p99(self) -> float:
        return self.percentile(99)
    
    @property
    def mean(self) -> float:
        return sum(self.samples) / len(self.samples) if self.samples else 0.0
    
    @property
    def duration_seconds(self) -> float:
        return self.end_time - self.start_time


class LatencySimulator:
    """Generates realistic latency distributions."""
    
    def __init__(
        self,
        p50_ms: float = 10.0,
        p99_ms: float = 100.0,
        bimodal: bool = False,
        bimodal_ratio: float = 0.1,  # Fraction of slow requests
        bimodal_slow_factor: float = 10.0,  # How much slower
    ) -> None:
        """
        Initialize simulator.
        
        Args:
            p50_ms: Target 50th percentile in milliseconds
            p99_ms: Target 99th percentile in milliseconds
            bimodal: Whether to generate bimodal distribution
            bimodal_ratio: Fraction of requests in slow mode
            bimodal_slow_factor: Multiplier for slow mode latencies
        """
        self.p50_ms = p50_ms
        self.p99_ms = p99_ms
        self.bimodal = bimodal
        self.bimodal_ratio = bimodal_ratio
        self.bimodal_slow_factor = bimodal_slow_factor
        
        # Calculate log-normal parameters
        # P99/P50 ratio determines sigma
        self._sigma = math.log(p99_ms / p50_ms) / 2.326  # z-score for 99th percentile
        self._mu = math.log(p50_ms)
    
    def _sample_lognormal(self) -> float:
        """Generate a single log-normal sample."""
        return random.lognormvariate(self._mu, self._sigma)
    
    def generate(self, n: int = 1000) -> list[float]:
        """
        Generate n latency samples.
        
        Args:
            n: Number of samples to generate
            
        Returns:
            List of latency values in milliseconds
        """
        samples = []
        for _ in range(n):
            latency = self._sample_lognormal()
            
            # Apply bimodal if enabled
            if self.bimodal and random.random() < self.bimodal_ratio:
                latency *= self.bimodal_slow_factor
            
            samples.append(latency)
        
        return samples
    
    def generate_syscall_breakdown(
        self,
        n: int = 1000,
        syscalls: Optional[list[str]] = None,
    ) -> dict[str, list[float]]:
        """
        Generate latencies broken down by syscall type.
        
        Args:
            n: Number of total samples
            syscalls: List of syscall names to simulate
            
        Returns:
            Dict mapping syscall name to list of latencies (microseconds)
        """
        if syscalls is None:
            syscalls = ["read", "write", "open", "close", "stat", "mmap", "poll"]
        
        # Distribute samples across syscalls with realistic ratios
        weights = {
            "read": 0.3,
            "write": 0.2,
            "poll": 0.15,
            "stat": 0.1,
            "open": 0.08,
            "close": 0.07,
            "mmap": 0.05,
        }
        
        breakdown = {sc: [] for sc in syscalls}
        
        for _ in range(n):
            # Pick syscall based on weights
            r = random.random()
            cumulative = 0.0
            selected = syscalls[0]
            for sc in syscalls:
                cumulative += weights.get(sc, 0.1)
                if r <= cumulative:
                    selected = sc
                    break
            
            # Generate latency (in microseconds for syscalls)
            # Syscalls are typically much faster than request latency
            base_latency = self._sample_lognormal() * 10  # Scale to microseconds
            
            # Adjust based on syscall type
            if selected in ("read", "write"):
                base_latency *= 2  # I/O is slower
            elif selected in ("stat", "open"):
                base_latency *= 1.5
            
            breakdown[selected].append(base_latency)
        
        return breakdown


class SimulatorLatencyCollector:
    """
    Latency collector using simulator (no privileged access needed).
    
    Provides the same interface as privileged collectors (DTrace, eBPF)
    for testing purposes.
    """
    
    def __init__(
        self,
        p50_ms: float = 10.0,
        p99_ms: float = 100.0,
        samples_per_second: int = 100,
    ) -> None:
        self.simulator = LatencySimulator(p50_ms=p50_ms, p99_ms=p99_ms)
        self.samples_per_second = samples_per_second
        self._results: Optional[LatencyResults] = None
        self._tracing = False
    
    @contextmanager
    def trace(self, pid: Optional[int] = None):
        """
        Context manager for tracing (simulated).
        
        Args:
            pid: Ignored in simulator mode
        """
        self._tracing = True
        self._results = LatencyResults(start_time=time.time())
        
        try:
            yield
        finally:
            self._tracing = False
            self._results.end_time = time.time()
            
            # Generate samples based on trace duration
            duration = self._results.duration_seconds
            n_samples = int(duration * self.samples_per_second)
            n_samples = max(n_samples, 10)  # Minimum samples
            
            self._results.samples = self.simulator.generate(n_samples)
            self._results.syscall_breakdown = self.simulator.generate_syscall_breakdown(
                n_samples * 10  # More syscalls than requests
            )
    
    def get_results(self) -> LatencyResults:
        """Get results from last trace."""
        if self._results is None:
            raise RuntimeError("No trace has been run")
        return self._results
    
    @staticmethod
    def is_privileged() -> bool:
        """Return False - this is the simulator."""
        return False


def create_collector(
    prefer_privileged: bool = True,
    **kwargs,
) -> SimulatorLatencyCollector:
    """
    Factory to create appropriate latency collector.
    
    In a real implementation, this would check for DTrace/eBPF availability
    and return the appropriate collector. Here we always return simulator.
    """
    # In real implementation:
    # if prefer_privileged and DTraceCollector.is_available():
    #     return DTraceCollector(**kwargs)
    # elif prefer_privileged and EBPFCollector.is_available():
    #     return EBPFCollector(**kwargs)
    
    return SimulatorLatencyCollector(**kwargs)


# Example usage
if __name__ == "__main__":
    print("=== Latency Simulator Demo ===\n")
    
    # Basic simulation
    sim = LatencySimulator(p50_ms=10, p99_ms=100)
    samples = sim.generate(1000)
    
    sorted_samples = sorted(samples)
    print(f"Generated {len(samples)} samples")
    print(f"P50: {sorted_samples[500]:.2f}ms")
    print(f"P95: {sorted_samples[950]:.2f}ms")
    print(f"P99: {sorted_samples[990]:.2f}ms")
    
    # Collector interface
    print("\n=== Collector Interface Demo ===\n")
    
    collector = create_collector(p50_ms=5, p99_ms=50)
    
    with collector.trace():
        print("Simulating 2 second workload...")
        time.sleep(2)
    
    results = collector.get_results()
    print(f"Duration: {results.duration_seconds:.2f}s")
    print(f"Samples: {len(results.samples)}")
    print(f"P50: {results.p50:.2f}ms")
    print(f"P99: {results.p99:.2f}ms")
    
    print("\nSyscall breakdown:")
    for syscall, latencies in results.syscall_breakdown.items():
        if latencies:
            avg = sum(latencies) / len(latencies)
            print(f"  {syscall}: {len(latencies)} calls, avg {avg:.1f}µs")
