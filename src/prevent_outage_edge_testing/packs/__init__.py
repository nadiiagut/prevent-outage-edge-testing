# src/prevent_outage_edge_testing/packs/__init__.py
# Knowledge packs module.
"""
Knowledge packs are structured collections of:
- Failure modes and their characteristics
- Test templates
- Observability recipes
- Code snippets

Pack structure:
    packs/<pack_id>/
    ├── pack.yaml          # Pack definition
    ├── README.md          # Pack documentation
    ├── recipes/           # Observability recipes
    │   └── *.md
    └── snippets/          # Code snippets
        └── *.*
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

__all__ = [
    "FailureMode",
    "KnowledgePack",
    "PackLoader",
    "PackValidator",
    "Recipe",
    "Severity",
    "Snippet",
    "TestAssertion",
    "TestTemplate",
]
