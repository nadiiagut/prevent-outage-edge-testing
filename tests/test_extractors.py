# tests/test_extractors.py
# Tests for the extractors framework.

"""
Unit tests for extractors.

Tests cover:
- Base extractor functionality
- Simulator mode operation
- Extractor registry
- Data collection and results

Note: Privileged mode tests are marked and skipped by default.
Run with `pytest -m privileged` on systems with appropriate permissions.
"""

import time

import pytest

from prevent_outage_edge_testing.extractors import (
    BaseExtractor,
    ExtractorRegistry,
    ExtractorResult,
    get_extractor_registry,
)
from prevent_outage_edge_testing.extractors.base import (
    ExtractorStatus,
    LogEntry,
    LogExtractor,
    MetricExtractor,
    MetricSample,
    TraceExtractor,
    TraceSpan,
)
from prevent_outage_edge_testing.extractors.privileged import (
    DTraceMetricExtractor,
    EBPFMetricExtractor,
    LDPreloadLogExtractor,
    NetworkTraceExtractor,
)
from prevent_outage_edge_testing.models import ExtractorMode


class TestExtractorBase:
    """Tests for base extractor classes."""

    def test_metric_sample_creation(self):
        """Test creating a metric sample."""
        sample = MetricSample(
            name="test_metric",
            value=42.0,
            labels={"host": "localhost"},
        )
        assert sample.name == "test_metric"
        assert sample.value == 42.0
        assert sample.timestamp is not None

    def test_log_entry_creation(self):
        """Test creating a log entry."""
        entry = LogEntry(
            level="ERROR",
            message="Something went wrong",
            source="test",
        )
        assert entry.level == "ERROR"
        assert entry.timestamp is not None

    def test_trace_span_creation(self):
        """Test creating a trace span."""
        from datetime import datetime

        span = TraceSpan(
            trace_id="abc123",
            span_id="def456",
            operation_name="test.operation",
            service_name="test-service",
            start_time=datetime.utcnow(),
        )
        assert span.trace_id == "abc123"
        assert span.status == "OK"


class TestExtractorRegistry:
    """Tests for ExtractorRegistry."""

    def test_registry_creation(self):
        """Test creating a registry."""
        registry = ExtractorRegistry()
        assert len(registry.list_types()) == 0

    def test_register_type(self, extractor_registry):
        """Test registering extractor types."""
        types = extractor_registry.list_types()
        assert "dtrace-metrics" in types
        assert "ebpf-metrics" in types
        assert "ldpreload-logs" in types
        assert "network-traces" in types

    def test_create_extractor(self, extractor_registry):
        """Test creating an extractor instance."""
        ext = extractor_registry.create(
            "dtrace-metrics",
            extractor_id="test-dtrace",
            mode=ExtractorMode.SIMULATOR,
        )
        assert ext.extractor_id == "test-dtrace"
        assert ext.mode == ExtractorMode.SIMULATOR

    def test_create_unknown_extractor(self, extractor_registry):
        """Test creating unknown extractor raises error."""
        with pytest.raises(ValueError, match="Unknown extractor"):
            extractor_registry.create("nonexistent")

    def test_get_extractor(self, extractor_registry):
        """Test getting extractor by ID."""
        ext = extractor_registry.create(
            "dtrace-metrics",
            extractor_id="get-test",
            mode=ExtractorMode.SIMULATOR,
        )
        retrieved = extractor_registry.get("get-test")
        assert retrieved is ext

    def test_list_instances(self, extractor_registry):
        """Test listing active instances."""
        extractor_registry.create("dtrace-metrics", extractor_id="inst-1")
        extractor_registry.create("ebpf-metrics", extractor_id="inst-2")
        instances = extractor_registry.list_instances()
        assert "inst-1" in instances
        assert "inst-2" in instances

    def test_get_privileged_capable(self, extractor_registry):
        """Test getting privileged-capable extractors."""
        capable = extractor_registry.get_privileged_capable()
        # Result depends on system, but should be a list
        assert isinstance(capable, list)

    def test_remove_extractor(self, extractor_registry):
        """Test removing an extractor."""
        extractor_registry.create("dtrace-metrics", extractor_id="to-remove")
        assert "to-remove" in extractor_registry.list_instances()
        extractor_registry.remove("to-remove")
        assert "to-remove" not in extractor_registry.list_instances()


class TestDTraceMetricExtractor:
    """Tests for DTrace metric extractor."""

    def test_simulator_mode(self):
        """Test DTrace extractor in simulator mode."""
        ext = DTraceMetricExtractor(
            extractor_id="dtrace-sim",
            mode=ExtractorMode.SIMULATOR,
        )
        assert ext.name == "DTrace Metric Extractor"
        assert ext.mode == ExtractorMode.SIMULATOR

    def test_simulator_data_collection(self):
        """Test data collection in simulator mode."""
        ext = DTraceMetricExtractor(
            extractor_id="dtrace-collect",
            mode=ExtractorMode.SIMULATOR,
        )
        ext.start()
        time.sleep(1.5)  # Let it collect some data
        result = ext.stop()

        assert isinstance(result, ExtractorResult)
        assert result.status in (ExtractorStatus.STOPPED, ExtractorStatus.ERROR)
        assert len(result.data) > 0
        # Check data structure
        for item in result.data:
            assert "name" in item
            assert "value" in item

    def test_can_run_privileged(self):
        """Test privileged capability check."""
        ext = DTraceMetricExtractor(extractor_id="dtrace-priv-check")
        # Result depends on system
        can_priv = ext.can_run_privileged()
        assert isinstance(can_priv, bool)


class TestEBPFMetricExtractor:
    """Tests for eBPF metric extractor."""

    def test_simulator_mode(self):
        """Test eBPF extractor in simulator mode."""
        ext = EBPFMetricExtractor(
            extractor_id="ebpf-sim",
            mode=ExtractorMode.SIMULATOR,
        )
        assert ext.name == "eBPF Metric Extractor"

    def test_simulator_data_collection(self):
        """Test data collection in simulator mode."""
        ext = EBPFMetricExtractor(
            extractor_id="ebpf-collect",
            mode=ExtractorMode.SIMULATOR,
        )
        ext.start()
        time.sleep(1.5)
        result = ext.stop()

        assert len(result.data) > 0


class TestLDPreloadLogExtractor:
    """Tests for LD_PRELOAD log extractor."""

    def test_simulator_mode(self):
        """Test LD_PRELOAD extractor in simulator mode."""
        ext = LDPreloadLogExtractor(
            extractor_id="ldpreload-sim",
            mode=ExtractorMode.SIMULATOR,
        )
        assert ext.name == "LD_PRELOAD Log Extractor"

    def test_simulator_data_collection(self):
        """Test data collection in simulator mode."""
        ext = LDPreloadLogExtractor(
            extractor_id="ldpreload-collect",
            mode=ExtractorMode.SIMULATOR,
        )
        ext.start()
        time.sleep(1.5)
        result = ext.stop()

        assert len(result.data) > 0
        # Should be log entries
        for item in result.data:
            assert "message" in item


class TestNetworkTraceExtractor:
    """Tests for network trace extractor."""

    def test_simulator_mode(self):
        """Test network extractor in simulator mode."""
        ext = NetworkTraceExtractor(
            extractor_id="network-sim",
            mode=ExtractorMode.SIMULATOR,
        )
        assert ext.name == "Network Trace Extractor"

    def test_simulator_data_collection(self):
        """Test data collection in simulator mode."""
        ext = NetworkTraceExtractor(
            extractor_id="network-collect",
            mode=ExtractorMode.SIMULATOR,
        )
        ext.start()
        time.sleep(1.5)
        result = ext.stop()

        assert len(result.data) > 0
        # Should be trace spans
        for item in result.data:
            assert "trace_id" in item
            assert "span_id" in item


class TestGlobalExtractorRegistry:
    """Tests for global extractor registry."""

    def test_get_global_registry(self):
        """Test getting the global registry."""
        registry = get_extractor_registry()
        assert isinstance(registry, ExtractorRegistry)
        # Should have built-in extractors
        assert len(registry.list_types()) >= 4

    def test_global_registry_singleton(self):
        """Test that global registry is a singleton."""
        reg1 = get_extractor_registry()
        reg2 = get_extractor_registry()
        assert reg1 is reg2


@pytest.mark.privileged
class TestPrivilegedExtractors:
    """Tests requiring elevated permissions.

    These tests are skipped by default. Run with:
        pytest -m privileged

    Note: Even with the marker, tests will be skipped if
    the system doesn't support the privileged mode.
    """

    def test_dtrace_privileged(self):
        """Test DTrace in privileged mode (macOS/Solaris only)."""
        ext = DTraceMetricExtractor(
            extractor_id="dtrace-priv",
            mode=ExtractorMode.PRIVILEGED,
        )
        if not ext.can_run_privileged():
            pytest.skip("DTrace not available or insufficient permissions")

        ext.start()
        time.sleep(2)
        result = ext.stop()
        assert len(result.data) > 0

    def test_ebpf_privileged(self):
        """Test eBPF in privileged mode (Linux only)."""
        ext = EBPFMetricExtractor(
            extractor_id="ebpf-priv",
            mode=ExtractorMode.PRIVILEGED,
        )
        if not ext.can_run_privileged():
            pytest.skip("eBPF not available or insufficient permissions")

        ext.start()
        time.sleep(2)
        result = ext.stop()
        assert len(result.data) > 0
