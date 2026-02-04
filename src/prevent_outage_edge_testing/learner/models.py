# src/prevent_outage_edge_testing/learner/models.py
"""
Pydantic models for learned patterns.

These models define the schema for .poet/learned_patterns.json
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class FixtureRole(str, Enum):
    """Inferred roles for fixtures."""
    
    EDGE_NODE = "edge_node"
    ORIGIN = "origin"
    CACHE = "cache"
    LOAD_BALANCER = "load_balancer"
    DATABASE = "database"
    CLIENT = "client"
    PURGE = "purge"
    MOCK_SERVER = "mock_server"
    CONFIG = "config"
    METRICS = "metrics"
    TRACER = "tracer"
    INJECTOR = "injector"
    UNKNOWN = "unknown"


class Signal(BaseModel):
    """A keyword or string pattern found in tests."""
    
    value: str = Field(..., description="The signal string/keyword")
    category: str = Field(default="general", description="Category of signal")
    occurrences: int = Field(default=1, description="Number of times found")
    source_files: list[str] = Field(default_factory=list, description="Files where found")
    context: str = Field(default="", description="Example context where found")


class ExtractedFixture(BaseModel):
    """A pytest fixture extracted from tests."""
    
    name: str = Field(..., description="Fixture name")
    inferred_role: FixtureRole = Field(default=FixtureRole.UNKNOWN)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Confidence in role inference")
    scope: str = Field(default="function", description="Fixture scope if detected")
    usages: int = Field(default=1, description="Number of times used")
    source_file: str = Field(default="", description="File where defined")
    parameters: list[str] = Field(default_factory=list, description="Parameters if any")
    docstring: str = Field(default="", description="Fixture docstring if found")
    role_indicators: list[str] = Field(default_factory=list, description="Why this role was inferred")


class AssertionTemplate(BaseModel):
    """A normalized assertion pattern."""
    
    pattern_type: str = Field(..., description="Type: status_code, header, cache, retry, etc.")
    template: str = Field(..., description="Normalized assertion template")
    examples: list[str] = Field(default_factory=list, description="Actual assertion examples")
    occurrences: int = Field(default=1)
    expected_values: list[str] = Field(default_factory=list, description="Common expected values")


class TimingAssertion(BaseModel):
    """A timing/performance assertion pattern."""
    
    metric_type: str = Field(..., description="Type: p50, p95, p99, latency, duration, etc.")
    comparison: str = Field(default="<", description="Comparison operator")
    threshold_value: Optional[float] = Field(default=None, description="Numeric threshold if found")
    threshold_unit: str = Field(default="ms", description="Unit: ms, s, etc.")
    context: str = Field(default="", description="What is being measured")
    occurrences: int = Field(default=1)
    examples: list[str] = Field(default_factory=list)


class ObservabilityPattern(BaseModel):
    """A pattern indicating observability tool usage."""
    
    tool_type: str = Field(..., description="Tool: tcpdump, dtrace, wireshark, prometheus, etc.")
    pattern: str = Field(..., description="The pattern/command found")
    source_file: str = Field(default="")
    line_number: int = Field(default=0)
    context: str = Field(default="", description="Surrounding context")


class FaultInjectionPattern(BaseModel):
    """A pattern indicating fault injection."""
    
    fault_type: str = Field(..., description="Type: timeout, connection_drop, dns, disk, etc.")
    method: str = Field(default="", description="How it's injected")
    target: str = Field(default="", description="What is targeted")
    examples: list[str] = Field(default_factory=list)
    source_files: list[str] = Field(default_factory=list)
    occurrences: int = Field(default=1)


class EndpointPattern(BaseModel):
    """An endpoint/host/port pattern found in tests."""
    
    pattern_type: str = Field(..., description="Type: url, host, port, path")
    value: str = Field(..., description="The pattern value")
    occurrences: int = Field(default=1)
    source_files: list[str] = Field(default_factory=list)
    is_parameterized: bool = Field(default=False, description="Uses variables/fixtures")


class RiskRule(BaseModel):
    """A derived heuristic for pack recommendation."""
    
    rule_id: str = Field(..., description="Unique rule identifier")
    description: str = Field(..., description="Human-readable description")
    condition: str = Field(..., description="What triggers this rule")
    recommended_packs: list[str] = Field(default_factory=list, description="Pack IDs to recommend")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    derived_from: list[str] = Field(default_factory=list, description="What patterns led to this rule")


class LearnedPatterns(BaseModel):
    """Root model for knowledge/learned/{knowledge_id}.json."""
    
    version: str = Field(default="1.0")
    knowledge_id: str = Field(default="", description="Unique knowledge ID for this learned set")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    source_paths: list[str] = Field(default_factory=list, description="Paths that were analyzed")
    total_files_analyzed: int = Field(default=0)
    total_test_functions: int = Field(default=0)
    total_test_classes: int = Field(default=0)
    
    signals: list[Signal] = Field(default_factory=list)
    fixtures: list[ExtractedFixture] = Field(default_factory=list)
    assertion_templates: list[AssertionTemplate] = Field(default_factory=list)
    timing_assertions: list[TimingAssertion] = Field(default_factory=list)
    observability_patterns: list[ObservabilityPattern] = Field(default_factory=list)
    fault_injection_patterns: list[FaultInjectionPattern] = Field(default_factory=list)
    endpoints: list[EndpointPattern] = Field(default_factory=list)
    risk_rules: list[RiskRule] = Field(default_factory=list)
    
    def get_high_confidence_fixtures(self, min_confidence: float = 0.7) -> list[ExtractedFixture]:
        """Get fixtures with confidence above threshold."""
        return [f for f in self.fixtures if f.confidence >= min_confidence]
    
    def get_signals_by_category(self, category: str) -> list[Signal]:
        """Get signals in a specific category."""
        return [s for s in self.signals if s.category == category]
    
    def get_applicable_risk_rules(self, min_confidence: float = 0.5) -> list[RiskRule]:
        """Get risk rules above confidence threshold."""
        return [r for r in self.risk_rules if r.confidence >= min_confidence]
