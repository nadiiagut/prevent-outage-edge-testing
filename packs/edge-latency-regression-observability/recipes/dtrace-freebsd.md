# DTrace Latency Tracing on FreeBSD

This recipe provides real DTrace commands and probes for measuring HTTP request latency on FreeBSD systems.

## Prerequisites

- FreeBSD 10+ with DTrace enabled
- Root access or `dtrace` group membership
- Target process (nginx, haproxy, varnish, or custom app)

## Quick Start

### 1. Trace HTTP Accept-to-Response Latency

```bash
# Measure time from accept() to close() for each connection
sudo dtrace -n '
syscall::accept:return /execname == "nginx"/ {
    self->start = timestamp;
    self->fd = arg1;
}

syscall::close:entry /execname == "nginx" && self->start && arg0 == self->fd/ {
    @latency["request_ns"] = quantize(timestamp - self->start);
    self->start = 0;
    self->fd = 0;
}

tick-10s { printa(@latency); trunc(@latency); }
'
```

### 2. Track Read/Write Syscall Latency

```bash
# Detailed I/O latency by syscall
sudo dtrace -n '
syscall::read:entry,syscall::write:entry /execname == "nginx"/ {
    self->io_start = timestamp;
}

syscall::read:return,syscall::write:return /self->io_start/ {
    @io[probefunc] = quantize(timestamp - self->io_start);
    self->io_start = 0;
}

tick-5s { printa(@io); }
'
```

### 3. HTTP Response Time Histogram (CSV Output)

```bash
#!/usr/bin/env bash
# dtrace_latency_csv.sh - Output latency samples as CSV
# Usage: ./dtrace_latency_csv.sh nginx 60 > latencies.csv

PROC=${1:-nginx}
DURATION=${2:-60}

echo "timestamp_ns,latency_ns,syscall"

sudo dtrace -q -n "
syscall::accept:return /execname == \"$PROC\"/ {
    self->conn_start[arg1] = timestamp;
}

syscall::close:entry /execname == \"$PROC\" && self->conn_start[arg0]/ {
    printf(\"%d,%d,connection\\n\", timestamp, timestamp - self->conn_start[arg0]);
    self->conn_start[arg0] = 0;
}

tick-${DURATION}s { exit(0); }
"
```

## Advanced Probes

### Probe: Network Stack Latency

```d
#!/usr/sbin/dtrace -s
/* net_latency.d - Track packets through network stack */

#pragma D option quiet

fbt:kernel:tcp_input:entry {
    self->tcp_in = timestamp;
}

fbt:kernel:tcp_output:entry /self->tcp_in/ {
    @tcp_latency = quantize(timestamp - self->tcp_in);
    self->tcp_in = 0;
}

profile:::tick-10s {
    printf("\n--- TCP Input->Output Latency (ns) ---\n");
    printa(@tcp_latency);
    trunc(@tcp_latency);
}
```

### Probe: Application-Level Function Timing

```d
#!/usr/sbin/dtrace -s
/* app_func_timing.d - Trace specific functions in userland */

#pragma D option quiet

pid$target::*handle_request*:entry {
    self->func_start = timestamp;
}

pid$target::*handle_request*:return /self->func_start/ {
    @func_time["handle_request_ns"] = quantize(timestamp - self->func_start);
    self->func_start = 0;
}

tick-5s { printa(@func_time); }
```

## Collecting Baseline Data

```bash
# Collect 5 minutes of baseline latency data
./dtrace_latency_csv.sh nginx 300 > baseline_latencies.csv

# Later, collect test run data
./dtrace_latency_csv.sh nginx 300 > test_latencies.csv

# Compare using the Python analyzer
python latency_analyzer.py --baseline baseline_latencies.csv --current test_latencies.csv
```

## Troubleshooting

### "dtrace: system integrity protection is on"
On systems with SIP, use specific providers:
```bash
sudo dtrace -l | grep -i nginx  # List available probes
```

### "dtrace: failed to grab pid"
Ensure the process is running and you have permissions:
```bash
pgrep nginx
sudo dtrace -p $(pgrep -o nginx) -n 'BEGIN { trace("attached"); }'
```

### High Overhead Warning
For production systems, limit probe frequency:
```d
/* Use profile provider with lower frequency */
profile:::profile-997hz /execname == "nginx"/ {
    @[ustack(5)] = count();
}
```

## Integration with Test Framework

```python
import subprocess
import tempfile
from pathlib import Path

def collect_dtrace_latencies(process: str, duration: int = 60) -> Path:
    """Collect latency samples using DTrace."""
    output = tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False)
    
    dtrace_script = f'''
    syscall::accept:return /execname == "{process}"/ {{
        self->start[arg1] = timestamp;
    }}
    syscall::close:entry /execname == "{process}" && self->start[arg0]/ {{
        printf("%d,%d\\n", timestamp, timestamp - self->start[arg0]);
        self->start[arg0] = 0;
    }}
    tick-{duration}s {{ exit(0); }}
    '''
    
    result = subprocess.run(
        ['sudo', 'dtrace', '-q', '-n', dtrace_script],
        capture_output=True,
        text=True,
        timeout=duration + 10
    )
    
    output.write("timestamp_ns,latency_ns\n")
    output.write(result.stdout)
    output.close()
    
    return Path(output.name)
```

## See Also

- [FreeBSD DTrace Guide](https://docs.freebsd.org/en/books/handbook/dtrace/)
- `bpftrace-linux.md` - Linux alternative using bpftrace
- `latency_analyzer.py` - Python tool for statistical analysis
