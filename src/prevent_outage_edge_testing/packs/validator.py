# src/prevent_outage_edge_testing/packs/validator.py
# Pack validation utilities.
"""
PackValidator checks packs for:
- Schema compliance (valid pack.yaml)
- Required files (pack.yaml)
- Recommended files (README.md)
- Internal consistency (referenced IDs exist)
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml
from pydantic import ValidationError

from prevent_outage_edge_testing.packs.models import KnowledgePack


@dataclass
class ValidationResult:
    """Result of pack validation."""
    
    pack_id: str
    valid: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class PackValidator:
    """Validates knowledge packs for correctness."""
    
    REQUIRED_FILES = ["pack.yaml"]
    RECOMMENDED_FILES = ["README.md"]
    RECOMMENDED_DIRS = ["recipes", "snippets"]
    
    def validate(self, pack_dir: Path) -> ValidationResult:
        """
        Validate a pack directory.
        
        Args:
            pack_dir: Path to pack directory
            
        Returns:
            ValidationResult with errors and warnings
        """
        result = ValidationResult(pack_id=pack_dir.name)
        
        # Check required files
        for required in self.REQUIRED_FILES:
            if not (pack_dir / required).exists():
                result.errors.append(f"Missing required file: {required}")
                result.valid = False
        
        # Check recommended files
        for recommended in self.RECOMMENDED_FILES:
            if not (pack_dir / recommended).exists():
                result.warnings.append(f"Missing recommended file: {recommended}")
        
        # Check recommended directories
        for rec_dir in self.RECOMMENDED_DIRS:
            dir_path = pack_dir / rec_dir
            if not dir_path.exists():
                result.warnings.append(f"Missing recommended directory: {rec_dir}/")
            elif dir_path.exists() and not any(dir_path.iterdir()):
                result.warnings.append(f"Empty directory: {rec_dir}/")
        
        # Validate pack.yaml schema
        pack_yaml = pack_dir / "pack.yaml"
        if pack_yaml.exists():
            schema_result = self._validate_schema(pack_yaml)
            result.errors.extend(schema_result.errors)
            result.warnings.extend(schema_result.warnings)
            if schema_result.errors:
                result.valid = False
            
            # Validate internal consistency
            if result.valid:
                pack = self._load_pack(pack_yaml)
                if pack:
                    consistency_result = self._validate_consistency(pack)
                    result.errors.extend(consistency_result.errors)
                    result.warnings.extend(consistency_result.warnings)
                    if consistency_result.errors:
                        result.valid = False
        
        return result
    
    def _validate_schema(self, pack_yaml: Path) -> ValidationResult:
        """Validate pack.yaml against Pydantic schema."""
        result = ValidationResult(pack_id=pack_yaml.parent.name)
        
        try:
            with open(pack_yaml) as f:
                data = yaml.safe_load(f)
            
            if data is None:
                result.errors.append("pack.yaml is empty")
                return result
            
            # Check required top-level fields
            if "id" not in data:
                result.errors.append("Missing required field: id")
            if "name" not in data:
                result.errors.append("Missing required field: name")
            
            # Validate with Pydantic
            KnowledgePack.model_validate(data)
            
        except yaml.YAMLError as e:
            result.errors.append(f"Invalid YAML syntax: {e}")
        except ValidationError as e:
            for error in e.errors():
                loc = ".".join(str(l) for l in error["loc"])
                result.errors.append(f"Schema error at {loc}: {error['msg']}")
        
        return result
    
    def _load_pack(self, pack_yaml: Path) -> Optional[KnowledgePack]:
        """Load pack for consistency validation."""
        try:
            with open(pack_yaml) as f:
                data = yaml.safe_load(f)
            return KnowledgePack.model_validate(data)
        except Exception:
            return None
    
    def _validate_consistency(self, pack: KnowledgePack) -> ValidationResult:
        """Validate internal consistency of pack."""
        result = ValidationResult(pack_id=pack.id)
        
        # Collect all failure mode IDs
        fm_ids = {fm.id for fm in pack.failure_modes}
        
        # Check test templates reference valid failure modes
        for template in pack.test_templates:
            if template.failure_mode_id and template.failure_mode_id not in fm_ids:
                result.warnings.append(
                    f"Test template '{template.id}' references unknown "
                    f"failure mode: {template.failure_mode_id}"
                )
        
        # Check recipes reference valid failure modes
        for recipe in pack.recipes:
            for fm_id in recipe.failure_mode_ids:
                if fm_id not in fm_ids:
                    result.warnings.append(
                        f"Recipe '{recipe.id}' references unknown "
                        f"failure mode: {fm_id}"
                    )
        
        # Check for duplicate IDs
        seen_fm_ids: set[str] = set()
        for fm in pack.failure_modes:
            if fm.id in seen_fm_ids:
                result.errors.append(f"Duplicate failure mode ID: {fm.id}")
            seen_fm_ids.add(fm.id)
        
        seen_template_ids: set[str] = set()
        for template in pack.test_templates:
            if template.id in seen_template_ids:
                result.errors.append(f"Duplicate test template ID: {template.id}")
            seen_template_ids.add(template.id)
        
        # Check snippets with fallbacks reference existing files
        snippet_files = {s.filename for s in pack.snippets}
        for snippet in pack.snippets:
            if snippet.fallback_snippet and snippet.fallback_snippet not in snippet_files:
                result.warnings.append(
                    f"Snippet '{snippet.filename}' references unknown "
                    f"fallback: {snippet.fallback_snippet}"
                )
        
        return result
    
    def validate_all(self, search_paths: list[Path]) -> list[ValidationResult]:
        """Validate all packs in search paths."""
        results = []
        
        for search_path in search_paths:
            if not search_path.exists():
                continue
            
            for item in search_path.iterdir():
                if item.is_dir() and not item.name.startswith("."):
                    results.append(self.validate(item))
        
        return results
