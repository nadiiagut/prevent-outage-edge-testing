#!/usr/bin/env python3
"""
latency_analyzer.py - Latency regression detection tool.

Reads latency samples from CSV or JSON lines, computes percentiles,
compares against baseline, and reports regressions.

Usage:
    # Analyze single file
    python latency_analyzer.py --current latencies.csv
    
    # Compare with baseline
    python latency_analyzer.py --baseline baseline.csv --current current.csv
    
    # Set regression thresholds
    python latency_analyzer.py --baseline baseline.csv --current current.csv \
        --threshold-p50 10 --threshold-p95 15 --threshold-p99 20
    
    # Output as JSON
    python latency_analyzer.py --current latencies.csv --json
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import TextIO


@dataclass
class LatencyStats:
    """Statistical summary of latency samples."""
    
    count: int = 0
    min_ns: int = 0
    max_ns: int = 0
    mean_ns: float = 0.0
    stddev_ns: float = 0.0
    p50_ns: int = 0
    p90_ns: int = 0
    p95_ns: int = 0
    p99_ns: int = 0
    p999_ns: int = 0
    
    @property
    def min_ms(self) -> float:
        return self.min_ns / 1_000_000
    
    @property
    def max_ms(self) -> float:
        return self.max_ns / 1_000_000
    
    @property
    def mean_ms(self) -> float:
        return self.mean_ns / 1_000_000
    
    @property
    def stddev_ms(self) -> float:
        return self.stddev_ns / 1_000_000
    
    @property
    def p50_ms(self) -> float:
        return self.p50_ns / 1_000_000
    
    @property
    def p90_ms(self) -> float:
        return self.p90_ns / 1_000_000
    
    @property
    def p95_ms(self) -> float:
        return self.p95_ns / 1_000_000
    
    @property
    def p99_ms(self) -> float:
        return self.p99_ns / 1_000_000
    
    @property
    def p999_ms(self) -> float:
        return self.p999_ns / 1_000_000
    
    def to_dict(self) -> dict:
        return {
            "count": self.count,
            "min_ms": round(self.min_ms, 3),
            "max_ms": round(self.max_ms, 3),
            "mean_ms": round(self.mean_ms, 3),
            "stddev_ms": round(self.stddev_ms, 3),
            "p50_ms": round(self.p50_ms, 3),
            "p90_ms": round(self.p90_ms, 3),
            "p95_ms": round(self.p95_ms, 3),
            "p99_ms": round(self.p99_ms, 3),
            "p999_ms": round(self.p999_ms, 3),
        }


@dataclass
class RegressionResult:
    """Result of regression comparison."""
    
    metric: str
    baseline_ms: float
    current_ms: float
    change_percent: float
    threshold_percent: float
    is_regression: bool
    
    def to_dict(self) -> dict:
        return {
            "metric": self.metric,
            "baseline_ms": round(self.baseline_ms, 3),
            "current_ms": round(self.current_ms, 3),
            "change_percent": round(self.change_percent, 2),
            "threshold_percent": self.threshold_percent,
            "is_regression": self.is_regression,
        }


@dataclass
class ComparisonReport:
    """Full comparison report between baseline and current."""
    
    baseline_stats: LatencyStats
    current_stats: LatencyStats
    regressions: list[RegressionResult] = field(default_factory=list)
    
    @property
    def has_regression(self) -> bool:
        return any(r.is_regression for r in self.regressions)
    
    @property
    def report(self) -> str:
        """Generate human-readable report."""
        lines = []
        lines.append("=" * 60)
        lines.append("LATENCY REGRESSION REPORT")
        lines.append("=" * 60)
        lines.append("")
        
        # Stats comparison table
        lines.append("Statistics Comparison:")
        lines.append("-" * 60)
        lines.append(f"{'Metric':<12} {'Baseline':>12} {'Current':>12} {'Change':>12}")
        lines.append("-" * 60)
        
        metrics = [
            ("Count", self.baseline_stats.count, self.current_stats.count),
            ("Min", f"{self.baseline_stats.min_ms:.2f}ms", f"{self.current_stats.min_ms:.2f}ms"),
            ("Mean", f"{self.baseline_stats.mean_ms:.2f}ms", f"{self.current_stats.mean_ms:.2f}ms"),
            ("P50", f"{self.baseline_stats.p50_ms:.2f}ms", f"{self.current_stats.p50_ms:.2f}ms"),
            ("P90", f"{self.baseline_stats.p90_ms:.2f}ms", f"{self.current_stats.p90_ms:.2f}ms"),
            ("P95", f"{self.baseline_stats.p95_ms:.2f}ms", f"{self.current_stats.p95_ms:.2f}ms"),
            ("P99", f"{self.baseline_stats.p99_ms:.2f}ms", f"{self.current_stats.p99_ms:.2f}ms"),
            ("P99.9", f"{self.baseline_stats.p999_ms:.2f}ms", f"{self.current_stats.p999_ms:.2f}ms"),
            ("Max", f"{self.baseline_stats.max_ms:.2f}ms", f"{self.current_stats.max_ms:.2f}ms"),
        ]
        
        for name, baseline, current in metrics:
            if isinstance(baseline, int):
                change = ""
            else:
                b = float(baseline.replace("ms", ""))
                c = float(current.replace("ms", ""))
                if b > 0:
                    pct = ((c - b) / b) * 100
                    change = f"{pct:+.1f}%"
                else:
                    change = "N/A"
            lines.append(f"{name:<12} {str(baseline):>12} {str(current):>12} {change:>12}")
        
        lines.append("")
        
        # Regression results
        if self.regressions:
            lines.append("Regression Check Results:")
            lines.append("-" * 60)
            
            for r in self.regressions:
                status = "❌ FAIL" if r.is_regression else "✓ PASS"
                lines.append(
                    f"  {r.metric}: {r.baseline_ms:.2f}ms → {r.current_ms:.2f}ms "
                    f"({r.change_percent:+.1f}%, threshold: {r.threshold_percent}%) [{status}]"
                )
            
            lines.append("")
        
        # Final verdict
        if self.has_regression:
            lines.append("❌ REGRESSION DETECTED")
        else:
            lines.append("✓ NO REGRESSION")
        
        lines.append("=" * 60)
        
        return "\n".join(lines)
    
    def to_dict(self) -> dict:
        return {
            "baseline": self.baseline_stats.to_dict(),
            "current": self.current_stats.to_dict(),
            "regressions": [r.to_dict() for r in self.regressions],
            "has_regression": self.has_regression,
        }


class LatencyAnalyzer:
    """Analyzes latency data and detects regressions."""
    
    def __init__(self):
        self._samples: list[int] = []
    
    def read_csv(self, path: Path) -> list[int]:
        """Read latency samples from CSV file."""
        samples = []
        with open(path, newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Support various column names
                latency = None
                for col in ['latency_ns', 'latency', 'duration_ns', 'duration']:
                    if col in row:
                        latency = int(row[col])
                        break
                if latency is not None:
                    samples.append(latency)
        return samples
    
    def read_jsonl(self, path: Path) -> list[int]:
        """Read latency samples from JSON lines file."""
        samples = []
        with open(path) as f:
            for line in f:
                if line.strip():
                    data = json.loads(line)
                    for key in ['latency_ns', 'latency', 'duration_ns', 'duration']:
                        if key in data:
                            samples.append(int(data[key]))
                            break
        return samples
    
    def read_file(self, path: Path) -> list[int]:
        """Auto-detect format and read latency samples."""
        suffix = path.suffix.lower()
        if suffix in ('.jsonl', '.ndjson'):
            return self.read_jsonl(path)
        elif suffix == '.json':
            # Try JSONL first, fall back to array
            try:
                return self.read_jsonl(path)
            except json.JSONDecodeError:
                with open(path) as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        return [int(d.get('latency_ns', d.get('latency', 0))) for d in data]
        else:
            return self.read_csv(path)
        return []
    
    def compute_stats(self, samples: list[int]) -> LatencyStats:
        """Compute statistical summary of latency samples."""
        if not samples:
            return LatencyStats()
        
        sorted_samples = sorted(samples)
        n = len(sorted_samples)
        
        # Basic stats
        total = sum(sorted_samples)
        mean = total / n
        
        # Standard deviation
        variance = sum((x - mean) ** 2 for x in sorted_samples) / n
        stddev = math.sqrt(variance)
        
        # Percentile function
        def percentile(p: float) -> int:
            idx = int(p / 100 * (n - 1))
            return sorted_samples[idx]
        
        return LatencyStats(
            count=n,
            min_ns=sorted_samples[0],
            max_ns=sorted_samples[-1],
            mean_ns=mean,
            stddev_ns=stddev,
            p50_ns=percentile(50),
            p90_ns=percentile(90),
            p95_ns=percentile(95),
            p99_ns=percentile(99),
            p999_ns=percentile(99.9),
        )
    
    def analyze_file(self, path: Path) -> LatencyStats:
        """Analyze a single latency file."""
        samples = self.read_file(path)
        return self.compute_stats(samples)
    
    def compare(
        self,
        baseline_path: Path,
        current_path: Path,
        threshold_p50_percent: float = 10.0,
        threshold_p90_percent: float = 15.0,
        threshold_p95_percent: float = 15.0,
        threshold_p99_percent: float = 20.0,
    ) -> ComparisonReport:
        """Compare current latencies against baseline."""
        baseline_samples = self.read_file(baseline_path)
        current_samples = self.read_file(current_path)
        
        baseline_stats = self.compute_stats(baseline_samples)
        current_stats = self.compute_stats(current_samples)
        
        regressions = []
        
        # Check each metric against threshold
        checks = [
            ("P50", baseline_stats.p50_ms, current_stats.p50_ms, threshold_p50_percent),
            ("P90", baseline_stats.p90_ms, current_stats.p90_ms, threshold_p90_percent),
            ("P95", baseline_stats.p95_ms, current_stats.p95_ms, threshold_p95_percent),
            ("P99", baseline_stats.p99_ms, current_stats.p99_ms, threshold_p99_percent),
        ]
        
        for metric, baseline, current, threshold in checks:
            if baseline > 0:
                change_percent = ((current - baseline) / baseline) * 100
            else:
                change_percent = 0.0
            
            is_regression = change_percent > threshold
            
            regressions.append(RegressionResult(
                metric=metric,
                baseline_ms=baseline,
                current_ms=current,
                change_percent=change_percent,
                threshold_percent=threshold,
                is_regression=is_regression,
            ))
        
        return ComparisonReport(
            baseline_stats=baseline_stats,
            current_stats=current_stats,
            regressions=regressions,
        )
    
    def print_stats(self, stats: LatencyStats, output: TextIO = sys.stdout) -> None:
        """Print statistics in human-readable format."""
        output.write("Latency Statistics:\n")
        output.write(f"  Count:  {stats.count:,}\n")
        output.write(f"  Min:    {stats.min_ms:.3f} ms\n")
        output.write(f"  Mean:   {stats.mean_ms:.3f} ms\n")
        output.write(f"  Stddev: {stats.stddev_ms:.3f} ms\n")
        output.write(f"  P50:    {stats.p50_ms:.3f} ms\n")
        output.write(f"  P90:    {stats.p90_ms:.3f} ms\n")
        output.write(f"  P95:    {stats.p95_ms:.3f} ms\n")
        output.write(f"  P99:    {stats.p99_ms:.3f} ms\n")
        output.write(f"  P99.9:  {stats.p999_ms:.3f} ms\n")
        output.write(f"  Max:    {stats.max_ms:.3f} ms\n")


def main():
    parser = argparse.ArgumentParser(
        description="Analyze latency samples and detect regressions."
    )
    parser.add_argument(
        "--baseline", "-b", type=Path,
        help="Baseline latency file (CSV or JSONL)"
    )
    parser.add_argument(
        "--current", "-c", type=Path, required=True,
        help="Current latency file to analyze"
    )
    parser.add_argument(
        "--threshold-p50", type=float, default=10.0,
        help="P50 regression threshold percentage (default: 10)"
    )
    parser.add_argument(
        "--threshold-p90", type=float, default=15.0,
        help="P90 regression threshold percentage (default: 15)"
    )
    parser.add_argument(
        "--threshold-p95", type=float, default=15.0,
        help="P95 regression threshold percentage (default: 15)"
    )
    parser.add_argument(
        "--threshold-p99", type=float, default=20.0,
        help="P99 regression threshold percentage (default: 20)"
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Output as JSON"
    )
    parser.add_argument(
        "--fail-on-regression", action="store_true",
        help="Exit with code 1 if regression detected"
    )
    
    args = parser.parse_args()
    
    analyzer = LatencyAnalyzer()
    
    if args.baseline:
        # Comparison mode
        report = analyzer.compare(
            baseline_path=args.baseline,
            current_path=args.current,
            threshold_p50_percent=args.threshold_p50,
            threshold_p90_percent=args.threshold_p90,
            threshold_p95_percent=args.threshold_p95,
            threshold_p99_percent=args.threshold_p99,
        )
        
        if args.json:
            print(json.dumps(report.to_dict(), indent=2))
        else:
            print(report.report)
        
        if args.fail_on_regression and report.has_regression:
            sys.exit(1)
    else:
        # Single file analysis
        stats = analyzer.analyze_file(args.current)
        
        if args.json:
            print(json.dumps(stats.to_dict(), indent=2))
        else:
            analyzer.print_stats(stats)


if __name__ == "__main__":
    main()
