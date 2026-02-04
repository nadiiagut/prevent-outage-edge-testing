# src/prevent_outage_edge_testing/cli/__init__.py
# CLI package for POET (Prevent Outage Edge Testing).
"""
CLI module providing the `poet` command-line interface.

Commands:
- poet init: Create local config with system profile
- poet build --jira-text: Generate test plan from Jira description
- poet packs list/show/validate: Manage knowledge packs
- poet learn --from-tests: Extract patterns from existing tests
"""

from prevent_outage_edge_testing.cli.main import app

__all__ = ["app"]
