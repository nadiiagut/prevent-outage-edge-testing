# tests/conftest.py
# Pytest configuration and fixtures for prevent-outage-edge-testing tests.

"""
Shared pytest fixtures for testing the library.

Provides:
- Sample knowledge packs
- Test plan builder instances
- Extractor fixtures with simulator mode
- Temporary directories for file operations
"""

from datetime import datetime
from pathlib import Path

import pytest

from prevent_outage_edge_testing.builder import BuilderConfig, TestPlanBuilder
from prevent_outage_edge_testing.extractors import get_extractor_registry
from prevent_outage_edge_testing.models import (
    ExtractorMode,
    FailureMode,
    KnowledgePack,
    ObservabilityRecipe,
    Severity,
    TestAssertion,
    TestCase,
)
from prevent_outage_edge_testing.registry import PackRegistry


@pytest.fixture
def sample_failure_mode() -> FailureMode:
    """Create a sample failure mode for testing."""
    return FailureMode(
        id="test-failure-001",
        name="Test Failure Mode",
        description="A sample failure mode for testing purposes",
        severity=Severity.HIGH,
        symptoms=["Symptom A", "Symptom B", "Symptom C"],
        root_causes=["Cause X", "Cause Y"],
        mitigation_strategies=["Fix 1", "Fix 2"],
        tags=["test", "sample"],
    )


@pytest.fixture
def sample_test_case() -> TestCase:
    """Create a sample test case for testing."""
    return TestCase(
        id="test-case-001",
        name="Sample Test Case",
        description="A test case for testing the framework",
        failure_mode_id="test-failure-001",
        priority=Severity.HIGH,
        setup_steps=["Step 1: Prepare environment"],
        execution_steps=["Step 2: Run test"],
        assertions=[
            TestAssertion(
                description="Check result",
                expression="result == expected",
                expected=True,
            )
        ],
        cleanup_steps=["Step 3: Cleanup"],
        tags=["test"],
        estimated_duration_seconds=30,
    )


@pytest.fixture
def sample_knowledge_pack(
    sample_failure_mode: FailureMode, sample_test_case: TestCase
) -> KnowledgePack:
    """Create a sample knowledge pack for testing."""
    return KnowledgePack(
        id="test-pack",
        name="Test Knowledge Pack",
        version="1.0.0",
        description="A sample knowledge pack for testing",
        author="Test Author",
        tags=["test", "cache", "cdn"],
        failure_modes=[sample_failure_mode],
        test_templates=[sample_test_case],
        observability_recipes=[
            ObservabilityRecipe(
                id="test-recipe",
                name="Test Recipe",
                description="Sample observability recipe",
                failure_mode_ids=["test-failure-001"],
                metrics=[],
                log_patterns=[],
            )
        ],
        references=["https://example.com"],
    )


@pytest.fixture
def empty_registry() -> PackRegistry:
    """Create an empty pack registry."""
    return PackRegistry()


@pytest.fixture
def populated_registry(
    empty_registry: PackRegistry, sample_knowledge_pack: KnowledgePack
) -> PackRegistry:
    """Create a registry with the sample pack."""
    empty_registry.register(sample_knowledge_pack)
    return empty_registry


@pytest.fixture
def test_plan_builder(populated_registry: PackRegistry) -> TestPlanBuilder:
    """Create a test plan builder with default config."""
    config = BuilderConfig(min_relevance_score=0.1)
    return TestPlanBuilder(registry=populated_registry, config=config)


@pytest.fixture
def extractor_registry():
    """Get the extractor registry."""
    return get_extractor_registry()


@pytest.fixture
def simulator_extractor(extractor_registry):
    """Create an extractor in simulator mode."""
    return extractor_registry.create(
        "dtrace-metrics",
        extractor_id="test-extractor",
        mode=ExtractorMode.SIMULATOR,
    )


@pytest.fixture
def sample_description() -> str:
    """Sample feature description for testing the builder."""
    return """
    Feature: CDN Cache Invalidation API

    As a content publisher, I need to invalidate cached content across all
    edge locations when I publish updates.

    Requirements:
    - Purge should complete within 30 seconds globally
    - Support purging by URL pattern, surrogate key, or full purge
    - Provide status API to check purge propagation
    - Handle rate limiting gracefully

    Acceptance Criteria:
    - Cache hit ratio should return to normal within 1 minute after purge
    - No stale content should be served after purge completes
    - Purge API should return 202 Accepted and propagation status endpoint
    """


@pytest.fixture
def temp_pack_dir(tmp_path: Path, sample_knowledge_pack: KnowledgePack) -> Path:
    """Create a temporary directory with a sample pack YAML."""
    import yaml

    pack_file = tmp_path / "test-pack.yaml"
    pack_file.write_text(yaml.dump(sample_knowledge_pack.model_dump()))
    return tmp_path


# Markers for special test categories
def pytest_configure(config):
    """Configure custom pytest markers."""
    config.addinivalue_line(
        "markers", "privileged: tests requiring elevated permissions (DTrace, eBPF)"
    )
    config.addinivalue_line("markers", "slow: tests that take significant time")
    config.addinivalue_line(
        "markers", "integration: integration tests requiring external services"
    )
