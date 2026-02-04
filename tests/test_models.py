# tests/test_models.py
# Tests for Pydantic models in prevent-outage-edge-testing.

"""
Unit tests for core data models.

Tests cover:
- Model validation
- Default values
- Serialization/deserialization
- Helper methods
"""

import pytest
from datetime import datetime
from pydantic import ValidationError

from prevent_outage_edge_testing.models import (
    ExtractorMode,
    FailureMode,
    KnowledgePack,
    LogPattern,
    MetricDefinition,
    ObservabilityRecipe,
    Severity,
    TestAssertion,
    TestCase,
    TestPlan,
    TraceConfig,
)


class TestSeverity:
    """Tests for Severity enum."""

    def test_severity_values(self):
        """Verify all severity levels exist."""
        assert Severity.CRITICAL == "critical"
        assert Severity.HIGH == "high"
        assert Severity.MEDIUM == "medium"
        assert Severity.LOW == "low"

    def test_severity_from_string(self):
        """Verify severity can be created from string."""
        assert Severity("critical") == Severity.CRITICAL


class TestFailureMode:
    """Tests for FailureMode model."""

    def test_minimal_failure_mode(self):
        """Create failure mode with required fields only."""
        fm = FailureMode(
            id="test-001",
            name="Test Failure",
            description="A test failure mode",
        )
        assert fm.id == "test-001"
        assert fm.severity == Severity.MEDIUM  # default
        assert fm.symptoms == []
        assert fm.tags == []

    def test_full_failure_mode(self, sample_failure_mode):
        """Verify full failure mode creation."""
        assert sample_failure_mode.id == "test-failure-001"
        assert sample_failure_mode.severity == Severity.HIGH
        assert len(sample_failure_mode.symptoms) == 3

    def test_failure_mode_serialization(self, sample_failure_mode):
        """Verify failure mode serializes to dict."""
        data = sample_failure_mode.model_dump()
        assert data["id"] == "test-failure-001"
        assert data["severity"] == "high"

    def test_failure_mode_from_dict(self):
        """Verify failure mode can be created from dict."""
        data = {
            "id": "fm-001",
            "name": "From Dict",
            "description": "Created from dictionary",
            "severity": "critical",
        }
        fm = FailureMode.model_validate(data)
        assert fm.severity == Severity.CRITICAL


class TestTestCase:
    """Tests for TestCase model."""

    def test_test_case_creation(self, sample_test_case):
        """Verify test case creation."""
        assert sample_test_case.id == "test-case-001"
        assert len(sample_test_case.assertions) == 1
        assert sample_test_case.requires_privileged is False

    def test_test_case_with_privileged(self):
        """Create test case requiring privileged mode."""
        tc = TestCase(
            id="priv-001",
            name="Privileged Test",
            description="Needs elevated permissions",
            requires_privileged=True,
        )
        assert tc.requires_privileged is True

    def test_test_assertion(self):
        """Test assertion model."""
        assertion = TestAssertion(
            description="Check value",
            expression="value > 0",
            expected=True,
            timeout_seconds=10.0,
        )
        assert assertion.expression == "value > 0"
        assert assertion.timeout_seconds == 10.0


class TestTestPlan:
    """Tests for TestPlan model."""

    def test_test_plan_creation(self, sample_test_case):
        """Create a test plan."""
        plan = TestPlan(
            id="plan-001",
            title="Test Plan",
            description="A test plan",
            source_description="Feature description here",
            test_cases=[sample_test_case],
        )
        assert plan.id == "plan-001"
        assert len(plan.test_cases) == 1
        assert plan.created_at is not None

    def test_test_plan_with_jira(self, sample_test_case):
        """Create test plan linked to Jira."""
        plan = TestPlan(
            id="plan-002",
            title="Jira-linked Plan",
            description="Linked to Jira issue",
            source_jira_key="PROJ-123",
            source_description="From Jira",
            test_cases=[sample_test_case],
        )
        assert plan.source_jira_key == "PROJ-123"


class TestKnowledgePack:
    """Tests for KnowledgePack model."""

    def test_knowledge_pack_creation(self, sample_knowledge_pack):
        """Verify knowledge pack creation."""
        assert sample_knowledge_pack.id == "test-pack"
        assert len(sample_knowledge_pack.failure_modes) == 1
        assert len(sample_knowledge_pack.test_templates) == 1

    def test_get_failure_mode(self, sample_knowledge_pack):
        """Test getting failure mode by ID."""
        fm = sample_knowledge_pack.get_failure_mode("test-failure-001")
        assert fm is not None
        assert fm.name == "Test Failure Mode"

        # Non-existent
        assert sample_knowledge_pack.get_failure_mode("nonexistent") is None

    def test_get_high_severity_modes(self, sample_knowledge_pack):
        """Test getting high severity failure modes."""
        high_modes = sample_knowledge_pack.get_high_severity_modes()
        assert len(high_modes) == 1
        assert high_modes[0].severity == Severity.HIGH

    def test_knowledge_pack_serialization(self, sample_knowledge_pack):
        """Verify pack serializes correctly."""
        data = sample_knowledge_pack.model_dump()
        assert data["id"] == "test-pack"
        assert "failure_modes" in data
        assert "test_templates" in data


class TestObservabilityRecipe:
    """Tests for ObservabilityRecipe model."""

    def test_metric_definition(self):
        """Test metric definition creation."""
        metric = MetricDefinition(
            name="request_count",
            type="counter",
            description="Total requests",
            labels=["method", "path"],
        )
        assert metric.name == "request_count"
        assert metric.collection_interval_seconds == 15.0

    def test_log_pattern(self):
        """Test log pattern creation."""
        pattern = LogPattern(
            name="error_pattern",
            pattern=r"ERROR.*exception",
            severity=Severity.HIGH,
            action="alert",
        )
        assert pattern.pattern == r"ERROR.*exception"

    def test_trace_config(self):
        """Test trace config creation."""
        config = TraceConfig(
            service_name="test-service",
            sample_rate=0.5,
        )
        assert config.sample_rate == 0.5
        assert config.propagation_format == "w3c"

    def test_observability_recipe(self):
        """Test full observability recipe."""
        recipe = ObservabilityRecipe(
            id="recipe-001",
            name="Test Recipe",
            description="Test observability",
            metrics=[
                MetricDefinition(
                    name="test_metric",
                    type="gauge",
                    description="Test",
                )
            ],
            log_patterns=[
                LogPattern(
                    name="test_pattern",
                    pattern="TEST",
                )
            ],
        )
        assert len(recipe.metrics) == 1
        assert len(recipe.log_patterns) == 1


class TestExtractorMode:
    """Tests for ExtractorMode enum."""

    def test_extractor_modes(self):
        """Verify extractor mode values."""
        assert ExtractorMode.PRIVILEGED == "privileged"
        assert ExtractorMode.SIMULATOR == "simulator"
