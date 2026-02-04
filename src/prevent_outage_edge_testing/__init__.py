# src/prevent_outage_edge_testing/__init__.py
# Main package init - exports public API for POET.

"""
POET (Prevent Outage Edge Testing): Knowledge pack library + AI-assisted builder
for converting Jira feature descriptions into test plans, starter tests,
and observability recipes.

This library does NOT guarantee 100% coverage or prevention of all outages.
It provides structured tooling to improve edge reliability testing practices.

CLI Usage:
    poet init                      # Initialize local configuration
    poet build --jira-text "..."   # Generate test plan from description
    poet packs list                # List available knowledge packs
    poet packs show <pack-id>      # Show pack details
    poet packs validate            # Validate all packs
    poet learn --from-tests <dir>  # Learn patterns from existing tests
"""

from prevent_outage_edge_testing.packs.models import (
    FailureMode,
    KnowledgePack,
    Recipe,
    Severity,
    Snippet,
    TestAssertion,
    TestTemplate,
)
from prevent_outage_edge_testing.packs.loader import PackLoader
from prevent_outage_edge_testing.packs.validator import PackValidator
from prevent_outage_edge_testing.core.config import PoetConfig, load_config
from prevent_outage_edge_testing.core.knowledge import KnowledgeIndex, LearnedPattern
from prevent_outage_edge_testing.core.builder import TestPlanBuilder, TestPlan, BuildResult

__version__ = "0.1.0"
__all__ = [
    # Pack models
    "FailureMode",
    "KnowledgePack",
    "Recipe",
    "Severity",
    "Snippet",
    "TestAssertion",
    "TestTemplate",
    # Pack utilities
    "PackLoader",
    "PackValidator",
    # Configuration
    "PoetConfig",
    "load_config",
    # Knowledge
    "KnowledgeIndex",
    "LearnedPattern",
    # Builder
    "BuildResult",
    "TestPlan",
    "TestPlanBuilder",
]
