# src/prevent_outage_edge_testing/learner/extractor.py
"""
Pattern extractor for learned test patterns.

Analyzes parsed test files and extracts:
- Endpoints/hosts/ports
- Fixtures and their inferred roles
- Assertion patterns
- Timing/performance assertions
- Observability tool usage
- Fault injection patterns
"""

import re
from collections import defaultdict
from pathlib import Path
from typing import Optional

from prevent_outage_edge_testing.learner.analyzer import (
    ParsedTestFile,
    FunctionInfo,
    AssertInfo,
    CallInfo,
    StringLiteral,
)
from prevent_outage_edge_testing.learner.models import (
    AssertionTemplate,
    EndpointPattern,
    ExtractedFixture,
    FaultInjectionPattern,
    FixtureRole,
    LearnedPatterns,
    ObservabilityPattern,
    RiskRule,
    Signal,
    TimingAssertion,
)


class PatternExtractor:
    """
    Extracts patterns from parsed test files.
    
    Uses heuristics and keyword matching to infer roles and categorize patterns.
    All analysis is static - no code execution.
    """
    
    # Keywords for fixture role inference
    ROLE_KEYWORDS: dict[FixtureRole, list[str]] = {
        FixtureRole.EDGE_NODE: ["edge", "cdn", "proxy", "varnish", "nginx", "haproxy", "envoy"],
        FixtureRole.ORIGIN: ["origin", "backend", "upstream", "server", "source"],
        FixtureRole.CACHE: ["cache", "redis", "memcached", "caching"],
        FixtureRole.LOAD_BALANCER: ["lb", "load_balancer", "loadbalancer", "balancer", "haproxy"],
        FixtureRole.DATABASE: ["db", "database", "postgres", "mysql", "mongo", "sql"],
        FixtureRole.CLIENT: ["client", "http_client", "session", "requester", "browser"],
        FixtureRole.PURGE: ["purge", "invalidate", "invalidation", "clear", "flush"],
        FixtureRole.MOCK_SERVER: ["mock", "fake", "stub", "httpserver", "wiremock", "responses"],
        FixtureRole.CONFIG: ["config", "settings", "configuration", "options", "params"],
        FixtureRole.METRICS: ["metrics", "prometheus", "statsd", "collector", "gauge", "counter"],
        FixtureRole.TRACER: ["tracer", "tracing", "span", "jaeger", "zipkin", "opentelemetry"],
        FixtureRole.INJECTOR: ["inject", "fault", "chaos", "failure", "error_injector"],
    }
    
    # Observability tool patterns
    OBSERVABILITY_PATTERNS: dict[str, list[str]] = {
        "tcpdump": [r"tcpdump", r"packet\s*capture", r"pcap"],
        "dtrace": [r"dtrace", r"dtruss", r"\.d\s+script"],
        "ebpf": [r"ebpf", r"bpf", r"bpftrace", r"bcc"],
        "wireshark": [r"wireshark", r"tshark", r"\.pcap"],
        "prometheus": [r"prometheus", r"prom_client", r"push_gateway"],
        "grafana": [r"grafana", r"dashboard"],
        "jaeger": [r"jaeger", r"opentracing"],
        "opentelemetry": [r"opentelemetry", r"otel", r"otlp"],
        "strace": [r"strace", r"ltrace"],
        "perf": [r"perf\s+record", r"perf\s+stat", r"linux\s+perf"],
        "logs": [r"logging", r"logger", r"log_capture", r"caplog"],
    }
    
    # Fault injection patterns
    FAULT_PATTERNS: dict[str, list[str]] = {
        "timeout": [r"timeout", r"read_timeout", r"connect_timeout", r"deadline"],
        "connection_drop": [r"connection\s*reset", r"conn.*drop", r"rst", r"econnreset"],
        "connection_refuse": [r"connection\s*refused", r"econnrefused", r"conn.*refuse"],
        "dns": [r"dns.*fail", r"resolve.*fail", r"nxdomain", r"dns.*error"],
        "disk": [r"disk.*fail", r"io.*error", r"eio", r"enospc", r"readonly.*fs"],
        "latency": [r"inject.*latency", r"add.*delay", r"slow.*down", r"throttle"],
        "packet_loss": [r"packet.*loss", r"drop.*packet", r"network.*partition"],
        "cpu": [r"cpu.*stress", r"cpu.*load", r"cpu.*exhaust"],
        "memory": [r"memory.*exhaust", r"oom", r"out.*of.*memory", r"mem.*pressure"],
        "chaos": [r"chaos", r"litmus", r"chaos.*mesh", r"chaos.*monkey"],
    }
    
    # URL/endpoint patterns
    URL_PATTERNS = [
        r'https?://[^\s"\'\)]+',
        r'localhost:\d+',
        r'127\.0\.0\.1:\d+',
        r'0\.0\.0\.0:\d+',
        r'/api/v\d+/\w+',
        r'/health',
        r'/metrics',
        r'/ready',
        r'/live',
    ]
    
    # Port patterns
    PORT_PATTERNS = [
        r'port\s*[=:]\s*(\d+)',
        r':\s*(\d{2,5})\b',
        r'PORT\s*[=:]\s*(\d+)',
    ]
    
    # Timing/performance keywords
    TIMING_KEYWORDS = [
        ("p50", r'p50|percentile.*50|50th'),
        ("p95", r'p95|percentile.*95|95th'),
        ("p99", r'p99|percentile.*99|99th'),
        ("latency", r'latency|response.*time'),
        ("duration", r'duration|elapsed'),
        ("timeout", r'timeout'),
        ("throughput", r'throughput|rps|qps|requests.*per.*second'),
    ]
    
    def __init__(self) -> None:
        self.signals: dict[str, Signal] = {}
        self.fixtures: dict[str, ExtractedFixture] = {}
        self.assertion_templates: dict[str, AssertionTemplate] = {}
        self.timing_assertions: list[TimingAssertion] = []
        self.observability_patterns: list[ObservabilityPattern] = []
        self.fault_patterns: list[FaultInjectionPattern] = {}
        self.endpoints: dict[str, EndpointPattern] = {}
        self.risk_rules: list[RiskRule] = []
        
        self._files_analyzed: list[str] = []
        self._total_test_functions = 0
        self._total_test_classes = 0
    
    def extract_from_files(self, parsed_files: list[ParsedTestFile]) -> LearnedPatterns:
        """
        Extract patterns from multiple parsed test files.
        
        Args:
            parsed_files: List of parsed test file results
            
        Returns:
            LearnedPatterns with all extracted patterns
        """
        for parsed in parsed_files:
            self._files_analyzed.append(str(parsed.path))
            self._extract_from_file(parsed)
        
        # Derive risk rules from collected patterns
        self._derive_risk_rules()
        
        return LearnedPatterns(
            source_paths=self._files_analyzed,
            total_files_analyzed=len(self._files_analyzed),
            total_test_functions=self._total_test_functions,
            total_test_classes=self._total_test_classes,
            signals=list(self.signals.values()),
            fixtures=list(self.fixtures.values()),
            assertion_templates=list(self.assertion_templates.values()),
            timing_assertions=self.timing_assertions,
            observability_patterns=self.observability_patterns,
            fault_injection_patterns=list(self.fault_patterns.values()) if isinstance(self.fault_patterns, dict) else self.fault_patterns,
            endpoints=list(self.endpoints.values()),
            risk_rules=self.risk_rules,
        )
    
    def _extract_from_file(self, parsed: ParsedTestFile) -> None:
        """Extract patterns from a single parsed file."""
        file_str = str(parsed.path)
        
        # Count tests
        self._total_test_functions += len(parsed.test_functions)
        self._total_test_classes += len(parsed.test_classes)
        
        # Extract fixtures
        for func in parsed.fixture_functions:
            self._extract_fixture(func, file_str)
        
        # Also look for fixtures in conftest
        if parsed.path.name == "conftest.py":
            for func in parsed.functions:
                if func.is_fixture:
                    self._extract_fixture(func, file_str)
        
        # Extract from assertions
        for assert_info in parsed.asserts:
            self._extract_assertion_pattern(assert_info, file_str)
        
        # Extract from string literals
        for literal in parsed.string_literals:
            self._extract_from_string(literal, file_str)
        
        # Extract from calls
        for call in parsed.calls:
            self._extract_from_call(call, file_str)
        
        # Extract signals from fixture usage
        for fixture_name in parsed.fixtures_used:
            self._add_signal(fixture_name, "fixture_reference", file_str)
        
        # Scan full source for observability and fault patterns
        try:
            source = parsed.path.read_text(encoding="utf-8")
            self._scan_for_observability(source, file_str)
            self._scan_for_faults(source, file_str)
            self._scan_for_endpoints(source, file_str)
        except Exception:
            pass
    
    def _extract_fixture(self, func: FunctionInfo, source_file: str) -> None:
        """Extract and analyze a fixture."""
        name = func.name
        
        # Infer role from name and docstring
        role, confidence, indicators = self._infer_fixture_role(
            name, 
            func.docstring or "", 
            func.body_source,
        )
        
        if name in self.fixtures:
            # Update existing
            self.fixtures[name].usages += 1
            if confidence > self.fixtures[name].confidence:
                self.fixtures[name].inferred_role = role
                self.fixtures[name].confidence = confidence
                self.fixtures[name].role_indicators = indicators
        else:
            self.fixtures[name] = ExtractedFixture(
                name=name,
                inferred_role=role,
                confidence=confidence,
                scope=func.fixture_scope,
                usages=1,
                source_file=source_file,
                parameters=func.args,
                docstring=func.docstring or "",
                role_indicators=indicators,
            )
    
    def _infer_fixture_role(
        self, 
        name: str, 
        docstring: str, 
        body: str,
    ) -> tuple[FixtureRole, float, list[str]]:
        """
        Infer the role of a fixture based on its name, docstring, and body.
        
        Returns:
            Tuple of (role, confidence, indicators)
        """
        name_lower = name.lower()
        doc_lower = docstring.lower()
        body_lower = body.lower()
        
        combined = f"{name_lower} {doc_lower} {body_lower}"
        
        best_role = FixtureRole.UNKNOWN
        best_score = 0.0
        best_indicators: list[str] = []
        
        for role, keywords in self.ROLE_KEYWORDS.items():
            score = 0.0
            indicators = []
            
            for kw in keywords:
                # Name match is strongest
                if kw in name_lower:
                    score += 0.5
                    indicators.append(f"name contains '{kw}'")
                # Docstring match
                if kw in doc_lower:
                    score += 0.3
                    indicators.append(f"docstring contains '{kw}'")
                # Body match
                if kw in body_lower:
                    score += 0.2
                    indicators.append(f"body contains '{kw}'")
            
            if score > best_score:
                best_score = score
                best_role = role
                best_indicators = indicators
        
        # Cap confidence at 1.0
        confidence = min(best_score, 1.0)
        
        # If no good match, check for common patterns
        if confidence < 0.3:
            if "request" in name_lower or "http" in name_lower:
                return FixtureRole.CLIENT, 0.4, ["name suggests HTTP client"]
            if "setup" in name_lower or "teardown" in name_lower:
                return FixtureRole.CONFIG, 0.3, ["name suggests setup/config"]
        
        return best_role, confidence, best_indicators
    
    def _extract_assertion_pattern(self, assert_info: AssertInfo, source_file: str) -> None:
        """Extract and categorize an assertion pattern."""
        source = assert_info.source
        
        # Determine pattern type
        if assert_info.is_status_code:
            self._add_assertion_template("status_code", source, source_file)
        if assert_info.is_header_check:
            self._add_assertion_template("header", source, source_file)
        if assert_info.is_cache_check:
            self._add_assertion_template("cache", source, source_file)
        if assert_info.is_timing_check:
            self._add_assertion_template("timing", source, source_file)
            self._extract_timing_assertion(source, source_file)
        
        # Extract retry patterns
        if re.search(r'retry|retries|attempt', source, re.I):
            self._add_assertion_template("retry", source, source_file)
        
        # General assertion if no specific type
        if not any([assert_info.is_status_code, assert_info.is_header_check, 
                    assert_info.is_cache_check, assert_info.is_timing_check]):
            self._add_assertion_template("general", source, source_file)
    
    def _add_assertion_template(self, pattern_type: str, source: str, source_file: str) -> None:
        """Add or update an assertion template."""
        # Normalize the assertion to a template
        template = self._normalize_assertion(source)
        
        key = f"{pattern_type}:{template}"
        
        if key in self.assertion_templates:
            self.assertion_templates[key].occurrences += 1
            if source not in self.assertion_templates[key].examples:
                self.assertion_templates[key].examples.append(source)
        else:
            # Extract expected values
            expected = self._extract_expected_values(source, pattern_type)
            
            self.assertion_templates[key] = AssertionTemplate(
                pattern_type=pattern_type,
                template=template,
                examples=[source],
                occurrences=1,
                expected_values=expected,
            )
    
    def _normalize_assertion(self, source: str) -> str:
        """Normalize an assertion to a template pattern."""
        # Replace specific values with placeholders
        template = source
        
        # Replace numbers
        template = re.sub(r'\b\d+\b', '{number}', template)
        
        # Replace string literals
        template = re.sub(r'"[^"]*"', '"{string}"', template)
        template = re.sub(r"'[^']*'", "'{string}'", template)
        
        # Replace variable names (keep common ones)
        # This is a simplified normalization
        
        return template.strip()
    
    def _extract_expected_values(self, source: str, pattern_type: str) -> list[str]:
        """Extract expected values from assertion source."""
        values = []
        
        if pattern_type == "status_code":
            # Extract status codes
            codes = re.findall(r'\b(1\d{2}|2\d{2}|3\d{2}|4\d{2}|5\d{2})\b', source)
            values.extend(codes)
        
        elif pattern_type == "header":
            # Extract header names
            headers = re.findall(r'["\']([A-Za-z-]+)["\']', source)
            values.extend(h for h in headers if len(h) > 2)
        
        elif pattern_type == "cache":
            # Extract cache states
            states = re.findall(r'\b(hit|miss|stale|expired|fresh)\b', source, re.I)
            values.extend(s.lower() for s in states)
        
        return list(set(values))
    
    def _extract_timing_assertion(self, source: str, source_file: str) -> None:
        """Extract timing/performance assertion details."""
        source_lower = source.lower()
        
        for metric_type, pattern in self.TIMING_KEYWORDS:
            if re.search(pattern, source_lower):
                # Try to extract threshold
                threshold_match = re.search(r'[<>=]+\s*(\d+(?:\.\d+)?)\s*(ms|s|seconds?|milliseconds?)?', source)
                threshold = None
                unit = "ms"
                comparison = "<"
                
                if threshold_match:
                    threshold = float(threshold_match.group(1))
                    if threshold_match.group(2):
                        unit = threshold_match.group(2)
                        if unit.startswith("s"):
                            unit = "s"
                        else:
                            unit = "ms"
                
                # Determine comparison
                if ">=" in source or ">" in source:
                    comparison = ">"
                elif "<=" in source or "<" in source:
                    comparison = "<"
                
                self.timing_assertions.append(TimingAssertion(
                    metric_type=metric_type,
                    comparison=comparison,
                    threshold_value=threshold,
                    threshold_unit=unit,
                    context=source[:100],
                    examples=[source],
                ))
                break
    
    def _extract_from_string(self, literal: StringLiteral, source_file: str) -> None:
        """Extract patterns from string literals."""
        value = literal.value
        
        # Check for URLs
        for pattern in self.URL_PATTERNS:
            if re.search(pattern, value, re.I):
                self._add_endpoint("url", value, source_file)
                break
        
        # Add as signal if interesting
        if len(value) > 3 and len(value) < 200:
            # Categorize the signal
            category = "general"
            value_lower = value.lower()
            
            if re.search(r'https?://', value):
                category = "endpoint"
            elif re.search(r'error|fail|exception', value_lower):
                category = "error_message"
            elif re.search(r'cache|hit|miss', value_lower):
                category = "cache"
            elif re.search(r'header|content-type', value_lower):
                category = "header"
            
            self._add_signal(value, category, source_file, literal.context)
    
    def _extract_from_call(self, call: CallInfo, source_file: str) -> None:
        """Extract patterns from function calls."""
        func_lower = call.func_name.lower()
        
        # HTTP method calls
        if any(m in func_lower for m in [".get", ".post", ".put", ".delete", ".patch", ".head"]):
            if call.args:
                self._add_endpoint("url", call.args[0], source_file)
        
        # requests library
        if "requests." in func_lower:
            self._add_signal("requests", "library", source_file)
        
        # httpx library
        if "httpx." in func_lower or "client." in func_lower:
            self._add_signal("httpx", "library", source_file)
        
        # aiohttp
        if "aiohttp" in func_lower:
            self._add_signal("aiohttp", "library", source_file)
        
        # Check for observability calls
        for tool, patterns in self.OBSERVABILITY_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, call.func_name, re.I):
                    self.observability_patterns.append(ObservabilityPattern(
                        tool_type=tool,
                        pattern=call.source,
                        source_file=source_file,
                        line_number=call.lineno,
                    ))
                    break
    
    def _scan_for_observability(self, source: str, source_file: str) -> None:
        """Scan source for observability tool usage."""
        for tool, patterns in self.OBSERVABILITY_PATTERNS.items():
            for pattern in patterns:
                matches = list(re.finditer(pattern, source, re.I | re.M))
                for match in matches:
                    # Get line number
                    line_no = source[:match.start()].count('\n') + 1
                    
                    # Get context (surrounding lines)
                    lines = source.split('\n')
                    start = max(0, line_no - 2)
                    end = min(len(lines), line_no + 2)
                    context = '\n'.join(lines[start:end])
                    
                    self.observability_patterns.append(ObservabilityPattern(
                        tool_type=tool,
                        pattern=match.group(),
                        source_file=source_file,
                        line_number=line_no,
                        context=context[:200],
                    ))
    
    def _scan_for_faults(self, source: str, source_file: str) -> None:
        """Scan source for fault injection patterns."""
        for fault_type, patterns in self.FAULT_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, source, re.I):
                    key = fault_type
                    
                    if key in self.fault_patterns:
                        self.fault_patterns[key].occurrences += 1
                        if source_file not in self.fault_patterns[key].source_files:
                            self.fault_patterns[key].source_files.append(source_file)
                    else:
                        self.fault_patterns[key] = FaultInjectionPattern(
                            fault_type=fault_type,
                            method="detected_in_source",
                            examples=[pattern],
                            source_files=[source_file],
                            occurrences=1,
                        )
                    break
    
    def _scan_for_endpoints(self, source: str, source_file: str) -> None:
        """Scan source for endpoint patterns."""
        for pattern in self.URL_PATTERNS:
            for match in re.finditer(pattern, source):
                self._add_endpoint("url", match.group(), source_file)
        
        # Extract ports
        for pattern in self.PORT_PATTERNS:
            for match in re.finditer(pattern, source):
                port = match.group(1) if match.lastindex else match.group()
                self._add_endpoint("port", port, source_file)
    
    def _add_endpoint(self, pattern_type: str, value: str, source_file: str) -> None:
        """Add or update an endpoint pattern."""
        # Clean the value
        value = value.strip().strip("'\"")
        if not value or len(value) < 2:
            return
        
        # Check if parameterized
        is_param = "{" in value or "$" in value or "%" in value
        
        key = f"{pattern_type}:{value}"
        
        if key in self.endpoints:
            self.endpoints[key].occurrences += 1
            if source_file not in self.endpoints[key].source_files:
                self.endpoints[key].source_files.append(source_file)
        else:
            self.endpoints[key] = EndpointPattern(
                pattern_type=pattern_type,
                value=value,
                occurrences=1,
                source_files=[source_file],
                is_parameterized=is_param,
            )
    
    def _add_signal(
        self, 
        value: str, 
        category: str, 
        source_file: str, 
        context: str = "",
    ) -> None:
        """Add or update a signal."""
        key = f"{category}:{value}"
        
        if key in self.signals:
            self.signals[key].occurrences += 1
            if source_file not in self.signals[key].source_files:
                self.signals[key].source_files.append(source_file)
        else:
            self.signals[key] = Signal(
                value=value,
                category=category,
                occurrences=1,
                source_files=[source_file],
                context=context[:100],
            )
    
    def _derive_risk_rules(self) -> None:
        """Derive risk rules from collected patterns."""
        # Rule: Cache-related tests suggest cache correctness pack
        cache_signals = sum(1 for s in self.signals.values() if s.category == "cache")
        cache_assertions = sum(1 for a in self.assertion_templates.values() if a.pattern_type == "cache")
        
        if cache_signals > 0 or cache_assertions > 0:
            confidence = min(0.3 + (cache_signals * 0.1) + (cache_assertions * 0.15), 0.95)
            self.risk_rules.append(RiskRule(
                rule_id="cache-testing-detected",
                description="Tests contain cache-related assertions and patterns",
                condition="cache assertions or cache signals present",
                recommended_packs=["edge-http-cache-correctness"],
                confidence=confidence,
                derived_from=[f"{cache_signals} cache signals", f"{cache_assertions} cache assertions"],
            ))
        
        # Rule: Timing assertions suggest latency pack
        if self.timing_assertions:
            confidence = min(0.4 + (len(self.timing_assertions) * 0.1), 0.9)
            self.risk_rules.append(RiskRule(
                rule_id="latency-testing-detected",
                description="Tests contain timing/latency assertions",
                condition="timing assertions present",
                recommended_packs=["edge-latency-regression-observability"],
                confidence=confidence,
                derived_from=[f"{len(self.timing_assertions)} timing assertions"],
            ))
        
        # Rule: Fault injection patterns suggest fault-injection-io pack
        if self.fault_patterns:
            fault_count = sum(f.occurrences for f in self.fault_patterns.values()) if isinstance(self.fault_patterns, dict) else len(self.fault_patterns)
            confidence = min(0.5 + (fault_count * 0.05), 0.95)
            fault_types = list(self.fault_patterns.keys()) if isinstance(self.fault_patterns, dict) else []
            self.risk_rules.append(RiskRule(
                rule_id="fault-injection-detected",
                description="Tests contain fault injection patterns",
                condition="fault injection patterns present",
                recommended_packs=["fault-injection-io"],
                confidence=confidence,
                derived_from=[f"fault types: {', '.join(fault_types[:5])}"],
            ))
        
        # Rule: HTTP status code assertions suggest HTTP testing
        status_assertions = sum(
            1 for a in self.assertion_templates.values() 
            if a.pattern_type == "status_code"
        )
        if status_assertions > 3:
            self.risk_rules.append(RiskRule(
                rule_id="http-api-testing-detected",
                description="Tests contain HTTP status code assertions",
                condition="multiple HTTP status assertions",
                recommended_packs=["edge-http-cache-correctness"],
                confidence=min(0.3 + (status_assertions * 0.05), 0.8),
                derived_from=[f"{status_assertions} status code assertions"],
            ))
        
        # Rule: Observability tools suggest latency/monitoring pack
        if self.observability_patterns:
            tools = set(p.tool_type for p in self.observability_patterns)
            self.risk_rules.append(RiskRule(
                rule_id="observability-tools-detected",
                description=f"Tests use observability tools: {', '.join(tools)}",
                condition="observability tool patterns present",
                recommended_packs=["edge-latency-regression-observability"],
                confidence=min(0.4 + (len(tools) * 0.1), 0.85),
                derived_from=[f"tools: {', '.join(tools)}"],
            ))
        
        # Rule: Edge/CDN fixtures suggest edge testing
        edge_fixtures = [
            f for f in self.fixtures.values() 
            if f.inferred_role in (FixtureRole.EDGE_NODE, FixtureRole.CACHE, FixtureRole.LOAD_BALANCER)
            and f.confidence > 0.5
        ]
        if edge_fixtures:
            self.risk_rules.append(RiskRule(
                rule_id="edge-infrastructure-detected",
                description="Tests use edge/CDN infrastructure fixtures",
                condition="edge-related fixtures present",
                recommended_packs=["edge-http-cache-correctness", "edge-latency-regression-observability"],
                confidence=min(0.5 + (len(edge_fixtures) * 0.1), 0.9),
                derived_from=[f.name for f in edge_fixtures[:5]],
            ))
