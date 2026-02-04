# tests/test_learner.py
"""
Tests for the learner module.

Tests cover:
- AST-based test file analysis
- Pattern extraction (fixtures, assertions, timing, etc.)
- Fixture role inference
- Risk rule derivation
- Pattern storage and merging
"""

import tempfile
from pathlib import Path

import pytest

from prevent_outage_edge_testing.learner.analyzer import (
    TestAnalyzer,
    analyze_test_file,
    discover_test_files,
    ParsedTestFile,
)
from prevent_outage_edge_testing.learner.extractor import PatternExtractor
from prevent_outage_edge_testing.learner.models import (
    LearnedPatterns,
    ExtractedFixture,
    FixtureRole,
    AssertionTemplate,
    TimingAssertion,
    Signal,
    RiskRule,
)
from prevent_outage_edge_testing.learner.storage import (
    save_patterns,
    load_patterns,
    merge_patterns,
    get_patterns_path,
)
from prevent_outage_edge_testing.learner.pack_advisor import PackAdvisor


# Sample test file content for testing
SAMPLE_TEST_CONTENT = '''
"""Sample test module for edge cache testing."""

import pytest
import requests
from unittest.mock import Mock


@pytest.fixture(scope="module")
def edge_server():
    """Fixture providing edge server connection."""
    return {"host": "edge.example.com", "port": 8080}


@pytest.fixture
def cache_client(edge_server):
    """HTTP client for cache testing."""
    return requests.Session()


@pytest.fixture
def origin_mock():
    """Mock origin server."""
    return Mock()


class TestCacheCorrectness:
    """Tests for HTTP cache correctness."""
    
    def test_cache_hit_returns_200(self, cache_client, edge_server):
        """Verify cache hit returns 200."""
        url = f"http://{edge_server['host']}:{edge_server['port']}/resource"
        response = cache_client.get(url)
        assert response.status_code == 200
        assert "hit" in response.headers.get("X-Cache", "").lower()
    
    def test_vary_header_respected(self, cache_client, edge_server):
        """Test Vary header is respected."""
        url = f"http://{edge_server['host']}/api/data"
        
        r1 = cache_client.get(url, headers={"Accept-Encoding": "gzip"})
        r2 = cache_client.get(url, headers={"Accept-Encoding": "identity"})
        
        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r1.headers.get("Content-Encoding") != r2.headers.get("Content-Encoding")
    
    def test_conditional_304(self, cache_client, edge_server):
        """Test conditional request returns 304."""
        url = f"http://{edge_server['host']}/resource"
        r1 = cache_client.get(url)
        etag = r1.headers.get("ETag")
        
        r2 = cache_client.get(url, headers={"If-None-Match": etag})
        assert r2.status_code == 304


class TestLatencyRegression:
    """Tests for latency regression detection."""
    
    def test_p99_latency_under_threshold(self, cache_client, edge_server):
        """Verify P99 latency is under 100ms."""
        import time
        latencies = []
        
        for _ in range(100):
            start = time.time()
            cache_client.get(f"http://{edge_server['host']}/health")
            latencies.append((time.time() - start) * 1000)
        
        latencies.sort()
        p99 = latencies[98]
        assert p99 < 100, f"P99 latency {p99}ms exceeds 100ms threshold"
    
    def test_response_time_acceptable(self, cache_client):
        """Test response time is acceptable."""
        response = cache_client.get("http://localhost:8080/api")
        assert response.elapsed.total_seconds() < 0.5


def test_timeout_handling():
    """Test timeout is properly handled."""
    with pytest.raises(requests.Timeout):
        requests.get("http://slow.example.com", timeout=0.001)


def test_connection_reset_recovery():
    """Test recovery from connection reset."""
    # Simulate connection reset scenario
    retries = 3
    for attempt in range(retries):
        try:
            requests.get("http://unstable.example.com")
            break
        except requests.ConnectionError:
            if attempt == retries - 1:
                raise
'''


SAMPLE_CONFTEST = '''
"""Conftest with shared fixtures."""

import pytest


@pytest.fixture(scope="session")
def load_balancer():
    """Load balancer fixture for tests."""
    return {"vip": "10.0.0.1", "port": 80}


@pytest.fixture
def metrics_collector():
    """Prometheus metrics collector."""
    from prometheus_client import CollectorRegistry
    return CollectorRegistry()


@pytest.fixture
def fault_injector():
    """Fault injection helper."""
    class FaultInjector:
        def inject_latency(self, ms):
            pass
        def inject_timeout(self):
            pass
    return FaultInjector()
'''


class TestAnalyzer:
    """Tests for the AST-based test analyzer."""
    
    def test_parse_test_file(self, tmp_path):
        """Test parsing a test file."""
        test_file = tmp_path / "test_sample.py"
        test_file.write_text(SAMPLE_TEST_CONTENT)
        
        result = analyze_test_file(test_file)
        
        assert result is not None
        assert result.path == test_file
        assert len(result.test_functions) > 0
        assert len(result.fixture_functions) > 0
        assert len(result.test_classes) > 0
    
    def test_extract_fixtures(self, tmp_path):
        """Test fixture extraction."""
        test_file = tmp_path / "test_sample.py"
        test_file.write_text(SAMPLE_TEST_CONTENT)
        
        result = analyze_test_file(test_file)
        
        fixtures = result.fixture_functions
        fixture_names = [f.name for f in fixtures]
        
        assert "edge_server" in fixture_names
        assert "cache_client" in fixture_names
        assert "origin_mock" in fixture_names
    
    def test_extract_fixture_scope(self, tmp_path):
        """Test fixture scope detection."""
        test_file = tmp_path / "test_sample.py"
        test_file.write_text(SAMPLE_TEST_CONTENT)
        
        result = analyze_test_file(test_file)
        
        for fixture in result.fixture_functions:
            if fixture.name == "edge_server":
                assert fixture.fixture_scope == "module"
    
    def test_extract_test_classes(self, tmp_path):
        """Test class extraction."""
        test_file = tmp_path / "test_sample.py"
        test_file.write_text(SAMPLE_TEST_CONTENT)
        
        result = analyze_test_file(test_file)
        
        class_names = [c.name for c in result.test_classes]
        assert "TestCacheCorrectness" in class_names
        assert "TestLatencyRegression" in class_names
    
    def test_extract_assertions(self, tmp_path):
        """Test assertion extraction."""
        test_file = tmp_path / "test_sample.py"
        test_file.write_text(SAMPLE_TEST_CONTENT)
        
        result = analyze_test_file(test_file)
        
        assert len(result.asserts) > 0
        
        # Check for status code assertions
        status_asserts = [a for a in result.asserts if a.is_status_code]
        assert len(status_asserts) > 0
        
        # Check for cache assertions
        cache_asserts = [a for a in result.asserts if a.is_cache_check]
        assert len(cache_asserts) > 0
    
    def test_discover_test_files(self, tmp_path):
        """Test file discovery."""
        # Create test directory structure
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        
        (tests_dir / "test_one.py").write_text("def test_a(): pass")
        (tests_dir / "test_two.py").write_text("def test_b(): pass")
        (tests_dir / "conftest.py").write_text("import pytest")
        (tests_dir / "helper.py").write_text("# not a test")
        
        files = discover_test_files(tests_dir)
        
        assert len(files) == 3  # test_one.py, test_two.py, conftest.py
        file_names = [f.name for f in files]
        assert "test_one.py" in file_names
        assert "test_two.py" in file_names
        assert "conftest.py" in file_names
        assert "helper.py" not in file_names
    
    def test_handle_syntax_error(self, tmp_path):
        """Test handling of files with syntax errors."""
        bad_file = tmp_path / "test_bad.py"
        bad_file.write_text("def broken(:\n    pass")
        
        result = analyze_test_file(bad_file)
        
        # Should return empty result, not crash
        assert result is not None
        assert len(result.functions) == 0


class TestPatternExtractor:
    """Tests for the pattern extractor."""
    
    def test_extract_fixtures_with_roles(self, tmp_path):
        """Test fixture extraction with role inference."""
        test_file = tmp_path / "test_sample.py"
        test_file.write_text(SAMPLE_TEST_CONTENT)
        
        parsed = analyze_test_file(test_file)
        extractor = PatternExtractor()
        patterns = extractor.extract_from_files([parsed])
        
        fixtures = patterns.fixtures
        fixture_map = {f.name: f for f in fixtures}
        
        # Check edge_server fixture role
        assert "edge_server" in fixture_map
        edge_fixture = fixture_map["edge_server"]
        assert edge_fixture.inferred_role == FixtureRole.EDGE_NODE
        assert edge_fixture.confidence > 0.3
        
        # Check origin_mock fixture role
        assert "origin_mock" in fixture_map
        origin_fixture = fixture_map["origin_mock"]
        assert origin_fixture.inferred_role in (FixtureRole.ORIGIN, FixtureRole.MOCK_SERVER)
    
    def test_extract_assertion_templates(self, tmp_path):
        """Test assertion template extraction."""
        test_file = tmp_path / "test_sample.py"
        test_file.write_text(SAMPLE_TEST_CONTENT)
        
        parsed = analyze_test_file(test_file)
        extractor = PatternExtractor()
        patterns = extractor.extract_from_files([parsed])
        
        templates = patterns.assertion_templates
        template_types = {t.pattern_type for t in templates}
        
        assert "status_code" in template_types
        assert "cache" in template_types
    
    def test_extract_timing_assertions(self, tmp_path):
        """Test timing assertion extraction."""
        test_file = tmp_path / "test_sample.py"
        test_file.write_text(SAMPLE_TEST_CONTENT)
        
        parsed = analyze_test_file(test_file)
        extractor = PatternExtractor()
        patterns = extractor.extract_from_files([parsed])
        
        timing = patterns.timing_assertions
        
        # Should find p99 and latency assertions
        metric_types = {t.metric_type for t in timing}
        assert len(metric_types) > 0
    
    def test_extract_endpoints(self, tmp_path):
        """Test endpoint extraction."""
        test_file = tmp_path / "test_sample.py"
        test_file.write_text(SAMPLE_TEST_CONTENT)
        
        parsed = analyze_test_file(test_file)
        extractor = PatternExtractor()
        patterns = extractor.extract_from_files([parsed])
        
        endpoints = patterns.endpoints
        
        # Should find URLs
        url_endpoints = [e for e in endpoints if e.pattern_type == "url"]
        assert len(url_endpoints) > 0
    
    def test_extract_fault_patterns(self, tmp_path):
        """Test fault injection pattern extraction."""
        test_file = tmp_path / "test_sample.py"
        test_file.write_text(SAMPLE_TEST_CONTENT)
        
        parsed = analyze_test_file(test_file)
        extractor = PatternExtractor()
        patterns = extractor.extract_from_files([parsed])
        
        faults = patterns.fault_injection_patterns
        fault_types = {f.fault_type for f in faults}
        
        # Should find timeout pattern
        assert "timeout" in fault_types
    
    def test_derive_risk_rules(self, tmp_path):
        """Test risk rule derivation."""
        test_file = tmp_path / "test_sample.py"
        test_file.write_text(SAMPLE_TEST_CONTENT)
        
        parsed = analyze_test_file(test_file)
        extractor = PatternExtractor()
        patterns = extractor.extract_from_files([parsed])
        
        rules = patterns.risk_rules
        
        assert len(rules) > 0
        
        # Should recommend cache-correctness pack
        recommended = set()
        for rule in rules:
            recommended.update(rule.recommended_packs)
        
        assert "edge-http-cache-correctness" in recommended
    
    def test_fixture_from_conftest(self, tmp_path):
        """Test fixture extraction from conftest.py."""
        conftest = tmp_path / "conftest.py"
        conftest.write_text(SAMPLE_CONFTEST)
        
        parsed = analyze_test_file(conftest)
        extractor = PatternExtractor()
        patterns = extractor.extract_from_files([parsed])
        
        fixtures = patterns.fixtures
        fixture_map = {f.name: f for f in fixtures}
        
        assert "load_balancer" in fixture_map
        assert "metrics_collector" in fixture_map
        assert "fault_injector" in fixture_map
        
        # Check role inference
        lb_fixture = fixture_map["load_balancer"]
        assert lb_fixture.inferred_role == FixtureRole.LOAD_BALANCER
        
        injector_fixture = fixture_map["fault_injector"]
        assert injector_fixture.inferred_role == FixtureRole.INJECTOR


class TestStorage:
    """Tests for pattern storage."""
    
    def test_save_and_load_patterns(self, tmp_path):
        """Test saving and loading patterns."""
        patterns = LearnedPatterns(
            total_files_analyzed=5,
            total_test_functions=10,
            signals=[Signal(value="cache", category="keyword", occurrences=3)],
            fixtures=[ExtractedFixture(
                name="test_fixture",
                inferred_role=FixtureRole.CLIENT,
                confidence=0.8,
            )],
        )
        
        # Save
        saved_path = save_patterns(patterns, tmp_path)
        assert saved_path.exists()
        
        # Load
        loaded = load_patterns(tmp_path)
        
        assert loaded is not None
        assert loaded.total_files_analyzed == 5
        assert loaded.total_test_functions == 10
        assert len(loaded.signals) == 1
        assert len(loaded.fixtures) == 1
    
    def test_merge_patterns(self):
        """Test merging patterns."""
        existing = LearnedPatterns(
            total_files_analyzed=5,
            total_test_functions=10,
            signals=[Signal(value="cache", category="keyword", occurrences=3, source_files=["a.py"])],
            fixtures=[ExtractedFixture(
                name="fixture_a",
                inferred_role=FixtureRole.CLIENT,
                confidence=0.6,
                usages=2,
            )],
        )
        
        new = LearnedPatterns(
            total_files_analyzed=3,
            total_test_functions=5,
            signals=[
                Signal(value="cache", category="keyword", occurrences=2, source_files=["b.py"]),
                Signal(value="latency", category="keyword", occurrences=1, source_files=["b.py"]),
            ],
            fixtures=[ExtractedFixture(
                name="fixture_a",
                inferred_role=FixtureRole.CLIENT,
                confidence=0.8,  # Higher confidence
                usages=1,
            )],
        )
        
        merged = merge_patterns(existing, new)
        
        # Check merged stats
        assert merged.total_test_functions == 15
        
        # Check signals merged
        signal_map = {s.value: s for s in merged.signals}
        assert signal_map["cache"].occurrences == 5
        assert "latency" in signal_map
        
        # Check fixtures merged with higher confidence
        fixture_map = {f.name: f for f in merged.fixtures}
        assert fixture_map["fixture_a"].confidence == 0.8
        assert fixture_map["fixture_a"].usages == 3
    
    def test_get_patterns_path(self, tmp_path):
        """Test patterns path calculation."""
        path = get_patterns_path(tmp_path)
        
        assert path.parent.name == ".poet"
        assert path.name == "learned_patterns.json"
    
    def test_load_nonexistent_returns_none(self, tmp_path):
        """Test loading from nonexistent path returns None."""
        result = load_patterns(tmp_path)
        assert result is None


class TestPackAdvisor:
    """Tests for the pack advisor."""
    
    def test_advisor_with_patterns(self):
        """Test advisor recommendations with patterns."""
        patterns = LearnedPatterns(
            risk_rules=[
                RiskRule(
                    rule_id="cache-test",
                    description="Cache testing detected",
                    condition="cache assertions",
                    recommended_packs=["edge-http-cache-correctness"],
                    confidence=0.8,
                ),
                RiskRule(
                    rule_id="latency-test",
                    description="Latency testing detected",
                    condition="timing assertions",
                    recommended_packs=["edge-latency-regression-observability"],
                    confidence=0.6,
                ),
            ]
        )
        
        advisor = PackAdvisor(patterns)
        result = advisor.get_recommendations()
        
        assert result.patterns_consulted
        assert result.total_rules_matched == 2
        assert len(result.recommendations) >= 2
        
        pack_ids = result.get_pack_ids(min_confidence=0.5)
        assert "edge-http-cache-correctness" in pack_ids
        assert "edge-latency-regression-observability" in pack_ids
    
    def test_advisor_without_patterns(self):
        """Test advisor without patterns."""
        advisor = PackAdvisor(None)
        result = advisor.get_recommendations()
        
        assert not result.patterns_consulted
        assert len(result.recommendations) == 0
    
    def test_advisor_from_file_nonexistent(self, tmp_path):
        """Test advisor from nonexistent file."""
        advisor = PackAdvisor.from_file(tmp_path)
        
        assert not advisor.has_patterns
        result = advisor.get_recommendations()
        assert not result.patterns_consulted
    
    def test_top_recommendations(self):
        """Test getting top recommendations."""
        patterns = LearnedPatterns(
            risk_rules=[
                RiskRule(
                    rule_id="rule-1",
                    description="Rule 1",
                    condition="cond",
                    recommended_packs=["pack-a"],
                    confidence=0.9,
                ),
                RiskRule(
                    rule_id="rule-2",
                    description="Rule 2",
                    condition="cond",
                    recommended_packs=["pack-b"],
                    confidence=0.5,
                ),
                RiskRule(
                    rule_id="rule-3",
                    description="Rule 3",
                    condition="cond",
                    recommended_packs=["pack-c"],
                    confidence=0.3,
                ),
            ]
        )
        
        advisor = PackAdvisor(patterns)
        result = advisor.get_recommendations(min_confidence=0.2)
        
        top = result.get_top_recommendations(2)
        
        assert len(top) == 2
        assert top[0].pack_id == "pack-a"
        assert top[1].pack_id == "pack-b"


class TestLearnedPatternsModel:
    """Tests for the LearnedPatterns model."""
    
    def test_get_high_confidence_fixtures(self):
        """Test filtering high confidence fixtures."""
        patterns = LearnedPatterns(
            fixtures=[
                ExtractedFixture(name="a", inferred_role=FixtureRole.CLIENT, confidence=0.9),
                ExtractedFixture(name="b", inferred_role=FixtureRole.CACHE, confidence=0.5),
                ExtractedFixture(name="c", inferred_role=FixtureRole.UNKNOWN, confidence=0.2),
            ]
        )
        
        high_conf = patterns.get_high_confidence_fixtures(0.7)
        
        assert len(high_conf) == 1
        assert high_conf[0].name == "a"
    
    def test_get_signals_by_category(self):
        """Test filtering signals by category."""
        patterns = LearnedPatterns(
            signals=[
                Signal(value="cache", category="keyword"),
                Signal(value="http://example.com", category="endpoint"),
                Signal(value="latency", category="keyword"),
            ]
        )
        
        keywords = patterns.get_signals_by_category("keyword")
        
        assert len(keywords) == 2
        assert all(s.category == "keyword" for s in keywords)
    
    def test_get_applicable_risk_rules(self):
        """Test filtering risk rules by confidence."""
        patterns = LearnedPatterns(
            risk_rules=[
                RiskRule(rule_id="a", description="A", condition="c", confidence=0.8),
                RiskRule(rule_id="b", description="B", condition="c", confidence=0.4),
                RiskRule(rule_id="c", description="C", condition="c", confidence=0.6),
            ]
        )
        
        applicable = patterns.get_applicable_risk_rules(0.5)
        
        assert len(applicable) == 2
        assert all(r.confidence >= 0.5 for r in applicable)


class TestIntegration:
    """Integration tests for the full learning pipeline."""
    
    def test_full_learning_pipeline(self, tmp_path):
        """Test the full learning pipeline."""
        # Create test directory
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        
        # Create test files
        (tests_dir / "test_cache.py").write_text(SAMPLE_TEST_CONTENT)
        (tests_dir / "conftest.py").write_text(SAMPLE_CONFTEST)
        
        # Discover and parse
        test_files = discover_test_files(tests_dir)
        assert len(test_files) == 2
        
        parsed = [analyze_test_file(f) for f in test_files]
        parsed = [p for p in parsed if p is not None]
        
        # Extract patterns
        extractor = PatternExtractor()
        patterns = extractor.extract_from_files(parsed)
        
        # Verify extraction results
        assert patterns.total_files_analyzed == 2
        assert patterns.total_test_functions > 0
        assert len(patterns.fixtures) > 0
        assert len(patterns.assertion_templates) > 0
        assert len(patterns.risk_rules) > 0
        
        # Save and reload
        save_patterns(patterns, tmp_path)
        loaded = load_patterns(tmp_path)
        
        assert loaded is not None
        assert loaded.total_files_analyzed == patterns.total_files_analyzed
        
        # Test advisor
        advisor = PackAdvisor(loaded)
        recommendations = advisor.get_recommendations()
        
        assert recommendations.patterns_consulted
        assert len(recommendations.recommendations) > 0
