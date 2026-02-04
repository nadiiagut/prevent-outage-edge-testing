#!/usr/bin/env python3
"""
demo.py - Demonstration of fault-injection-io pack.

This script demonstrates:
1. Python socket fault injection (no LD_PRELOAD needed)
2. Various fault scenarios (timeouts, resets, short reads)
3. Integration patterns for testing

Run: python demo.py
"""

import errno
import os
import socket
import sys
import time
from pathlib import Path

# Add snippets to path
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR / "snippets"))

from socket_fault_injector import (
    FaultInjector,
    FaultConfig,
    inject_connection_timeouts,
    inject_broken_pipes,
    inject_connection_resets,
    inject_short_reads,
)


def demo_basic_injection():
    """Demonstrate basic fault injection."""
    print("=" * 60)
    print("Demo 1: Basic Connection Fault Injection")
    print("=" * 60)
    
    print("\nInjecting 50% connection timeouts...")
    print("Attempting 5 connections to httpbin.org:80\n")
    
    with FaultInjector(
        connect_fail_rate=0.5,
        connect_errno=errno.ETIMEDOUT,
        log_injections=False,
    ) as fi:
        for i in range(5):
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(2)
                sock.connect(("httpbin.org", 80))
                print(f"  Attempt {i+1}: ✓ Connected successfully")
                sock.close()
            except OSError as e:
                print(f"  Attempt {i+1}: ✗ {e}")
            except Exception as e:
                print(f"  Attempt {i+1}: ✗ {type(e).__name__}: {e}")
    
    print(f"\nStats: {fi.stats}")


def demo_short_reads():
    """Demonstrate short read injection."""
    print("\n" + "=" * 60)
    print("Demo 2: Short Read (Partial Data) Injection")
    print("=" * 60)
    
    print("\nInjecting 100% short reads...")
    print("This simulates network fragmentation\n")
    
    with FaultInjector(recv_short_rate=1.0, log_injections=False) as fi:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect(("httpbin.org", 80))
            
            # Send HTTP request
            request = b"GET /bytes/100 HTTP/1.0\r\nHost: httpbin.org\r\n\r\n"
            sock.send(request)
            
            # Receive response (will be fragmented)
            total_data = b""
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                print(f"  Received chunk: {len(chunk)} bytes")
                total_data += chunk
            
            print(f"\n  Total received: {len(total_data)} bytes")
            sock.close()
        except Exception as e:
            print(f"  Error: {e}")
    
    print(f"\nStats: {fi.stats}")


def demo_send_failure():
    """Demonstrate send failure injection."""
    print("\n" + "=" * 60)
    print("Demo 3: EPIPE (Broken Pipe) Injection")
    print("=" * 60)
    
    print("\nInjecting 100% send failures with EPIPE...")
    print("This simulates the remote end closing connection\n")
    
    with FaultInjector(
        send_fail_rate=1.0,
        send_errno=errno.EPIPE,
        log_injections=False,
    ) as fi:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect(("httpbin.org", 80))
            print("  Connected successfully")
            
            # Try to send (will fail)
            sock.send(b"GET / HTTP/1.0\r\n\r\n")
            print("  Send succeeded (unexpected)")
        except OSError as e:
            print(f"  Send failed as expected: {e}")
        finally:
            sock.close()
    
    print(f"\nStats: {fi.stats}")


def demo_targeted_injection():
    """Demonstrate targeting specific hosts/ports."""
    print("\n" + "=" * 60)
    print("Demo 4: Targeted Fault Injection")
    print("=" * 60)
    
    print("\nInjecting faults only for port 8080...")
    print("Port 80 should work normally\n")
    
    with FaultInjector(
        connect_fail_rate=1.0,
        target_ports=[8080],
        log_injections=False,
    ) as fi:
        # Connection to port 80 should work
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            sock.connect(("httpbin.org", 80))
            print("  Port 80: ✓ Connected (not targeted)")
            sock.close()
        except OSError as e:
            print(f"  Port 80: ✗ {e}")
        
        # Connection to port 8080 would fail (if we had a server there)
        print("  Port 8080: Would fail if targeted server existed")
    
    print(f"\nStats: {fi.stats}")


def demo_convenience_functions():
    """Demonstrate convenience functions."""
    print("\n" + "=" * 60)
    print("Demo 5: Convenience Functions")
    print("=" * 60)
    
    print("\nUsing inject_connection_timeouts(0.3)...")
    
    with inject_connection_timeouts(0.3) as fi:
        successes = 0
        failures = 0
        for i in range(10):
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(2)
                sock.connect(("httpbin.org", 80))
                successes += 1
                sock.close()
            except OSError:
                failures += 1
        
        print(f"  Results: {successes} successes, {failures} failures")
    print(f"  Stats: {fi.stats}")


def demo_error_recovery():
    """Demonstrate testing error recovery logic."""
    print("\n" + "=" * 60)
    print("Demo 6: Testing Error Recovery Logic")
    print("=" * 60)
    
    print("\nSimulating a client with retry logic...")
    
    class RetryingClient:
        def __init__(self, max_retries=3):
            self.max_retries = max_retries
            self.attempts = 0
        
        def connect(self, host, port):
            for attempt in range(self.max_retries):
                self.attempts += 1
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(2)
                    sock.connect((host, port))
                    return sock
                except OSError as e:
                    print(f"    Attempt {attempt + 1} failed: {e}")
                    if attempt == self.max_retries - 1:
                        raise
                    time.sleep(0.1)  # Brief delay before retry
            return None
    
    with FaultInjector(connect_fail_rate=0.6, log_injections=False) as fi:
        client = RetryingClient(max_retries=5)
        
        try:
            print("  Client attempting to connect with retry logic...")
            sock = client.connect("httpbin.org", 80)
            if sock:
                print(f"  ✓ Connected after {client.attempts} attempts")
                sock.close()
        except OSError:
            print(f"  ✗ Failed after {client.attempts} attempts")
    
    print(f"\nStats: {fi.stats}")


def demo_pytest_integration():
    """Show pytest integration examples."""
    print("\n" + "=" * 60)
    print("pytest Integration Examples")
    print("=" * 60)
    
    print("""
# conftest.py
import pytest
from socket_fault_injector import FaultInjector

@pytest.fixture
def network_chaos():
    with FaultInjector(
        connect_fail_rate=0.1,
        recv_short_rate=0.2,
    ) as fi:
        yield fi

# test_resilience.py
def test_handles_connection_failures(network_chaos):
    from myapp import Client
    
    client = Client(retry_count=3)
    result = client.fetch_data()
    
    assert result is not None
    # Verify injection actually happened
    assert network_chaos.stats.connect_attempts > 0
""")


def demo_ldpreload_usage():
    """Show LD_PRELOAD usage for C library."""
    print("\n" + "=" * 60)
    print("LD_PRELOAD Usage (C Library)")
    print("=" * 60)
    
    print("""
# Build the library
cd snippets
gcc -shared -fPIC -o libfaultinject.so fault_inject.c -ldl -lpthread

# Use with any application
FAULT_INJECT_ENABLED=1 \\
FAULT_CONNECT_FAIL_RATE=0.1 \\
FAULT_CONNECT_ERRNO=ETIMEDOUT \\
FAULT_LOG_FILE=/tmp/faults.log \\
LD_PRELOAD=./libfaultinject.so \\
python my_app.py

# Or with curl
FAULT_INJECT_ENABLED=1 \\
FAULT_RECV_SHORT_RATE=0.5 \\
LD_PRELOAD=./libfaultinject.so \\
curl http://example.com/large-file

# View injection log
tail -f /tmp/faults.log
""")


def main():
    print("\n" + "=" * 60)
    print("Fault Injection I/O - Demo")
    print("=" * 60)
    print("\nThis demo uses pure Python socket injection.")
    print("No LD_PRELOAD or root access required.")
    print("Works on macOS with SIP, Windows, and containers.\n")
    
    # Check if we can reach the internet
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        sock.connect(("httpbin.org", 80))
        sock.close()
        has_internet = True
    except Exception:
        has_internet = False
        print("⚠️  No internet connection - some demos will be skipped\n")
    
    if has_internet:
        demo_basic_injection()
        demo_short_reads()
        demo_send_failure()
        demo_targeted_injection()
        demo_convenience_functions()
        demo_error_recovery()
    else:
        print("Skipping network demos (no connectivity)")
    
    demo_pytest_integration()
    demo_ldpreload_usage()
    
    print("\n" + "=" * 60)
    print("Demo Complete!")
    print("=" * 60)
    print("\nSee recipes/ for detailed usage instructions.")
    print("See snippets/ for source code:")
    print("  - socket_fault_injector.py (Python)")
    print("  - fault_inject.c (LD_PRELOAD library)")


if __name__ == "__main__":
    main()
