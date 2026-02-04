#!/usr/bin/env python3
"""
demo.py - Demonstration of edge-latency-regression-observability pack.

This script demonstrates:
1. Generating synthetic latency data
2. Analyzing latency distributions
3. Detecting regressions between baseline and current
4. Generating reports

Run: python demo.py
"""

import json
import math
import random
import sys
import tempfile
from pathlib import Path

# Add snippets to path
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR / "snippets"))

from latency_analyzer import LatencyAnalyzer, LatencyStats


def generate_samples(
    count: int,
    base_latency_ms: float,
    p99_latency_ms: float,
    anomaly_rate: float = 0.01,
) -> list[int]:
    """Generate synthetic latency samples (nanoseconds)."""
    mu = math.log(base_latency_ms)
    sigma = (math.log(p99_latency_ms) - mu) / 2.326
    
    samples = []
    for _ in range(count):
        if random.random() < anomaly_rate:
            latency_ms = p99_latency_ms * 5 * random.random()
        else:
            latency_ms = random.lognormvariate(mu, sigma)
        samples.append(int(latency_ms * 1_000_000))  # Convert to ns
    
    return samples


def write_csv(samples: list[int], path: Path) -> None:
    """Write samples to CSV file."""
    with open(path, 'w') as f:
        f.write("timestamp_ns,latency_ns,event\n")
        base_ts = 1706789012000000000
        for i, latency in enumerate(samples):
            f.write(f"{base_ts + i * 1000000},{latency},request\n")


def demo_single_analysis():
    """Demonstrate analyzing a single latency file."""
    print("=" * 60)
    print("Demo 1: Single File Analysis")
    print("=" * 60)
    
    # Generate data
    samples = generate_samples(
        count=10000,
        base_latency_ms=5.0,
        p99_latency_ms=50.0,
    )
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        f.write("timestamp_ns,latency_ns,event\n")
        for i, latency in enumerate(samples):
            f.write(f"{i * 1000000},{latency},request\n")
        temp_path = Path(f.name)
    
    try:
        analyzer = LatencyAnalyzer()
        stats = analyzer.analyze_file(temp_path)
        
        print("\nGenerated 10,000 latency samples")
        print(f"Target: base=5ms, p99=50ms\n")
        analyzer.print_stats(stats)
    finally:
        temp_path.unlink()


def demo_regression_detection():
    """Demonstrate regression detection between baseline and current."""
    print("\n" + "=" * 60)
    print("Demo 2: Regression Detection")
    print("=" * 60)
    
    # Generate baseline (good performance)
    baseline_samples = generate_samples(
        count=5000,
        base_latency_ms=5.0,
        p99_latency_ms=50.0,
    )
    
    # Generate current with regression (worse performance)
    current_samples = generate_samples(
        count=5000,
        base_latency_ms=7.0,  # 40% higher base
        p99_latency_ms=80.0,  # 60% higher p99
    )
    
    with tempfile.TemporaryDirectory() as tmpdir:
        baseline_path = Path(tmpdir) / "baseline.csv"
        current_path = Path(tmpdir) / "current.csv"
        
        write_csv(baseline_samples, baseline_path)
        write_csv(current_samples, current_path)
        
        analyzer = LatencyAnalyzer()
        report = analyzer.compare(
            baseline_path=baseline_path,
            current_path=current_path,
            threshold_p50_percent=10.0,
            threshold_p95_percent=15.0,
            threshold_p99_percent=20.0,
        )
        
        print("\nBaseline: base=5ms, p99=50ms")
        print("Current:  base=7ms, p99=80ms (simulated regression)")
        print()
        print(report.report)


def demo_no_regression():
    """Demonstrate when there's no regression."""
    print("\n" + "=" * 60)
    print("Demo 3: No Regression (Within Threshold)")
    print("=" * 60)
    
    # Generate baseline
    baseline_samples = generate_samples(
        count=5000,
        base_latency_ms=5.0,
        p99_latency_ms=50.0,
    )
    
    # Generate current with minor variation (within threshold)
    current_samples = generate_samples(
        count=5000,
        base_latency_ms=5.2,  # 4% higher
        p99_latency_ms=52.0,  # 4% higher
    )
    
    with tempfile.TemporaryDirectory() as tmpdir:
        baseline_path = Path(tmpdir) / "baseline.csv"
        current_path = Path(tmpdir) / "current.csv"
        
        write_csv(baseline_samples, baseline_path)
        write_csv(current_samples, current_path)
        
        analyzer = LatencyAnalyzer()
        report = analyzer.compare(
            baseline_path=baseline_path,
            current_path=current_path,
            threshold_p99_percent=20.0,
        )
        
        print("\nBaseline: base=5.0ms, p99=50ms")
        print("Current:  base=5.2ms, p99=52ms (minor variation)")
        print()
        print(report.report)


def demo_json_output():
    """Demonstrate JSON output for CI/CD integration."""
    print("\n" + "=" * 60)
    print("Demo 4: JSON Output (for CI/CD)")
    print("=" * 60)
    
    samples = generate_samples(count=1000, base_latency_ms=5.0, p99_latency_ms=50.0)
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        f.write("timestamp_ns,latency_ns\n")
        for i, latency in enumerate(samples):
            f.write(f"{i * 1000000},{latency}\n")
        temp_path = Path(f.name)
    
    try:
        analyzer = LatencyAnalyzer()
        stats = analyzer.analyze_file(temp_path)
        
        print("\nJSON output:")
        print(json.dumps(stats.to_dict(), indent=2))
    finally:
        temp_path.unlink()


def demo_cli_usage():
    """Show CLI usage examples."""
    print("\n" + "=" * 60)
    print("CLI Usage Examples")
    print("=" * 60)
    
    print("""
# Analyze a single file
python snippets/latency_analyzer.py --current latencies.csv

# Compare baseline and current
python snippets/latency_analyzer.py \\
    --baseline baseline.csv \\
    --current current.csv

# With custom thresholds
python snippets/latency_analyzer.py \\
    --baseline baseline.csv \\
    --current current.csv \\
    --threshold-p99 20 \\
    --threshold-p95 15

# Output as JSON
python snippets/latency_analyzer.py --current latencies.csv --json

# Fail CI if regression detected
python snippets/latency_analyzer.py \\
    --baseline baseline.csv \\
    --current current.csv \\
    --fail-on-regression
""")


def demo_dtrace_info():
    """Show DTrace usage information."""
    print("\n" + "=" * 60)
    print("DTrace/bpftrace Integration")
    print("=" * 60)
    
    print("""
For real latency collection (requires root/privileged access):

# FreeBSD/macOS with DTrace:
sudo dtrace -n '
syscall::accept:return /execname == "nginx"/ {
    self->start = timestamp;
}
syscall::close:entry /self->start/ {
    printf("%d,%d\\n", timestamp, timestamp - self->start);
    self->start = 0;
}
' > latencies.csv

# Linux with bpftrace:
sudo bpftrace -e '
tracepoint:syscalls:sys_enter_accept4 /comm == "nginx"/ {
    @start[tid] = nsecs;
}
tracepoint:syscalls:sys_enter_close /@start[tid]/ {
    printf("%lld,%lld\\n", nsecs, nsecs - @start[tid]);
    delete(@start[tid]);
}
' > latencies.csv

# Then analyze:
python snippets/latency_analyzer.py --current latencies.csv
""")


def main():
    print("\n" + "=" * 60)
    print("Edge Latency Regression Observability - Demo")
    print("=" * 60)
    
    demo_single_analysis()
    demo_regression_detection()
    demo_no_regression()
    demo_json_output()
    demo_cli_usage()
    demo_dtrace_info()
    
    print("\n" + "=" * 60)
    print("Demo Complete!")
    print("=" * 60)
    print("\nSee recipes/ for detailed DTrace and bpftrace instructions.")
    print("See snippets/latency_analyzer.py for the full implementation.")


if __name__ == "__main__":
    main()
