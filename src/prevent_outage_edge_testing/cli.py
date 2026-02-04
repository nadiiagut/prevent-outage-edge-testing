# src/prevent_outage_edge_testing/cli.py
# Command-line interface for prevent-outage-edge-testing.

"""
CLI for the prevent-outage-edge-testing library.

Commands:
- packs: List and inspect knowledge packs
- build: Generate test plans from feature descriptions
- extractors: Manage and run data extractors
- export: Export test plans and observability recipes
"""

import json
import sys
from pathlib import Path
from typing import Optional

import typer
import yaml
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree

from prevent_outage_edge_testing.builder import TestPlanBuilder, BuilderConfig
from prevent_outage_edge_testing.extractors import get_extractor_registry
from prevent_outage_edge_testing.models import ExtractorMode, Severity
from prevent_outage_edge_testing.registry import PackRegistry, get_global_registry

app = typer.Typer(
    name="poet",
    help="Prevent Outage Edge Testing - Knowledge packs and test plan builder",
    no_args_is_help=True,
)
console = Console()

# Sub-command groups
packs_app = typer.Typer(help="Manage knowledge packs")
build_app = typer.Typer(help="Build test plans from descriptions")
extractors_app = typer.Typer(help="Manage data extractors")
export_app = typer.Typer(help="Export generated artifacts")

app.add_typer(packs_app, name="packs")
app.add_typer(build_app, name="build")
app.add_typer(extractors_app, name="extractors")
app.add_typer(export_app, name="export")


# ============== Packs Commands ==============


@packs_app.command("list")
def packs_list(
    tags: Optional[list[str]] = typer.Option(None, "--tag", "-t", help="Filter by tags"),
    severity: Optional[str] = typer.Option(None, "--severity", "-s", help="Min severity"),
) -> None:
    """List all available knowledge packs."""
    registry = get_global_registry()

    if tags:
        packs = registry.search_by_tags(tags)
    elif severity:
        try:
            sev = Severity(severity.lower())
            packs = registry.get_packs_with_severity(sev)
        except ValueError:
            console.print(f"[red]Invalid severity: {severity}[/red]")
            raise typer.Exit(1)
    else:
        packs = registry.list_all()

    if not packs:
        console.print("[yellow]No packs found. Load packs with 'poet packs load'[/yellow]")
        return

    table = Table(title="Knowledge Packs")
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="green")
    table.add_column("Version")
    table.add_column("Failure Modes", justify="right")
    table.add_column("Tags")

    for pack in packs:
        table.add_row(
            pack.id,
            pack.name,
            pack.version,
            str(len(pack.failure_modes)),
            ", ".join(pack.tags[:3]),
        )

    console.print(table)


@packs_app.command("show")
def packs_show(pack_id: str = typer.Argument(..., help="Pack ID to show")) -> None:
    """Show details of a specific knowledge pack."""
    registry = get_global_registry()
    pack = registry.get(pack_id)

    if not pack:
        console.print(f"[red]Pack not found: {pack_id}[/red]")
        raise typer.Exit(1)

    # Build a tree view
    tree = Tree(f"[bold cyan]{pack.name}[/bold cyan] (v{pack.version})")
    tree.add(f"[dim]ID:[/dim] {pack.id}")
    tree.add(f"[dim]Author:[/dim] {pack.author}")
    tree.add(f"[dim]Tags:[/dim] {', '.join(pack.tags)}")

    # Failure modes
    fm_branch = tree.add("[bold]Failure Modes[/bold]")
    for fm in pack.failure_modes:
        severity_color = {
            Severity.CRITICAL: "red",
            Severity.HIGH: "yellow",
            Severity.MEDIUM: "blue",
            Severity.LOW: "dim",
        }.get(fm.severity, "white")
        fm_node = fm_branch.add(f"[{severity_color}]{fm.name}[/{severity_color}]")
        fm_node.add(f"[dim]{fm.description[:80]}...[/dim]")

    # Test templates
    if pack.test_templates:
        tt_branch = tree.add("[bold]Test Templates[/bold]")
        for tt in pack.test_templates:
            tt_branch.add(f"{tt.name}")

    # Observability recipes
    if pack.observability_recipes:
        obs_branch = tree.add("[bold]Observability Recipes[/bold]")
        for recipe in pack.observability_recipes:
            obs_branch.add(f"{recipe.name}")

    console.print(tree)
    console.print()
    console.print(Panel(pack.description, title="Description"))


@packs_app.command("load")
def packs_load(
    path: Path = typer.Argument(..., help="Path to pack YAML or directory"),
) -> None:
    """Load knowledge pack(s) from file or directory."""
    registry = get_global_registry()

    if path.is_dir():
        packs = registry.load_from_directory(path)
        console.print(f"[green]Loaded {len(packs)} packs from {path}[/green]")
    elif path.is_file():
        pack = registry.load_from_yaml(path)
        console.print(f"[green]Loaded pack: {pack.id}[/green]")
    else:
        console.print(f"[red]Path not found: {path}[/red]")
        raise typer.Exit(1)


# ============== Build Commands ==============


@build_app.command("plan")
def build_plan(
    description: Optional[str] = typer.Option(
        None, "--description", "-d", help="Feature description text"
    ),
    file: Optional[Path] = typer.Option(
        None, "--file", "-f", help="Read description from file"
    ),
    jira_key: Optional[str] = typer.Option(
        None, "--jira", "-j", help="Jira issue key"
    ),
    title: Optional[str] = typer.Option(
        None, "--title", "-t", help="Test plan title"
    ),
    output: Optional[Path] = typer.Option(
        None, "--output", "-o", help="Output file (JSON or YAML)"
    ),
    max_tests: int = typer.Option(20, "--max-tests", "-m", help="Max test cases"),
) -> None:
    """Generate a test plan from a feature description."""
    # Get description
    if file:
        if not file.exists():
            console.print(f"[red]File not found: {file}[/red]")
            raise typer.Exit(1)
        desc_text = file.read_text()
    elif description:
        desc_text = description
    else:
        console.print("[yellow]Enter feature description (Ctrl+D to end):[/yellow]")
        desc_text = sys.stdin.read()

    if not desc_text.strip():
        console.print("[red]No description provided[/red]")
        raise typer.Exit(1)

    # Build plan
    config = BuilderConfig(max_test_cases=max_tests)
    builder = TestPlanBuilder(config=config)
    plan = builder.build(desc_text, jira_key=jira_key, title=title)

    # Output
    if output:
        plan_dict = plan.model_dump(mode="json")
        if output.suffix in (".yaml", ".yml"):
            output.write_text(yaml.dump(plan_dict, default_flow_style=False))
        else:
            output.write_text(json.dumps(plan_dict, indent=2, default=str))
        console.print(f"[green]Test plan written to {output}[/green]")
    else:
        # Display summary
        console.print()
        console.print(Panel(f"[bold]{plan.title}[/bold]\nID: {plan.id}"))

        table = Table(title=f"Generated Test Cases ({len(plan.test_cases)})")
        table.add_column("Name", style="cyan")
        table.add_column("Priority")
        table.add_column("Failure Mode")
        table.add_column("Tags")

        for tc in plan.test_cases:
            priority_color = {
                Severity.CRITICAL: "red",
                Severity.HIGH: "yellow",
                Severity.MEDIUM: "blue",
                Severity.LOW: "dim",
            }.get(tc.priority, "white")
            table.add_row(
                tc.name[:40],
                f"[{priority_color}]{tc.priority.value}[/{priority_color}]",
                tc.failure_mode_id or "-",
                ", ".join(tc.tags[:2]),
            )

        console.print(table)
        console.print()
        console.print(Panel(plan.coverage_notes, title="Coverage Notes"))


@build_app.command("observability")
def build_observability(
    plan_file: Path = typer.Argument(..., help="Test plan JSON/YAML file"),
    output: Optional[Path] = typer.Option(
        None, "--output", "-o", help="Output file"
    ),
) -> None:
    """Get observability recipes for a test plan."""
    if not plan_file.exists():
        console.print(f"[red]File not found: {plan_file}[/red]")
        raise typer.Exit(1)

    # Load plan
    content = plan_file.read_text()
    if plan_file.suffix in (".yaml", ".yml"):
        plan_data = yaml.safe_load(content)
    else:
        plan_data = json.loads(content)

    from prevent_outage_edge_testing.models import TestPlan

    plan = TestPlan.model_validate(plan_data)

    # Get recipes
    builder = TestPlanBuilder()
    recipes = builder.get_observability_recipes(plan)

    if not recipes:
        console.print("[yellow]No observability recipes found for this plan[/yellow]")
        return

    if output:
        recipes_data = [r.model_dump(mode="json") for r in recipes]
        if output.suffix in (".yaml", ".yml"):
            output.write_text(yaml.dump(recipes_data, default_flow_style=False))
        else:
            output.write_text(json.dumps(recipes_data, indent=2))
        console.print(f"[green]Recipes written to {output}[/green]")
    else:
        for recipe in recipes:
            console.print(
                Panel(
                    f"[dim]Metrics:[/dim] {len(recipe.metrics)}\n"
                    f"[dim]Log Patterns:[/dim] {len(recipe.log_patterns)}\n"
                    f"[dim]Alerts:[/dim] {len(recipe.alerts)}",
                    title=f"[bold]{recipe.name}[/bold]",
                )
            )


# ============== Extractors Commands ==============


@extractors_app.command("list")
def extractors_list() -> None:
    """List available extractor types."""
    registry = get_extractor_registry()

    table = Table(title="Available Extractors")
    table.add_column("Name", style="cyan")
    table.add_column("Privileged Mode", justify="center")

    privileged_capable = registry.get_privileged_capable()

    for name in registry.list_types():
        can_priv = "✓" if name in privileged_capable else "✗"
        priv_style = "green" if name in privileged_capable else "dim"
        table.add_row(name, f"[{priv_style}]{can_priv}[/{priv_style}]")

    console.print(table)

    if not privileged_capable:
        console.print()
        console.print(
            "[yellow]No extractors can run in privileged mode on this system.[/yellow]"
        )
        console.print("[dim]Extractors will use simulator mode (safe fallback).[/dim]")


@extractors_app.command("run")
def extractors_run(
    extractor_type: str = typer.Argument(..., help="Extractor type to run"),
    duration: int = typer.Option(10, "--duration", "-d", help="Duration in seconds"),
    mode: str = typer.Option(
        "simulator", "--mode", "-m", help="Mode: privileged or simulator"
    ),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file"),
) -> None:
    """Run an extractor and collect data."""
    import time

    registry = get_extractor_registry()

    if extractor_type not in registry.list_types():
        console.print(f"[red]Unknown extractor: {extractor_type}[/red]")
        console.print(f"Available: {', '.join(registry.list_types())}")
        raise typer.Exit(1)

    try:
        ext_mode = ExtractorMode(mode.lower())
    except ValueError:
        console.print(f"[red]Invalid mode: {mode}. Use 'privileged' or 'simulator'[/red]")
        raise typer.Exit(1)

    extractor = registry.create(extractor_type, mode=ext_mode)

    console.print(f"[blue]Starting {extractor.name} in {ext_mode.value} mode...[/blue]")
    extractor.start()

    with console.status(f"Collecting for {duration} seconds..."):
        time.sleep(duration)

    result = extractor.stop()

    console.print(f"[green]Collected {len(result.data)} data points[/green]")

    if output:
        result_dict = result.model_dump(mode="json")
        if output.suffix in (".yaml", ".yml"):
            output.write_text(yaml.dump(result_dict, default_flow_style=False))
        else:
            output.write_text(json.dumps(result_dict, indent=2, default=str))
        console.print(f"[green]Results written to {output}[/green]")
    else:
        # Show sample
        console.print()
        console.print("[bold]Sample data (first 5 entries):[/bold]")
        for entry in result.data[:5]:
            console.print(f"  {entry}")


# ============== Export Commands ==============


@export_app.command("pytest")
def export_pytest(
    plan_file: Path = typer.Argument(..., help="Test plan JSON/YAML file"),
    output_dir: Path = typer.Option(
        Path("./generated_tests"), "--output", "-o", help="Output directory"
    ),
) -> None:
    """Export test plan as pytest test file."""
    if not plan_file.exists():
        console.print(f"[red]File not found: {plan_file}[/red]")
        raise typer.Exit(1)

    content = plan_file.read_text()
    if plan_file.suffix in (".yaml", ".yml"):
        plan_data = yaml.safe_load(content)
    else:
        plan_data = json.loads(content)

    from prevent_outage_edge_testing.models import TestPlan

    plan = TestPlan.model_validate(plan_data)

    # Generate pytest file
    output_dir.mkdir(parents=True, exist_ok=True)
    test_file = output_dir / f"test_{plan.id.replace('-', '_')}.py"

    lines = [
        '"""',
        f"Auto-generated tests for: {plan.title}",
        f"Plan ID: {plan.id}",
        "",
        "WARNING: These are starter tests. Review and customize before use.",
        "This tool does NOT guarantee complete coverage of all failure modes.",
        '"""',
        "",
        "import pytest",
        "",
        "",
    ]

    for tc in plan.test_cases:
        func_name = f"test_{tc.id.replace('-', '_')}"
        lines.append(f"@pytest.mark.{tc.priority.value}")
        if tc.requires_privileged:
            lines.append("@pytest.mark.privileged")
        lines.append(f"def {func_name}():")
        lines.append(f'    """')
        lines.append(f"    {tc.name}")
        lines.append(f"    ")
        lines.append(f"    {tc.description}")
        lines.append(f'    """')
        lines.append(f"    # Setup")
        for step in tc.setup_steps:
            lines.append(f"    # {step}")
        lines.append(f"    ")
        lines.append(f"    # Execution")
        for step in tc.execution_steps:
            lines.append(f"    # {step}")
        lines.append(f"    ")
        lines.append(f"    # Assertions")
        for assertion in tc.assertions:
            lines.append(f"    # TODO: {assertion.description}")
            lines.append(f"    # assert {assertion.expression}")
        lines.append(f"    ")
        lines.append(f"    # Cleanup")
        for step in tc.cleanup_steps:
            lines.append(f"    # {step}")
        lines.append(f"    ")
        lines.append(f"    pytest.skip('Generated test - implement before use')")
        lines.append("")
        lines.append("")

    test_file.write_text("\n".join(lines))
    console.print(f"[green]Generated pytest file: {test_file}[/green]")


@export_app.command("grafana")
def export_grafana(
    recipes_file: Path = typer.Argument(..., help="Observability recipes JSON/YAML"),
    output: Path = typer.Option(
        Path("./dashboard.json"), "--output", "-o", help="Output file"
    ),
) -> None:
    """Export observability recipes as Grafana dashboard JSON."""
    if not recipes_file.exists():
        console.print(f"[red]File not found: {recipes_file}[/red]")
        raise typer.Exit(1)

    content = recipes_file.read_text()
    if recipes_file.suffix in (".yaml", ".yml"):
        recipes_data = yaml.safe_load(content)
    else:
        recipes_data = json.loads(content)

    from prevent_outage_edge_testing.models import ObservabilityRecipe

    if isinstance(recipes_data, list):
        recipes = [ObservabilityRecipe.model_validate(r) for r in recipes_data]
    else:
        recipes = [ObservabilityRecipe.model_validate(recipes_data)]

    # Generate basic Grafana dashboard
    panels = []
    panel_id = 1

    for recipe in recipes:
        for metric in recipe.metrics:
            panels.append(
                {
                    "id": panel_id,
                    "title": metric.name,
                    "type": "timeseries" if metric.type != "gauge" else "gauge",
                    "targets": [
                        {
                            "expr": metric.name,
                            "legendFormat": "{{" + ",".join(metric.labels) + "}}",
                        }
                    ],
                    "gridPos": {"h": 8, "w": 12, "x": (panel_id - 1) % 2 * 12, "y": ((panel_id - 1) // 2) * 8},
                }
            )
            panel_id += 1

    dashboard = {
        "title": f"Generated Dashboard - {recipes[0].name if recipes else 'Unknown'}",
        "uid": None,
        "panels": panels,
        "schemaVersion": 38,
        "version": 1,
        "refresh": "30s",
    }

    output.write_text(json.dumps(dashboard, indent=2))
    console.print(f"[green]Generated Grafana dashboard: {output}[/green]")


# ============== Main Entry ==============


@app.callback()
def main(
    version: bool = typer.Option(False, "--version", "-v", help="Show version"),
) -> None:
    """Prevent Outage Edge Testing CLI."""
    if version:
        from prevent_outage_edge_testing import __version__

        console.print(f"poet version {__version__}")
        raise typer.Exit()


if __name__ == "__main__":
    app()
