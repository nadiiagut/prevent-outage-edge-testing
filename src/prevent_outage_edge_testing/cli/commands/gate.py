# src/prevent_outage_edge_testing/cli/commands/gate.py
"""
Commands for running release gates.

Usage:
    poet gate list                    # List available gates
    poet gate run --all               # Run all gates
    poet gate run --gate contract     # Run specific gate
    poet gate report                  # Show latest report
"""

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree

from prevent_outage_edge_testing.gates.runner import GateRunner
from prevent_outage_edge_testing.gates.reporter import ReportGenerator
from prevent_outage_edge_testing.gates.models import GateStatus

app = typer.Typer(help="Run release gates and generate reports")
console = Console()


def _status_style(status: GateStatus) -> str:
    """Get rich style for status."""
    return {
        GateStatus.PASSED: "green",
        GateStatus.FAILED: "red",
        GateStatus.SKIPPED: "yellow",
        GateStatus.ERROR: "red bold",
    }.get(status, "white")


def _status_icon(status: GateStatus) -> str:
    """Get icon for status."""
    return {
        GateStatus.PASSED: "✓",
        GateStatus.FAILED: "✗",
        GateStatus.SKIPPED: "−",
        GateStatus.ERROR: "⚠",
    }.get(status, "?")


@app.command("list")
def list_gates() -> None:
    """List all available release gates."""
    gates = GateRunner.available_gates()
    
    table = Table(title="Available Release Gates")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Name", style="green")
    table.add_column("Required", justify="center")
    table.add_column("Description")
    
    for gate in gates:
        table.add_row(
            gate["id"],
            gate["name"],
            "✓" if gate["required"] else "−",
            gate["description"][:60] + "..." if len(gate["description"]) > 60 else gate["description"],
        )
    
    console.print(table)
    console.print(f"\n[dim]Total: {len(gates)} gates[/dim]")


@app.command("run")
def run_gates(
    all_gates: bool = typer.Option(
        False, "--all", "-a", help="Run all gates"
    ),
    gate: Optional[list[str]] = typer.Option(
        None, "--gate", "-g", help="Specific gate ID(s) to run"
    ),
    test_dir: Optional[Path] = typer.Option(
        None, "--test-dir", "-t", help="Directory containing generated tests"
    ),
    baseline: Optional[Path] = typer.Option(
        None, "--baseline", "-b", help="Baseline file for perf comparison"
    ),
    output_dir: Optional[Path] = typer.Option(
        None, "--output", "-o", help="Output directory for reports"
    ),
    json_only: bool = typer.Option(
        False, "--json", help="Output JSON only, no console"
    ),
    fail_fast: bool = typer.Option(
        False, "--fail-fast", help="Stop on first gate failure"
    ),
) -> None:
    """
    Run release gates and generate reports.
    
    Examples:
        poet gate run --all                    # Run all gates
        poet gate run --gate contract --gate cache  # Run specific gates
        poet gate run --all --fail-fast        # Stop on first failure
    """
    import json as json_lib
    
    if not all_gates and not gate:
        console.print("[red]Error: Specify --all or --gate <id>[/red]")
        raise typer.Exit(1)
    
    # Determine test directory
    if test_dir is None:
        test_dir = Path(".poet/generated_tests")
    
    # Initialize runner
    runner = GateRunner(
        test_dir=test_dir,
        baseline_file=baseline,
    )
    
    # Determine which gates to run
    gate_ids = None if all_gates else list(gate) if gate else None
    
    if not json_only:
        console.print(Panel(
            f"[bold]Running Release Gates[/bold]\n"
            f"Test directory: {test_dir}\n"
            f"Gates: {'all' if all_gates else ', '.join(gate_ids or [])}",
            title="POET Gate Runner",
        ))
        console.print()
    
    # Run gates
    with console.status("[bold blue]Running gates...[/bold blue]") if not json_only else nullcontext():
        report = runner.run_all(gate_ids=gate_ids, fail_fast=fail_fast)
    
    # Generate reports
    reporter = ReportGenerator(output_dir=output_dir)
    json_path, html_path = reporter.save_all(report)
    
    if json_only:
        console.print(json_lib.dumps(report.to_dict(), indent=2))
        raise typer.Exit(0 if report.overall_status == GateStatus.PASSED else 1)
    
    # Print results
    for gate_result in report.gates:
        style = _status_style(gate_result.status)
        icon = _status_icon(gate_result.status)
        
        tree = Tree(f"[{style}]{icon} {gate_result.gate_name}[/{style}] ({gate_result.gate_id})")
        
        for check in gate_result.checks:
            check_style = _status_style(check.status)
            check_icon = _status_icon(check.status)
            tree.add(f"[{check_style}]{check_icon}[/{check_style}] {check.name}: {check.message[:60]}")
        
        console.print(tree)
        console.print()
    
    # Summary
    overall_style = _status_style(report.overall_status)
    overall_icon = _status_icon(report.overall_status)
    
    console.print(Panel(
        f"[{overall_style} bold]{overall_icon} {report.overall_status.value.upper()}[/{overall_style} bold]\n\n"
        f"Gates: {report.passed_gates} passed, {report.failed_gates} failed\n"
        f"Duration: {report.total_duration_ms:.0f}ms\n\n"
        f"Reports saved:\n"
        f"  JSON: {json_path}\n"
        f"  HTML: {html_path}",
        title="Gate Results",
    ))
    
    # Exit with appropriate code
    if report.overall_status != GateStatus.PASSED:
        raise typer.Exit(1)


@app.command("report")
def show_report(
    output_dir: Optional[Path] = typer.Option(
        None, "--output", "-o", help="Reports directory"
    ),
    json_output: bool = typer.Option(
        False, "--json", help="Output as JSON"
    ),
) -> None:
    """Show the latest gate report."""
    import json as json_lib
    
    reports_dir = output_dir or Path(".poet/reports")
    latest_json = reports_dir / "latest.json"
    latest_html = reports_dir / "latest.html"
    
    if not latest_json.exists():
        console.print("[yellow]No reports found. Run 'poet gate run --all' first.[/yellow]")
        raise typer.Exit(1)
    
    with open(latest_json) as f:
        data = json_lib.load(f)
    
    if json_output:
        console.print(json_lib.dumps(data, indent=2))
        return
    
    # Display summary
    status = data.get("overall_status", "unknown")
    summary = data.get("summary", {})
    
    status_style = {
        "passed": "green",
        "failed": "red",
        "skipped": "yellow",
        "error": "red bold",
    }.get(status, "white")
    
    console.print(Panel(
        f"[{status_style} bold]{status.upper()}[/{status_style} bold]\n\n"
        f"Timestamp: {data.get('timestamp', 'unknown')}\n"
        f"Gates: {summary.get('passed', 0)} passed, {summary.get('failed', 0)} failed\n"
        f"Duration: {summary.get('total_duration_ms', 0):.0f}ms\n\n"
        f"HTML Report: {latest_html}",
        title="Latest Gate Report",
    ))
    
    # Show gate details
    for gate in data.get("gates", []):
        gate_status = gate.get("status", "unknown")
        gate_style = {
            "passed": "green",
            "failed": "red",
            "skipped": "yellow",
            "error": "red bold",
        }.get(gate_status, "white")
        
        console.print(f"\n[{gate_style}]● {gate.get('gate_name')}[/{gate_style}]: "
                      f"{gate.get('passed', 0)}/{len(gate.get('checks', []))} checks passed")


class nullcontext:
    """Simple null context manager for Python < 3.10 compatibility."""
    def __enter__(self):
        return None
    def __exit__(self, *args):
        pass
