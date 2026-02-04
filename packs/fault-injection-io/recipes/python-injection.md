# Python Socket Fault Injection

When LD_PRELOAD is not available, use the pure-Python `socket_fault_injector.py` module to inject faults at the Python socket level.

## When to Use Python Injection

- **macOS with SIP enabled** - System Integrity Protection blocks LD_PRELOAD for system binaries
- **Windows** - No LD_PRELOAD equivalent
- **Containers** - Some container runtimes restrict LD_PRELOAD
- **Python applications** - When you only need to test Python code
- **CI/CD pipelines** - No compilation required

## Quick Start

### Basic Usage

```python
from socket_fault_injector import FaultInjector

# Inject 10% connection failures
with FaultInjector(connect_fail_rate=0.1) as fi:
    import requests
    
    for i in range(10):
        try:
            response = requests.get("http://httpbin.org/get", timeout=5)
            print(f"Request {i}: {response.status_code}")
        except Exception as e:
            print(f"Request {i}: {e}")

print(f"\nStats: {fi.stats}")
```

### With pytest

```python
# conftest.py
import pytest
from socket_fault_injector import FaultInjector

@pytest.fixture
def fault_injector():
    """Fixture providing fault injection for tests."""
    with FaultInjector(log_injections=True) as fi:
        yield fi
    print(f"\nInjection stats: {fi.stats}")

@pytest.fixture
def connection_chaos():
    """10% connection failure rate."""
    with FaultInjector(
        connect_fail_rate=0.1,
        connect_errno=errno.ETIMEDOUT,
    ) as fi:
        yield fi

@pytest.fixture
def network_chaos():
    """Full network chaos."""
    with FaultInjector(
        connect_fail_rate=0.05,
        send_fail_rate=0.05,
        recv_fail_rate=0.05,
        recv_short_rate=0.1,
    ) as fi:
        yield fi
```

```python
# test_resilience.py
import errno

def test_handles_connection_timeout(connection_chaos):
    """Test application handles connection timeouts."""
    from myapp import Client
    
    client = Client(retry_count=3)
    
    # Should succeed despite some failures (due to retries)
    result = client.fetch_data()
    
    assert result is not None
    assert connection_chaos.stats.connect_failures > 0  # Verify injection worked

def test_handles_short_reads(network_chaos):
    """Test application handles partial data correctly."""
    from myapp import Client
    
    client = Client()
    
    # Should reassemble partial reads
    data = client.download_file("/large-file")
    
    assert len(data) == expected_size
    assert network_chaos.stats.short_reads > 0
```

## Configuration Options

### FaultInjector Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `connect_fail_rate` | float | 0.0 | Probability of connect() failure (0.0-1.0) |
| `connect_errno` | int | ETIMEDOUT | errno for connect failures |
| `send_fail_rate` | float | 0.0 | Probability of send() failure |
| `send_errno` | int | EPIPE | errno for send failures |
| `recv_fail_rate` | float | 0.0 | Probability of recv() failure |
| `recv_errno` | int | ECONNRESET | errno for recv failures |
| `recv_short_rate` | float | 0.0 | Probability of short read |
| `target_hosts` | list | [] | Only affect these hosts |
| `target_ports` | list | [] | Only affect these ports |
| `log_injections` | bool | True | Log when faults are injected |

### From Environment Variables

```python
from socket_fault_injector import FaultConfig, FaultInjector

# Load config from environment
config = FaultConfig.from_env()
with FaultInjector(config=config) as fi:
    # Run tests
    pass
```

Environment variables:
- `FAULT_CONNECT_FAIL_RATE`
- `FAULT_CONNECT_ERRNO`
- `FAULT_SEND_FAIL_RATE`
- `FAULT_SEND_ERRNO`
- `FAULT_RECV_FAIL_RATE`
- `FAULT_RECV_ERRNO`
- `FAULT_RECV_SHORT_RATE`

## Common Scenarios

### Scenario 1: Test Retry Logic

```python
def test_retry_on_connection_failure():
    """Verify client retries on connection failure."""
    
    with FaultInjector(
        connect_fail_rate=0.5,  # 50% failure
        connect_errno=errno.ECONNREFUSED,
    ) as fi:
        client = MyClient(max_retries=5)
        
        # Should eventually succeed
        result = client.make_request()
        
        assert result is not None
        assert fi.stats.connect_failures >= 1
        assert fi.stats.connect_attempts >= 2  # Had to retry
```

### Scenario 2: Test Circuit Breaker

```python
def test_circuit_breaker_opens():
    """Verify circuit breaker opens after failures."""
    
    with FaultInjector(
        connect_fail_rate=1.0,  # 100% failure
        connect_errno=errno.ETIMEDOUT,
    ) as fi:
        client = MyClient(circuit_breaker_threshold=3)
        
        # First 3 requests fail
        for _ in range(3):
            with pytest.raises(ConnectionError):
                client.make_request()
        
        # Circuit breaker should now be open
        assert client.circuit_breaker.is_open
        
        # Next request fails fast without attempting connection
        attempts_before = fi.stats.connect_attempts
        with pytest.raises(CircuitBreakerOpen):
            client.make_request()
        assert fi.stats.connect_attempts == attempts_before  # No new attempt
```

### Scenario 3: Test Timeout Handling

```python
def test_handles_slow_response():
    """Test handling of slow/stalled connections."""
    
    # Note: Python injector can't add latency at socket level
    # Use recv_fail_rate with ETIMEDOUT errno instead
    with FaultInjector(
        recv_fail_rate=0.3,
        recv_errno=errno.ETIMEDOUT,
    ) as fi:
        client = MyClient(timeout=5)
        
        results = [client.safe_request() for _ in range(10)]
        
        successes = sum(1 for r in results if r is not None)
        assert successes > 0  # Some should succeed
        assert fi.stats.recv_failures > 0  # Some should fail
```

### Scenario 4: Test Partial Data Handling

```python
def test_handles_fragmented_response():
    """Test reassembly of fragmented responses."""
    
    with FaultInjector(recv_short_rate=0.8) as fi:  # 80% short reads
        client = MyClient()
        
        # Should reassemble despite fragmentation
        response = client.download(url="/large-file", expected_size=10000)
        
        assert len(response) == 10000
        assert fi.stats.short_reads > 5  # Multiple fragments
```

### Scenario 5: Target Specific Endpoints

```python
def test_downstream_failure_isolation():
    """Test that failure in one downstream doesn't affect others."""
    
    with FaultInjector(
        connect_fail_rate=1.0,
        target_hosts=["failing-service.local"],
        target_ports=[8080],
    ) as fi:
        client = MyClient()
        
        # Requests to failing service fail
        with pytest.raises(ConnectionError):
            client.call_service("failing-service.local", 8080)
        
        # Requests to other services succeed
        result = client.call_service("healthy-service.local", 8080)
        assert result is not None
```

## Integration with HTTP Libraries

### requests

```python
import requests
from socket_fault_injector import FaultInjector

with FaultInjector(connect_fail_rate=0.2) as fi:
    session = requests.Session()
    
    try:
        response = session.get("http://api.example.com/data")
    except requests.ConnectionError as e:
        print(f"Connection failed: {e}")
```

### httpx

```python
import httpx
from socket_fault_injector import FaultInjector

with FaultInjector(recv_short_rate=0.3) as fi:
    with httpx.Client() as client:
        response = client.get("http://api.example.com/data")
```

### aiohttp (async)

```python
import aiohttp
import asyncio
from socket_fault_injector import FaultInjector

async def test_async():
    with FaultInjector(connect_fail_rate=0.1) as fi:
        async with aiohttp.ClientSession() as session:
            async with session.get("http://api.example.com") as response:
                data = await response.text()

asyncio.run(test_async())
```

## Limitations

1. **No latency injection** - Can't add delays at socket level (use mocks for this)
2. **Python only** - Doesn't affect subprocesses or non-Python code
3. **No SSL interception** - SSL sockets partially supported
4. **Thread safety** - Stats are approximate under high concurrency

## Comparison with LD_PRELOAD

| Feature | LD_PRELOAD | Python Injector |
|---------|------------|-----------------|
| Works on macOS with SIP | ❌ | ✅ |
| Works on Windows | ❌ | ✅ |
| Affects subprocesses | ✅ | ❌ |
| Affects non-Python code | ✅ | ❌ |
| Requires compilation | ✅ | ❌ |
| Easy pytest integration | ⚠️ | ✅ |
| Latency injection | ✅ | ❌ |
| File I/O injection | ✅ | ❌ |

## See Also

- `ldpreload-injection.md` - LD_PRELOAD approach
- `socket_fault_injector.py` - Source code
- `fault_inject.c` - C library source
