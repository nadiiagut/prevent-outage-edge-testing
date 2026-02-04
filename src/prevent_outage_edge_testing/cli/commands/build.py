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
        None, "--jira-file", "-f", help="File containing Jira description"
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
    include_snippets: bool = typer.Option(
        True, "--snippets/--no-snippets", help="Include code snippets"
    ),
    include_recipes: bool = typer.Option(
        True, "--recipes/--no-recipes", help="Include observability recipes"
    ),
) -> None:
    """Build test plan and starter tests from Jira feature description."""
    
    # Get description text
    if jira_file:
        if not jira_file.exists():
            console.print(f"[red]File not found: {jira_file}[/red]")
            raise typer.Exit(1)
        description = jira_file.read_text()
    elif jira_text:
        description = jira_text
    else:
        console.print("[yellow]Enter Jira feature description (Ctrl+D to end):[/yellow]")
        import sys
        description = sys.stdin.read()
    
    if not description.strip():
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
