# tests/test_builder.py
# Tests for the AI-assisted test plan builder.

"""
Unit tests for TestPlanBuilder functionality.

Tests cover:
- Pack matching from descriptions
- Test plan generation
- Observability recipe retrieval
- Builder configuration options
"""

import pytest

from prevent_outage_edge_testing.builder import (
    BuilderConfig,
    MatchResult,
    TestPlanBuilder,
    build_test_plan,
)
from prevent_outage_edge_testing.models import Severity, TestPlan


class TestBuilderConfig:
    """Tests for BuilderConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = BuilderConfig()
        assert config.min_relevance_score == 0.3
        assert config.include_observability is True
        assert config.max_test_cases == 20
        assert config.prioritize_critical is True

    def test_custom_config(self):
        """Test custom configuration."""
        config = BuilderConfig(
            min_relevance_score=0.5,
            max_test_cases=10,
            prioritize_critical=False,
        )
        assert config.min_relevance_score == 0.5
        assert config.max_test_cases == 10


class TestTestPlanBuilder:
    """Tests for TestPlanBuilder class."""

    def test_builder_creation(self, populated_registry):
        """Test creating a builder."""
        builder = TestPlanBuilder(registry=populated_registry)
        assert builder.registry is populated_registry

    def test_extract_keywords(self, test_plan_builder, sample_description):
        """Test keyword extraction from description."""
        keywords = test_plan_builder._extract_keywords(sample_description)
        assert "cache" in keywords
        assert "cdn" in keywords
        assert "purge" in keywords

    def test_match_packs(self, test_plan_builder, sample_description):
        """Test matching packs against description."""
        matches = test_plan_builder.match_packs(sample_description)
        assert len(matches) > 0
        assert all(isinstance(m, MatchResult) for m in matches)

    def test_match_packs_with_cache_keywords(self, test_plan_builder):
        """Test that cache-related keywords trigger pack matching."""
        description = "We need to implement cache invalidation for our CDN"
        matches = test_plan_builder.match_packs(description)
        # Should match the test pack which has 'cache' and 'cdn' tags
        assert len(matches) >= 1

    def test_build_plan(self, test_plan_builder, sample_description):
        """Test building a test plan."""
        plan = test_plan_builder.build(
            sample_description,
            jira_key="TEST-123",
            title="CDN Cache Tests",
        )
        assert isinstance(plan, TestPlan)
        assert plan.source_jira_key == "TEST-123"
        assert plan.title == "CDN Cache Tests"
        assert len(plan.test_cases) > 0

    def test_build_plan_with_no_matches(self, test_plan_builder):
        """Test building plan when no packs match."""
        description = "Completely unrelated feature about something obscure"
        plan = test_plan_builder.build(description)
        # Should still create a plan, just with notes about no matches
        assert isinstance(plan, TestPlan)
        assert "No matching" in plan.coverage_notes or len(plan.test_cases) == 0

    def test_build_plan_prioritizes_critical(self, test_plan_builder, sample_description):
        """Test that critical tests are prioritized."""
        plan = test_plan_builder.build(sample_description)
        if len(plan.test_cases) >= 2:
            # First test should be high or critical priority
            priorities = [tc.priority for tc in plan.test_cases]
            # Critical/High should come before Medium/Low
            severity_order = {
                Severity.CRITICAL: 0,
                Severity.HIGH: 1,
                Severity.MEDIUM: 2,
                Severity.LOW: 3,
            }
            orders = [severity_order[p] for p in priorities]
            assert orders == sorted(orders)

    def test_build_plan_respects_max_tests(self, populated_registry):
        """Test that max_test_cases config is respected."""
        config = BuilderConfig(max_test_cases=1, min_relevance_score=0.1)
        builder = TestPlanBuilder(registry=populated_registry, config=config)
        plan = builder.build("cache cdn purge invalidation")
        assert len(plan.test_cases) <= 1

    def test_get_observability_recipes(self, test_plan_builder, sample_description):
        """Test retrieving observability recipes for a plan."""
        plan = test_plan_builder.build(sample_description)
        recipes = test_plan_builder.get_observability_recipes(plan)
        # May or may not have recipes depending on failure mode matching
        assert isinstance(recipes, list)

    def test_generate_test_id(self, test_plan_builder):
        """Test test ID generation."""
        id1 = test_plan_builder._generate_test_id("test", "My Test Name")
        id2 = test_plan_builder._generate_test_id("test", "My Test Name")
        # IDs should be unique (include timestamp)
        # Both should start with test- prefix
        assert id1.startswith("test-")
        assert id2.startswith("test-")


class TestBuildTestPlanFunction:
    """Tests for the convenience function."""

    def test_build_test_plan_function(self):
        """Test the standalone build_test_plan function."""
        plan = build_test_plan(
            "A feature involving cache and CDN operations",
            jira_key="FEAT-001",
        )
        assert isinstance(plan, TestPlan)
        assert plan.source_jira_key == "FEAT-001"
