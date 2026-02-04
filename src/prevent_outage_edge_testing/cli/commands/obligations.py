# src/prevent_outage_edge_testing/cli/commands/obligations.py
"""
CLI commands for browsing obligations.

Commands:
- poet obligations list    : List all obligations
- poet obligations show <id> : Show obligation details
"""

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.markdown import Markdown
import yaml

console = Console()

obligations_app = typer.Typer(help="Browse and inspect obligations")


def get_obligations_dir() -> Path:
    """Get the obligations directory."""
    # Try relative to package first, then current directory
    pkg_dir = Path(__file__).parent.parent.parent.parent.parent / "obligations"
    if pkg_dir.exists():
        return pkg_dir
    
    cwd_dir = Path.cwd() / "obligations"
    if cwd_dir.exists():
        return cwd_dir
    
    return pkg_dir  # Return default even if not found


def load_obligation(filepath: Path) -> dict:
    """Load an obligation YAML file."""
    with open(filepath) as f:
        return yaml.safe_load(f)


def find_all_obligations(obligations_dir: Path) -> list[tuple[str, Path]]:
    """Find all obligation YAML files."""
    obligations = []
    for yaml_file in obligations_dir.rglob("*.yaml"):
        try:
            data = load_obligation(yaml_file)
            if "id" in data:
                obligations.append((data["id"], yaml_file))
        except Exception:
            pass
    return sorted(obligations, key=lambda x: x[0])


@obligations_app.command("list")
def list_obligations(
    domain: Optional[str] = typer.Option(
        None, "--domain", "-d", help="Filter by domain (routing, cache, etc.)"
    ),
) -> None:
    """
    List all available obligations.
    
    Examples:
        poet obligations list
        poet obligations list --domain routing
    """
    obligations_dir = get_obligations_dir()
    
    if not obligations_dir.exists():
        console.print(f"[red]Obligations directory not found: {obligations_dir}[/red]")
        raise typer.Exit(1)
    
    obligations = find_all_obligations(obligations_dir)
    
    if not obligations:
        console.print("[yellow]No obligations found.[/yellow]")
        raise typer.Exit(1)
    
    # Filter by domain if specified
    if domain:
        obligations = [(oid, path) for oid, path in obligations if oid.startswith(f"{domain}.")]
    
    # Group by domain
    by_domain: dict[str, list[tuple[str, dict]]] = {}
    for oid, path in obligations:
        data = load_obligation(path)
        domain_name = oid.split(".")[0]
        if domain_name not in by_domain:
            by_domain[domain_name] = []
        by_domain[domain_name].append((oid, data))
    
    # Display table
    table = Table(title="Obligations")
    table.add_column("ID", style="cyan")
    table.add_column("Title", style="white")
    table.add_column("Risk", style="yellow")
    table.add_column("Safe in Prod", style="green")
    
    for domain_name in sorted(by_domain.keys()):
        for oid, data in by_domain[domain_name]:
            risk = data.get("risk", "?")
            risk_style = "red" if risk == "high" else "yellow" if risk == "medium" else "green"
            safe = "✓" if data.get("safe_in_prod", False) else "✗"
            safe_style = "green" if data.get("safe_in_prod", False) else "red"
            
            table.add_row(
                oid,
                data.get("title", ""),
                f"[{risk_style}]{risk}[/{risk_style}]",
                f"[{safe_style}]{safe}[/{safe_style}]",
            )
    
    console.print(table)
    console.print(f"\n[dim]Total: {len(obligations)} obligations[/dim]")
    console.print("[dim]Run 'poet obligations show <id>' for details[/dim]")


@obligations_app.command("show")
def show_obligation(
    obligation_id: str = typer.Argument(..., help="Obligation ID (e.g., routing.backend.selection)"),
) -> None:
    """
    Show details of a specific obligation.
    
    Examples:
        poet obligations show routing.backend.selection
        poet obligations show cache.vary.honored
    """
    obligations_dir = get_obligations_dir()
    
    if not obligations_dir.exists():
        console.print(f"[red]Obligations directory not found: {obligations_dir}[/red]")
        raise typer.Exit(1)
    
    # Find the obligation
    obligations = find_all_obligations(obligations_dir)
    matching = [(oid, path) for oid, path in obligations if oid == obligation_id]
    
    if not matching:
        # Try partial match
        matching = [(oid, path) for oid, path in obligations if obligation_id in oid]
        if matching:
            console.print(f"[yellow]Did you mean one of these?[/yellow]")
            for oid, _ in matching:
                console.print(f"  - {oid}")
            raise typer.Exit(1)
        
        console.print(f"[red]Obligation not found: {obligation_id}[/red]")
        console.print("[dim]Run 'poet obligations list' to see all obligations[/dim]")
        raise typer.Exit(1)
    
    _, path = matching[0]
    data = load_obligation(path)
    
    # Build display
    title = data.get("title", obligation_id)
    description = data.get("description", "No description")
    risk = data.get("risk", "unknown")
    safe_in_prod = data.get("safe_in_prod", False)
    
    # Header panel
    risk_color = "red" if risk == "high" else "yellow" if risk == "medium" else "green"
    safe_text = "[green]Yes[/green]" if safe_in_prod else "[red]No[/red]"
    
    header = f"""[bold]{title}[/bold]
[dim]{obligation_id}[/dim]

{description}

[bold]Risk:[/bold] [{risk_color}]{risk}[/{risk_color}]
[bold]Safe in Production:[/bold] {safe_text}"""
    
    console.print(Panel(header, title="Obligation"))
    
    # Required signals
    signals = data.get("required_signals", [])
    if signals:
        console.print("\n[bold]Required Signals:[/bold]")
        for signal in signals:
            console.print(f"  • {signal}")
    
    # Pass criteria
    criteria = data.get("pass_criteria", [])
    if criteria:
        console.print("\n[bold]Pass Criteria:[/bold]")
        for criterion in criteria:
            console.print(f"  • {criterion}")
    
    # Suggested checks
    checks = data.get("suggested_checks", [])
    if checks:
        console.print("\n[bold]Suggested Checks:[/bold]")
        for check in checks:
            name = check.get("name", "unnamed")
            method = check.get("method", "?")
            console.print(f"  • [cyan]{name}[/cyan] ({method})")
    
    # Evidence to capture
    evidence = data.get("evidence_to_capture", [])
    if evidence:
        console.print("\n[bold]Evidence to Capture:[/bold]")
        for item in evidence:
            console.print(f"  • {item}")
    
    # Assumptions
    assumptions = data.get("assumptions", [])
    if assumptions:
        console.print("\n[bold]Assumptions:[/bold]")
        for assumption in assumptions:
            console.print(f"  • [dim]{assumption}[/dim]")
    
    console.print()
