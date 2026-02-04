# src/prevent_outage_edge_testing/packs/models.py
# Pydantic models for knowledge pack schema.
"""
Defines the schema for knowledge packs using Pydantic models.

These models are used for:
- Schema validation during pack loading
- Type-safe access to pack data
- JSON/YAML serialization
"""

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field


class Severity(str, Enum):
    """Severity levels for failure modes and test priorities."""
    
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class FailureMode(BaseModel):
    """A specific failure mode that can occur."""
    
    id: str = Field(..., description="Unique identifier")
    name: str = Field(..., description="Human-readable name")
    description: str = Field(default="", description="Detailed description")
    severity: Severity = Field(default=Severity.MEDIUM)
    symptoms: list[str] = Field(default_factory=list, description="Observable symptoms")
    root_causes: list[str] = Field(default_factory=list, description="Potential causes")
    mitigation_strategies: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class TestAssertion(BaseModel):
    """A single test assertion."""
    
    description: str = Field(..., description="What this assertion checks")
    expression: str = Field(default="True", description="Python expression")
    expected: bool = Field(default=True)
    timeout_seconds: float = Field(default=30.0)


class TestTemplate(BaseModel):
    """A test template for generating test cases."""
    
    id: str = Field(..., description="Unique identifier")
    name: str = Field(..., description="Test name")
    description: str = Field(default="")
    failure_mode_id: Optional[str] = Field(default=None, description="Linked failure mode")
    priority: Severity = Field(default=Severity.MEDIUM)
    setup_steps: list[str] = Field(default_factory=list)
    execution_steps: list[str] = Field(default_factory=list)
    assertions: list[TestAssertion] = Field(default_factory=list)
    cleanup_steps: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    requires_privileged: bool = Field(default=False)
    fallback_available: bool = Field(default=True, description="Has simulator fallback")


class MetricDefinition(BaseModel):
    """Definition of a metric to collect."""
    
    name: str
    type: str = Field(default="gauge", description="counter, gauge, histogram")
    description: str = Field(default="")
    labels: list[str] = Field(default_factory=list)
    unit: str = Field(default="")


class AlertDefinition(BaseModel):
    """Definition of an alert rule."""
    
    name: str
    expression: str = Field(..., description="Alert expression (e.g., PromQL)")
    duration: str = Field(default="5m", description="How long condition must be true")
    severity: Severity = Field(default=Severity.MEDIUM)
    description: str = Field(default="")


class Recipe(BaseModel):
    """An observability recipe."""
    
    id: str = Field(..., description="Unique identifier")
    name: str = Field(..., description="Recipe name")
    description: str = Field(default="")
    failure_mode_ids: list[str] = Field(default_factory=list)
    metrics: list[MetricDefinition] = Field(default_factory=list)
    alerts: list[AlertDefinition] = Field(default_factory=list)
    dashboard_json: Optional[dict[str, Any]] = Field(default=None)
    runbook_url: Optional[str] = Field(default=None)
    content: str = Field(default="", description="Markdown content if loaded from file")
    
    def to_markdown(self) -> str:
        """Convert recipe to markdown format."""
        if self.content:
            return self.content
        
        lines = [
            f"# {self.name}",
            "",
            self.description,
            "",
            "## Metrics",
            "",
        ]
        
        for metric in self.metrics:
            lines.append(f"- **{metric.name}** ({metric.type}): {metric.description}")
        
        if self.alerts:
            lines.extend(["", "## Alerts", ""])
            for alert in self.alerts:
                lines.append(f"- **{alert.name}** [{alert.severity.value}]: {alert.description}")
        
        if self.runbook_url:
            lines.extend(["", f"## Runbook", "", f"See: {self.runbook_url}"])
        
        return "\n".join(lines)


class Snippet(BaseModel):
    """A code snippet."""
    
    filename: str = Field(..., description="Snippet filename")
    language: str = Field(default="python", description="Programming language")
    description: str = Field(default="")
    content: str = Field(default="", description="Snippet content")
    requires_privileged: bool = Field(default=False)
    fallback_snippet: Optional[str] = Field(default=None, description="Fallback snippet filename")
    tags: list[str] = Field(default_factory=list)


class KnowledgePack(BaseModel):
    """A complete knowledge pack."""
    
    id: str = Field(..., description="Unique pack identifier")
    name: str = Field(..., description="Human-readable name")
    version: str = Field(default="1.0.0")
    description: str = Field(default="")
    author: str = Field(default="unknown")
    tags: list[str] = Field(default_factory=list)
    failure_modes: list[FailureMode] = Field(default_factory=list)
    test_templates: list[TestTemplate] = Field(default_factory=list)
    recipes: list[Recipe] = Field(default_factory=list)
    snippets: list[Snippet] = Field(default_factory=list)
    references: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Path where pack was loaded from (not serialized)
    _source_path: Optional[Path] = None
    
    def get_failure_mode(self, mode_id: str) -> Optional[FailureMode]:
        """Get failure mode by ID."""
        for fm in self.failure_modes:
            if fm.id == mode_id:
                return fm
        return None
    
    def get_test_template(self, template_id: str) -> Optional[TestTemplate]:
        """Get test template by ID."""
        for tt in self.test_templates:
            if tt.id == template_id:
                return tt
        return None
