# src/prevent_outage_edge_testing/learner/storage.py
"""
Storage utilities for learned patterns.

Handles saving and loading of knowledge/learned/${KNOWLEDGE_ID}.json
"""

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from prevent_outage_edge_testing.learner.models import LearnedPatterns


KNOWLEDGE_DIR = "knowledge/learned"
LEGACY_POET_DIR = ".poet"
LEGACY_PATTERNS_FILE = "learned_patterns.json"


def generate_knowledge_id(source_path: str) -> str:
    """
    Generate a knowledge ID from source path.
    
    Creates a readable ID like: irr-abc123
    """
    # Extract meaningful name from path
    path = Path(source_path).expanduser().resolve()
    name = path.name or path.parent.name or "unknown"
    # Clean name to be filesystem-safe
    name = re.sub(r'[^a-zA-Z0-9_-]', '', name.lower())[:20]
    
    # Add short hash for uniqueness
    hash_input = str(path).encode()
    short_hash = hashlib.sha256(hash_input).hexdigest()[:8]
    
    return f"{name}-{short_hash}" if name else short_hash


def get_knowledge_path(knowledge_id: str, base_dir: Optional[Path] = None) -> Path:
    """
    Get path to a specific knowledge file.
    
    Args:
        knowledge_id: The knowledge ID
        base_dir: Base directory (defaults to current directory)
        
    Returns:
        Path to knowledge/learned/{knowledge_id}.json
    """
    if base_dir is None:
        base_dir = Path.cwd()
    return base_dir / KNOWLEDGE_DIR / f"{knowledge_id}.json"


def get_patterns_path(base_dir: Optional[Path] = None, knowledge_id: Optional[str] = None) -> Path:
    """
    Get the path to patterns file.
    
    If knowledge_id is provided, returns knowledge/learned/{id}.json
    Otherwise returns legacy .poet/learned_patterns.json for backwards compat.
    
    Args:
        base_dir: Base directory (defaults to current directory)
        knowledge_id: Optional knowledge ID
        
    Returns:
        Path to patterns file
    """
    if base_dir is None:
        base_dir = Path.cwd()
    
    if knowledge_id:
        return base_dir / KNOWLEDGE_DIR / f"{knowledge_id}.json"
    
    # Legacy path for backwards compatibility
    return base_dir / LEGACY_POET_DIR / LEGACY_PATTERNS_FILE


def ensure_knowledge_dir(base_dir: Optional[Path] = None) -> Path:
    """
    Ensure knowledge/learned directory exists.
    
    Args:
        base_dir: Base directory (defaults to current directory)
        
    Returns:
        Path to knowledge/learned directory
    """
    if base_dir is None:
        base_dir = Path.cwd()
    
    knowledge_dir = base_dir / KNOWLEDGE_DIR
    knowledge_dir.mkdir(parents=True, exist_ok=True)
    return knowledge_dir


def ensure_poet_dir(base_dir: Optional[Path] = None) -> Path:
    """
    Ensure .poet directory exists (legacy, for reports etc).
    
    Args:
        base_dir: Base directory (defaults to current directory)
        
    Returns:
        Path to .poet directory
    """
    if base_dir is None:
        base_dir = Path.cwd()
    
    poet_dir = base_dir / LEGACY_POET_DIR
    poet_dir.mkdir(parents=True, exist_ok=True)
    return poet_dir


def save_patterns(
    patterns: LearnedPatterns,
    base_dir: Optional[Path] = None,
    knowledge_id: Optional[str] = None,
) -> Path:
    """
    Save learned patterns to JSON file.
    
    Saves to knowledge/learned/{knowledge_id}.json
    If no knowledge_id provided, generates one from source paths.
    
    Args:
        patterns: LearnedPatterns to save
        base_dir: Base directory (defaults to current directory)
        knowledge_id: Optional explicit knowledge ID
        
    Returns:
        Path where patterns were saved
    """
    if base_dir is None:
        base_dir = Path.cwd()
    
    # Generate knowledge_id if not provided
    if not knowledge_id and patterns.source_paths:
        knowledge_id = generate_knowledge_id(patterns.source_paths[0])
    elif not knowledge_id:
        knowledge_id = f"learned-{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
    
    # Store the knowledge_id in patterns
    patterns.knowledge_id = knowledge_id
    
    # Ensure directory exists
    ensure_knowledge_dir(base_dir)
    
    # Get path and save
    patterns_path = get_knowledge_path(knowledge_id, base_dir)
    
    # Update timestamp
    patterns.updated_at = datetime.utcnow()
    
    # Serialize to JSON
    data = patterns.model_dump(mode="json")
    
    with open(patterns_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)
    
    return patterns_path


def list_knowledge_files(base_dir: Optional[Path] = None) -> list[Path]:
    """
    List all knowledge files in knowledge/learned/.
    
    Args:
        base_dir: Base directory (defaults to current directory)
        
    Returns:
        List of paths to knowledge JSON files
    """
    if base_dir is None:
        base_dir = Path.cwd()
    
    knowledge_dir = base_dir / KNOWLEDGE_DIR
    if not knowledge_dir.exists():
        return []
    
    return sorted(knowledge_dir.glob("*.json"))


def load_patterns(
    base_dir: Optional[Path] = None,
    knowledge_id: Optional[str] = None,
) -> Optional[LearnedPatterns]:
    """
    Load learned patterns from JSON file.
    
    If knowledge_id is provided, loads from knowledge/learned/{id}.json.
    Otherwise, tries to load the most recent knowledge file, or falls back
    to legacy .poet/learned_patterns.json.
    
    Args:
        base_dir: Base directory (defaults to current directory)
        knowledge_id: Optional specific knowledge ID to load
        
    Returns:
        LearnedPatterns or None if file doesn't exist
    """
    if base_dir is None:
        base_dir = Path.cwd()
    
    # If specific knowledge_id requested
    if knowledge_id:
        patterns_path = get_knowledge_path(knowledge_id, base_dir)
    else:
        # Try to find most recent knowledge file
        knowledge_files = list_knowledge_files(base_dir)
        if knowledge_files:
            patterns_path = knowledge_files[-1]  # Most recent (sorted by name)
        else:
            # Fall back to legacy path
            patterns_path = base_dir / LEGACY_POET_DIR / LEGACY_PATTERNS_FILE
    
    if not patterns_path.exists():
        return None
    
    try:
        with open(patterns_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return LearnedPatterns.model_validate(data)
    except (json.JSONDecodeError, Exception):
        return None


def merge_patterns(existing: LearnedPatterns, new: LearnedPatterns) -> LearnedPatterns:
    """
    Merge new patterns into existing patterns.
    
    Updates counts and adds new items while preserving existing data.
    
    Args:
        existing: Existing patterns
        new: New patterns to merge
        
    Returns:
        Merged LearnedPatterns
    """
    # Merge source paths
    existing.source_paths = list(set(existing.source_paths + new.source_paths))
    existing.total_files_analyzed = len(existing.source_paths)
    existing.total_test_functions += new.total_test_functions
    existing.total_test_classes += new.total_test_classes
    
    # Merge signals
    existing_signals = {s.value: s for s in existing.signals}
    for signal in new.signals:
        if signal.value in existing_signals:
            existing_signals[signal.value].occurrences += signal.occurrences
            existing_signals[signal.value].source_files = list(
                set(existing_signals[signal.value].source_files + signal.source_files)
            )
        else:
            existing_signals[signal.value] = signal
    existing.signals = list(existing_signals.values())
    
    # Merge fixtures
    existing_fixtures = {f.name: f for f in existing.fixtures}
    for fixture in new.fixtures:
        if fixture.name in existing_fixtures:
            existing_fixtures[fixture.name].usages += fixture.usages
            if fixture.confidence > existing_fixtures[fixture.name].confidence:
                existing_fixtures[fixture.name].inferred_role = fixture.inferred_role
                existing_fixtures[fixture.name].confidence = fixture.confidence
        else:
            existing_fixtures[fixture.name] = fixture
    existing.fixtures = list(existing_fixtures.values())
    
    # Merge assertion templates
    existing_templates = {f"{t.pattern_type}:{t.template}": t for t in existing.assertion_templates}
    for template in new.assertion_templates:
        key = f"{template.pattern_type}:{template.template}"
        if key in existing_templates:
            existing_templates[key].occurrences += template.occurrences
            existing_templates[key].examples = list(
                set(existing_templates[key].examples + template.examples)
            )[:10]  # Keep max 10 examples
        else:
            existing_templates[key] = template
    existing.assertion_templates = list(existing_templates.values())
    
    # Merge timing assertions (simple append, dedupe by metric_type)
    existing_timing = {t.metric_type: t for t in existing.timing_assertions}
    for timing in new.timing_assertions:
        if timing.metric_type not in existing_timing:
            existing_timing[timing.metric_type] = timing
        else:
            existing_timing[timing.metric_type].occurrences += timing.occurrences
    existing.timing_assertions = list(existing_timing.values())
    
    # Merge observability patterns
    existing.observability_patterns.extend(new.observability_patterns)
    
    # Merge fault injection patterns
    existing_faults = {f.fault_type: f for f in existing.fault_injection_patterns}
    for fault in new.fault_injection_patterns:
        if fault.fault_type in existing_faults:
            existing_faults[fault.fault_type].occurrences += fault.occurrences
            existing_faults[fault.fault_type].source_files = list(
                set(existing_faults[fault.fault_type].source_files + fault.source_files)
            )
        else:
            existing_faults[fault.fault_type] = fault
    existing.fault_injection_patterns = list(existing_faults.values())
    
    # Merge endpoints
    existing_endpoints = {f"{e.pattern_type}:{e.value}": e for e in existing.endpoints}
    for endpoint in new.endpoints:
        key = f"{endpoint.pattern_type}:{endpoint.value}"
        if key in existing_endpoints:
            existing_endpoints[key].occurrences += endpoint.occurrences
        else:
            existing_endpoints[key] = endpoint
    existing.endpoints = list(existing_endpoints.values())
    
    # Merge risk rules (replace with higher confidence)
    existing_rules = {r.rule_id: r for r in existing.risk_rules}
    for rule in new.risk_rules:
        if rule.rule_id not in existing_rules or rule.confidence > existing_rules[rule.rule_id].confidence:
            existing_rules[rule.rule_id] = rule
    existing.risk_rules = list(existing_rules.values())
    
    existing.updated_at = datetime.utcnow()
    
    return existing
