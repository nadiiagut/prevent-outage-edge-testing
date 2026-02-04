# src/prevent_outage_edge_testing/extractors/privileged.py
# Privileged extractors using DTrace (macOS), eBPF (Linux), and LD_PRELOAD.

"""
Privileged extractors that require elevated system permissions.

These extractors use:
- DTrace: Available on macOS and Solaris (requires root or dtrace group)
- eBPF: Available on Linux 4.4+ (requires CAP_BPF or root)
- LD_PRELOAD: Works on Linux/macOS to intercept library calls

Each extractor provides:
- A "real" implementation for systems where it's possible
- Automatic fallback to simulator mode if privileges are unavailable
"""

import os
import platform
import shutil
import subprocess
import threading
import time
from datetime import datetime
from typing import Any

from prevent_outage_edge_testing.extractors.base import (
    LogEntry,
    LogExtractor,
    MetricExtractor,
    MetricSample,
    TraceExtractor,
    TraceSpan,
)
from prevent_outage_edge_testing.models import ExtractorMode


class DTraceMetricExtractor(MetricExtractor):
    """
    Extracts system metrics using DTrace (macOS/Solaris).

    Privileged mode: Runs actual DTrace scripts to collect syscall stats.
    Simulator mode: Generates synthetic metrics for testing.
    """

    def __init__(
        self,
        extractor_id: str = "dtrace-metrics",
        mode: ExtractorMode = ExtractorMode.SIMULATOR,
        dtrace_script: str | None = None,
    ) -> None:
        super().__init__(extractor_id, mode)
        self._dtrace_script = dtrace_script or self._default_script()
        self._process: subprocess.Popen[str] | None = None
        self._collector_thread: threading.Thread | None = None
        self._running = False

    @property
    def name(self) -> str:
        return "DTrace Metric Extractor"

    def _default_script(self) -> str:
        """Default DTrace script for syscall counting."""
        return """
        syscall:::entry
        {
            @calls[probefunc] = count();
        }

        tick-1s
        {
            printa(@calls);
            clear(@calls);
        }
        """

    def can_run_privileged(self) -> bool:
        """Check if DTrace is available and we have permissions."""
        if platform.system() not in ("Darwin", "SunOS"):
            return False
        if not shutil.which("dtrace"):
            return False
        # Check if we have dtrace permissions (root or dtrace group)
        try:
            result = subprocess.run(
                ["dtrace", "-l", "-n", "syscall:::entry"],
                capture_output=True,
                timeout=5,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, OSError):
            return False

    def _run_privileged(self) -> None:
        """Start DTrace collection."""
        self._running = True
        self._process = subprocess.Popen(
            ["dtrace", "-n", self._dtrace_script],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        def collect() -> None:
            while self._running and self._process:
                line = self._process.stdout.readline() if self._process.stdout else ""
                if line:
                    # Parse DTrace output and create metrics
                    parts = line.strip().split()
                    if len(parts) >= 2:
                        try:
                            self.add_data(
                                MetricSample(
                                    name=f"syscall.{parts[0]}",
                                    value=float(parts[1]),
                                    labels={"source": "dtrace"},
                                )
                            )
                        except (ValueError, IndexError):
                            pass

        self._collector_thread = threading.Thread(target=collect, daemon=True)
        self._collector_thread.start()

    def _run_simulator(self) -> None:
        """Generate synthetic metrics."""
        self._running = True

        def generate() -> None:
            syscalls = ["read", "write", "open", "close", "stat", "mmap"]
            while self._running:
                for sc in syscalls:
                    import random

                    self.add_data(
                        MetricSample(
                            name=f"syscall.{sc}",
                            value=float(random.randint(10, 1000)),
                            labels={"source": "simulator"},
                        )
                    )
                time.sleep(1)

        self._collector_thread = threading.Thread(target=generate, daemon=True)
        self._collector_thread.start()

    def _stop_privileged(self) -> None:
        """Stop DTrace collection."""
        self._running = False
        if self._process:
            self._process.terminate()
            self._process.wait(timeout=5)
            self._process = None

    def _stop_simulator(self) -> None:
        """Stop simulator."""
        self._running = False
        if self._collector_thread:
            self._collector_thread.join(timeout=2)


class EBPFMetricExtractor(MetricExtractor):
    """
    Extracts metrics using eBPF (Linux).

    Privileged mode: Attaches eBPF programs to kernel tracepoints.
    Simulator mode: Generates synthetic metrics for testing.

    Note: Requires the 'bcc' package and appropriate capabilities.
    """

    def __init__(
        self,
        extractor_id: str = "ebpf-metrics",
        mode: ExtractorMode = ExtractorMode.SIMULATOR,
    ) -> None:
        super().__init__(extractor_id, mode)
        self._bpf: Any = None
        self._collector_thread: threading.Thread | None = None
        self._running = False

    @property
    def name(self) -> str:
        return "eBPF Metric Extractor"

    def can_run_privileged(self) -> bool:
        """Check if eBPF/BCC is available."""
        if platform.system() != "Linux":
            return False
        try:
            from bcc import BPF  # noqa: F401

            # Check for CAP_BPF or root
            return os.geteuid() == 0 or self._has_cap_bpf()
        except ImportError:
            return False

    def _has_cap_bpf(self) -> bool:
        """Check if current process has CAP_BPF."""
        try:
            # Try to read capabilities
            with open("/proc/self/status") as f:
                for line in f:
                    if line.startswith("CapEff:"):
                        cap_eff = int(line.split()[1], 16)
                        CAP_BPF = 1 << 39
                        return bool(cap_eff & CAP_BPF)
        except Exception:
            pass
        return False

    def _run_privileged(self) -> None:
        """Start eBPF collection."""
        from bcc import BPF

        bpf_program = """
        #include <uapi/linux/ptrace.h>

        BPF_HASH(syscall_count, u32);

        TRACEPOINT_PROBE(raw_syscalls, sys_enter) {
            u32 syscall_id = args->id;
            syscall_count.increment(syscall_id);
            return 0;
        }
        """

        self._bpf = BPF(text=bpf_program)
        self._running = True

        def collect() -> None:
            while self._running:
                time.sleep(1)
                syscall_count = self._bpf["syscall_count"]
                for k, v in syscall_count.items():
                    self.add_data(
                        MetricSample(
                            name=f"syscall.id.{k.value}",
                            value=float(v.value),
                            labels={"source": "ebpf"},
                        )
                    )
                syscall_count.clear()

        self._collector_thread = threading.Thread(target=collect, daemon=True)
        self._collector_thread.start()

    def _run_simulator(self) -> None:
        """Generate synthetic metrics."""
        self._running = True

        def generate() -> None:
            import random

            syscall_ids = [0, 1, 2, 3, 4, 5, 9, 10, 11, 12]  # Common syscall IDs
            while self._running:
                for sid in syscall_ids:
                    self.add_data(
                        MetricSample(
                            name=f"syscall.id.{sid}",
                            value=float(random.randint(100, 10000)),
                            labels={"source": "simulator"},
                        )
                    )
                time.sleep(1)

        self._collector_thread = threading.Thread(target=generate, daemon=True)
        self._collector_thread.start()

    def _stop_privileged(self) -> None:
        """Stop eBPF collection."""
        self._running = False
        if self._collector_thread:
            self._collector_thread.join(timeout=2)
        self._bpf = None

    def _stop_simulator(self) -> None:
        """Stop simulator."""
        self._running = False
        if self._collector_thread:
            self._collector_thread.join(timeout=2)


class LDPreloadLogExtractor(LogExtractor):
    """
    Extracts logs by intercepting library calls via LD_PRELOAD.

    Privileged mode: Injects a shared library to intercept calls.
    Simulator mode: Generates synthetic log entries.

    This is useful for intercepting network calls, file operations, etc.
    """

    def __init__(
        self,
        extractor_id: str = "ldpreload-logs",
        mode: ExtractorMode = ExtractorMode.SIMULATOR,
        target_functions: list[str] | None = None,
    ) -> None:
        super().__init__(extractor_id, mode)
        self._target_functions = target_functions or ["connect", "send", "recv"]
        self._collector_thread: threading.Thread | None = None
        self._running = False
        self._log_file: str | None = None

    @property
    def name(self) -> str:
        return "LD_PRELOAD Log Extractor"

    def can_run_privileged(self) -> bool:
        """Check if LD_PRELOAD interception is possible."""
        # LD_PRELOAD works on Linux and macOS (as DYLD_INSERT_LIBRARIES)
        return platform.system() in ("Linux", "Darwin")

    def _run_privileged(self) -> None:
        """
        Start LD_PRELOAD-based logging.

        Note: This would require:
        1. Compiling a shared library that intercepts target functions
        2. Setting LD_PRELOAD before starting the target process
        3. Reading the intercepted data from a pipe/file

        For safety, we provide the framework but don't auto-compile.
        """
        # In a real implementation, this would:
        # 1. Check if precompiled intercept library exists
        # 2. Set up communication channel (pipe, shared memory)
        # 3. Start monitoring

        # For now, fall back to simulator with a warning
        import warnings

        warnings.warn(
            "LD_PRELOAD extractor requires precompiled intercept library. "
            "Falling back to simulator mode."
        )
        self._run_simulator()

    def _run_simulator(self) -> None:
        """Generate synthetic log entries."""
        self._running = True

        def generate() -> None:
            import random

            operations = [
                ("connect", "Connecting to 10.0.0.1:443"),
                ("send", "Sent 1024 bytes to socket"),
                ("recv", "Received 2048 bytes from socket"),
                ("open", "Opened file /etc/hosts"),
                ("close", "Closed file descriptor 5"),
            ]
            while self._running:
                op, msg = random.choice(operations)
                self.add_data(
                    LogEntry(
                        level="DEBUG",
                        message=msg,
                        source=f"ldpreload.{op}",
                        attributes={"function": op, "simulated": True},
                    )
                )
                time.sleep(0.5)

        self._collector_thread = threading.Thread(target=generate, daemon=True)
        self._collector_thread.start()

    def _stop_privileged(self) -> None:
        """Stop LD_PRELOAD collection."""
        self._running = False

    def _stop_simulator(self) -> None:
        """Stop simulator."""
        self._running = False
        if self._collector_thread:
            self._collector_thread.join(timeout=2)


class NetworkTraceExtractor(TraceExtractor):
    """
    Extracts network traces using system tools.

    Privileged mode: Uses tcpdump/libpcap for packet capture.
    Simulator mode: Generates synthetic trace spans.
    """

    def __init__(
        self,
        extractor_id: str = "network-traces",
        mode: ExtractorMode = ExtractorMode.SIMULATOR,
        interface: str = "any",
        filter_expr: str = "tcp port 80 or tcp port 443",
    ) -> None:
        super().__init__(extractor_id, mode)
        self._interface = interface
        self._filter_expr = filter_expr
        self._process: subprocess.Popen[str] | None = None
        self._collector_thread: threading.Thread | None = None
        self._running = False

    @property
    def name(self) -> str:
        return "Network Trace Extractor"

    def can_run_privileged(self) -> bool:
        """Check if tcpdump is available with permissions."""
        if not shutil.which("tcpdump"):
            return False
        # Would need root or CAP_NET_RAW
        return os.geteuid() == 0

    def _run_privileged(self) -> None:
        """Start network capture."""
        self._running = True
        self._process = subprocess.Popen(
            [
                "tcpdump",
                "-i",
                self._interface,
                "-l",  # Line buffered
                "-n",  # No DNS resolution
                self._filter_expr,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        def collect() -> None:
            import uuid

            trace_id = uuid.uuid4().hex
            span_counter = 0

            while self._running and self._process:
                line = self._process.stdout.readline() if self._process.stdout else ""
                if line:
                    span_counter += 1
                    self.add_data(
                        TraceSpan(
                            trace_id=trace_id,
                            span_id=f"{span_counter:016x}",
                            operation_name="network.packet",
                            service_name="tcpdump",
                            start_time=datetime.utcnow(),
                            attributes={"raw": line.strip()},
                        )
                    )

        self._collector_thread = threading.Thread(target=collect, daemon=True)
        self._collector_thread.start()

    def _run_simulator(self) -> None:
        """Generate synthetic trace spans."""
        self._running = True

        def generate() -> None:
            import random
            import uuid

            trace_id = uuid.uuid4().hex
            span_counter = 0

            services = ["web", "api", "db", "cache"]
            operations = ["request", "response", "query", "get", "set"]

            while self._running:
                span_counter += 1
                svc = random.choice(services)
                op = random.choice(operations)
                start = datetime.utcnow()

                self.add_data(
                    TraceSpan(
                        trace_id=trace_id,
                        span_id=f"{span_counter:016x}",
                        parent_span_id=f"{max(1, span_counter-1):016x}"
                        if span_counter > 1
                        else None,
                        operation_name=f"{svc}.{op}",
                        service_name=svc,
                        start_time=start,
                        end_time=start,
                        attributes={"simulated": True, "latency_ms": random.randint(1, 100)},
                    )
                )
                time.sleep(0.2)

        self._collector_thread = threading.Thread(target=generate, daemon=True)
        self._collector_thread.start()

    def _stop_privileged(self) -> None:
        """Stop network capture."""
        self._running = False
        if self._process:
            self._process.terminate()
            self._process.wait(timeout=5)
            self._process = None

    def _stop_simulator(self) -> None:
        """Stop simulator."""
        self._running = False
        if self._collector_thread:
            self._collector_thread.join(timeout=2)
