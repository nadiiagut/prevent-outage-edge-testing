# src/prevent_outage_edge_testing/packs/loader.py
# Pack loading utilities.
"""
PackLoader discovers and loads knowledge packs from disk.

Expected pack structure:
    packs/<pack_id>/
    ├── pack.yaml          # Required: Pack definition
    ├── README.md          # Optional: Documentation
    ├── recipes/           # Optional: Observability recipes
    │   └── *.md
    └── snippets/          # Optional: Code snippets
        └── *.*
"""

from pathlib import Path
from typing import Optional

import yaml
from pydantic import ValidationError
from rich.console import Console

from prevent_outage_edge_testing.packs.models import (
    KnowledgePack,
    Recipe,
    Snippet,
)

console = Console()


class PackLoader:
    """Loads knowledge packs from filesystem."""
    
    def __init__(self, search_paths: list[Path]) -> None:
        """
        Initialize loader with search paths.
        
        Args:
            search_paths: List of directories to search for packs
        """
        self.search_paths = search_paths
    
    def _load_recipes(self, pack_dir: Path) -> list[Recipe]:
        """Load recipes from pack's recipes/ directory."""
        recipes = []
        recipes_dir = pack_dir / "recipes"
        
        if not recipes_dir.exists():
            return recipes
        
        for recipe_file in recipes_dir.glob("*.md"):
            content = recipe_file.read_text()
            
            # Extract title from first heading
            name = recipe_file.stem
            lines = content.split("\n")
            for line in lines:
                if line.startswith("# "):
                    name = line[2:].strip()
                    break
            
            recipes.append(Recipe(
                id=recipe_file.stem,
                name=name,
                description=f"Recipe from {recipe_file.name}",
                content=content,
            ))
        
        return recipes
    
    def _load_snippets(self, pack_dir: Path) -> list[Snippet]:
        """Load snippets from pack's snippets/ directory."""
        snippets = []
        snippets_dir = pack_dir / "snippets"
        
        if not snippets_dir.exists():
            return snippets
        
        # Language detection by extension
        lang_map = {
            ".py": "python",
            ".sh": "bash",
            ".bash": "bash",
            ".js": "javascript",
            ".ts": "typescript",
            ".go": "go",
            ".rs": "rust",
            ".c": "c",
            ".h": "c",
            ".yaml": "yaml",
            ".yml": "yaml",
            ".json": "json",
            ".d": "dtrace",
            ".bt": "bpftrace",
        }
        
        for snippet_file in snippets_dir.iterdir():
            if snippet_file.is_file() and not snippet_file.name.startswith("."):
                content = snippet_file.read_text()
                language = lang_map.get(snippet_file.suffix, "text")
                
                # Check if privileged (contains sudo, dtrace, bpf, etc.)
                requires_priv = any(
                    kw in content.lower()
                    for kw in ["sudo", "dtrace", "bpf", "ld_preload", "cap_"]
                )
                
                snippets.append(Snippet(
                    filename=snippet_file.name,
                    language=language,
                    content=content,
                    requires_privileged=requires_priv,
                ))
        
        return snippets
    
    def load_pack(self, pack_id: str) -> Optional[KnowledgePack]:
        """
        Load a specific pack by ID.
        
        Args:
            pack_id: Pack identifier (directory name)
            
        Returns:
            KnowledgePack if found, None otherwise
        """
        for search_path in self.search_paths:
            pack_dir = search_path / pack_id
            if pack_dir.exists() and (pack_dir / "pack.yaml").exists():
                return self._load_from_dir(pack_dir)
        return None
    
    def _load_from_dir(self, pack_dir: Path) -> Optional[KnowledgePack]:
        """Load a pack from a directory."""
        pack_yaml = pack_dir / "pack.yaml"
        
        if not pack_yaml.exists():
            return None
        
        try:
            with open(pack_yaml) as f:
                data = yaml.safe_load(f)
            
            # Load additional resources
            file_recipes = self._load_recipes(pack_dir)
            file_snippets = self._load_snippets(pack_dir)
            
            # Merge with pack.yaml recipes/snippets
            if "recipes" not in data:
                data["recipes"] = []
            if "snippets" not in data:
                data["snippets"] = []
            
            # Add file-based recipes (avoid duplicates)
            existing_recipe_ids = {r.get("id") for r in data["recipes"]}
            for recipe in file_recipes:
                if recipe.id not in existing_recipe_ids:
                    data["recipes"].append(recipe.model_dump())
            
            # Add file-based snippets (avoid duplicates)
            existing_snippet_files = {s.get("filename") for s in data["snippets"]}
            for snippet in file_snippets:
                if snippet.filename not in existing_snippet_files:
                    data["snippets"].append(snippet.model_dump())
            
            pack = KnowledgePack.model_validate(data)
            pack._source_path = pack_dir
            return pack
            
        except (yaml.YAMLError, ValidationError) as e:
            console.print(f"[red]Error loading pack from {pack_dir}: {e}[/red]")
            return None
    
    def load_all(self) -> list[KnowledgePack]:
        """Load all packs from search paths."""
        packs = []
        seen_ids: set[str] = set()
        
        for search_path in self.search_paths:
            if not search_path.exists():
                continue
            
            for item in search_path.iterdir():
                if item.is_dir() and not item.name.startswith("."):
                    pack = self._load_from_dir(item)
                    if pack and pack.id not in seen_ids:
                        packs.append(pack)
                        seen_ids.add(pack.id)
        
        return packs
    
    def discover_pack_ids(self) -> list[str]:
        """Discover all pack IDs without fully loading them."""
        pack_ids = []
        
        for search_path in self.search_paths:
            if not search_path.exists():
                continue
            
            for item in search_path.iterdir():
                if item.is_dir() and (item / "pack.yaml").exists():
                    pack_ids.append(item.name)
        
        return list(set(pack_ids))
