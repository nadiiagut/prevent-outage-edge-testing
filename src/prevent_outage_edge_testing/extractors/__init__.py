# src/prevent_outage_edge_testing/extractors/__init__.py
# Extractors framework for collecting metrics, logs, and traces.

"""
Extractors are components that collect observability data from systems.

This module provides:
- Base extractor classes
- Privileged extractors (DTrace, eBPF, LD_PRELOAD) for systems that support them
- Simulator/fallback extractors for safe local testing

Use the appropriate mode based on your environment and permissions.
"""

from prevent_outage_edge_testing.extractors.base import (
    BaseExtractor,
    ExtractorResult,
    MetricExtractor,
    LogExtractor,
    TraceExtractor,
)
from prevent_outage_edge_testing.extractors.registry import (
    ExtractorRegistry,
    get_extractor_registry,
)

__all__ = [
    "BaseExtractor",
    "ExtractorRegistry",
    "ExtractorResult",
    "LogExtractor",
    "MetricExtractor",
    "TraceExtractor",
    "get_extractor_registry",
]
