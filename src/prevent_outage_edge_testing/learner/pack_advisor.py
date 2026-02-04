# src/prevent_outage_edge_testing/learner/pack_advisor.py
"""
Pack advisor that uses learned patterns to recommend knowledge packs.

Integrates with the pack selection engine to provide recommendations
based on patterns extracted from existing tests.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from prevent_outage_edge_testing.learner.models import LearnedPatterns, RiskRule
from prevent_outage_edge_testing.learner.storage import load_patterns


@dataclass
class PackRecommendation:
    """A pack recommendation with reasoning."""
    
    pack_id: str
    confidence: float
    reasons: list[str] = field(default_factory=list)
    source_rules: list[str] = field(default_factory=list)


@dataclass
class AdvisorResult:
    """Result from pack advisor."""
    
    recommendations: list[PackRecommendation]
    patterns_consulted: bool
    total_rules_matched: int
    
    def get_top_recommendations(self, n: int = 5) -> list[PackRecommendation]:
        """Get top N recommendations by confidence."""
        return sorted(self.recommendations, key=lambda r: r.confidence, reverse=True)[:n]
    
    def get_pack_ids(self, min_confidence: float = 0.5) -> list[str]:
        """Get pack IDs above confidence threshold."""
        return [r.pack_id for r in self.recommendations if r.confidence >= min_confidence]


class PackAdvisor:
    """
    Advises on pack selection using learned patterns.
    
    Can be used standalone or integrated with the TestPlanBuilder.
    """
    
    def __init__(self, patterns: Optional[LearnedPatterns] = None) -> None:
        """
        Initialize the advisor.
        
        Args:
            patterns: LearnedPatterns to use, or None to load from default location
        """
        self._patterns = patterns
        self._loaded = patterns is not None
    
    @classmethod
    def from_file(cls, base_dir: Optional[Path] = None) -> "PackAdvisor":
        """
        Create advisor loading patterns from file.
        
        Args:
            base_dir: Base directory containing .poet/learned_patterns.json
            
        Returns:
            PackAdvisor instance (may have no patterns if file not found)
        """
        patterns = load_patterns(base_dir)
        advisor = cls(patterns)
        advisor._loaded = patterns is not None
        return advisor
    
    @property
    def has_patterns(self) -> bool:
        """Check if patterns are available."""
        return self._patterns is not None
    
    def get_recommendations(
        self,
        description: Optional[str] = None,
        min_confidence: float = 0.3,
    ) -> AdvisorResult:
        """
        Get pack recommendations based on learned patterns.
        
        Args:
            description: Optional feature description to match against
            min_confidence: Minimum confidence for recommendations
            
        Returns:
            AdvisorResult with recommendations
        """
        if not self._patterns:
            return AdvisorResult(
                recommendations=[],
                patterns_consulted=False,
                total_rules_matched=0,
            )
        
        # Collect recommendations from risk rules
        pack_scores: dict[str, PackRecommendation] = {}
        rules_matched = 0
        
        for rule in self._patterns.risk_rules:
            if rule.confidence < min_confidence:
                continue
            
            # Check if rule applies (for now, all rules apply)
            # In future, could match against description
            applies = True
            
            if description:
                # Boost confidence if description matches rule indicators
                desc_lower = description.lower()
                for indicator in rule.derived_from:
                    if any(word in desc_lower for word in indicator.lower().split()):
                        applies = True
                        break
            
            if applies:
                rules_matched += 1
                for pack_id in rule.recommended_packs:
                    if pack_id not in pack_scores:
                        pack_scores[pack_id] = PackRecommendation(
                            pack_id=pack_id,
                            confidence=0.0,
                            reasons=[],
                            source_rules=[],
                        )
                    
                    # Accumulate confidence (with diminishing returns)
                    current = pack_scores[pack_id].confidence
                    added = rule.confidence * (1 - current * 0.3)
                    pack_scores[pack_id].confidence = min(current + added, 0.99)
                    pack_scores[pack_id].reasons.append(rule.description)
                    pack_scores[pack_id].source_rules.append(rule.rule_id)
        
        # Add recommendations from fixture roles
        self._add_fixture_recommendations(pack_scores, min_confidence)
        
        # Add recommendations from assertion patterns
        self._add_assertion_recommendations(pack_scores, min_confidence)
        
        recommendations = list(pack_scores.values())
        recommendations.sort(key=lambda r: r.confidence, reverse=True)
        
        return AdvisorResult(
            recommendations=recommendations,
            patterns_consulted=True,
            total_rules_matched=rules_matched,
        )
    
    def _add_fixture_recommendations(
        self, 
        pack_scores: dict[str, PackRecommendation],
        min_confidence: float,
    ) -> None:
        """Add recommendations based on fixture roles."""
        if not self._patterns:
            return
        
        from prevent_outage_edge_testing.learner.models import FixtureRole
        
        # Map fixture roles to packs
        role_packs = {
            FixtureRole.EDGE_NODE: ["edge-http-cache-correctness", "edge-latency-regression-observability"],
            FixtureRole.CACHE: ["edge-http-cache-correctness"],
            FixtureRole.LOAD_BALANCER: ["edge-latency-regression-observability"],
            FixtureRole.INJECTOR: ["fault-injection-io"],
        }
        
        for fixture in self._patterns.fixtures:
            if fixture.confidence < min_confidence:
                continue
            
            if fixture.inferred_role in role_packs:
                for pack_id in role_packs[fixture.inferred_role]:
                    if pack_id not in pack_scores:
                        pack_scores[pack_id] = PackRecommendation(
                            pack_id=pack_id,
                            confidence=0.0,
                            reasons=[],
                            source_rules=[],
                        )
                    
                    boost = fixture.confidence * 0.2
                    pack_scores[pack_id].confidence = min(
                        pack_scores[pack_id].confidence + boost, 0.99
                    )
                    pack_scores[pack_id].reasons.append(
                        f"Fixture '{fixture.name}' suggests {fixture.inferred_role.value}"
                    )
    
    def _add_assertion_recommendations(
        self,
        pack_scores: dict[str, PackRecommendation],
        min_confidence: float,
    ) -> None:
        """Add recommendations based on assertion patterns."""
        if not self._patterns:
            return
        
        # Map assertion types to packs
        type_packs = {
            "cache": ["edge-http-cache-correctness"],
            "header": ["edge-http-cache-correctness"],
            "timing": ["edge-latency-regression-observability"],
            "status_code": ["edge-http-cache-correctness"],
        }
        
        for template in self._patterns.assertion_templates:
            if template.pattern_type in type_packs:
                # Scale by occurrences
                base_confidence = min(0.1 + template.occurrences * 0.02, 0.4)
                
                if base_confidence >= min_confidence:
                    for pack_id in type_packs[template.pattern_type]:
                        if pack_id not in pack_scores:
                            pack_scores[pack_id] = PackRecommendation(
                                pack_id=pack_id,
                                confidence=0.0,
                                reasons=[],
                                source_rules=[],
                            )
                        
                        pack_scores[pack_id].confidence = min(
                            pack_scores[pack_id].confidence + base_confidence, 0.99
                        )
                        pack_scores[pack_id].reasons.append(
                            f"{template.occurrences}x {template.pattern_type} assertions"
                        )
    
    def get_signals_for_pack(self, pack_id: str) -> list[str]:
        """
        Get signals that suggest a specific pack.
        
        Args:
            pack_id: Pack ID to get signals for
            
        Returns:
            List of signal values that point to this pack
        """
        if not self._patterns:
            return []
        
        signals = []
        
        # Find rules that recommend this pack
        for rule in self._patterns.risk_rules:
            if pack_id in rule.recommended_packs:
                signals.extend(rule.derived_from)
        
        return signals
    
    def get_matching_fixtures(self, pack_id: str) -> list[str]:
        """
        Get fixture names that suggest a specific pack.
        
        Args:
            pack_id: Pack ID to find fixtures for
            
        Returns:
            List of fixture names
        """
        if not self._patterns:
            return []
        
        from prevent_outage_edge_testing.learner.models import FixtureRole
        
        # Map packs to relevant roles
        pack_roles = {
            "edge-http-cache-correctness": [FixtureRole.EDGE_NODE, FixtureRole.CACHE, FixtureRole.ORIGIN],
            "edge-latency-regression-observability": [FixtureRole.EDGE_NODE, FixtureRole.LOAD_BALANCER, FixtureRole.TRACER],
            "fault-injection-io": [FixtureRole.INJECTOR],
        }
        
        roles = pack_roles.get(pack_id, [])
        
        return [
            f.name for f in self._patterns.fixtures
            if f.inferred_role in roles and f.confidence > 0.3
        ]


def get_pack_advisor(base_dir: Optional[Path] = None) -> PackAdvisor:
    """
    Get a pack advisor, loading patterns if available.
    
    Args:
        base_dir: Base directory to look for patterns
        
    Returns:
        PackAdvisor instance
    """
    return PackAdvisor.from_file(base_dir)
