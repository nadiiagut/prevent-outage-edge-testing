# src/prevent_outage_edge_testing/core/knowledge.py
# Knowledge index for learned patterns.
"""
Models and utilities for the local knowledge index.

The knowledge index stores patterns learned from existing tests:
- Assertion patterns
- Naming conventions
- Marker usage
- Fixture patterns

This helps POET generate more contextually relevant tests.
"""

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


class PatternType(str, Enum):
    """Types of patterns that can be learned."""
    
    ASSERTION = "assertion"
    NAMING = "naming"
    MARKER = "marker"
    FIXTURE = "fixture"
    SETUP = "setup"
    TEARDOWN = "teardown"
    PARAMETRIZE = "parametrize"


class LearnedPattern(BaseModel):
    """A pattern learned from existing tests."""
    
    pattern_type: PatternType
    name: str = Field(..., description="Pattern identifier")
    source_file: str = Field(default="", description="File where pattern was found")
    line_number: int = Field(default=0, description="Line number in source")
    context: str = Field(default="", description="Surrounding code context")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0, description="Pattern confidence")
    occurrences: int = Field(default=1, description="Number of times seen")
    tags: list[str] = Field(default_factory=list, description="Associated tags")
    
    def to_suggestion(self) -> str:
        """Convert pattern to a code suggestion."""
        if self.pattern_type == PatternType.ASSERTION:
            return f"# Pattern: {self.name}\n# assert ..."
        elif self.pattern_type == PatternType.MARKER:
            return f"@pytest.mark.{self.name}"
        elif self.pattern_type == PatternType.FIXTURE:
            return f"# Use fixture: {self.name}"
        return f"# {self.pattern_type.value}: {self.name}"


class KnowledgeIndex(BaseModel):
    """Local knowledge index storing learned patterns."""
    
    version: str = Field(default="1.0")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    patterns: list[LearnedPattern] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list, description="Source paths scanned")
    
    def get_patterns_by_type(self, pattern_type: PatternType) -> list[LearnedPattern]:
        """Get all patterns of a specific type."""
        return [p for p in self.patterns if p.pattern_type == pattern_type]
    
    def get_high_confidence_patterns(self, min_confidence: float = 0.7) -> list[LearnedPattern]:
        """Get patterns above a confidence threshold."""
        return [p for p in self.patterns if p.confidence >= min_confidence]
    
    def get_suggestions_for_failure_mode(self, failure_mode_id: str) -> list[str]:
        """Get code suggestions relevant to a failure mode."""
        suggestions = []
        
        # Map failure mode keywords to pattern types
        keywords = failure_mode_id.lower().split("-")
        
        for pattern in self.get_high_confidence_patterns():
            if any(kw in pattern.name.lower() for kw in keywords):
                suggestions.append(pattern.to_suggestion())
        
        return suggestions[:5]  # Limit suggestions


def load_knowledge_index(path: Path) -> Optional[KnowledgeIndex]:
    """Load knowledge index from JSON file."""
    if not path.exists():
        return None
    
    import json
    with open(path) as f:
        data = json.load(f)
    
    return KnowledgeIndex.model_validate(data)


def save_knowledge_index(index: KnowledgeIndex, path: Path) -> None:
    """Save knowledge index to JSON file."""
    import json
    
    with open(path, "w") as f:
        json.dump(index.model_dump(mode="json"), f, indent=2, default=str)
