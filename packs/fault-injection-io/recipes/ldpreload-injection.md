# LD_PRELOAD Fault Injection

This recipe provides a shared library that intercepts system calls to inject faults like EPIPE, ETIMEDOUT, ECONNRESET, and short reads.

## Overview

The `libfaultinject.so` library intercepts:
- `connect()` - Inject connection failures (ECONNREFUSED, ETIMEDOUT)
- `send()` / `write()` - Inject EPIPE, partial writes
- `recv()` / `read()` - Inject short reads, ECONNRESET
- `open()` - Inject file I/O errors (ENOENT, EACCES)

## Building the Library

### Prerequisites

```bash
# Linux
sudo apt install build-essential

# macOS
xcode-select --install

# FreeBSD
pkg install gcc
```

### Compile

```bash
# Linux
gcc -shared -fPIC -o libfaultinject.so fault_inject.c -ldl -lpthread

# macOS (uses DYLD_INSERT_LIBRARIES)
gcc -dynamiclib -o libfaultinject.dylib fault_inject.c

# FreeBSD
cc -shared -fPIC -o libfaultinject.so fault_inject.c -lpthread
```

## Configuration

The library is controlled via environment variables:

| Variable | Description | Example |
|----------|-------------|---------|
| `FAULT_INJECT_ENABLED` | Enable injection (1/0) | `1` |
| `FAULT_CONNECT_FAIL_RATE` | Probability of connect() failure (0.0-1.0) | `0.1` |
| `FAULT_CONNECT_ERRNO` | errno for connect failures | `ETIMEDOUT` |
| `FAULT_SEND_FAIL_RATE` | Probability of send() failure | `0.05` |
| `FAULT_SEND_ERRNO` | errno for send failures | `EPIPE` |
| `FAULT_RECV_SHORT_RATE` | Probability of short read | `0.1` |
| `FAULT_RECV_FAIL_RATE` | Probability of recv() failure | `0.02` |
| `FAULT_RECV_ERRNO` | errno for recv failures | `ECONNRESET` |
| `FAULT_LATENCY_MS` | Added latency (milliseconds) | `100` |
| `FAULT_TARGET_HOST` | Only affect this host (optional) | `api.example.com` |
| `FAULT_TARGET_PORT` | Only affect this port (optional) | `8080` |
| `FAULT_LOG_FILE` | Log injected faults to file | `/tmp/faults.log` |

## Usage Examples

### Inject Random Connection Timeouts

```bash
FAULT_INJECT_ENABLED=1 \
FAULT_CONNECT_FAIL_RATE=0.2 \
FAULT_CONNECT_ERRNO=ETIMEDOUT \
LD_PRELOAD=./libfaultinject.so \
python my_test.py
```

### Inject EPIPE on Send

```bash
FAULT_INJECT_ENABLED=1 \
FAULT_SEND_FAIL_RATE=0.1 \
FAULT_SEND_ERRNO=EPIPE \
LD_PRELOAD=./libfaultinject.so \
./my_application
```

### Inject Short Reads (Partial Data)

```bash
FAULT_INJECT_ENABLED=1 \
FAULT_RECV_SHORT_RATE=0.3 \
LD_PRELOAD=./libfaultinject.so \
curl http://localhost:8080/large-file
```

### Inject Connection Reset

```bash
FAULT_INJECT_ENABLED=1 \
FAULT_RECV_FAIL_RATE=0.1 \
FAULT_RECV_ERRNO=ECONNRESET \
LD_PRELOAD=./libfaultinject.so \
python test_resilience.py
```

### Add Network Latency

```bash
FAULT_INJECT_ENABLED=1 \
FAULT_LATENCY_MS=200 \
LD_PRELOAD=./libfaultinject.so \
./benchmark_client
```

### Target Specific Host/Port

```bash
FAULT_INJECT_ENABLED=1 \
FAULT_TARGET_HOST=database.local \
FAULT_TARGET_PORT=5432 \
FAULT_CONNECT_FAIL_RATE=0.5 \
LD_PRELOAD=./libfaultinject.so \
python test_db_failover.py
```

## macOS Usage

On macOS, use `DYLD_INSERT_LIBRARIES`:

```bash
FAULT_INJECT_ENABLED=1 \
FAULT_CONNECT_FAIL_RATE=0.1 \
DYLD_INSERT_LIBRARIES=./libfaultinject.dylib \
./my_application
```

Note: SIP may prevent injection into system binaries. Disable SIP for testing or use the Python wrapper alternative.

## Integration with pytest

```python
import os
import subprocess
import pytest

@pytest.fixture
def fault_injection_env():
    """Fixture providing fault injection environment."""
    return {
        "FAULT_INJECT_ENABLED": "1",
        "LD_PRELOAD": str(Path(__file__).parent / "libfaultinject.so"),
    }

def test_handles_connection_timeout(fault_injection_env):
    """Test application handles connection timeouts."""
    env = {
        **os.environ,
        **fault_injection_env,
        "FAULT_CONNECT_FAIL_RATE": "1.0",  # 100% failure
        "FAULT_CONNECT_ERRNO": "ETIMEDOUT",
    }
    
    result = subprocess.run(
        ["python", "client.py", "--connect", "api.example.com"],
        env=env,
        capture_output=True,
        text=True,
    )
    
    # Should handle gracefully, not crash
    assert result.returncode == 0
    assert "connection timeout" in result.stdout.lower() or \
           "retry" in result.stdout.lower()

def test_handles_epipe(fault_injection_env):
    """Test application handles broken pipe."""
    env = {
        **os.environ,
        **fault_injection_env,
        "FAULT_SEND_FAIL_RATE": "1.0",
        "FAULT_SEND_ERRNO": "EPIPE",
    }
    
    result = subprocess.run(
        ["python", "client.py", "--send-data"],
        env=env,
        capture_output=True,
        text=True,
    )
    
    assert result.returncode == 0
    assert "broken pipe" in result.stdout.lower() or \
           "reconnect" in result.stdout.lower()
```

## Supported Errno Values

The library recognizes these symbolic errno names:

| Name | Value | Description |
|------|-------|-------------|
| `EPIPE` | 32 | Broken pipe |
| `ECONNRESET` | 104 | Connection reset by peer |
| `ECONNREFUSED` | 111 | Connection refused |
| `ETIMEDOUT` | 110 | Connection timed out |
| `ENETUNREACH` | 101 | Network unreachable |
| `EHOSTUNREACH` | 113 | Host unreachable |
| `ENOENT` | 2 | No such file |
| `EACCES` | 13 | Permission denied |
| `EIO` | 5 | I/O error |
| `ENOSPC` | 28 | No space left |

## Logging

Enable logging to see injected faults:

```bash
FAULT_LOG_FILE=/tmp/faults.log \
FAULT_INJECT_ENABLED=1 \
FAULT_CONNECT_FAIL_RATE=0.1 \
LD_PRELOAD=./libfaultinject.so \
./my_app

# View log
tail -f /tmp/faults.log
# Output:
# [1706789012.123] INJECT connect() -> ETIMEDOUT (fd=5, addr=10.0.0.1:8080)
# [1706789012.456] INJECT recv() -> short read (fd=5, requested=4096, returned=1024)
```

## Troubleshooting

### Library not loaded
```bash
# Check library exists and is readable
ls -la libfaultinject.so
ldd libfaultinject.so  # Linux
otool -L libfaultinject.dylib  # macOS
```

### Injection not working
```bash
# Verify environment variables
env | grep FAULT

# Check if process is statically linked
file /path/to/binary  # Should say "dynamically linked"
```

### Permission denied
```bash
# Ensure library is executable
chmod +x libfaultinject.so
```

## See Also

- `fault_inject.c` - Source code for the shared library
- `socket_fault_injector.py` - Pure Python alternative
- `chaos-testing.md` - Higher-level chaos testing patterns
