# src/prevent_outage_edge_testing/registry.py
# Knowledge pack registry - manages loading, storing, and querying packs.

"""
PackRegistry provides a central store for knowledge packs.
Supports loading from YAML files, in-memory registration, and semantic search.
"""

import importlib.resources
from pathlib import Path
from typing import Iterator

import yaml
from pydantic import ValidationError
from rich.console import Console

from prevent_outage_edge_testing.models import KnowledgePack, Severity

console = Console()


class PackRegistry:
    """
    Central registry for knowledge packs.

    Packs can be registered programmatically or loaded from YAML files.
    The registry supports querying by tags, severity, and text search.
    """

    def __init__(self) -> None:
        self._packs: dict[str, KnowledgePack] = {}

    def register(self, pack: KnowledgePack) -> None:
        """Register a knowledge pack."""
        if pack.id in self._packs:
            console.print(
                f"[yellow]Warning: Overwriting existing pack '{pack.id}'[/yellow]"
            )
        self._packs[pack.id] = pack

    def get(self, pack_id: str) -> KnowledgePack | None:
        """Get a pack by ID."""
        return self._packs.get(pack_id)

    def list_all(self) -> list[KnowledgePack]:
        """List all registered packs."""
        return list(self._packs.values())

    def list_ids(self) -> list[str]:
        """List all pack IDs."""
        return list(self._packs.keys())

    def search_by_tags(self, tags: list[str]) -> list[KnowledgePack]:
        """Find packs that have any of the specified tags."""
        tag_set = set(tags)
        return [p for p in self._packs.values() if tag_set & set(p.tags)]

    def search_by_text(self, query: str) -> list[KnowledgePack]:
        """Simple text search across pack name, description, and failure modes."""
        query_lower = query.lower()
        results = []
        for pack in self._packs.values():
            searchable = f"{pack.name} {pack.description}"
            for fm in pack.failure_modes:
                searchable += f" {fm.name} {fm.description}"
            if query_lower in searchable.lower():
                results.append(pack)
        return results

    def get_packs_with_severity(
        self, min_severity: Severity = Severity.HIGH
    ) -> list[KnowledgePack]:
        """Get packs that have failure modes at or above the given severity."""
        severity_order = {
            Severity.CRITICAL: 0,
            Severity.HIGH: 1,
            Severity.MEDIUM: 2,
            Severity.LOW: 3,
        }
        min_order = severity_order[min_severity]
        results = []
        for pack in self._packs.values():
            for fm in pack.failure_modes:
                if severity_order[fm.severity] <= min_order:
                    results.append(pack)
                    break
        return results

    def load_from_yaml(self, path: Path) -> KnowledgePack:
        """Load a single pack from a YAML file."""
        with open(path) as f:
            data = yaml.safe_load(f)
        try:
            pack = KnowledgePack.model_validate(data)
            self.register(pack)
            return pack
        except ValidationError as e:
            console.print(f"[red]Error loading pack from {path}:[/red]")
            console.print(e)
            raise

    def load_from_directory(self, directory: Path) -> list[KnowledgePack]:
        """Load all YAML packs from a directory."""
        packs = []
        for yaml_file in directory.glob("*.yaml"):
            try:
                pack = self.load_from_yaml(yaml_file)
                packs.append(pack)
            except Exception as e:
                console.print(f"[red]Failed to load {yaml_file}: {e}[/red]")
        return packs

    def load_builtin_packs(self) -> list[KnowledgePack]:
        """Load the built-in knowledge packs shipped with the library."""
        try:
            packs_path = (
                importlib.resources.files("prevent_outage_edge_testing") / "packs"
            )
            if hasattr(packs_path, "_path"):
                # For editable installs
                pack_dir = Path(str(packs_path))
            else:
                # Fallback for installed packages
                with importlib.resources.as_file(packs_path) as p:
                    pack_dir = p
            if pack_dir.exists():
                return self.load_from_directory(pack_dir)
        except Exception as e:
            console.print(f"[yellow]Could not load built-in packs: {e}[/yellow]")
        return []

    def __iter__(self) -> Iterator[KnowledgePack]:
        return iter(self._packs.values())

    def __len__(self) -> int:
        return len(self._packs)

    def __contains__(self, pack_id: str) -> bool:
        return pack_id in self._packs


# Global registry instance
_global_registry: PackRegistry | None = None


def get_global_registry() -> PackRegistry:
    """Get the global pack registry, creating it if needed."""
    global _global_registry
    if _global_registry is None:
        _global_registry = PackRegistry()
        _global_registry.load_builtin_packs()
    return _global_registry
