# src/prevent_outage_edge_testing/cli/commands/packs.py
# Implementation of `poet packs` commands.
"""
Commands for managing knowledge packs:
- list: Show all available packs
- show: Display details of a specific pack
- validate: Check pack schema and required files
"""

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree

from prevent_outage_edge_testing.core.config import load_config
from prevent_outage_edge_testing.packs.loader import PackLoader
from prevent_outage_edge_testing.packs.validator import PackValidator

app = typer.Typer(help="Manage knowledge packs")
console = Console()


@app.command("list")
def list_packs(
    path: Optional[Path] = typer.Option(
        None, "--path", "-p", help="Custom packs directory"
    ),
    tags: Optional[str] = typer.Option(
        None, "--tags", "-t", help="Filter by tags (comma-separated)"
    ),
) -> None:
    """List all available knowledge packs."""
    config = load_config()
    paths = [path] if path else (config.packs_paths if config else [Path("packs")])
    
    loader = PackLoader(paths)
    packs = loader.load_all()
    
    if not packs:
        console.print("[yellow]No packs found.[/yellow]")
        console.print(f"[dim]Searched in: {', '.join(str(p) for p in paths)}[/dim]")
        return
    
    # Filter by tags if specified
    if tags:
        tag_set = set(t.strip() for t in tags.split(","))
        packs = [p for p in packs if tag_set & set(p.tags)]
    
    table = Table(title="Knowledge Packs")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Name", style="green")
    table.add_column("Version")
    table.add_column("Recipes", justify="right")
    table.add_column("Snippets", justify="right")
    table.add_column("Tags")
    
    for pack in packs:
        table.add_row(
            pack.id,
            pack.name,
            pack.version,
            str(len(pack.recipes)),
            str(len(pack.snippets)),
            ", ".join(pack.tags[:3]) + ("..." if len(pack.tags) > 3 else ""),
        )
    
    console.print(table)
    console.print(f"\n[dim]Total: {len(packs)} packs[/dim]")


@app.command("show")
def show_pack(
    pack_id: str = typer.Argument(..., help="Pack ID to display"),
    path: Optional[Path] = typer.Option(
        None, "--path", "-p", help="Custom packs directory"
    ),
) -> None:
    """Show detailed information about a specific pack."""
    config = load_config()
    paths = [path] if path else (config.packs_paths if config else [Path("packs")])
    
    loader = PackLoader(paths)
    pack = loader.load_pack(pack_id)
    
    if not pack:
        console.print(f"[red]Pack not found: {pack_id}[/red]")
        raise typer.Exit(1)
    
    # Build tree view
    tree = Tree(f"[bold cyan]{pack.name}[/bold cyan] (v{pack.version})")
    tree.add(f"[dim]ID:[/dim] {pack.id}")
    tree.add(f"[dim]Author:[/dim] {pack.author}")
    tree.add(f"[dim]Tags:[/dim] {', '.join(pack.tags)}")
    
    # Failure modes
    if pack.failure_modes:
        fm_branch = tree.add("[bold]Failure Modes[/bold]")
        for fm in pack.failure_modes:
            severity_color = {
                "critical": "red",
                "high": "yellow", 
                "medium": "blue",
                "low": "dim",
            }.get(fm.severity.value, "white")
            fm_node = fm_branch.add(
                f"[{severity_color}]● {fm.name}[/{severity_color}] ({fm.severity.value})"
            )
            if fm.symptoms:
                fm_node.add(f"[dim]Symptoms: {', '.join(fm.symptoms[:2])}...[/dim]")
    
    # Recipes
    if pack.recipes:
        recipes_branch = tree.add("[bold]Recipes[/bold]")
        for recipe in pack.recipes:
            recipes_branch.add(f"📊 {recipe.name}")
    
    # Snippets
    if pack.snippets:
        snippets_branch = tree.add("[bold]Snippets[/bold]")
        for snippet in pack.snippets:
            snippets_branch.add(f"📝 {snippet.filename} ({snippet.language})")
    
    # Test templates
    if pack.test_templates:
        tests_branch = tree.add("[bold]Test Templates[/bold]")
        for template in pack.test_templates:
            tests_branch.add(f"🧪 {template.name}")
    
    console.print(tree)
    console.print()
    console.print(Panel(pack.description, title="Description"))
    
    if pack.references:
        console.print("\n[bold]References:[/bold]")
        for ref in pack.references:
            console.print(f"  • {ref}")


@app.command("validate")
def validate_packs(
    path: Optional[Path] = typer.Option(
        None, "--path", "-p", help="Custom packs directory"
    ),
    strict: bool = typer.Option(
        False, "--strict", "-s", help="Fail on warnings"
    ),
) -> None:
    """Validate all packs for schema compliance and required files."""
    config = load_config()
    paths = [path] if path else (config.packs_paths if config else [Path("packs")])
    
    validator = PackValidator()
    all_valid = True
    total_errors = 0
    total_warnings = 0
    
    for pack_path in paths:
        if not pack_path.exists():
            continue
        
        for pack_dir in pack_path.iterdir():
            if not pack_dir.is_dir():
                continue
            if pack_dir.name.startswith("."):
                continue
            
            console.print(f"\n[bold]Validating:[/bold] {pack_dir.name}")
            result = validator.validate(pack_dir)
            
            if result.errors:
                all_valid = False
                total_errors += len(result.errors)
                for error in result.errors:
                    console.print(f"  [red]✗ ERROR:[/red] {error}")
            
            if result.warnings:
                total_warnings += len(result.warnings)
                for warning in result.warnings:
                    console.print(f"  [yellow]⚠ WARNING:[/yellow] {warning}")
            
            if not result.errors and not result.warnings:
                console.print(f"  [green]✓ Valid[/green]")
            elif not result.errors:
                console.print(f"  [green]✓ Valid[/green] (with warnings)")
    
    # Summary
    console.print()
    if all_valid and (not strict or total_warnings == 0):
        console.print(Panel(
            f"[green]All packs valid[/green]\n"
            f"Errors: {total_errors}, Warnings: {total_warnings}",
            title="Validation Complete",
        ))
    else:
        console.print(Panel(
            f"[red]Validation failed[/red]\n"
            f"Errors: {total_errors}, Warnings: {total_warnings}",
            title="Validation Complete",
        ))
        raise typer.Exit(1)
