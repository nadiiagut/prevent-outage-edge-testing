# tests/test_registry.py
# Tests for the knowledge pack registry.

"""
Unit tests for PackRegistry functionality.

Tests cover:
- Pack registration and retrieval
- Search by tags and text
- Loading from YAML files
- Global registry management
"""

import pytest
from pathlib import Path

from prevent_outage_edge_testing.models import KnowledgePack, Severity
from prevent_outage_edge_testing.registry import PackRegistry, get_global_registry


class TestPackRegistry:
    """Tests for PackRegistry class."""

    def test_register_pack(self, empty_registry, sample_knowledge_pack):
        """Test registering a knowledge pack."""
        empty_registry.register(sample_knowledge_pack)
        assert "test-pack" in empty_registry
        assert len(empty_registry) == 1

    def test_get_pack(self, populated_registry):
        """Test retrieving a pack by ID."""
        pack = populated_registry.get("test-pack")
        assert pack is not None
        assert pack.name == "Test Knowledge Pack"

    def test_get_nonexistent_pack(self, empty_registry):
        """Test getting a pack that doesn't exist."""
        pack = empty_registry.get("nonexistent")
        assert pack is None

    def test_list_all_packs(self, populated_registry):
        """Test listing all packs."""
        packs = populated_registry.list_all()
        assert len(packs) == 1
        assert packs[0].id == "test-pack"

    def test_list_ids(self, populated_registry):
        """Test listing pack IDs."""
        ids = populated_registry.list_ids()
        assert ids == ["test-pack"]

    def test_search_by_tags(self, populated_registry):
        """Test searching packs by tags."""
        # Should find pack with 'cache' tag
        results = populated_registry.search_by_tags(["cache"])
        assert len(results) == 1
        assert results[0].id == "test-pack"

        # Should not find pack with nonexistent tag
        results = populated_registry.search_by_tags(["nonexistent"])
        assert len(results) == 0

    def test_search_by_text(self, populated_registry):
        """Test text search across packs."""
        # Search by pack name
        results = populated_registry.search_by_text("Knowledge Pack")
        assert len(results) == 1

        # Search by failure mode name
        results = populated_registry.search_by_text("Test Failure")
        assert len(results) == 1

        # No match
        results = populated_registry.search_by_text("xyz123nonexistent")
        assert len(results) == 0

    def test_get_packs_with_severity(self, populated_registry):
        """Test filtering packs by severity."""
        # HIGH severity should match (pack has HIGH severity failure mode)
        results = populated_registry.get_packs_with_severity(Severity.HIGH)
        assert len(results) == 1

        # CRITICAL should not match (pack only has HIGH)
        results = populated_registry.get_packs_with_severity(Severity.CRITICAL)
        assert len(results) == 0

    def test_iterate_registry(self, populated_registry):
        """Test iterating over registry."""
        pack_ids = [p.id for p in populated_registry]
        assert pack_ids == ["test-pack"]

    def test_contains(self, populated_registry):
        """Test membership check."""
        assert "test-pack" in populated_registry
        assert "nonexistent" not in populated_registry

    def test_load_from_yaml(self, empty_registry, temp_pack_dir):
        """Test loading a pack from YAML file."""
        yaml_file = temp_pack_dir / "test-pack.yaml"
        pack = empty_registry.load_from_yaml(yaml_file)
        assert pack.id == "test-pack"
        assert "test-pack" in empty_registry

    def test_load_from_directory(self, empty_registry, temp_pack_dir):
        """Test loading all packs from a directory."""
        packs = empty_registry.load_from_directory(temp_pack_dir)
        assert len(packs) == 1
        assert packs[0].id == "test-pack"

    def test_overwrite_warning(self, populated_registry, sample_knowledge_pack, capsys):
        """Test warning when overwriting existing pack."""
        # Register same pack again
        populated_registry.register(sample_knowledge_pack)
        # Should still only have one pack
        assert len(populated_registry) == 1


class TestGlobalRegistry:
    """Tests for global registry singleton."""

    def test_get_global_registry(self):
        """Test getting the global registry."""
        registry = get_global_registry()
        assert registry is not None
        assert isinstance(registry, PackRegistry)

    def test_global_registry_singleton(self):
        """Test that global registry is a singleton."""
        reg1 = get_global_registry()
        reg2 = get_global_registry()
        assert reg1 is reg2
