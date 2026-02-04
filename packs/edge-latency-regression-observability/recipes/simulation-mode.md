# Simulation Mode: Latency Analysis Without Kernel Tracing

When DTrace (FreeBSD) or bpftrace (Linux) are not available, use simulation mode to analyze latency from application logs or synthetic data.

## Use Cases

- CI/CD environments without root access
- Containers without kernel tracing capabilities
- Development machines without DTrace/BPF
- Replay analysis of historical data

## Input Formats

### CSV Format
```csv
timestamp_ns,latency_ns,event
1706789012000000000,1500000,request
1706789012001000000,2300000,request
1706789012002000000,980000,request
```

### JSON Lines Format
```json
{"timestamp_ns": 1706789012000000000, "latency_ns": 1500000, "event": "request"}
{"timestamp_ns": 1706789012001000000, "latency_ns": 2300000, "event": "request"}
```

### Application Log Format (Parsed)
```
2024-02-01T12:00:00.000Z INFO request completed in 1.5ms
2024-02-01T12:00:00.001Z INFO request completed in 2.3ms
```

## Generating Synthetic Latency Data

For testing the analyzer without real traffic:

```python
#!/usr/bin/env python3
"""generate_latency_data.py - Generate synthetic latency samples."""

import random
import time
import json
import argparse
from pathlib import Path


def generate_latency_samples(
    count: int = 10000,
    base_latency_ms: float = 5.0,
    p99_latency_ms: float = 50.0,
    anomaly_rate: float = 0.01,
    anomaly_latency_ms: float = 500.0,
) -> list[dict]:
    """
    Generate realistic latency samples with log-normal distribution.
    
    Args:
        count: Number of samples to generate
        base_latency_ms: Median latency
        p99_latency_ms: Target P99 latency
        anomaly_rate: Rate of anomalous slow requests
        anomaly_latency_ms: Latency for anomalies
    """
    import math
    
    # Calculate log-normal parameters
    mu = math.log(base_latency_ms)
    # Approximate sigma to hit p99 target
    sigma = (math.log(p99_latency_ms) - mu) / 2.326  # z-score for 99th percentile
    
    samples = []
    start_ns = int(time.time() * 1e9)
    
    for i in range(count):
        if random.random() < anomaly_rate:
            latency_ms = anomaly_latency_ms * (0.8 + random.random() * 0.4)
        else:
            latency_ms = random.lognormvariate(mu, sigma)
        
        samples.append({
            "timestamp_ns": start_ns + i * 1_000_000,  # 1ms apart
            "latency_ns": int(latency_ms * 1_000_000),
            "event": "request",
        })
    
    return samples


def write_csv(samples: list[dict], path: Path) -> None:
    """Write samples as CSV."""
    with open(path, 'w') as f:
        f.write("timestamp_ns,latency_ns,event\n")
        for s in samples:
            f.write(f"{s['timestamp_ns']},{s['latency_ns']},{s['event']}\n")


def write_jsonl(samples: list[dict], path: Path) -> None:
    """Write samples as JSON lines."""
    with open(path, 'w') as f:
        for s in samples:
            f.write(json.dumps(s) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=10000)
    parser.add_argument("--base-latency", type=float, default=5.0)
    parser.add_argument("--p99-latency", type=float, default=50.0)
    parser.add_argument("--anomaly-rate", type=float, default=0.01)
    parser.add_argument("--format", choices=["csv", "jsonl"], default="csv")
    parser.add_argument("--output", type=Path, default=Path("latencies.csv"))
    args = parser.parse_args()
    
    samples = generate_latency_samples(
        count=args.count,
        base_latency_ms=args.base_latency,
        p99_latency_ms=args.p99_latency,
        anomaly_rate=args.anomaly_rate,
    )
    
    if args.format == "csv":
        write_csv(samples, args.output)
    else:
        write_jsonl(samples, args.output)
    
    print(f"Generated {len(samples)} samples to {args.output}")
```

## Parsing Application Logs

```python
#!/usr/bin/env python3
"""parse_app_logs.py - Extract latency from application logs."""

import re
import json
from pathlib import Path
from datetime import datetime


# Common log patterns
PATTERNS = [
    # "request completed in 1.5ms"
    (r'completed in (\d+(?:\.\d+)?)(ms|µs|us|ns|s)', 'duration'),
    # "latency=1.5ms" or "latency: 1.5ms"
    (r'latency[=:]\s*(\d+(?:\.\d+)?)(ms|µs|us|ns|s)', 'latency'),
    # "response_time_ms=1.5"
    (r'response_time_ms[=:]\s*(\d+(?:\.\d+)?)', 'ms'),
    # "duration_ns=1500000"
    (r'duration_ns[=:]\s*(\d+)', 'ns'),
    # nginx: request_time=0.001
    (r'request_time[=:]\s*(\d+(?:\.\d+)?)', 's'),
]

UNIT_TO_NS = {
    's': 1_000_000_000,
    'ms': 1_000_000,
    'µs': 1_000,
    'us': 1_000,
    'ns': 1,
}


def parse_log_line(line: str) -> int | None:
    """Extract latency in nanoseconds from a log line."""
    for pattern, default_unit in PATTERNS:
        match = re.search(pattern, line, re.IGNORECASE)
        if match:
            value = float(match.group(1))
            unit = match.group(2) if match.lastindex > 1 else default_unit
            multiplier = UNIT_TO_NS.get(unit.lower(), 1_000_000)
            return int(value * multiplier)
    return None


def parse_timestamp(line: str) -> int | None:
    """Extract timestamp from log line."""
    # ISO format: 2024-02-01T12:00:00.000Z
    iso_match = re.search(r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?)', line)
    if iso_match:
        dt = datetime.fromisoformat(iso_match.group(1).rstrip('Z'))
        return int(dt.timestamp() * 1e9)
    
    # Unix timestamp
    unix_match = re.search(r'\b(\d{10}(?:\.\d+)?)\b', line)
    if unix_match:
        return int(float(unix_match.group(1)) * 1e9)
    
    return None


def parse_log_file(path: Path) -> list[dict]:
    """Parse log file and extract latency samples."""
    samples = []
    
    with open(path) as f:
        for i, line in enumerate(f):
            latency_ns = parse_log_line(line)
            if latency_ns is None:
                continue
            
            timestamp_ns = parse_timestamp(line)
            if timestamp_ns is None:
                timestamp_ns = int((datetime.now().timestamp() + i * 0.001) * 1e9)
            
            samples.append({
                "timestamp_ns": timestamp_ns,
                "latency_ns": latency_ns,
                "event": "request",
            })
    
    return samples


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument("logfile", type=Path)
    parser.add_argument("--output", "-o", type=Path, default=Path("parsed_latencies.csv"))
    args = parser.parse_args()
    
    samples = parse_log_file(args.logfile)
    
    with open(args.output, 'w') as f:
        f.write("timestamp_ns,latency_ns,event\n")
        for s in samples:
            f.write(f"{s['timestamp_ns']},{s['latency_ns']},{s['event']}\n")
    
    print(f"Parsed {len(samples)} latency samples to {args.output}")
```

## Running in Simulation Mode

```bash
# Generate baseline data (normal performance)
python generate_latency_data.py \
    --count 10000 \
    --base-latency 5.0 \
    --p99-latency 50.0 \
    --output baseline.csv

# Generate test data (simulated regression)
python generate_latency_data.py \
    --count 10000 \
    --base-latency 7.0 \
    --p99-latency 80.0 \
    --output current.csv

# Analyze for regression
python latency_analyzer.py \
    --baseline baseline.csv \
    --current current.csv \
    --threshold-p99 20
```

## Integration with pytest

```python
import pytest
from pathlib import Path

@pytest.fixture
def baseline_latencies(tmp_path):
    """Generate baseline latency data."""
    from generate_latency_data import generate_latency_samples, write_csv
    
    samples = generate_latency_samples(
        count=5000,
        base_latency_ms=5.0,
        p99_latency_ms=50.0,
    )
    path = tmp_path / "baseline.csv"
    write_csv(samples, path)
    return path


def test_latency_regression(baseline_latencies, tmp_path):
    """Test that current latencies don't regress from baseline."""
    from latency_analyzer import LatencyAnalyzer
    
    # Simulate current run (your actual test would collect real data)
    from generate_latency_data import generate_latency_samples, write_csv
    current_samples = generate_latency_samples(
        count=5000,
        base_latency_ms=5.5,  # Slight increase
        p99_latency_ms=55.0,
    )
    current_path = tmp_path / "current.csv"
    write_csv(current_samples, current_path)
    
    # Analyze
    analyzer = LatencyAnalyzer()
    result = analyzer.compare(
        baseline_path=baseline_latencies,
        current_path=current_path,
        threshold_p99_percent=20.0,
    )
    
    assert not result.has_regression, result.report
```

## See Also

- `latency_analyzer.py` - Full-featured analysis tool
- `dtrace-freebsd.md` - Real tracing on FreeBSD
- `bpftrace-linux.md` - Real tracing on Linux
