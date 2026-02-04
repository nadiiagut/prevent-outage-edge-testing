# src/prevent_outage_edge_testing/extractors/registry.py
# Registry for managing and discovering extractors.

"""
ExtractorRegistry provides centralized management of extractors.

Use this to:
- Register custom extractors
- Discover available extractors for your platform
- Create extractor instances with appropriate configuration
"""

from typing import Type

from prevent_outage_edge_testing.extractors.base import BaseExtractor, ExtractorResult
from prevent_outage_edge_testing.models import ExtractorMode


class ExtractorRegistry:
    """
    Central registry for extractor types and instances.

    Extractors are registered by type and can be instantiated on demand.
    The registry tracks which extractors support privileged mode on the
    current platform.
    """

    def __init__(self) -> None:
        self._extractor_types: dict[str, Type[BaseExtractor]] = {}  # type: ignore[type-arg]
        self._instances: dict[str, BaseExtractor] = {}  # type: ignore[type-arg]

    def register_type(
        self, name: str, extractor_class: Type[BaseExtractor]  # type: ignore[type-arg]
    ) -> None:
        """Register an extractor type."""
        self._extractor_types[name] = extractor_class

    def create(
        self,
        name: str,
        extractor_id: str | None = None,
        mode: ExtractorMode = ExtractorMode.SIMULATOR,
        **kwargs,  # type: ignore[no-untyped-def]
    ) -> BaseExtractor:  # type: ignore[type-arg]
        """Create an extractor instance."""
        if name not in self._extractor_types:
            raise ValueError(f"Unknown extractor type: {name}")

        ext_id = extractor_id or f"{name}-{len(self._instances)}"
        instance = self._extractor_types[name](extractor_id=ext_id, mode=mode, **kwargs)
        self._instances[ext_id] = instance
        return instance

    def get(self, extractor_id: str) -> BaseExtractor | None:  # type: ignore[type-arg]
        """Get an extractor instance by ID."""
        return self._instances.get(extractor_id)

    def list_types(self) -> list[str]:
        """List all registered extractor types."""
        return list(self._extractor_types.keys())

    def list_instances(self) -> list[str]:
        """List all active extractor instances."""
        return list(self._instances.keys())

    def get_privileged_capable(self) -> list[str]:
        """Get extractor types that can run in privileged mode on this system."""
        capable = []
        for name, cls in self._extractor_types.items():
            # Create a temporary instance to check capability
            try:
                temp = cls(extractor_id="capability-check", mode=ExtractorMode.SIMULATOR)
                if temp.can_run_privileged():
                    capable.append(name)
            except Exception:
                pass
        return capable

    def stop_all(self) -> list[ExtractorResult]:
        """Stop all running extractors and return results."""
        results = []
        for ext in self._instances.values():
            try:
                result = ext.stop()
                results.append(result)
            except Exception:
                pass
        return results

    def remove(self, extractor_id: str) -> None:
        """Remove an extractor instance."""
        if extractor_id in self._instances:
            try:
                self._instances[extractor_id].stop()
            except Exception:
                pass
            del self._instances[extractor_id]


# Global registry instance
_global_registry: ExtractorRegistry | None = None


def get_extractor_registry() -> ExtractorRegistry:
    """Get the global extractor registry with built-in extractors registered."""
    global _global_registry
    if _global_registry is None:
        _global_registry = ExtractorRegistry()

        # Register built-in extractors
        from prevent_outage_edge_testing.extractors.privileged import (
            DTraceMetricExtractor,
            EBPFMetricExtractor,
            LDPreloadLogExtractor,
            NetworkTraceExtractor,
        )

        _global_registry.register_type("dtrace-metrics", DTraceMetricExtractor)
        _global_registry.register_type("ebpf-metrics", EBPFMetricExtractor)
        _global_registry.register_type("ldpreload-logs", LDPreloadLogExtractor)
        _global_registry.register_type("network-traces", NetworkTraceExtractor)

    return _global_registry
