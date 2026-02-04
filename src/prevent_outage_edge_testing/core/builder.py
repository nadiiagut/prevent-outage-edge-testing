# src/prevent_outage_edge_testing/core/builder.py
# Test plan builder from Jira descriptions.
"""
TestPlanBuilder generates test plans by:
1. Analyzing feature descriptions
2. Matching against knowledge packs
3. Synthesizing test cases
4. Including relevant recipes and snippets

This is the core AI-assisted builder functionality.
"""

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from prevent_outage_edge_testing.packs.models import (
    KnowledgePack,
    Recipe,
    Snippet,
    TestTemplate,
    FailureMode,
    Severity,
)


@dataclass
class TestAssertion:
    """A single test assertion."""
    description: str
    expression: str = "True"
    expected: bool = True


@dataclass 
class TestCase:
    """A generated test case."""
    id: str
    name: str
    description: str
    failure_mode_id: Optional[str] = None
    priority: Severity = Severity.MEDIUM
    setup_steps: list[str] = field(default_factory=list)
    execution_steps: list[str] = field(default_factory=list)
    assertions: list[TestAssertion] = field(default_factory=list)
    cleanup_steps: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)


@dataclass
class TestPlan:
    """A complete test plan."""
    id: str
    title: str
    description: str
    jira_key: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    test_cases: list[TestCase] = field(default_factory=list)
    failure_modes_covered: list[str] = field(default_factory=list)
    coverage_notes: str = ""


@dataclass
class BuildResult:
    """Result of the build process."""
    plan: TestPlan
    matched_packs: list[KnowledgePack]
    recipes: list[Recipe]
    snippets: list[Snippet]


class TestPlanBuilder:
    """Builds test plans from feature descriptions using knowledge packs."""
    
    # Keyword to pack ID mapping for quick matching
    KEYWORD_MAP: dict[str, list[str]] = {
        # HTTP/Cache keywords
        "cache": ["edge-http-cache-correctness"],
        "http": ["edge-http-cache-correctness"],
        "etag": ["edge-http-cache-correctness"],
        "vary": ["edge-http-cache-correctness"],
        "304": ["edge-http-cache-correctness"],
        "stale": ["edge-http-cache-correctness"],
        "revalidate": ["edge-http-cache-correctness"],
        
        # Latency/Observability keywords
        "latency": ["edge-latency-regression-observability"],
        "p99": ["edge-latency-regression-observability"],
        "p95": ["edge-latency-regression-observability"],
        "percentile": ["edge-latency-regression-observability"],
        "dtrace": ["edge-latency-regression-observability"],
        "trace": ["edge-latency-regression-observability"],
        "observability": ["edge-latency-regression-observability"],
        "regression": ["edge-latency-regression-observability"],
        
        # Fault injection keywords
        "fault": ["fault-injection-io"],
        "inject": ["fault-injection-io"],
        "io": ["fault-injection-io"],
        "disk": ["fault-injection-io"],
        "ld_preload": ["fault-injection-io"],
        "chaos": ["fault-injection-io"],
        "failure": ["fault-injection-io"],
    }
    
    def __init__(self, packs: list[KnowledgePack]) -> None:
        self.packs = {p.id: p for p in packs}
    
    def _extract_keywords(self, text: str) -> set[str]:
        """Extract relevant keywords from description text."""
        text_lower = text.lower()
        found = set()
        for keyword in self.KEYWORD_MAP:
            if keyword in text_lower:
                found.add(keyword)
        return found
    
    def _match_packs(self, keywords: set[str]) -> list[KnowledgePack]:
        """Find packs matching the extracted keywords."""
        matched_ids: set[str] = set()
        for kw in keywords:
            if kw in self.KEYWORD_MAP:
                matched_ids.update(self.KEYWORD_MAP[kw])
        
        return [self.packs[pid] for pid in matched_ids if pid in self.packs]
    
    def _generate_test_id(self, prefix: str, name: str) -> str:
        """Generate a unique test ID."""
        hash_input = f"{prefix}-{name}-{datetime.utcnow().isoformat()}"
        short_hash = hashlib.md5(hash_input.encode()).hexdigest()[:8]
        safe_name = re.sub(r"[^a-z0-9]", "-", name.lower())[:30]
        return f"{prefix}-{safe_name}-{short_hash}"
    
    def _template_to_test_case(self, template: TestTemplate) -> TestCase:
        """Convert a test template to a test case."""
        return TestCase(
            id=self._generate_test_id("tc", template.name),
            name=template.name,
            description=template.description,
            failure_mode_id=template.failure_mode_id,
            priority=template.priority,
            setup_steps=template.setup_steps.copy(),
            execution_steps=template.execution_steps.copy(),
            assertions=[
                TestAssertion(
                    description=a.description,
                    expression=a.expression,
                    expected=a.expected,
                )
                for a in template.assertions
            ],
            cleanup_steps=template.cleanup_steps.copy(),
            tags=template.tags.copy() + ["generated"],
        )
    
    def _generate_basic_test(self, fm: FailureMode) -> TestCase:
        """Generate a basic test for a failure mode without a template."""
        return TestCase(
            id=self._generate_test_id("tc", fm.name),
            name=f"Test: {fm.name}",
            description=f"Verify system handles: {fm.description}",
            failure_mode_id=fm.id,
            priority=fm.severity,
            setup_steps=[
                "# TODO: Configure test environment",
                f"# Target failure mode: {fm.id}",
            ],
            execution_steps=[
                "# TODO: Execute test scenario",
                f"# Expected symptoms if failing: {', '.join(fm.symptoms[:2])}",
            ],
            assertions=[
                TestAssertion(
                    description=f"Verify absence of: {symptom}",
                    expression=f"not symptom_present('{symptom}')",
                )
                for symptom in fm.symptoms[:3]
            ],
            cleanup_steps=["# TODO: Cleanup test environment"],
            tags=fm.tags + ["generated", "needs-implementation"],
        )
    
    def build(
        self,
        description: str,
        title: Optional[str] = None,
        jira_key: Optional[str] = None,
    ) -> BuildResult:
        """
        Build a test plan from a feature description.
        
        Args:
            description: Feature description text
            title: Optional plan title
            jira_key: Optional Jira issue key
            
        Returns:
            BuildResult with plan, recipes, and snippets
        """
        # Extract keywords and match packs
        keywords = self._extract_keywords(description)
        matched_packs = self._match_packs(keywords)
        
        # Collect test cases
        test_cases: list[TestCase] = []
        failure_modes_covered: list[str] = []
        recipes: list[Recipe] = []
        snippets: list[Snippet] = []
        
        for pack in matched_packs:
            # Add test templates
            for template in pack.test_templates:
                test_cases.append(self._template_to_test_case(template))
                if template.failure_mode_id:
                    failure_modes_covered.append(template.failure_mode_id)
            
            # Generate tests for failure modes without templates
            template_fm_ids = {t.failure_mode_id for t in pack.test_templates}
            for fm in pack.failure_modes:
                if fm.id not in template_fm_ids:
                    test_cases.append(self._generate_basic_test(fm))
                    failure_modes_covered.append(fm.id)
            
            # Collect recipes and snippets
            recipes.extend(pack.recipes)
            snippets.extend(pack.snippets)
        
        # Sort by priority
        priority_order = {
            Severity.CRITICAL: 0,
            Severity.HIGH: 1,
            Severity.MEDIUM: 2,
            Severity.LOW: 3,
        }
        test_cases.sort(key=lambda tc: priority_order.get(tc.priority, 2))
        
        # Build coverage notes
        if matched_packs:
            coverage_notes = (
                f"Matched {len(matched_packs)} knowledge packs: "
                f"{', '.join(p.id for p in matched_packs)}.\n"
                f"Generated {len(test_cases)} test cases covering "
                f"{len(set(failure_modes_covered))} failure modes."
            )
        else:
            coverage_notes = (
                "No matching knowledge packs found for this description. "
                "Consider adding custom packs or using more specific keywords."
            )
        
        # Create plan
        plan_title = title or f"Test Plan for {jira_key or 'Feature'}"
        plan = TestPlan(
            id=self._generate_test_id("plan", plan_title),
            title=plan_title,
            description="Auto-generated test plan from feature description analysis.",
            jira_key=jira_key,
            test_cases=test_cases,
            failure_modes_covered=list(set(failure_modes_covered)),
            coverage_notes=coverage_notes,
        )
        
        return BuildResult(
            plan=plan,
            matched_packs=matched_packs,
            recipes=recipes,
            snippets=snippets,
        )
