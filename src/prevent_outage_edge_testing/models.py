# src/prevent_outage_edge_testing/models.py
# Core Pydantic models for knowledge packs, test plans, and observability recipes.

"""
Defines the core data structures used throughout the library:
- KnowledgePack: encapsulates domain knowledge for a specific failure mode
- TestPlan: structured test plan generated from Jira descriptions
- TestCase: individual test case with assertions and setup
- ObservabilityRecipe: metrics/logs/traces configuration for monitoring
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class Severity(str, Enum):
    """Severity levels for failure modes and test priorities."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ExtractorMode(str, Enum):
    """Mode for running extractors - privileged requires elevated permissions."""

    PRIVILEGED = "privileged"  # DTrace, eBPF, LD_PRELOAD
    SIMULATOR = "simulator"  # Safe fallback that simulates behavior


class FailureMode(BaseModel):
    """Describes a specific failure mode that can occur at the edge."""

    id: str = Field(..., description="Unique identifier for this failure mode")
    name: str = Field(..., description="Human-readable name")
    description: str = Field(..., description="Detailed description of the failure")
    severity: Severity = Field(default=Severity.MEDIUM)
    symptoms: list[str] = Field(default_factory=list, description="Observable symptoms")
    root_causes: list[str] = Field(default_factory=list, description="Potential root causes")
    mitigation_strategies: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class TestAssertion(BaseModel):
    """A single assertion within a test case."""

    description: str
    expression: str = Field(..., description="Python expression to evaluate")
    expected: Any = Field(default=True)
    timeout_seconds: float = Field(default=30.0)


class TestCase(BaseModel):
    """Individual test case with setup, execution, and assertions."""

    id: str
    name: str
    description: str
    failure_mode_id: str | None = Field(
        default=None, description="Links to a specific failure mode"
    )
    priority: Severity = Field(default=Severity.MEDIUM)
    setup_steps: list[str] = Field(default_factory=list)
    execution_steps: list[str] = Field(default_factory=list)
    assertions: list[TestAssertion] = Field(default_factory=list)
    cleanup_steps: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    estimated_duration_seconds: int = Field(default=60)
    requires_privileged: bool = Field(
        default=False, description="Whether test needs elevated permissions"
    )


class TestPlan(BaseModel):
    """A complete test plan generated from a Jira feature description."""

    id: str
    title: str
    description: str
    source_jira_key: str | None = Field(default=None)
    source_description: str = Field(..., description="Original feature description")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    test_cases: list[TestCase] = Field(default_factory=list)
    failure_modes_covered: list[str] = Field(
        default_factory=list, description="IDs of failure modes addressed"
    )
    coverage_notes: str = Field(
        default="",
        description="Notes about what is/isn't covered. No guarantees of completeness.",
    )
    tags: list[str] = Field(default_factory=list)


class MetricDefinition(BaseModel):
    """Definition of a metric to collect."""

    name: str
    type: str = Field(..., description="counter, gauge, histogram, summary")
    description: str
    labels: list[str] = Field(default_factory=list)
    unit: str = Field(default="")
    collection_interval_seconds: float = Field(default=15.0)


class LogPattern(BaseModel):
    """Pattern to watch for in logs."""

    name: str
    pattern: str = Field(..., description="Regex pattern to match")
    severity: Severity = Field(default=Severity.MEDIUM)
    action: str = Field(default="alert", description="alert, sample, count")


class TraceConfig(BaseModel):
    """Configuration for distributed tracing."""

    service_name: str
    sample_rate: float = Field(default=0.1, ge=0.0, le=1.0)
    propagation_format: str = Field(default="w3c")
    export_endpoint: str | None = Field(default=None)


class ObservabilityRecipe(BaseModel):
    """Complete observability configuration for a feature or failure mode."""

    id: str
    name: str
    description: str
    failure_mode_ids: list[str] = Field(
        default_factory=list, description="Related failure modes"
    )
    metrics: list[MetricDefinition] = Field(default_factory=list)
    log_patterns: list[LogPattern] = Field(default_factory=list)
    trace_config: TraceConfig | None = Field(default=None)
    dashboards: list[dict[str, Any]] = Field(
        default_factory=list, description="Dashboard definitions (Grafana JSON, etc.)"
    )
    alerts: list[dict[str, Any]] = Field(default_factory=list)
    runbook_url: str | None = Field(default=None)


class KnowledgePack(BaseModel):
    """
    A knowledge pack encapsulates domain expertise about a category of failures.

    Packs are contributed by reliability engineers and used by the AI builder
    to generate contextually relevant test plans.
    """

    id: str = Field(..., description="Unique pack identifier, e.g., 'cdn-cache-invalidation'")
    name: str
    version: str = Field(default="1.0.0")
    description: str
    author: str = Field(default="unknown")
    tags: list[str] = Field(default_factory=list)
    failure_modes: list[FailureMode] = Field(default_factory=list)
    test_templates: list[TestCase] = Field(
        default_factory=list, description="Starter test templates"
    )
    observability_recipes: list[ObservabilityRecipe] = Field(default_factory=list)
    references: list[str] = Field(
        default_factory=list, description="Links to documentation, postmortems, etc."
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    def get_failure_mode(self, mode_id: str) -> FailureMode | None:
        """Get a failure mode by ID."""
        for fm in self.failure_modes:
            if fm.id == mode_id:
                return fm
        return None

    def get_high_severity_modes(self) -> list[FailureMode]:
        """Get all critical and high severity failure modes."""
        return [
            fm
            for fm in self.failure_modes
            if fm.severity in (Severity.CRITICAL, Severity.HIGH)
        ]
