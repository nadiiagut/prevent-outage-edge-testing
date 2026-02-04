# src/prevent_outage_edge_testing/builder.py
# AI-assisted builder that converts Jira feature descriptions into test plans.

"""
TestPlanBuilder: Takes a Jira feature description and generates a test plan
by matching against knowledge packs and synthesizing relevant test cases.

This module provides both:
- Rule-based matching using keywords and tags
- LLM-assisted generation when an API key is provided (optional)

Note: Generated test plans are starting points and should be reviewed.
No tool can guarantee complete coverage of all failure modes.
"""

import hashlib
import re
from datetime import datetime
from typing import Any

from jinja2 import Environment, BaseLoader
from pydantic import BaseModel, Field
from rich.console import Console

from prevent_outage_edge_testing.models import (
    FailureMode,
    KnowledgePack,
    ObservabilityRecipe,
    Severity,
    TestAssertion,
    TestCase,
    TestPlan,
)
from prevent_outage_edge_testing.registry import PackRegistry, get_global_registry

console = Console()


class MatchResult(BaseModel):
    """Result of matching a description against knowledge packs."""

    pack: KnowledgePack
    matched_failure_modes: list[FailureMode]
    relevance_score: float = Field(ge=0.0, le=1.0)
    matched_keywords: list[str]


class BuilderConfig(BaseModel):
    """Configuration for the test plan builder."""

    min_relevance_score: float = Field(default=0.3, ge=0.0, le=1.0)
    include_observability: bool = Field(default=True)
    max_test_cases: int = Field(default=20)
    prioritize_critical: bool = Field(default=True)
    llm_api_key: str | None = Field(default=None, description="Optional LLM API key")
    llm_model: str = Field(default="gpt-4")
    llm_base_url: str | None = Field(default=None)


class TestPlanBuilder:
    """
    Builds test plans from feature descriptions using knowledge packs.

    The builder performs keyword matching to find relevant failure modes,
    then synthesizes test cases from pack templates.
    """

    # Keywords mapped to pack IDs for quick matching
    KEYWORD_MAP: dict[str, list[str]] = {
        "cache": ["cdn-cache-invalidation"],
        "cdn": ["cdn-cache-invalidation"],
        "invalidation": ["cdn-cache-invalidation"],
        "purge": ["cdn-cache-invalidation"],
        "stale": ["cdn-cache-invalidation"],
        "ttl": ["cdn-cache-invalidation"],
        "tls": ["tls-termination-failures"],
        "ssl": ["tls-termination-failures"],
        "certificate": ["tls-termination-failures"],
        "https": ["tls-termination-failures"],
        "cipher": ["tls-termination-failures"],
        "handshake": ["tls-termination-failures"],
        "load balancer": ["load-balancer-failures"],
        "health check": ["load-balancer-failures"],
        "backend": ["load-balancer-failures"],
        "upstream": ["load-balancer-failures"],
        "draining": ["load-balancer-failures"],
        "sticky": ["load-balancer-failures"],
        "session": ["load-balancer-failures"],
    }

    def __init__(
        self,
        registry: PackRegistry | None = None,
        config: BuilderConfig | None = None,
    ) -> None:
        self.registry = registry or get_global_registry()
        self.config = config or BuilderConfig()
        self._jinja_env = Environment(loader=BaseLoader())

    def _extract_keywords(self, text: str) -> set[str]:
        """Extract relevant keywords from text."""
        text_lower = text.lower()
        found = set()
        for keyword in self.KEYWORD_MAP:
            if keyword in text_lower:
                found.add(keyword)
        return found

    def _calculate_relevance(
        self, pack: KnowledgePack, keywords: set[str], description: str
    ) -> tuple[float, list[str]]:
        """Calculate relevance score for a pack given extracted keywords."""
        matched_keywords = []
        score = 0.0

        # Keyword matching
        for kw in keywords:
            if pack.id in self.KEYWORD_MAP.get(kw, []):
                matched_keywords.append(kw)
                score += 0.2

        # Tag matching
        desc_lower = description.lower()
        for tag in pack.tags:
            if tag.lower() in desc_lower:
                score += 0.1
                matched_keywords.append(f"tag:{tag}")

        # Failure mode symptom matching
        for fm in pack.failure_modes:
            for symptom in fm.symptoms:
                if any(word in desc_lower for word in symptom.lower().split()[:3]):
                    score += 0.05

        return min(score, 1.0), matched_keywords

    def match_packs(self, description: str) -> list[MatchResult]:
        """Find knowledge packs relevant to the given description."""
        keywords = self._extract_keywords(description)
        results = []

        for pack in self.registry:
            relevance, matched_kw = self._calculate_relevance(pack, keywords, description)

            if relevance >= self.config.min_relevance_score:
                # Find which failure modes are most relevant
                matched_modes = []
                desc_lower = description.lower()

                for fm in pack.failure_modes:
                    fm_text = f"{fm.name} {fm.description} {' '.join(fm.symptoms)}"
                    if any(kw in fm_text.lower() for kw in keywords) or any(
                        word in desc_lower for word in fm.name.lower().split()
                    ):
                        matched_modes.append(fm)

                # If no specific modes matched, include high-severity ones
                if not matched_modes:
                    matched_modes = pack.get_high_severity_modes()

                results.append(
                    MatchResult(
                        pack=pack,
                        matched_failure_modes=matched_modes,
                        relevance_score=relevance,
                        matched_keywords=matched_kw,
                    )
                )

        # Sort by relevance
        results.sort(key=lambda r: r.relevance_score, reverse=True)
        return results

    def _generate_test_id(self, prefix: str, name: str) -> str:
        """Generate a unique test ID."""
        hash_input = f"{prefix}-{name}-{datetime.utcnow().isoformat()}"
        short_hash = hashlib.md5(hash_input.encode()).hexdigest()[:8]
        safe_name = re.sub(r"[^a-z0-9]", "-", name.lower())[:30]
        return f"{prefix}-{safe_name}-{short_hash}"

    def _adapt_test_template(
        self, template: TestCase, context: dict[str, Any]
    ) -> TestCase:
        """Adapt a test template with context-specific information."""
        # For now, return template as-is with new ID
        return TestCase(
            id=self._generate_test_id("gen", template.name),
            name=template.name,
            description=template.description,
            failure_mode_id=template.failure_mode_id,
            priority=template.priority,
            setup_steps=template.setup_steps.copy(),
            execution_steps=template.execution_steps.copy(),
            assertions=[a.model_copy() for a in template.assertions],
            cleanup_steps=template.cleanup_steps.copy(),
            tags=template.tags.copy() + ["generated"],
            estimated_duration_seconds=template.estimated_duration_seconds,
            requires_privileged=template.requires_privileged,
        )

    def _generate_basic_test(self, failure_mode: FailureMode) -> TestCase:
        """Generate a basic test case for a failure mode without a template."""
        assertions = []
        for i, symptom in enumerate(failure_mode.symptoms[:3]):
            assertions.append(
                TestAssertion(
                    description=f"Verify absence of symptom: {symptom}",
                    expression=f"symptom_{i}_absent",
                    expected=True,
                )
            )

        return TestCase(
            id=self._generate_test_id("basic", failure_mode.name),
            name=f"Basic Test: {failure_mode.name}",
            description=f"Generated test for failure mode: {failure_mode.description}",
            failure_mode_id=failure_mode.id,
            priority=failure_mode.severity,
            setup_steps=[
                "# TODO: Implement setup for this failure mode",
                f"# Failure mode: {failure_mode.name}",
            ],
            execution_steps=[
                "# TODO: Implement test execution",
                f"# Test should verify absence of: {', '.join(failure_mode.symptoms[:2])}",
            ],
            assertions=assertions,
            cleanup_steps=["# TODO: Implement cleanup"],
            tags=["generated", "needs-implementation"] + failure_mode.tags,
            estimated_duration_seconds=60,
        )

    def build(
        self,
        description: str,
        jira_key: str | None = None,
        title: str | None = None,
    ) -> TestPlan:
        """
        Build a test plan from a feature description.

        Args:
            description: The feature description (from Jira or elsewhere)
            jira_key: Optional Jira issue key
            title: Optional title for the test plan

        Returns:
            A TestPlan with generated test cases and observability recipes
        """
        console.print(f"[blue]Building test plan for description ({len(description)} chars)...[/blue]")

        # Match against knowledge packs
        matches = self.match_packs(description)
        console.print(f"[green]Found {len(matches)} relevant knowledge packs[/green]")

        test_cases: list[TestCase] = []
        failure_modes_covered: list[str] = []
        coverage_notes_parts: list[str] = []

        for match in matches:
            coverage_notes_parts.append(
                f"Pack '{match.pack.name}' (relevance: {match.relevance_score:.2f}): "
                f"{len(match.matched_failure_modes)} failure modes"
            )

            for fm in match.matched_failure_modes:
                failure_modes_covered.append(fm.id)

                # Find matching template
                template_found = False
                for template in match.pack.test_templates:
                    if template.failure_mode_id == fm.id:
                        test_cases.append(
                            self._adapt_test_template(template, {"failure_mode": fm})
                        )
                        template_found = True

                # Generate basic test if no template
                if not template_found:
                    test_cases.append(self._generate_basic_test(fm))

        # Prioritize critical tests if configured
        if self.config.prioritize_critical:
            test_cases.sort(
                key=lambda t: {
                    Severity.CRITICAL: 0,
                    Severity.HIGH: 1,
                    Severity.MEDIUM: 2,
                    Severity.LOW: 3,
                }.get(t.priority, 2)
            )

        # Limit test cases
        if len(test_cases) > self.config.max_test_cases:
            test_cases = test_cases[: self.config.max_test_cases]
            coverage_notes_parts.append(
                f"Limited to {self.config.max_test_cases} test cases"
            )

        # Build coverage notes
        coverage_notes = "\n".join(coverage_notes_parts)
        if not matches:
            coverage_notes = (
                "No matching knowledge packs found. "
                "Consider adding custom packs for this domain."
            )

        plan_id = self._generate_test_id("plan", title or "untitled")
        plan_title = title or f"Test Plan for {jira_key or 'Feature'}"

        return TestPlan(
            id=plan_id,
            title=plan_title,
            description=f"Auto-generated test plan based on feature description analysis.",
            source_jira_key=jira_key,
            source_description=description,
            test_cases=test_cases,
            failure_modes_covered=failure_modes_covered,
            coverage_notes=coverage_notes,
            tags=["generated"],
        )

    def get_observability_recipes(
        self, test_plan: TestPlan
    ) -> list[ObservabilityRecipe]:
        """Get observability recipes relevant to a test plan's failure modes."""
        recipes = []
        seen_ids: set[str] = set()

        for pack in self.registry:
            for recipe in pack.observability_recipes:
                if recipe.id in seen_ids:
                    continue
                # Check if any failure mode in recipe matches plan
                if set(recipe.failure_mode_ids) & set(test_plan.failure_modes_covered):
                    recipes.append(recipe)
                    seen_ids.add(recipe.id)

        return recipes


def build_test_plan(
    description: str,
    jira_key: str | None = None,
    title: str | None = None,
) -> TestPlan:
    """Convenience function to build a test plan with default settings."""
    builder = TestPlanBuilder()
    return builder.build(description, jira_key, title)
