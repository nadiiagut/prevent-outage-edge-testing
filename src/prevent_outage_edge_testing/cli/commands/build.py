# src/prevent_outage_edge_testing/cli/commands/build.py
# Implementation of `poet build` command.
"""
Generates test plans and starter tests from Jira feature descriptions.

Outputs:
- TESTPLAN.md: Structured test plan document
- tests/: Generated pytest starter files
- observability/: Monitoring recipes (optional)
"""

import hashlib
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

import typer
import yaml
from jinja2 import Environment, PackageLoader, select_autoescape
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from prevent_outage_edge_testing.core.config import load_config
from prevent_outage_edge_testing.core.builder import TestPlanBuilder
from prevent_outage_edge_testing.packs.loader import PackLoader

console = Console()


def build_command(
    jira_text: Optional[str] = typer.Option(
        None, "--jira-text", "-j", help="Jira feature description text"
    ),
    jira_file: Optional[Path] = typer.Option(
        None, "--jira-file", "-f", help="File containing Jira/markdown description"
    ),
    openapi: Optional[Path] = typer.Option(
        None, "--openapi", help="OpenAPI/Swagger spec file (YAML or JSON)"
    ),
    obligations: Optional[str] = typer.Option(
        None, "--obligations", help="Obligation patterns to include (e.g., 'cache.*')"
    ),
    packs_filter: Optional[str] = typer.Option(
        None, "--packs", help="Specific packs to use (comma-separated)"
    ),
    output_dir: Path = typer.Option(
        Path("generated"), "--output", "-o", help="Output directory"
    ),
    title: Optional[str] = typer.Option(
        None, "--title", "-t", help="Test plan title"
    ),
    jira_key: Optional[str] = typer.Option(
        None, "--jira-key", "-k", help="Jira issue key (e.g., PROJ-123)"
    ),
    explain: bool = typer.Option(
        False, "--explain", "-e", help="Show pack selection explanation"
    ),
    include_snippets: bool = typer.Option(
        True, "--snippets/--no-snippets", help="Include code snippets"
    ),
    include_recipes: bool = typer.Option(
        True, "--recipes/--no-recipes", help="Include observability recipes"
    ),
) -> None:
    """
    Build test plan and starter tests from feature description.
    
    Input modes:
      --jira-text    Inline Jira/feature description
      --jira-file    File containing description (txt, md)
      --openapi      OpenAPI/Swagger spec file
      --obligations  Direct obligation selection (e.g., 'cache.*')
      --packs        Specific packs to use
    
    Examples:
      poet build --jira-text "Add cache bypass..."
      poet build --jira-file feature.md --title "My Feature"
      poet build --openapi api.yaml
      poet build --obligations "cache.*,routing.*"
      poet build --jira-file spec.md --explain
    """
    
    # Get description text
    description = ""
    input_mode = "unknown"
    
    if openapi:
        if not openapi.exists():
            console.print(f"[red]File not found: {openapi}[/red]")
            raise typer.Exit(1)
        # For now, extract paths from OpenAPI as description
        console.print(f"[yellow]OpenAPI support is experimental[/yellow]")
        description = f"OpenAPI spec: {openapi.name}\n\n" + openapi.read_text()[:2000]
        input_mode = "openapi"
    elif jira_file:
        if not jira_file.exists():
            console.print(f"[red]File not found: {jira_file}[/red]")
            raise typer.Exit(1)
        description = jira_file.read_text()
        input_mode = "file"
    elif jira_text:
        description = jira_text
        input_mode = "text"
    elif obligations or packs_filter:
        # Direct selection mode - no description needed
        description = f"Direct selection: obligations={obligations}, packs={packs_filter}"
        input_mode = "direct"
    else:
        console.print("[yellow]Enter feature description (Ctrl+D to end):[/yellow]")
        import sys
        description = sys.stdin.read()
        input_mode = "stdin"
    
    if not description.strip() and input_mode not in ("direct",):
        console.print("[red]No description provided[/red]")
        raise typer.Exit(1)
    
    # Load config
    config = load_config()
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        # Load packs
        task = progress.add_task("Loading knowledge packs...", total=None)
        loader = PackLoader(config.packs_paths if config else [Path("packs")])
        packs = loader.load_all()
        progress.update(task, completed=True)
        
        # Build test plan
        task = progress.add_task("Analyzing description...", total=None)
        builder = TestPlanBuilder(packs)
        result = builder.build(
            description=description,
            title=title,
            jira_key=jira_key,
        )
        progress.update(task, completed=True)
        
        # Create output directory
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate TESTPLAN.md
        task = progress.add_task("Generating TESTPLAN.md...", total=None)
        testplan_path = output_dir / "TESTPLAN.md"
        _write_testplan_md(testplan_path, result, description)
        progress.update(task, completed=True)
        
        # Generate starter tests
        task = progress.add_task("Generating starter tests...", total=None)
        tests_dir = output_dir / "tests"
        tests_dir.mkdir(exist_ok=True)
        _write_starter_tests(tests_dir, result)
        progress.update(task, completed=True)
        
        # Generate snippets
        if include_snippets and result.snippets:
            task = progress.add_task("Copying code snippets...", total=None)
            snippets_dir = output_dir / "snippets"
            snippets_dir.mkdir(exist_ok=True)
            for snippet in result.snippets:
                (snippets_dir / snippet.filename).write_text(snippet.content)
            progress.update(task, completed=True)
        
        # Generate observability recipes
        if include_recipes and result.recipes:
            task = progress.add_task("Generating observability recipes...", total=None)
            recipes_dir = output_dir / "observability"
            recipes_dir.mkdir(exist_ok=True)
            for recipe in result.recipes:
                recipe_path = recipes_dir / f"{recipe.id}.md"
                recipe_path.write_text(recipe.to_markdown())
            progress.update(task, completed=True)
    
    # Show explanation if requested
    if explain:
        _print_explanation(result, description)
    
    # Summary
    console.print()
    console.print(Panel(
        f"[bold]Title:[/bold] {result.plan.title}\n"
        f"[bold]Test Cases:[/bold] {len(result.plan.test_cases)}\n"
        f"[bold]Failure Modes:[/bold] {len(result.plan.failure_modes_covered)}\n"
        f"[bold]Packs Used:[/bold] {len(result.matched_packs)}",
        title="[green]✓ Build Complete[/green]",
    ))
    
    console.print(f"\n[bold]Output:[/bold]")
    console.print(f"  📄 {testplan_path}")
    console.print(f"  🧪 {tests_dir}/")
    if include_snippets and result.snippets:
        console.print(f"  📝 {output_dir}/snippets/")
    if include_recipes and result.recipes:
        console.print(f"  📊 {output_dir}/observability/")


def _write_testplan_md(path: Path, result, description: str) -> None:
    """Write the TESTPLAN.md file."""
    lines = [
        f"# {result.plan.title}",
        "",
        f"> Generated by POET on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## Source Description",
        "",
        "```",
        description.strip(),
        "```",
        "",
        "## Failure Modes Covered",
        "",
    ]
    
    for fm_id in result.plan.failure_modes_covered:
        lines.append(f"- `{fm_id}`")
    
    lines.extend([
        "",
        "## Test Cases",
        "",
    ])
    
    for i, tc in enumerate(result.plan.test_cases, 1):
        lines.extend([
            f"### {i}. {tc.name}",
            "",
            f"**Priority:** {tc.priority.value}",
            f"**Failure Mode:** `{tc.failure_mode_id or 'N/A'}`",
            "",
            tc.description,
            "",
            "**Setup:**",
        ])
        for step in tc.setup_steps:
            lines.append(f"1. {step}")
        
        lines.extend(["", "**Execution:**"])
        for step in tc.execution_steps:
            lines.append(f"1. {step}")
        
        lines.extend(["", "**Assertions:**"])
        for assertion in tc.assertions:
            lines.append(f"- [ ] {assertion.description}")
        
        lines.append("")
    
    lines.extend([
        "## Coverage Notes",
        "",
        result.plan.coverage_notes or "_No additional notes._",
        "",
        "---",
        "",
        "_This test plan is a starting point. Review and customize before use._",
        "_POET does not guarantee complete coverage of all failure modes._",
    ])
    
    path.write_text("\n".join(lines))


def _print_explanation(result, description: str) -> None:
    """Print pack selection explanation."""
    from rich.table import Table
    from rich.tree import Tree
    
    console.print()
    console.print(Panel("[bold]Pack Selection Explanation[/bold]", style="cyan"))
    
    # Extract keywords from description
    keywords = _extract_keywords(description)
    
    # Show matched keywords
    console.print("\n[bold]Matched Keywords:[/bold]")
    if keywords:
        for kw, packs in keywords.items():
            pack_names = ", ".join(packs)
            console.print(f"  • \"{kw}\" → {pack_names}")
    else:
        console.print("  [dim]No domain keywords detected[/dim]")
    
    # Show selected packs with reasons
    console.print("\n[bold]Selected Packs:[/bold]")
    if result.matched_packs:
        for pack in result.matched_packs:
            tree = Tree(f"[green]✓ {pack.name}[/green] ({pack.id})")
            if hasattr(pack, 'failure_modes') and pack.failure_modes:
                fm_names = [fm.name for fm in pack.failure_modes[:3]]
                tree.add(f"[dim]Failure modes: {', '.join(fm_names)}[/dim]")
            if hasattr(pack, 'test_templates') and pack.test_templates:
                tree.add(f"[dim]Test templates: {len(pack.test_templates)} applicable[/dim]")
            if hasattr(pack, 'recipes') and pack.recipes:
                tree.add(f"[dim]Recipes: {len(pack.recipes)} applicable[/dim]")
            console.print(tree)
    else:
        console.print("  [yellow]No packs matched - using defaults[/yellow]")
    
    # Show assumptions
    console.print("\n[bold]Assumptions Detected:[/bold]")
    assumptions = _detect_assumptions(description)
    if assumptions:
        for assumption in assumptions:
            console.print(f"  • {assumption}")
    else:
        console.print("  [dim]No specific assumptions detected[/dim]")
    
    # Show obligations covered
    console.print("\n[bold]Obligations Covered:[/bold]")
    if result.plan.failure_modes_covered:
        for fm in result.plan.failure_modes_covered[:5]:
            console.print(f"  • {fm}")
        if len(result.plan.failure_modes_covered) > 5:
            console.print(f"  [dim]... and {len(result.plan.failure_modes_covered) - 5} more[/dim]")
    else:
        console.print("  [dim]No specific obligations matched[/dim]")


def _extract_keywords(description: str) -> dict[str, list[str]]:
    """Extract domain keywords from description."""
    keyword_map = {
        "cache": ["edge-http-cache-correctness"],
        "caching": ["edge-http-cache-correctness"],
        "stale": ["edge-http-cache-correctness"],
        "vary": ["edge-http-cache-correctness"],
        "ttl": ["edge-http-cache-correctness"],
        "routing": ["edge-http-cache-correctness"],
        "backend": ["edge-http-cache-correctness"],
        "latency": ["edge-latency-regression-observability"],
        "p99": ["edge-latency-regression-observability"],
        "timeout": ["edge-latency-regression-observability", "fault-injection-io"],
        "performance": ["edge-latency-regression-observability"],
        "fault": ["fault-injection-io"],
        "injection": ["fault-injection-io"],
        "failure": ["fault-injection-io"],
        "retry": ["fault-injection-io"],
        "circuit": ["fault-injection-io"],
    }
    
    found = {}
    desc_lower = description.lower()
    for keyword, packs in keyword_map.items():
        if keyword in desc_lower:
            found[keyword] = packs
    return found


def _detect_assumptions(description: str) -> list[str]:
    """Detect assumptions from description."""
    assumptions = []
    desc_lower = description.lower()
    
    if "nginx" in desc_lower:
        assumptions.append("Proxy type: NGINX")
    if "haproxy" in desc_lower:
        assumptions.append("Proxy type: HAProxy")
    if "envoy" in desc_lower:
        assumptions.append("Proxy type: Envoy")
    if "redis" in desc_lower:
        assumptions.append("Cache backend: Redis")
    if "production" in desc_lower:
        assumptions.append("Environment: Production")
    if "staging" in desc_lower:
        assumptions.append("Environment: Staging")
    if "api" in desc_lower or "/api/" in desc_lower:
        assumptions.append("Scope: API endpoints")
    if "cdn" in desc_lower:
        assumptions.append("Scope: CDN/Edge")
    
    return assumptions


def _write_starter_tests(tests_dir: Path, result) -> None:
    """Write starter pytest files."""
    # Write conftest.py
    conftest = tests_dir / "conftest.py"
    conftest.write_text('''# conftest.py - Generated by POET
# Shared fixtures for generated tests.
"""
Auto-generated pytest configuration.
Customize fixtures as needed for your environment.
"""

import pytest


@pytest.fixture
def test_config():
    """Test configuration fixture."""
    return {
        "timeout": 30,
        "retries": 3,
    }


@pytest.fixture
def mock_service():
    """Mock service fixture - implement for your environment."""
    # TODO: Implement mock service setup
    yield None
    # TODO: Implement cleanup
''')
    
    # Write test file
    safe_title = re.sub(r"[^a-z0-9]+", "_", result.plan.title.lower())[:50]
    test_file = tests_dir / f"test_{safe_title}.py"
    
    lines = [
        f'# test_{safe_title}.py - Generated by POET',
        '# Starter tests for: ' + result.plan.title,
        '"""',
        f'Auto-generated tests for: {result.plan.title}',
        f'Generated: {datetime.now().isoformat()}',
        '',
        'WARNING: These are starter tests. Review and implement before use.',
        'POET does not guarantee complete coverage of all failure modes.',
        '"""',
        '',
        'import pytest',
        '',
        '',
    ]
    
    for tc in result.plan.test_cases:
        func_name = re.sub(r"[^a-z0-9]+", "_", tc.name.lower())[:60]
        lines.extend([
            f'@pytest.mark.{tc.priority.value}',
            f'def test_{func_name}(test_config):',
            f'    """',
            f'    {tc.name}',
            f'    ',
            f'    {tc.description}',
            f'    ',
            f'    Failure Mode: {tc.failure_mode_id or "N/A"}',
            f'    """',
            f'    # === SETUP ===',
        ])
        for step in tc.setup_steps:
            lines.append(f'    # {step}')
        
        lines.extend([
            f'    ',
            f'    # === EXECUTION ===',
        ])
        for step in tc.execution_steps:
            lines.append(f'    # {step}')
        
        lines.extend([
            f'    ',
            f'    # === ASSERTIONS ===',
        ])
        for assertion in tc.assertions:
            lines.append(f'    # TODO: {assertion.description}')
            lines.append(f'    # assert {assertion.expression}')
        
        lines.extend([
            f'    ',
            f'    # === CLEANUP ===',
        ])
        for step in tc.cleanup_steps:
            lines.append(f'    # {step}')
        
        lines.extend([
            f'    ',
            f'    pytest.skip("Generated test - implement before use")',
            '',
            '',
        ])
    
    test_file.write_text('\n'.join(lines))
