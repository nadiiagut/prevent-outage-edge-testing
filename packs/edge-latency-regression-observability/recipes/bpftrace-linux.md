# bpftrace Latency Tracing on Linux

This recipe provides bpftrace commands for measuring HTTP request latency on Linux systems when DTrace is not available.

## Prerequisites

- Linux kernel 4.9+ (5.x recommended)
- bpftrace installed (`apt install bpftrace` or `dnf install bpftrace`)
- Root access or CAP_BPF capability
- BTF (BPF Type Format) enabled kernel for best results

## Quick Start

### 1. Trace Connection Latency

```bash
# Measure time from accept() to close() for nginx
sudo bpftrace -e '
tracepoint:syscalls:sys_enter_accept4 /comm == "nginx"/ {
    @start[tid] = nsecs;
}

tracepoint:syscalls:sys_exit_accept4 /@start[tid]/ {
    @conn_fd[tid] = args->ret;
}

tracepoint:syscalls:sys_enter_close /comm == "nginx" && @conn_fd[tid] == args->fd/ {
    @latency_ns = hist(nsecs - @start[tid]);
    delete(@start[tid]);
    delete(@conn_fd[tid]);
}

interval:s:10 { print(@latency_ns); clear(@latency_ns); }
'
```

### 2. Read/Write Syscall Latency

```bash
# Track I/O latency by syscall type
sudo bpftrace -e '
tracepoint:syscalls:sys_enter_read,
tracepoint:syscalls:sys_enter_write /comm == "nginx"/ {
    @io_start[tid] = nsecs;
    @io_name[tid] = probe;
}

tracepoint:syscalls:sys_exit_read,
tracepoint:syscalls:sys_exit_write /@io_start[tid]/ {
    @io_latency[@io_name[tid]] = hist(nsecs - @io_start[tid]);
    delete(@io_start[tid]);
    delete(@io_name[tid]);
}

interval:s:5 { print(@io_latency); }
'
```

### 3. CSV Output for Analysis

```bash
#!/usr/bin/env bash
# bpftrace_latency_csv.sh - Output latency samples as CSV
# Usage: ./bpftrace_latency_csv.sh nginx 60 > latencies.csv

PROC=${1:-nginx}
DURATION=${2:-60}

echo "timestamp_ns,latency_ns,event"

sudo bpftrace -e "
tracepoint:syscalls:sys_enter_accept4 /comm == \"$PROC\"/ {
    @accept_start[tid] = nsecs;
}

tracepoint:syscalls:sys_exit_accept4 /@accept_start[tid]/ {
    @conn_start[args->ret] = @accept_start[tid];
    delete(@accept_start[tid]);
}

tracepoint:syscalls:sys_enter_close /comm == \"$PROC\" && @conn_start[args->fd]/ {
    \$latency = nsecs - @conn_start[args->fd];
    printf(\"%lld,%lld,connection\\n\", nsecs, \$latency);
    delete(@conn_start[args->fd]);
}

interval:s:$DURATION { exit(); }
" 2>/dev/null
```

## Advanced Scripts

### HTTP Request Timing with TCP States

```bash
#!/usr/bin/env bpftrace
/* tcp_http_latency.bt - Track TCP connection lifecycle */

#include <net/sock.h>

kprobe:tcp_v4_connect {
    @connect_start[tid] = nsecs;
}

kretprobe:tcp_v4_connect /@connect_start[tid]/ {
    @tcp_connect_latency = hist(nsecs - @connect_start[tid]);
    delete(@connect_start[tid]);
}

kprobe:tcp_sendmsg {
    @send_start[tid] = nsecs;
}

kretprobe:tcp_sendmsg /@send_start[tid]/ {
    @tcp_send_latency = hist(nsecs - @send_start[tid]);
    delete(@send_start[tid]);
}

kprobe:tcp_recvmsg {
    @recv_start[tid] = nsecs;
}

kretprobe:tcp_recvmsg /@recv_start[tid]/ {
    @tcp_recv_latency = hist(nsecs - @recv_start[tid]);
    delete(@recv_start[tid]);
}

interval:s:10 {
    print(@tcp_connect_latency);
    print(@tcp_send_latency);
    print(@tcp_recv_latency);
    clear(@tcp_connect_latency);
    clear(@tcp_send_latency);
    clear(@tcp_recv_latency);
}
```

### Userspace Function Tracing (USDT)

```bash
# If application has USDT probes
sudo bpftrace -e '
usdt:/path/to/app:request_start {
    @req_start[arg0] = nsecs;
}

usdt:/path/to/app:request_end /@req_start[arg0]/ {
    @request_latency = hist(nsecs - @req_start[arg0]);
    delete(@req_start[arg0]);
}

interval:s:5 { print(@request_latency); }
'
```

### Per-Connection Latency with Client IP

```bash
sudo bpftrace -e '
#include <linux/socket.h>
#include <net/sock.h>

kprobe:inet_csk_accept {
    @accept_time[tid] = nsecs;
}

kretprobe:inet_csk_accept /@accept_time[tid]/ {
    $sk = (struct sock *)retval;
    $daddr = ntop($sk->__sk_common.skc_daddr);
    @conn_info[retval] = ($daddr, @accept_time[tid]);
    delete(@accept_time[tid]);
}

kprobe:tcp_close {
    $sk = (struct sock *)arg0;
    $info = @conn_info[$sk];
    if ($info.1 > 0) {
        $latency = nsecs - $info.1;
        printf("%s,%lld\n", $info.0, $latency);
        delete(@conn_info[$sk]);
    }
}
'
```

## Collecting Data for Regression Testing

```bash
# Collect baseline (5 minutes, production traffic)
./bpftrace_latency_csv.sh nginx 300 > baseline_latencies.csv

# Run test scenario
./bpftrace_latency_csv.sh nginx 300 > test_latencies.csv

# Analyze with Python tool
python latency_analyzer.py \
    --baseline baseline_latencies.csv \
    --current test_latencies.csv \
    --threshold-p99 20  # Fail if p99 regresses >20%
```

## Integration with pytest

```python
import subprocess
import tempfile
import threading
from pathlib import Path

class BpftraceLatencyCollector:
    """Collect latencies using bpftrace during test execution."""
    
    def __init__(self, process: str = "nginx"):
        self.process = process
        self._output_file = None
        self._proc = None
        
    def __enter__(self):
        self._output_file = tempfile.NamedTemporaryFile(
            mode='w', suffix='.csv', delete=False
        )
        self._output_file.write("timestamp_ns,latency_ns\n")
        
        script = f'''
        tracepoint:syscalls:sys_enter_accept4 /comm == "{self.process}"/ {{
            @start[tid] = nsecs;
        }}
        tracepoint:syscalls:sys_exit_accept4 /@start[tid]/ {{
            @fd[args->ret] = @start[tid];
            delete(@start[tid]);
        }}
        tracepoint:syscalls:sys_enter_close /comm == "{self.process}" && @fd[args->fd]/ {{
            printf("%lld,%lld\\n", nsecs, nsecs - @fd[args->fd]);
            delete(@fd[args->fd]);
        }}
        '''
        
        self._proc = subprocess.Popen(
            ['sudo', 'bpftrace', '-e', script],
            stdout=self._output_file,
            stderr=subprocess.DEVNULL,
        )
        return self
    
    def __exit__(self, *args):
        if self._proc:
            self._proc.terminate()
            self._proc.wait(timeout=5)
        if self._output_file:
            self._output_file.close()
    
    @property
    def output_path(self) -> Path:
        return Path(self._output_file.name) if self._output_file else None


# Usage in pytest
def test_latency_under_load(bpftrace_collector):
    with BpftraceLatencyCollector("nginx") as collector:
        # Run load test
        run_load_test(duration=60, rps=1000)
    
    # Analyze results
    from latency_analyzer import LatencyAnalyzer
    analyzer = LatencyAnalyzer()
    stats = analyzer.analyze_file(collector.output_path)
    
    assert stats.p99_ms < 100, f"P99 latency {stats.p99_ms}ms exceeds 100ms"
```

## Troubleshooting

### "bpftrace: command not found"
```bash
# Ubuntu/Debian
sudo apt install bpftrace

# Fedora/RHEL
sudo dnf install bpftrace

# Build from source if needed
git clone https://github.com/iovisor/bpftrace
cd bpftrace && mkdir build && cd build
cmake .. && make && sudo make install
```

### "ERROR: Could not resolve symbol"
Ensure kernel headers and BTF are available:
```bash
# Check BTF support
ls /sys/kernel/btf/vmlinux

# Install kernel headers
sudo apt install linux-headers-$(uname -r)
```

### Permission Denied
```bash
# Run with sudo or add CAP_BPF
sudo setcap cap_bpf,cap_perfmon+ep /usr/bin/bpftrace
```

## See Also

- `dtrace-freebsd.md` - FreeBSD alternative using DTrace
- `simulation-mode.md` - Fallback without kernel tracing
- `latency_analyzer.py` - Python statistical analysis tool
