# src/prevent_outage_edge_testing/learner/analyzer.py
"""
AST-based test analyzer.

Parses pytest test files and extracts structural information without executing code.
"""

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class FunctionInfo:
    """Information about a function/method."""
    
    name: str
    lineno: int
    end_lineno: int
    args: list[str]
    decorators: list[str]
    docstring: Optional[str]
    body_source: str
    is_test: bool
    is_fixture: bool
    fixture_scope: str = "function"
    class_name: Optional[str] = None


@dataclass
class ClassInfo:
    """Information about a test class."""
    
    name: str
    lineno: int
    bases: list[str]
    methods: list[FunctionInfo]
    docstring: Optional[str]


@dataclass
class ImportInfo:
    """Information about an import statement."""
    
    module: str
    names: list[str]
    is_from_import: bool
    lineno: int


@dataclass
class StringLiteral:
    """A string literal found in the code."""
    
    value: str
    lineno: int
    context: str  # 'call_arg', 'assignment', 'assert', 'decorator', etc.
    parent_call: Optional[str] = None


@dataclass
class AssertInfo:
    """Information about an assert statement."""
    
    lineno: int
    source: str
    comparison_op: Optional[str] = None
    left_side: Optional[str] = None
    right_side: Optional[str] = None
    is_status_code: bool = False
    is_header_check: bool = False
    is_cache_check: bool = False
    is_timing_check: bool = False


@dataclass
class CallInfo:
    """Information about a function call."""
    
    func_name: str
    lineno: int
    args: list[str]
    kwargs: dict[str, str]
    source: str


@dataclass
class ParsedTestFile:
    """Complete parsed information from a test file."""
    
    path: Path
    imports: list[ImportInfo] = field(default_factory=list)
    functions: list[FunctionInfo] = field(default_factory=list)
    classes: list[ClassInfo] = field(default_factory=list)
    string_literals: list[StringLiteral] = field(default_factory=list)
    asserts: list[AssertInfo] = field(default_factory=list)
    calls: list[CallInfo] = field(default_factory=list)
    fixtures_used: set[str] = field(default_factory=set)
    
    @property
    def test_functions(self) -> list[FunctionInfo]:
        """Get all test functions."""
        return [f for f in self.functions if f.is_test]
    
    @property
    def fixture_functions(self) -> list[FunctionInfo]:
        """Get all fixture functions."""
        return [f for f in self.functions if f.is_fixture]
    
    @property
    def test_classes(self) -> list[ClassInfo]:
        """Get classes that contain tests."""
        return [c for c in self.classes if c.name.startswith("Test")]


class TestAnalyzer(ast.NodeVisitor):
    """
    AST-based analyzer for pytest test files.
    
    Extracts structural information without executing any code.
    """
    
    def __init__(self, source: str, file_path: Path) -> None:
        self.source = source
        self.source_lines = source.split("\n")
        self.file_path = file_path
        
        self.imports: list[ImportInfo] = []
        self.functions: list[FunctionInfo] = []
        self.classes: list[ClassInfo] = []
        self.string_literals: list[StringLiteral] = []
        self.asserts: list[AssertInfo] = []
        self.calls: list[CallInfo] = []
        self.fixtures_used: set[str] = set()
        
        self._current_class: Optional[str] = None
        self._current_function: Optional[str] = None
        self._context_stack: list[str] = []
    
    def analyze(self) -> ParsedTestFile:
        """Parse and analyze the source code."""
        try:
            tree = ast.parse(self.source)
            self.visit(tree)
        except SyntaxError:
            pass  # Skip files with syntax errors
        
        return ParsedTestFile(
            path=self.file_path,
            imports=self.imports,
            functions=self.functions,
            classes=self.classes,
            string_literals=self.string_literals,
            asserts=self.asserts,
            calls=self.calls,
            fixtures_used=self.fixtures_used,
        )
    
    def _get_source_segment(self, node: ast.AST) -> str:
        """Get source code for a node."""
        try:
            return ast.get_source_segment(self.source, node) or ""
        except Exception:
            return ""
    
    def _get_decorator_names(self, decorators: list[ast.expr]) -> list[str]:
        """Extract decorator names from decorator list."""
        names = []
        for dec in decorators:
            if isinstance(dec, ast.Name):
                names.append(dec.id)
            elif isinstance(dec, ast.Attribute):
                names.append(f"{self._get_source_segment(dec)}")
            elif isinstance(dec, ast.Call):
                if isinstance(dec.func, ast.Name):
                    names.append(dec.func.id)
                elif isinstance(dec.func, ast.Attribute):
                    names.append(self._get_source_segment(dec.func))
        return names
    
    def _is_fixture(self, decorators: list[str]) -> tuple[bool, str]:
        """Check if function is a pytest fixture and get scope."""
        for dec in decorators:
            if "fixture" in dec.lower():
                # Try to extract scope
                scope_match = re.search(r'scope\s*=\s*["\'](\w+)["\']', dec)
                scope = scope_match.group(1) if scope_match else "function"
                return True, scope
        return False, "function"
    
    def _is_test_function(self, name: str) -> bool:
        """Check if function name indicates a test."""
        return name.startswith("test_") or name.startswith("test")
    
    def visit_Import(self, node: ast.Import) -> None:
        """Visit import statement."""
        for alias in node.names:
            self.imports.append(ImportInfo(
                module=alias.name,
                names=[alias.asname or alias.name],
                is_from_import=False,
                lineno=node.lineno,
            ))
        self.generic_visit(node)
    
    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Visit from ... import statement."""
        module = node.module or ""
        names = [alias.asname or alias.name for alias in node.names]
        self.imports.append(ImportInfo(
            module=module,
            names=names,
            is_from_import=True,
            lineno=node.lineno,
        ))
        self.generic_visit(node)
    
    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Visit class definition."""
        self._current_class = node.name
        
        bases = []
        for base in node.bases:
            if isinstance(base, ast.Name):
                bases.append(base.id)
            elif isinstance(base, ast.Attribute):
                bases.append(self._get_source_segment(base))
        
        docstring = ast.get_docstring(node)
        
        # Visit children first to collect methods
        old_functions = len(self.functions)
        self.generic_visit(node)
        
        # Collect methods defined in this class
        methods = self.functions[old_functions:]
        
        self.classes.append(ClassInfo(
            name=node.name,
            lineno=node.lineno,
            bases=bases,
            methods=methods,
            docstring=docstring,
        ))
        
        self._current_class = None
    
    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Visit function definition."""
        self._visit_function(node)
    
    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Visit async function definition."""
        self._visit_function(node)
    
    def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        """Process a function definition."""
        decorators = self._get_decorator_names(node.decorator_list)
        is_fixture, fixture_scope = self._is_fixture(decorators)
        is_test = self._is_test_function(node.name)
        
        # Extract argument names (potential fixture references)
        args = []
        for arg in node.args.args:
            arg_name = arg.arg
            args.append(arg_name)
            # Skip 'self' and 'cls'
            if arg_name not in ("self", "cls"):
                self.fixtures_used.add(arg_name)
        
        docstring = ast.get_docstring(node)
        body_source = self._get_source_segment(node)
        
        func_info = FunctionInfo(
            name=node.name,
            lineno=node.lineno,
            end_lineno=node.end_lineno or node.lineno,
            args=args,
            decorators=decorators,
            docstring=docstring,
            body_source=body_source,
            is_test=is_test,
            is_fixture=is_fixture,
            fixture_scope=fixture_scope,
            class_name=self._current_class,
        )
        self.functions.append(func_info)
        
        # Continue visiting children
        self._current_function = node.name
        self.generic_visit(node)
        self._current_function = None
    
    def visit_Assert(self, node: ast.Assert) -> None:
        """Visit assert statement."""
        source = self._get_source_segment(node)
        
        assert_info = AssertInfo(
            lineno=node.lineno,
            source=source,
        )
        
        # Analyze the assertion test
        test = node.test
        if isinstance(test, ast.Compare):
            assert_info.comparison_op = self._get_comparison_op(test.ops[0])
            assert_info.left_side = self._get_source_segment(test.left)
            if test.comparators:
                assert_info.right_side = self._get_source_segment(test.comparators[0])
        
        # Detect assertion types
        source_lower = source.lower()
        assert_info.is_status_code = any(
            kw in source_lower for kw in ["status_code", "status", ".status", "== 200", "== 201", "== 204", "== 304", "== 400", "== 404", "== 500"]
        )
        assert_info.is_header_check = any(
            kw in source_lower for kw in ["header", "content-type", "cache-control", "vary", "etag", "x-cache"]
        )
        assert_info.is_cache_check = any(
            kw in source_lower for kw in ["cache", "hit", "miss", "stale", "cached"]
        )
        assert_info.is_timing_check = any(
            kw in source_lower for kw in ["latency", "duration", "elapsed", "time", "p50", "p95", "p99", "percentile", "timeout"]
        )
        
        self.asserts.append(assert_info)
        self.generic_visit(node)
    
    def _get_comparison_op(self, op: ast.cmpop) -> str:
        """Convert comparison operator to string."""
        op_map = {
            ast.Eq: "==",
            ast.NotEq: "!=",
            ast.Lt: "<",
            ast.LtE: "<=",
            ast.Gt: ">",
            ast.GtE: ">=",
            ast.Is: "is",
            ast.IsNot: "is not",
            ast.In: "in",
            ast.NotIn: "not in",
        }
        return op_map.get(type(op), "?")
    
    def visit_Call(self, node: ast.Call) -> None:
        """Visit function call."""
        func_name = ""
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            func_name = self._get_source_segment(node.func)
        
        args = [self._get_source_segment(arg) for arg in node.args]
        kwargs = {}
        for kw in node.keywords:
            if kw.arg:
                kwargs[kw.arg] = self._get_source_segment(kw.value)
        
        self.calls.append(CallInfo(
            func_name=func_name,
            lineno=node.lineno,
            args=args,
            kwargs=kwargs,
            source=self._get_source_segment(node),
        ))
        
        self.generic_visit(node)
    
    def visit_Constant(self, node: ast.Constant) -> None:
        """Visit constant (including string literals)."""
        if isinstance(node.value, str) and len(node.value) > 2:
            context = "unknown"
            if self._context_stack:
                context = self._context_stack[-1]
            
            self.string_literals.append(StringLiteral(
                value=node.value,
                lineno=node.lineno,
                context=context,
            ))
        self.generic_visit(node)


def analyze_test_file(file_path: Path) -> Optional[ParsedTestFile]:
    """
    Analyze a single test file.
    
    Args:
        file_path: Path to the test file
        
    Returns:
        ParsedTestFile or None if file cannot be parsed
    """
    try:
        source = file_path.read_text(encoding="utf-8")
        analyzer = TestAnalyzer(source, file_path)
        return analyzer.analyze()
    except Exception:
        return None


def discover_test_files(root_path: Path) -> list[Path]:
    """
    Discover all pytest test files in a directory.
    
    Args:
        root_path: Root directory to search
        
    Returns:
        List of paths to test files
    """
    test_files = []
    
    if root_path.is_file():
        if root_path.name.startswith("test_") or root_path.name.endswith("_test.py"):
            return [root_path]
        if root_path.suffix == ".py" and "test" in root_path.name.lower():
            return [root_path]
        return []
    
    for py_file in root_path.rglob("*.py"):
        # Skip hidden directories and common non-test paths
        if any(part.startswith(".") for part in py_file.parts):
            continue
        if any(part in ("venv", "env", ".venv", "node_modules", "__pycache__", "build", "dist") for part in py_file.parts):
            continue
        
        # Include test files
        if py_file.name.startswith("test_") or py_file.name.endswith("_test.py"):
            test_files.append(py_file)
        # Also include conftest.py for fixtures
        elif py_file.name == "conftest.py":
            test_files.append(py_file)
    
    return sorted(test_files)
