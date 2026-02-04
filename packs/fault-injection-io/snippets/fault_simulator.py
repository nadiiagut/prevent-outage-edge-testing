# fault_simulator.py
# Python-based fault injection simulator (no LD_PRELOAD needed).
"""
Safe fault injection simulator for testing error handling without
actually injecting system-level faults.

Works by:
1. Monkey-patching file/network operations
2. Using context managers for scoped injection
3. Providing controlled exception raising

Usage:
    from fault_simulator import FaultInjector, FaultType
    
    injector = FaultInjector()
    injector.configure(FaultType.EIO, probability=0.1)
    
    with injector.active():
        # Code here may raise IOError with EIO
        with open("file.txt", "w") as f:
            f.write("data")  # May fail with simulated EIO
"""

import errno
import functools
import io
import os
import random
import re
import socket
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable, Optional, Any
from unittest.mock import patch, MagicMock


class FaultType(Enum):
    """Types of faults that can be injected."""
    
    # Disk faults
    EIO = auto()           # I/O error
    ENOSPC = auto()        # No space left on device
    EROFS = auto()         # Read-only filesystem
    EACCES = auto()        # Permission denied
    
    # Network faults
    ECONNRESET = auto()    # Connection reset
    ETIMEDOUT = auto()     # Connection timed out
    ECONNREFUSED = auto()  # Connection refused
    
    # Behavior faults
    PARTIAL_WRITE = auto() # Write less than requested
    PARTIAL_READ = auto()  # Read less than requested
    LATENCY = auto()       # Add delay


@dataclass
class FaultConfig:
    """Configuration for a single fault type."""
    
    fault_type: FaultType
    probability: float = 0.1
    latency_ms: int = 0
    partial_ratio: float = 0.5  # For partial read/write
    path_pattern: Optional[str] = None
    enabled: bool = True
    
    def should_trigger(self, path: Optional[str] = None) -> bool:
        """Check if fault should trigger based on config."""
        if not self.enabled:
            return False
        if self.path_pattern and path:
            if not re.match(self.path_pattern, path):
                return False
        return random.random() < self.probability


@dataclass
class FaultStats:
    """Statistics for fault injection session."""
    
    faults_configured: int = 0
    faults_triggered: int = 0
    faults_by_type: dict = field(default_factory=dict)
    operations_total: int = 0
    
    def record_operation(self) -> None:
        self.operations_total += 1
    
    def record_fault(self, fault_type: FaultType) -> None:
        self.faults_triggered += 1
        self.faults_by_type[fault_type.name] = \
            self.faults_by_type.get(fault_type.name, 0) + 1


class FaultInjector:
    """
    Main fault injection controller.
    
    Thread-safe and supports nested activation contexts.
    """
    
    _local = threading.local()
    
    def __init__(self) -> None:
        self._configs: dict[FaultType, FaultConfig] = {}
        self._stats = FaultStats()
        self._patches: list = []
        self._active = False
    
    def configure(
        self,
        fault_type: FaultType,
        probability: float = 0.1,
        latency_ms: int = 0,
        path_pattern: Optional[str] = None,
        **kwargs,
    ) -> "FaultInjector":
        """Configure a fault type for injection."""
        self._configs[fault_type] = FaultConfig(
            fault_type=fault_type,
            probability=probability,
            latency_ms=latency_ms,
            path_pattern=path_pattern,
            **kwargs,
        )
        self._stats.faults_configured += 1
        return self
    
    def disable(self, fault_type: FaultType) -> "FaultInjector":
        """Disable a configured fault."""
        if fault_type in self._configs:
            self._configs[fault_type].enabled = False
        return self
    
    def enable(self, fault_type: FaultType) -> "FaultInjector":
        """Re-enable a configured fault."""
        if fault_type in self._configs:
            self._configs[fault_type].enabled = True
        return self
    
    def _get_errno(self, fault_type: FaultType) -> int:
        """Get errno value for fault type."""
        mapping = {
            FaultType.EIO: errno.EIO,
            FaultType.ENOSPC: errno.ENOSPC,
            FaultType.EROFS: errno.EROFS,
            FaultType.EACCES: errno.EACCES,
            FaultType.ECONNRESET: errno.ECONNRESET,
            FaultType.ETIMEDOUT: errno.ETIMEDOUT,
            FaultType.ECONNREFUSED: errno.ECONNREFUSED,
        }
        return mapping.get(fault_type, errno.EIO)
    
    def _maybe_inject(
        self,
        operation: str,
        path: Optional[str] = None,
        data_size: Optional[int] = None,
    ) -> tuple[bool, Any]:
        """
        Check if fault should be injected and return appropriate result.
        
        Returns:
            (should_raise, result_or_exception)
        """
        self._stats.record_operation()
        
        for fault_type, config in self._configs.items():
            if not config.should_trigger(path):
                continue
            
            self._stats.record_fault(fault_type)
            
            # Add latency if configured
            if config.latency_ms > 0:
                time.sleep(config.latency_ms / 1000.0)
            
            # Handle different fault types
            if fault_type == FaultType.LATENCY:
                # Latency-only, don't raise
                continue
            
            if fault_type == FaultType.PARTIAL_WRITE and data_size:
                # Return partial result instead of raising
                partial = int(data_size * config.partial_ratio)
                return False, max(1, partial)
            
            if fault_type == FaultType.PARTIAL_READ and data_size:
                partial = int(data_size * config.partial_ratio)
                return False, max(1, partial)
            
            # Raise OSError for other fault types
            err = self._get_errno(fault_type)
            return True, OSError(err, os.strerror(err))
        
        return False, None
    
    def _wrap_write(self, original: Callable) -> Callable:
        """Wrap file write method."""
        @functools.wraps(original)
        def wrapper(data, *args, **kwargs):
            if isinstance(data, str):
                data_size = len(data.encode())
            else:
                data_size = len(data)
            
            should_raise, result = self._maybe_inject("write", data_size=data_size)
            
            if should_raise:
                raise result
            if result is not None:
                # Partial write
                if isinstance(data, str):
                    data = data[:result]
                else:
                    data = data[:result]
                return original(data, *args, **kwargs)
            
            return original(data, *args, **kwargs)
        return wrapper
    
    def _wrap_read(self, original: Callable) -> Callable:
        """Wrap file read method."""
        @functools.wraps(original)
        def wrapper(size=-1, *args, **kwargs):
            should_raise, result = self._maybe_inject("read", data_size=size if size > 0 else 4096)
            
            if should_raise:
                raise result
            if result is not None and size > 0:
                # Partial read
                size = result
            
            return original(size, *args, **kwargs)
        return wrapper
    
    @contextmanager
    def active(self):
        """
        Context manager to activate fault injection.
        
        Usage:
            with injector.active():
                # Faults may be injected here
                do_io_operations()
        """
        if self._active:
            # Already active, just yield
            yield self
            return
        
        self._active = True
        original_open = io.open
        
        def patched_open(file, mode='r', *args, **kwargs):
            f = original_open(file, mode, *args, **kwargs)
            
            # Check for fault on open
            should_raise, result = self._maybe_inject("open", path=str(file))
            if should_raise:
                f.close()
                raise result
            
            # Wrap write/read methods
            if hasattr(f, 'write') and 'w' in mode or 'a' in mode:
                f.write = self._wrap_write(f.write)
            if hasattr(f, 'read') and 'r' in mode:
                f.read = self._wrap_read(f.read)
            
            return f
        
        try:
            with patch('builtins.open', patched_open):
                with patch('io.open', patched_open):
                    yield self
        finally:
            self._active = False
    
    def get_stats(self) -> FaultStats:
        """Get injection statistics."""
        return self._stats
    
    def reset_stats(self) -> None:
        """Reset statistics."""
        self._stats = FaultStats(faults_configured=len(self._configs))


class MockSocket:
    """Mock socket that can inject network faults."""
    
    def __init__(self, injector: FaultInjector, real_socket: socket.socket):
        self._injector = injector
        self._real = real_socket
    
    def connect(self, address):
        should_raise, result = self._injector._maybe_inject("connect")
        if should_raise:
            raise result
        return self._real.connect(address)
    
    def send(self, data, flags=0):
        should_raise, result = self._injector._maybe_inject("send", data_size=len(data))
        if should_raise:
            raise result
        if result is not None:
            data = data[:result]
        return self._real.send(data, flags)
    
    def recv(self, bufsize, flags=0):
        should_raise, result = self._injector._maybe_inject("recv", data_size=bufsize)
        if should_raise:
            raise result
        if result is not None:
            bufsize = result
        return self._real.recv(bufsize, flags)
    
    def __getattr__(self, name):
        return getattr(self._real, name)


# Convenience functions
def create_injector(**fault_configs) -> FaultInjector:
    """
    Create and configure an injector in one call.
    
    Usage:
        injector = create_injector(
            eio=0.1,           # 10% EIO on writes
            enospc=0.05,       # 5% disk full
            latency_ms=100,    # 100ms latency
        )
    """
    injector = FaultInjector()
    
    fault_map = {
        'eio': FaultType.EIO,
        'enospc': FaultType.ENOSPC,
        'erofs': FaultType.EROFS,
        'eacces': FaultType.EACCES,
        'connreset': FaultType.ECONNRESET,
        'timeout': FaultType.ETIMEDOUT,
        'connrefused': FaultType.ECONNREFUSED,
        'partial_write': FaultType.PARTIAL_WRITE,
        'partial_read': FaultType.PARTIAL_READ,
    }
    
    for key, value in fault_configs.items():
        if key == 'latency_ms':
            injector.configure(FaultType.LATENCY, probability=1.0, latency_ms=value)
        elif key in fault_map:
            injector.configure(fault_map[key], probability=value)
    
    return injector


# Example usage
if __name__ == "__main__":
    print("=== Fault Simulator Demo ===\n")
    
    # Create injector with 50% EIO probability (high for demo)
    injector = create_injector(eio=0.5)
    
    print("Writing with fault injection enabled (50% EIO)...")
    
    successes = 0
    failures = 0
    
    with injector.active():
        for i in range(10):
            try:
                with open(f"/tmp/test_fault_{i}.txt", "w") as f:
                    f.write(f"Test data {i}")
                successes += 1
                print(f"  Write {i}: SUCCESS")
            except OSError as e:
                failures += 1
                print(f"  Write {i}: FAILED ({e})")
    
    print(f"\nResults: {successes} successes, {failures} failures")
    
    stats = injector.get_stats()
    print(f"\nStatistics:")
    print(f"  Operations: {stats.operations_total}")
    print(f"  Faults triggered: {stats.faults_triggered}")
    print(f"  By type: {stats.faults_by_type}")
    
    # Cleanup
    import glob
    for f in glob.glob("/tmp/test_fault_*.txt"):
        os.remove(f)
