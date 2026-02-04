# Edge Latency Regression Observability

Knowledge pack for detecting and diagnosing latency regressions using system-level tracing.

## Overview

This pack provides tools for:

- **P99 Latency Tracking**: Baseline and regression detection for tail latencies
- **Syscall Attribution**: DTrace/eBPF scripts to identify slow system calls
- **Connection Timing**: TCP and TLS handshake latency measurement
- **Queue Delay Detection**: Identify request queuing bottlenecks

## Privileged vs Simulator Mode

Many tests in this pack use system tracing tools that require elevated permissions:

| Tool | Platform | Requirements | Fallback |
|------|----------|--------------|----------|
| DTrace | macOS, Solaris | root or dtrace group | Simulator |
| eBPF/bcc | Linux 4.4+ | CAP_BPF or root | Simulator |
| perf | Linux | CAP_PERFMON or root | Simulator |

**Simulator mode** generates synthetic data that follows realistic distributions, allowing you to validate test logic without elevated permissions.

```bash
# Check what's available on your system
poet init  # Shows system profile with capabilities

# Run with simulator fallback
poet build --jira-text "Track P99 latency for new endpoint"
```

## Failure Modes

| ID | Severity | Description |
|----|----------|-------------|
| `p99-latency-spike` | High | P99 exceeds threshold |
| `syscall-latency-regression` | Medium | System calls slower than baseline |
| `connection-establishment-slow` | High | TCP/TLS connection setup delays |
| `request-queuing-delay` | Medium | Requests waiting in queue |

## Snippets

### DTrace Syscall Latency (Privileged)

```d
/* syscall_latency.d - Measure syscall latencies */
syscall:::entry
/pid == $target/
{
    self->ts = timestamp;
}

syscall:::return
/self->ts/
{
    @latency[probefunc] = quantize(timestamp - self->ts);
    self->ts = 0;
}
```

### Simulator Fallback (No Privileges)

```python
# latency_simulator.py - Generates realistic latency data
import numpy as np

def simulate_latencies(n=1000, p50=10, p99_ratio=5):
    """Generate latencies following log-normal distribution."""
    sigma = np.log(p99_ratio) / 2.326  # 99th percentile z-score
    mu = np.log(p50)
    return np.random.lognormal(mu, sigma, n)
```

## Recipes

- `latency-histogram.md`: Prometheus histogram configuration
- `regression-alerts.md`: Alert rules for latency regression detection

## Usage Example

```python
from poet_latency import LatencyCollector, DTraceBackend, SimulatorBackend

# Auto-selects based on capabilities
collector = LatencyCollector.create()

with collector.trace(pid=1234):
    # Run your workload
    pass

results = collector.get_results()
print(f"P99: {results.percentile(99):.2f}ms")
```

## References

- [Brendan Gregg's DTrace Guide](https://www.brendangregg.com/dtrace.html)
- [BPF Performance Tools](https://www.brendangregg.com/bpf-performance-tools-book.html)
- [Linux perf Wiki](https://perf.wiki.kernel.org/)
