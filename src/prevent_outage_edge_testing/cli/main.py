# src/prevent_outage_edge_testing/cli/main.py
# Main CLI entrypoint for POET (Prevent Outage Edge Testing).
"""
Main Typer application with all sub-commands.

Usage:
    poet init                              # Initialize local config
    poet build --jira-text "..."           # Generate test plan
    poet packs list                        # List available packs
    poet packs show <pack_id>              # Show pack details
    poet packs validate                    # Validate all packs
    poet learn from-tests <path>           # Learn patterns from tests
    poet learn show                        # Display learned patterns summary
"""

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree

from prevent_outage_edge_testing import __version__
from prevent_outage_edge_testing.cli.commands import build, init, learn, packs, gate

app = typer.Typer(
    name="poet",
    help="POET - Prevent Outage Edge Testing: Knowledge packs and test plan builder",
    no_args_is_help=True,
    rich_markup_mode="rich",
)
console = Console()

# Register sub-commands
app.add_typer(packs.app, name="packs", help="Manage knowledge packs")
app.add_typer(learn.learn_app, name="learn", help="Learn patterns from existing tests")
app.add_typer(gate.app, name="gate", help="Run release gates and generate reports")
app.command("init")(init.init_command)
app.command("build")(build.build_command)


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool = typer.Option(False, "--version", "-v", help="Show version and exit"),
) -> None:
    """POET - Prevent Outage Edge Testing CLI."""
    if version:
        console.print(f"[bold]poet[/bold] version {__version__}")
        raise typer.Exit()
    if ctx.invoked_subcommand is None:
        console.print(ctx.get_help())


if __name__ == "__main__":
    app()
