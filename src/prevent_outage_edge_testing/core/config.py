# src/prevent_outage_edge_testing/core/config.py
# Configuration management for POET.
"""
Configuration models and loading utilities.

The config file (.poet.yaml) stores:
- System profile (OS, capabilities)
- Pack search paths
- Knowledge index location
- User preferences
"""

from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field


class SystemProfile(BaseModel):
    """Detected system capabilities."""
    
    os_name: str = Field(..., description="Operating system name")
    os_version: str = Field(default="", description="OS version string")
    architecture: str = Field(default="", description="CPU architecture")
    python_version: str = Field(default="", description="Python version")
    has_dtrace: bool = Field(default=False, description="DTrace available")
    has_ebpf: bool = Field(default=False, description="eBPF available")
    has_ld_preload: bool = Field(default=False, description="LD_PRELOAD capable")
    is_privileged: bool = Field(default=False, description="Running with elevated permissions")


class PoetConfig(BaseModel):
    """POET configuration model."""
    
    version: str = Field(default="1.0", description="Config version")
    system_profile: SystemProfile = Field(..., description="System capabilities")
    packs_paths: list[Path] = Field(
        default_factory=lambda: [Path("packs")],
        description="Paths to search for knowledge packs",
    )
    knowledge_index_path: Path = Field(
        default=Path(".poet_knowledge.json"),
        description="Path to local knowledge index",
    )
    default_output_dir: Path = Field(
        default=Path("generated"),
        description="Default output directory for generated files",
    )
    preferred_test_framework: str = Field(
        default="pytest",
        description="Preferred test framework",
    )
    auto_include_recipes: bool = Field(
        default=True,
        description="Automatically include observability recipes",
    )
    auto_include_snippets: bool = Field(
        default=True,
        description="Automatically include code snippets",
    )


# Global config cache
_cached_config: Optional[PoetConfig] = None
_config_path: Optional[Path] = None


def load_config(path: Optional[Path] = None) -> Optional[PoetConfig]:
    """
    Load POET configuration from file.
    
    Searches for config in order:
    1. Specified path
    2. Current directory (.poet.yaml)
    3. Home directory (~/.poet.yaml)
    
    Returns None if no config found.
    """
    global _cached_config, _config_path
    
    # Use cached config if same path
    if _cached_config and (path is None or path == _config_path):
        return _cached_config
    
    # Search for config file
    search_paths = []
    if path:
        search_paths.append(path)
    search_paths.extend([
        Path(".poet.yaml"),
        Path.home() / ".poet.yaml",
    ])
    
    config_file = None
    for p in search_paths:
        if p.exists():
            config_file = p
            break
    
    if not config_file:
        return None
    
    # Load and parse config
    with open(config_file) as f:
        data = yaml.safe_load(f)
    
    # Convert string paths back to Path objects
    if "packs_paths" in data:
        data["packs_paths"] = [Path(p) for p in data["packs_paths"]]
    if "knowledge_index_path" in data:
        data["knowledge_index_path"] = Path(data["knowledge_index_path"])
    if "default_output_dir" in data:
        data["default_output_dir"] = Path(data["default_output_dir"])
    
    config = PoetConfig.model_validate(data)
    
    # Cache config
    _cached_config = config
    _config_path = config_file
    
    return config


def clear_config_cache() -> None:
    """Clear the cached configuration."""
    global _cached_config, _config_path
    _cached_config = None
    _config_path = None
