#!/usr/bin/env python3
"""
socket_fault_injector.py - Pure Python socket wrapper for fault injection.

When LD_PRELOAD is not available (e.g., macOS with SIP, containers, Windows),
this module provides a Python-level socket wrapper that can inject faults.

Usage:
    # As a context manager (recommended)
    with FaultInjector(connect_fail_rate=0.1, send_fail_rate=0.05) as injector:
        # Your test code using requests, httpx, etc.
        response = requests.get("http://api.example.com")
    
    # Manual patching
    injector = FaultInjector(recv_short_rate=0.2)
    injector.install()
    try:
        # Your test code
        pass
    finally:
        injector.uninstall()
    
    # With pytest fixture
    @pytest.fixture
    def fault_injector():
        with FaultInjector(connect_fail_rate=0.1) as fi:
            yield fi
"""

from __future__ import annotations

import errno
import logging
import os
import random
import socket
import ssl
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional
from unittest.mock import patch

logger = logging.getLogger(__name__)


# Errno mappings
ERRNO_MAP = {
    "EPIPE": errno.EPIPE,
    "ECONNRESET": errno.ECONNRESET,
    "ECONNREFUSED": errno.ECONNREFUSED,
    "ETIMEDOUT": errno.ETIMEDOUT,
    "ENETUNREACH": getattr(errno, "ENETUNREACH", 101),
    "EHOSTUNREACH": getattr(errno, "EHOSTUNREACH", 113),
}


@dataclass
class FaultConfig:
    """Configuration for fault injection."""
    
    # Connection faults
    connect_fail_rate: float = 0.0
    connect_errno: int = errno.ETIMEDOUT
    connect_delay_ms: int = 0
    
    # Send faults
    send_fail_rate: float = 0.0
    send_errno: int = errno.EPIPE
    send_delay_ms: int = 0
    
    # Recv faults
    recv_fail_rate: float = 0.0
    recv_errno: int = errno.ECONNRESET
    recv_short_rate: float = 0.0
    recv_delay_ms: int = 0
    
    # Targeting
    target_hosts: list[str] = field(default_factory=list)
    target_ports: list[int] = field(default_factory=list)
    
    # Logging
    log_injections: bool = True
    
    @classmethod
    def from_env(cls) -> "FaultConfig":
        """Create config from environment variables."""
        def get_float(key: str, default: float = 0.0) -> float:
            val = os.environ.get(key)
            return float(val) if val else default
        
        def get_int(key: str, default: int = 0) -> int:
            val = os.environ.get(key)
            return int(val) if val else default
        
        def get_errno(key: str, default: int) -> int:
            val = os.environ.get(key)
            if val:
                return ERRNO_MAP.get(val, int(val) if val.isdigit() else default)
            return default
        
        return cls(
            connect_fail_rate=get_float("FAULT_CONNECT_FAIL_RATE"),
            connect_errno=get_errno("FAULT_CONNECT_ERRNO", errno.ETIMEDOUT),
            send_fail_rate=get_float("FAULT_SEND_FAIL_RATE"),
            send_errno=get_errno("FAULT_SEND_ERRNO", errno.EPIPE),
            recv_fail_rate=get_float("FAULT_RECV_FAIL_RATE"),
            recv_errno=get_errno("FAULT_RECV_ERRNO", errno.ECONNRESET),
            recv_short_rate=get_float("FAULT_RECV_SHORT_RATE"),
            connect_delay_ms=get_int("FAULT_CONNECT_DELAY_MS"),
            send_delay_ms=get_int("FAULT_SEND_DELAY_MS"),
            recv_delay_ms=get_int("FAULT_RECV_DELAY_MS"),
        )


@dataclass
class InjectionStats:
    """Statistics about injected faults."""
    
    connect_attempts: int = 0
    connect_failures: int = 0
    send_attempts: int = 0
    send_failures: int = 0
    recv_attempts: int = 0
    recv_failures: int = 0
    short_reads: int = 0
    
    def __str__(self) -> str:
        return (
            f"InjectionStats(connect={self.connect_failures}/{self.connect_attempts}, "
            f"send={self.send_failures}/{self.send_attempts}, "
            f"recv={self.recv_failures}/{self.recv_attempts}, "
            f"short_reads={self.short_reads})"
        )


class FaultSocket:
    """Wrapper around socket that injects faults."""
    
    def __init__(
        self,
        real_socket: socket.socket,
        config: FaultConfig,
        stats: InjectionStats,
    ):
        self._socket = real_socket
        self._config = config
        self._stats = stats
        self._connected_addr: Optional[tuple] = None
        self._is_targeted = False
    
    def _should_inject(self, rate: float) -> bool:
        """Check if should inject based on rate."""
        if rate <= 0:
            return False
        if rate >= 1:
            return True
        return random.random() < rate
    
    def _check_target(self, address: tuple) -> bool:
        """Check if address is in target list."""
        if not self._config.target_hosts and not self._config.target_ports:
            return True
        
        host, port = address[0], address[1]
        
        if self._config.target_hosts and host not in self._config.target_hosts:
            return False
        if self._config.target_ports and port not in self._config.target_ports:
            return False
        
        return True
    
    def _add_delay(self, delay_ms: int) -> None:
        """Add artificial delay."""
        if delay_ms > 0:
            time.sleep(delay_ms / 1000.0)
    
    def _log(self, msg: str) -> None:
        """Log if enabled."""
        if self._config.log_injections:
            logger.info(f"[FAULT_INJECT] {msg}")
    
    def connect(self, address: tuple) -> None:
        """Connect with potential fault injection."""
        self._connected_addr = address
        self._is_targeted = self._check_target(address)
        self._stats.connect_attempts += 1
        
        self._add_delay(self._config.connect_delay_ms)
        
        if self._is_targeted and self._should_inject(self._config.connect_fail_rate):
            self._stats.connect_failures += 1
            self._log(f"connect({address}) -> errno {self._config.connect_errno}")
            raise OSError(self._config.connect_errno, os.strerror(self._config.connect_errno))
        
        return self._socket.connect(address)
    
    def connect_ex(self, address: tuple) -> int:
        """Connect_ex with potential fault injection."""
        self._connected_addr = address
        self._is_targeted = self._check_target(address)
        self._stats.connect_attempts += 1
        
        self._add_delay(self._config.connect_delay_ms)
        
        if self._is_targeted and self._should_inject(self._config.connect_fail_rate):
            self._stats.connect_failures += 1
            self._log(f"connect_ex({address}) -> errno {self._config.connect_errno}")
            return self._config.connect_errno
        
        return self._socket.connect_ex(address)
    
    def send(self, data: bytes, flags: int = 0) -> int:
        """Send with potential fault injection."""
        self._stats.send_attempts += 1
        
        self._add_delay(self._config.send_delay_ms)
        
        if self._is_targeted and self._should_inject(self._config.send_fail_rate):
            self._stats.send_failures += 1
            self._log(f"send({len(data)} bytes) -> errno {self._config.send_errno}")
            raise OSError(self._config.send_errno, os.strerror(self._config.send_errno))
        
        return self._socket.send(data, flags)
    
    def sendall(self, data: bytes, flags: int = 0) -> None:
        """Sendall with potential fault injection."""
        self._stats.send_attempts += 1
        
        self._add_delay(self._config.send_delay_ms)
        
        if self._is_targeted and self._should_inject(self._config.send_fail_rate):
            self._stats.send_failures += 1
            self._log(f"sendall({len(data)} bytes) -> errno {self._config.send_errno}")
            raise OSError(self._config.send_errno, os.strerror(self._config.send_errno))
        
        return self._socket.sendall(data, flags)
    
    def recv(self, bufsize: int, flags: int = 0) -> bytes:
        """Recv with potential fault injection."""
        self._stats.recv_attempts += 1
        
        self._add_delay(self._config.recv_delay_ms)
        
        if self._is_targeted and self._should_inject(self._config.recv_fail_rate):
            self._stats.recv_failures += 1
            self._log(f"recv({bufsize}) -> errno {self._config.recv_errno}")
            raise OSError(self._config.recv_errno, os.strerror(self._config.recv_errno))
        
        data = self._socket.recv(bufsize, flags)
        
        # Short read injection
        if self._is_targeted and len(data) > 1 and self._should_inject(self._config.recv_short_rate):
            short_len = random.randint(1, len(data) // 2)
            self._stats.short_reads += 1
            self._log(f"recv short read: {len(data)} -> {short_len} bytes")
            return data[:short_len]
        
        return data
    
    def recv_into(self, buffer: bytearray, nbytes: int = 0, flags: int = 0) -> int:
        """Recv_into with potential fault injection."""
        self._stats.recv_attempts += 1
        
        self._add_delay(self._config.recv_delay_ms)
        
        if self._is_targeted and self._should_inject(self._config.recv_fail_rate):
            self._stats.recv_failures += 1
            self._log(f"recv_into() -> errno {self._config.recv_errno}")
            raise OSError(self._config.recv_errno, os.strerror(self._config.recv_errno))
        
        n = self._socket.recv_into(buffer, nbytes, flags)
        
        # Short read injection
        if self._is_targeted and n > 1 and self._should_inject(self._config.recv_short_rate):
            short_n = random.randint(1, n // 2)
            self._stats.short_reads += 1
            self._log(f"recv_into short read: {n} -> {short_n} bytes")
            return short_n
        
        return n
    
    def makefile(self, mode: str = "r", buffering: int = -1, **kwargs) -> Any:
        """Create a file-like wrapper."""
        return self._socket.makefile(mode, buffering, **kwargs)
    
    def __getattr__(self, name: str) -> Any:
        """Delegate unknown attributes to real socket."""
        return getattr(self._socket, name)
    
    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        self._socket.close()


class FaultInjector:
    """
    Context manager that patches socket to inject faults.
    
    Example:
        with FaultInjector(connect_fail_rate=0.1) as injector:
            response = requests.get("http://example.com")
        print(injector.stats)
    """
    
    def __init__(
        self,
        config: Optional[FaultConfig] = None,
        # Convenience kwargs
        connect_fail_rate: float = 0.0,
        connect_errno: int = errno.ETIMEDOUT,
        send_fail_rate: float = 0.0,
        send_errno: int = errno.EPIPE,
        recv_fail_rate: float = 0.0,
        recv_errno: int = errno.ECONNRESET,
        recv_short_rate: float = 0.0,
        target_hosts: Optional[list[str]] = None,
        target_ports: Optional[list[int]] = None,
        log_injections: bool = True,
    ):
        if config:
            self._config = config
        else:
            self._config = FaultConfig(
                connect_fail_rate=connect_fail_rate,
                connect_errno=connect_errno,
                send_fail_rate=send_fail_rate,
                send_errno=send_errno,
                recv_fail_rate=recv_fail_rate,
                recv_errno=recv_errno,
                recv_short_rate=recv_short_rate,
                target_hosts=target_hosts or [],
                target_ports=target_ports or [],
                log_injections=log_injections,
            )
        
        self._stats = InjectionStats()
        self._patches: list = []
        self._original_socket = None
        self._original_ssl_socket = None
    
    @property
    def stats(self) -> InjectionStats:
        """Get injection statistics."""
        return self._stats
    
    @property
    def config(self) -> FaultConfig:
        """Get configuration."""
        return self._config
    
    def _create_socket(self, family: int = -1, type: int = -1, proto: int = -1, fileno: int = None):
        """Factory for creating wrapped sockets."""
        real_sock = self._original_socket(family, type, proto, fileno)
        return FaultSocket(real_sock, self._config, self._stats)
    
    def _wrap_ssl_socket(self, sock, *args, **kwargs):
        """Wrap SSL socket creation."""
        # If it's our FaultSocket, get the real socket
        if isinstance(sock, FaultSocket):
            real_sock = sock._socket
            ssl_sock = self._original_ssl_socket(real_sock, *args, **kwargs)
            # Return wrapped SSL socket
            return FaultSocket(ssl_sock, self._config, self._stats)
        return self._original_ssl_socket(sock, *args, **kwargs)
    
    def install(self) -> None:
        """Install the socket patches."""
        self._original_socket = socket.socket
        
        # Patch socket.socket
        socket.socket = self._create_socket
        
        # Also patch ssl.wrap_socket if using SSL
        if hasattr(ssl, 'wrap_socket'):
            self._original_ssl_socket = ssl.wrap_socket
            ssl.wrap_socket = self._wrap_ssl_socket
    
    def uninstall(self) -> None:
        """Uninstall the socket patches."""
        if self._original_socket:
            socket.socket = self._original_socket
            self._original_socket = None
        
        if self._original_ssl_socket:
            ssl.wrap_socket = self._original_ssl_socket
            self._original_ssl_socket = None
    
    def __enter__(self) -> "FaultInjector":
        self.install()
        return self
    
    def __exit__(self, *args) -> None:
        self.uninstall()


# Convenience functions for common scenarios

def inject_connection_timeouts(rate: float = 0.1) -> FaultInjector:
    """Create injector for connection timeouts."""
    return FaultInjector(connect_fail_rate=rate, connect_errno=errno.ETIMEDOUT)


def inject_broken_pipes(rate: float = 0.1) -> FaultInjector:
    """Create injector for broken pipe errors."""
    return FaultInjector(send_fail_rate=rate, send_errno=errno.EPIPE)


def inject_connection_resets(rate: float = 0.1) -> FaultInjector:
    """Create injector for connection reset errors."""
    return FaultInjector(recv_fail_rate=rate, recv_errno=errno.ECONNRESET)


def inject_short_reads(rate: float = 0.2) -> FaultInjector:
    """Create injector for short reads (partial data)."""
    return FaultInjector(recv_short_rate=rate)


# Pytest fixtures

def pytest_fault_injector_fixture():
    """
    Example pytest fixture. Copy this to your conftest.py:
    
    @pytest.fixture
    def fault_injector():
        with FaultInjector(
            connect_fail_rate=0.1,
            recv_short_rate=0.2,
            log_injections=True,
        ) as injector:
            yield injector
        print(f"Injection stats: {injector.stats}")
    """
    pass


# Demo and testing

def demo():
    """Demonstrate fault injection."""
    import urllib.request
    
    print("=== Socket Fault Injector Demo ===\n")
    
    # Demo 1: Connection timeout
    print("1. Testing connection timeout injection (50% rate)...")
    with FaultInjector(connect_fail_rate=0.5, connect_errno=errno.ETIMEDOUT) as fi:
        for i in range(5):
            try:
                # This will be affected by injection
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1)
                sock.connect(("httpbin.org", 80))
                print(f"   Attempt {i+1}: Connected successfully")
                sock.close()
            except OSError as e:
                print(f"   Attempt {i+1}: {e}")
    print(f"   Stats: {fi.stats}\n")
    
    # Demo 2: Short reads
    print("2. Testing short read injection (100% rate)...")
    with FaultInjector(recv_short_rate=1.0) as fi:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect(("httpbin.org", 80))
            sock.send(b"GET /bytes/100 HTTP/1.0\r\nHost: httpbin.org\r\n\r\n")
            data = sock.recv(4096)
            print(f"   Received {len(data)} bytes (may be truncated)")
            sock.close()
        except Exception as e:
            print(f"   Error: {e}")
    print(f"   Stats: {fi.stats}\n")
    
    # Demo 3: Send failure
    print("3. Testing EPIPE injection (100% rate)...")
    with FaultInjector(send_fail_rate=1.0, send_errno=errno.EPIPE) as fi:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect(("httpbin.org", 80))
            sock.send(b"GET / HTTP/1.0\r\n\r\n")
        except OSError as e:
            print(f"   Got expected error: {e}")
        finally:
            sock.close()
    print(f"   Stats: {fi.stats}\n")
    
    print("=== Demo Complete ===")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    demo()
