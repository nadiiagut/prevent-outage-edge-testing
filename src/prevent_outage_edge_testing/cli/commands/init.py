# src/prevent_outage_edge_testing/cli/commands/init.py
# Implementation of `poet init` command.
"""
Creates a local configuration file (.poet.yaml) with system profile detection.

The config file stores:
- System capabilities (DTrace, eBPF, LD_PRELOAD support)
- Default pack paths
- Local knowledge index location
- User preferences
"""

import os
import platform
import shutil
from pathlib import Path

import typer
import yaml
from rich.console import Console
from rich.panel import Panel

from prevent_outage_edge_testing.core.config import PoetConfig, SystemProfile

console = Console()


def detect_system_profile() -> SystemProfile:
    """Detect system capabilities for privileged operations."""
    system = platform.system()
    
    # Check DTrace availability (macOS, Solaris)
    has_dtrace = False
    if system in ("Darwin", "SunOS"):
        has_dtrace = shutil.which("dtrace") is not None
    
    # Check eBPF availability (Linux)
    has_ebpf = False
    if system == "Linux":
        # Check for BPF filesystem
        has_ebpf = Path("/sys/fs/bpf").exists()
    
    # Check LD_PRELOAD capability
    has_ld_preload = system in ("Linux", "Darwin")
    
    # Check if running as root
    is_root = os.geteuid() == 0 if hasattr(os, "geteuid") else False
    
    return SystemProfile(
        os_name=system,
        os_version=platform.version(),
        architecture=platform.machine(),
        python_version=platform.python_version(),
        has_dtrace=has_dtrace,
        has_ebpf=has_ebpf,
        has_ld_preload=has_ld_preload,
        is_privileged=is_root,
    )


def init_command(
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing config"),
    path: Path = typer.Option(
        Path(".poet.yaml"), "--path", "-p", help="Config file path"
    ),
) -> None:
    """Initialize POET configuration with system profile detection."""
    
    if path.exists() and not force:
        console.print(f"[yellow]Config already exists at {path}[/yellow]")
        console.print("Use --force to overwrite")
        raise typer.Exit(1)
    
    console.print("[blue]Detecting system profile...[/blue]")
    profile = detect_system_profile()
    
    # Display detected capabilities
    console.print()
    console.print(Panel(
        f"[bold]OS:[/bold] {profile.os_name} ({profile.os_version})\n"
        f"[bold]Architecture:[/bold] {profile.architecture}\n"
        f"[bold]Python:[/bold] {profile.python_version}\n"
        f"[bold]DTrace:[/bold] {'✓' if profile.has_dtrace else '✗'}\n"
        f"[bold]eBPF:[/bold] {'✓' if profile.has_ebpf else '✗'}\n"
        f"[bold]LD_PRELOAD:[/bold] {'✓' if profile.has_ld_preload else '✗'}\n"
        f"[bold]Privileged:[/bold] {'✓' if profile.is_privileged else '✗'}",
        title="System Profile",
    ))
    
    # Create config
    config = PoetConfig(
        version="1.0",
        system_profile=profile,
        packs_paths=[
            Path("packs"),
            Path.home() / ".poet" / "packs",
        ],
        knowledge_index_path=Path(".poet_knowledge.json"),
        default_output_dir=Path("generated"),
    )
    
    # Write config
    config_dict = config.model_dump(mode="json")
    # Convert Path objects to strings for YAML
    def path_to_str(obj):
        if isinstance(obj, dict):
            return {k: path_to_str(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [path_to_str(v) for v in obj]
        elif isinstance(obj, Path):
            return str(obj)
        return obj
    
    config_dict = path_to_str(config_dict)
    
    with open(path, "w") as f:
        yaml.dump(config_dict, f, default_flow_style=False, sort_keys=False)
    
    console.print(f"\n[green]✓ Created config at {path}[/green]")
    
    # Create directories
    for pack_path in config.packs_paths:
        if not pack_path.exists():
            pack_path.mkdir(parents=True, exist_ok=True)
            console.print(f"[dim]Created directory: {pack_path}[/dim]")
    
    console.print("\n[bold]Next steps:[/bold]")
    console.print("  1. Run [cyan]poet packs list[/cyan] to see available packs")
    console.print("  2. Run [cyan]poet build --jira-text \"...\"[/cyan] to generate a test plan")
