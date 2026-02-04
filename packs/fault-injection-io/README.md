# Fault Injection for I/O Operations

Knowledge pack for I/O fault injection using LD_PRELOAD interposition.

## Overview

This pack provides tools to inject faults into I/O operations to validate error handling:

- **Disk Errors**: EIO, ENOSPC, EROFS, EACCES
- **Network Faults**: Connection reset, timeout, partial send
- **Latency**: Inject delays into read/write operations
- **Partial I/O**: Simulate short reads and writes

## How LD_PRELOAD Injection Works

The `LD_PRELOAD` environment variable (Linux) or `DYLD_INSERT_LIBRARIES` (macOS) allows intercepting library calls:

```bash
# Linux
LD_PRELOAD=./libfaultinject.so ./my_application

# macOS
DYLD_INSERT_LIBRARIES=./libfaultinject.dylib ./my_application
```

The injected library wraps standard libc functions (`read`, `write`, `open`, etc.) and can:
- Return error codes
- Inject latency
- Modify data
- Log all calls

## Failure Modes

| ID | Severity | Description |
|----|----------|-------------|
| `disk-io-error-unhandled` | Critical | App crashes on EIO |
| `disk-full-graceful` | High | ENOSPC not handled |
| `network-timeout-cascade` | Critical | Timeouts exhaust resources |
| `partial-write-corruption` | High | Partial writes corrupt data |

## Privileged vs Simulator Mode

| Mode | Requirements | Use Case |
|------|--------------|----------|
| **LD_PRELOAD** | Linux/macOS, no root needed | Real fault injection |
| **Simulator** | None | Logic testing without actual faults |

The simulator mode uses mock objects and controlled exceptions to validate error handling paths without actually injecting faults.

## Snippets

### LD_PRELOAD Library (C)

See `snippets/fault_inject.c` - Compile and use:

```bash
gcc -shared -fPIC -o libfaultinject.so fault_inject.c -ldl
FAULT_INJECT_WRITE_EIO=0.1 LD_PRELOAD=./libfaultinject.so ./app
```

### Python Simulator

See `snippets/fault_simulator.py` - Use as:

```python
from fault_simulator import FaultInjector, DiskFault

injector = FaultInjector()
injector.add_fault(DiskFault.EIO, probability=0.1, target="/data/*")

with injector.active():
    # Your code here - write() calls may fail with EIO
    result = my_write_operation()
```

## Recipes

- `fault-injection-metrics.md`: Prometheus metrics for fault injection campaigns
- `error-rate-alerts.md`: Alerting on error handling failures

## Usage Example

```bash
# Generate tests for error handling feature
poet build --jira-text "Add graceful handling for disk full scenarios"

# View pack details
poet packs show fault-injection-io
```

## Configuration

Fault injection is configured via environment variables:

```bash
# Inject EIO on 10% of write() calls
FAULT_INJECT_WRITE_EIO=0.1

# Inject 100ms latency on all read() calls
FAULT_INJECT_READ_LATENCY_MS=100

# Only inject faults for paths matching pattern
FAULT_INJECT_PATH_PATTERN="/data/.*"

# Inject ENOSPC after 1MB written
FAULT_INJECT_ENOSPC_AFTER_BYTES=1048576
```

## Safety Considerations

1. **Never use in production** - Fault injection should only run in test environments
2. **Use path filters** - Limit injection to specific files/directories
3. **Set probability < 1.0** - Allow some operations to succeed for realistic testing
4. **Monitor closely** - Watch for unintended cascading failures
5. **Have kill switch** - Ability to instantly disable injection

## References

- [Linux LD_PRELOAD man page](https://man7.org/linux/man-pages/man8/ld.so.8.html)
- [Chaos Mesh](https://github.com/chaos-mesh/chaos-mesh)
- [LitmusChaos](https://litmuschaos.io/)
