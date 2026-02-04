# src/prevent_outage_edge_testing/cli/commands/learn.py
# Implementation of `poet learn` command.
"""
Extracts patterns from existing tests using AST analysis.

The learn command:
1. Discovers and parses test files (static analysis, no execution)
2. Extracts endpoints, fixtures, assertions, timing patterns
3. Identifies observability tool usage and fault injection patterns
4. Derives risk rules for pack recommendations
5. Saves to .poet/learned_patterns.json

Commands:
- poet learn --from-tests <path>  : Learn patterns from test suite
- poet learn show                 : Display learned patterns summary
"""

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.table import Table
from rich.tree import Tree

from prevent_outage_edge_testing.learner.analyzer import (
    TestAnalyzer,
    analyze_test_file,
    discover_test_files,
)
from prevent_outage_edge_testing.learner.extractor import PatternExtractor
from prevent_outage_edge_testing.learner.models import LearnedPatterns, FixtureRole
from prevent_outage_edge_testing.learner.storage import (
    save_patterns,
    load_patterns,
    merge_patterns,
    get_patterns_path,
)

console = Console()

# Create subcommand app for learn
learn_app = typer.Typer(help="Learn patterns from existing tests")


@learn_app.command("from-tests")
def learn_from_tests(
    path: Path = typer.Argument(
        ..., help="Path to test directory or file"
    ),
    output_dir: Optional[Path] = typer.Option(
        None, "--output", "-o", help="Output directory for .poet folder"
    ),
    merge: bool = typer.Option(
        True, "--merge/--replace", help="Merge with existing patterns"
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Show detailed output"
    ),
) -> None:
    """
    Learn patterns from existing pytest test suite.
    
    Performs static analysis (AST parsing) on test files to extract:
    - Endpoints/hosts/ports referenced
    - Fixtures and their inferred roles
    - Assertion patterns (status codes, headers, cache, timing)
    - Observability tool usage (tcpdump, dtrace, etc.)
    - Fault injection patterns (timeouts, connection drops, etc.)
    
    Results are saved to .poet/learned_patterns.json
    
    Examples:
        poet learn from-tests ./tests/
        poet learn from-tests ./tests/test_cache.py -v
        poet learn from-tests ./tests/ --replace
    """
    if not path.exists():
        console.print(f"[red]Error: Path not found: {path}[/red]")
        raise typer.Exit(1)
    
    base_dir = output_dir or Path.cwd()
    
    # Discover test files
    console.print(f"\n[bold]Discovering test files in:[/bold] {path}")
    test_files = discover_test_files(path)
    
    if not test_files:
        console.print("[yellow]No test files found.[/yellow]")
        console.print("[dim]Looking for files matching: test_*.py, *_test.py, conftest.py[/dim]")
        raise typer.Exit(1)
    
    console.print(f"[green]Found {len(test_files)} test files[/green]\n")
    
    # Parse test files
    parsed_files = []
    parse_errors = []
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        console=console,
    ) as progress:
        task = progress.add_task("Parsing test files...", total=len(test_files))
        
        for test_file in test_files:
            result = analyze_test_file(test_file)
            if result:
                parsed_files.append(result)
            else:
                parse_errors.append(test_file)
            progress.advance(task)
    
    if parse_errors and verbose:
        console.print(f"[yellow]Warning: Could not parse {len(parse_errors)} files[/yellow]")
    
    # Extract patterns
    console.print("\n[bold]Extracting patterns...[/bold]")
    extractor = PatternExtractor()
    patterns = extractor.extract_from_files(parsed_files)
    
    # Merge with existing if requested
    if merge:
        existing = load_patterns(base_dir)
        if existing:
            console.print("[dim]Merging with existing patterns...[/dim]")
            patterns = merge_patterns(existing, patterns)
    
    # Save patterns
    patterns_path = save_patterns(patterns, base_dir)
    
    # Display summary
    _display_learn_summary(patterns, verbose)
    
    console.print(f"\n[green]✓ Patterns saved to:[/green] {patterns_path}")


@learn_app.command("show")
def learn_show(
    base_dir: Optional[Path] = typer.Option(
        None, "--dir", "-d", help="Directory containing .poet folder"
    ),
    section: Optional[str] = typer.Option(
        None, "--section", "-s", 
        help="Show specific section: signals, fixtures, assertions, timing, observability, faults, endpoints, rules"
    ),
    json_output: bool = typer.Option(
        False, "--json", help="Output as JSON"
    ),
) -> None:
    """
    Display summary of learned patterns.
    
    Shows patterns extracted from previous `poet learn from-tests` runs.
    
    Examples:
        poet learn show
        poet learn show --section fixtures
        poet learn show --json
    """
    dir_path = base_dir or Path.cwd()
    patterns = load_patterns(dir_path)
    
    if not patterns:
        console.print("[yellow]No learned patterns found.[/yellow]")
        console.print(f"[dim]Expected file: {get_patterns_path(dir_path)}[/dim]")
        console.print("\n[dim]Run 'poet learn from-tests <path>' first.[/dim]")
        raise typer.Exit(1)
    
    if json_output:
        import json
        console.print(json.dumps(patterns.model_dump(mode="json"), indent=2, default=str))
        return
    
    if section:
        _display_section(patterns, section)
    else:
        _display_full_summary(patterns)


def _display_learn_summary(patterns: LearnedPatterns, verbose: bool) -> None:
    """Display summary after learning."""
    
    # Summary panel
    summary_text = (
        f"[bold]Files analyzed:[/bold] {patterns.total_files_analyzed}\n"
        f"[bold]Test functions:[/bold] {patterns.total_test_functions}\n"
        f"[bold]Test classes:[/bold] {patterns.total_test_classes}\n"
        f"[bold]Signals:[/bold] {len(patterns.signals)}\n"
        f"[bold]Fixtures:[/bold] {len(patterns.fixtures)}\n"
        f"[bold]Assertion templates:[/bold] {len(patterns.assertion_templates)}\n"
        f"[bold]Timing assertions:[/bold] {len(patterns.timing_assertions)}\n"
        f"[bold]Observability patterns:[/bold] {len(patterns.observability_patterns)}\n"
        f"[bold]Fault injection patterns:[/bold] {len(patterns.fault_injection_patterns)}\n"
        f"[bold]Endpoints:[/bold] {len(patterns.endpoints)}\n"
        f"[bold]Risk rules derived:[/bold] {len(patterns.risk_rules)}"
    )
    
    console.print(Panel(summary_text, title="[green]✓ Learning Complete[/green]"))
    
    # Show top fixtures with roles
    if patterns.fixtures:
        table = Table(title="Top Fixtures (Inferred Roles)")
        table.add_column("Fixture", style="cyan")
        table.add_column("Role", style="green")
        table.add_column("Confidence", justify="right")
        table.add_column("Usages", justify="right")
        
        sorted_fixtures = sorted(patterns.fixtures, key=lambda f: f.confidence, reverse=True)[:8]
        for f in sorted_fixtures:
            conf_color = "green" if f.confidence > 0.7 else "yellow" if f.confidence > 0.4 else "red"
            table.add_row(
                f.name,
                f.inferred_role.value,
                f"[{conf_color}]{f.confidence:.0%}[/{conf_color}]",
                str(f.usages),
            )
        console.print(table)
    
    # Show risk rules
    if patterns.risk_rules:
        console.print("\n[bold]Pack Recommendations:[/bold]")
        for rule in sorted(patterns.risk_rules, key=lambda r: r.confidence, reverse=True)[:5]:
            packs = ", ".join(rule.recommended_packs)
            console.print(f"  • [cyan]{rule.description}[/cyan]")
            console.print(f"    → Recommend: [green]{packs}[/green] (confidence: {rule.confidence:.0%})")
    
    if verbose:
        # Show assertion patterns
        if patterns.assertion_templates:
            console.print("\n[bold]Assertion Patterns:[/bold]")
            for template in sorted(patterns.assertion_templates, key=lambda t: t.occurrences, reverse=True)[:5]:
                console.print(f"  • [{template.pattern_type}] {template.occurrences}x occurrences")
                if template.expected_values:
                    console.print(f"    Expected values: {', '.join(template.expected_values[:5])}")


def _display_full_summary(patterns: LearnedPatterns) -> None:
    """Display full summary of learned patterns."""
    
    # Header
    console.print(Panel(
        f"[bold]Learned Patterns Summary[/bold]\n\n"
        f"Created: {patterns.created_at.strftime('%Y-%m-%d %H:%M')}\n"
        f"Updated: {patterns.updated_at.strftime('%Y-%m-%d %H:%M')}\n"
        f"Sources: {len(patterns.source_paths)} paths analyzed",
        title="POET Knowledge Base"
    ))
    
    # Statistics tree
    tree = Tree("[bold]Statistics[/bold]")
    tree.add(f"Files analyzed: {patterns.total_files_analyzed}")
    tree.add(f"Test functions: {patterns.total_test_functions}")
    tree.add(f"Test classes: {patterns.total_test_classes}")
    
    patterns_branch = tree.add("Patterns extracted:")
    patterns_branch.add(f"Signals: {len(patterns.signals)}")
    patterns_branch.add(f"Fixtures: {len(patterns.fixtures)}")
    patterns_branch.add(f"Assertion templates: {len(patterns.assertion_templates)}")
    patterns_branch.add(f"Timing assertions: {len(patterns.timing_assertions)}")
    patterns_branch.add(f"Observability patterns: {len(patterns.observability_patterns)}")
    patterns_branch.add(f"Fault injection patterns: {len(patterns.fault_injection_patterns)}")
    patterns_branch.add(f"Endpoints: {len(patterns.endpoints)}")
    
    console.print(tree)
    
    # Fixtures table
    if patterns.fixtures:
        console.print("\n")
        table = Table(title="Fixtures with Inferred Roles")
        table.add_column("Name", style="cyan")
        table.add_column("Inferred Role", style="green")
        table.add_column("Confidence", justify="right")
        table.add_column("Scope")
        table.add_column("Indicators")
        
        for f in sorted(patterns.fixtures, key=lambda x: x.confidence, reverse=True)[:10]:
            indicators = ", ".join(f.role_indicators[:2]) if f.role_indicators else "-"
            conf_color = "green" if f.confidence > 0.7 else "yellow" if f.confidence > 0.4 else "dim"
            table.add_row(
                f.name,
                f.inferred_role.value,
                f"[{conf_color}]{f.confidence:.0%}[/{conf_color}]",
                f.scope,
                indicators[:40],
            )
        console.print(table)
    
    # Risk rules
    if patterns.risk_rules:
        console.print("\n")
        table = Table(title="Derived Risk Rules (Pack Recommendations)")
        table.add_column("Rule", style="cyan")
        table.add_column("Confidence", justify="right")
        table.add_column("Recommended Packs", style="green")
        table.add_column("Evidence")
        
        for rule in sorted(patterns.risk_rules, key=lambda r: r.confidence, reverse=True):
            evidence = ", ".join(rule.derived_from[:2])
            table.add_row(
                rule.description[:50],
                f"{rule.confidence:.0%}",
                ", ".join(rule.recommended_packs),
                evidence[:40],
            )
        console.print(table)


def _display_section(patterns: LearnedPatterns, section: str) -> None:
    """Display a specific section of patterns."""
    
    section = section.lower()
    
    if section == "signals":
        if not patterns.signals:
            console.print("[yellow]No signals found.[/yellow]")
            return
        
        table = Table(title="Signals")
        table.add_column("Value", style="cyan")
        table.add_column("Category", style="green")
        table.add_column("Occurrences", justify="right")
        table.add_column("Sources")
        
        for s in sorted(patterns.signals, key=lambda x: x.occurrences, reverse=True)[:20]:
            sources = ", ".join(Path(p).name for p in s.source_files[:2])
            table.add_row(s.value[:50], s.category, str(s.occurrences), sources)
        console.print(table)
    
    elif section == "fixtures":
        if not patterns.fixtures:
            console.print("[yellow]No fixtures found.[/yellow]")
            return
        
        table = Table(title="Extracted Fixtures")
        table.add_column("Name", style="cyan")
        table.add_column("Role", style="green")
        table.add_column("Confidence", justify="right")
        table.add_column("Scope")
        table.add_column("Usages", justify="right")
        table.add_column("Indicators")
        
        for f in sorted(patterns.fixtures, key=lambda x: x.confidence, reverse=True):
            indicators = "; ".join(f.role_indicators[:2])
            table.add_row(
                f.name, f.inferred_role.value, f"{f.confidence:.0%}",
                f.scope, str(f.usages), indicators[:50]
            )
        console.print(table)
    
    elif section == "assertions":
        if not patterns.assertion_templates:
            console.print("[yellow]No assertion templates found.[/yellow]")
            return
        
        table = Table(title="Assertion Templates")
        table.add_column("Type", style="cyan")
        table.add_column("Template", style="green")
        table.add_column("Occurrences", justify="right")
        table.add_column("Expected Values")
        
        for t in sorted(patterns.assertion_templates, key=lambda x: x.occurrences, reverse=True):
            values = ", ".join(t.expected_values[:3])
            table.add_row(t.pattern_type, t.template[:60], str(t.occurrences), values)
        console.print(table)
    
    elif section == "timing":
        if not patterns.timing_assertions:
            console.print("[yellow]No timing assertions found.[/yellow]")
            return
        
        table = Table(title="Timing/Performance Assertions")
        table.add_column("Metric", style="cyan")
        table.add_column("Comparison")
        table.add_column("Threshold", justify="right")
        table.add_column("Occurrences", justify="right")
        
        for t in patterns.timing_assertions:
            threshold = f"{t.threshold_value} {t.threshold_unit}" if t.threshold_value else "-"
            table.add_row(t.metric_type, t.comparison, threshold, str(t.occurrences))
        console.print(table)
    
    elif section == "observability":
        if not patterns.observability_patterns:
            console.print("[yellow]No observability patterns found.[/yellow]")
            return
        
        table = Table(title="Observability Tool Usage")
        table.add_column("Tool", style="cyan")
        table.add_column("Pattern", style="green")
        table.add_column("File")
        table.add_column("Line", justify="right")
        
        for p in patterns.observability_patterns:
            file_name = Path(p.source_file).name if p.source_file else "-"
            table.add_row(p.tool_type, p.pattern[:40], file_name, str(p.line_number))
        console.print(table)
    
    elif section in ("faults", "fault-injection"):
        if not patterns.fault_injection_patterns:
            console.print("[yellow]No fault injection patterns found.[/yellow]")
            return
        
        table = Table(title="Fault Injection Patterns")
        table.add_column("Fault Type", style="cyan")
        table.add_column("Occurrences", justify="right")
        table.add_column("Sources")
        
        for f in sorted(patterns.fault_injection_patterns, key=lambda x: x.occurrences, reverse=True):
            sources = ", ".join(Path(p).name for p in f.source_files[:3])
            table.add_row(f.fault_type, str(f.occurrences), sources)
        console.print(table)
    
    elif section == "endpoints":
        if not patterns.endpoints:
            console.print("[yellow]No endpoints found.[/yellow]")
            return
        
        table = Table(title="Endpoints")
        table.add_column("Type", style="cyan")
        table.add_column("Value", style="green")
        table.add_column("Occurrences", justify="right")
        table.add_column("Parameterized")
        
        for e in sorted(patterns.endpoints, key=lambda x: x.occurrences, reverse=True)[:20]:
            param = "Yes" if e.is_parameterized else "No"
            table.add_row(e.pattern_type, e.value[:60], str(e.occurrences), param)
        console.print(table)
    
    elif section == "rules":
        if not patterns.risk_rules:
            console.print("[yellow]No risk rules derived.[/yellow]")
            return
        
        table = Table(title="Risk Rules (Pack Recommendations)")
        table.add_column("ID", style="dim")
        table.add_column("Description", style="cyan")
        table.add_column("Confidence", justify="right")
        table.add_column("Recommended Packs", style="green")
        table.add_column("Derived From")
        
        for r in sorted(patterns.risk_rules, key=lambda x: x.confidence, reverse=True):
            derived = ", ".join(r.derived_from[:2])
            packs = ", ".join(r.recommended_packs)
            table.add_row(r.rule_id, r.description[:40], f"{r.confidence:.0%}", packs, derived[:40])
        console.print(table)
    
    else:
        console.print(f"[red]Unknown section: {section}[/red]")
        console.print("[dim]Valid sections: signals, fixtures, assertions, timing, observability, faults, endpoints, rules[/dim]")
        raise typer.Exit(1)


# Legacy function for backwards compatibility
def learn_command(
    from_tests: Path = typer.Option(
        ..., "--from-tests", "-t", help="Path to test directory"
    ),
    output: Optional[Path] = typer.Option(
        None, "--output", "-o", help="Output directory"
    ),
    merge: bool = typer.Option(
        True, "--merge/--replace", help="Merge with existing patterns"
    ),
) -> None:
    """Learn patterns from existing tests (legacy interface)."""
    learn_from_tests(from_tests, output, merge, verbose=False)
