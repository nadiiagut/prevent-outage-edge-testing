# src/prevent_outage_edge_testing/learner/__init__.py
"""
Test pattern learner module.

Extracts patterns from existing pytest test suites using static analysis (AST).
No tests are executed - all analysis is done by parsing Python source code.

Usage:
    from prevent_outage_edge_testing.learner import (
        TestAnalyzer,
        PatternExtractor,
        PackAdvisor,
        save_patterns,
        load_patterns,
    )
    
    # Analyze test files
    parsed = TestAnalyzer(source, path).analyze()
    
    # Extract patterns
    extractor = PatternExtractor()
    patterns = extractor.extract_from_files([parsed])
    
    # Save to .poet/learned_patterns.json
    save_patterns(patterns)
    
    # Get pack recommendations
    advisor = PackAdvisor(patterns)
    recommendations = advisor.get_recommendations()
"""

from prevent_outage_edge_testing.learner.analyzer import (
    TestAnalyzer,
    analyze_test_file,
    discover_test_files,
    ParsedTestFile,
)
from prevent_outage_edge_testing.learner.models import (
    AssertionTemplate,
    EndpointPattern,
    ExtractedFixture,
    FixtureRole,
    LearnedPatterns,
    ObservabilityPattern,
    FaultInjectionPattern,
    RiskRule,
    Signal,
    TimingAssertion,
)
from prevent_outage_edge_testing.learner.extractor import PatternExtractor
from prevent_outage_edge_testing.learner.storage import (
    save_patterns,
    load_patterns,
    merge_patterns,
    get_patterns_path,
)
from prevent_outage_edge_testing.learner.pack_advisor import (
    PackAdvisor,
    PackRecommendation,
    AdvisorResult,
    get_pack_advisor,
)

__all__ = [
    # Analyzer
    "TestAnalyzer",
    "analyze_test_file",
    "discover_test_files",
    "ParsedTestFile",
    # Models
    "AssertionTemplate",
    "EndpointPattern",
    "ExtractedFixture",
    "FaultInjectionPattern",
    "FixtureRole",
    "LearnedPatterns",
    "ObservabilityPattern",
    "RiskRule",
    "Signal",
    "TimingAssertion",
    # Extractor
    "PatternExtractor",
    # Storage
    "save_patterns",
    "load_patterns",
    "merge_patterns",
    "get_patterns_path",
    # Pack Advisor
    "AdvisorResult",
    "PackAdvisor",
    "PackRecommendation",
    "get_pack_advisor",
]
