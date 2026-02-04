# Contributing to POET

Thank you for your interest in contributing to POET (Prevent Outage Edge Testing)!

## Development Setup

### Prerequisites

- Python 3.11+
- [Poetry](https://python-poetry.org/) or [uv](https://github.com/astral-sh/uv)

### Installation

```bash
# Clone the repository
git clone https://github.com/your-org/prevent-outage-edge-testing.git
cd prevent-outage-edge-testing

# Install with Poetry
poetry install

# Or with uv
uv pip install -e ".[dev]"

# Verify installation
poet --help
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=prevent_outage_edge_testing --cov-report=html

# Run specific test file
pytest tests/test_cli.py -v
```

## How to Contribute

### Reporting Issues

1. Check existing issues first
2. Include Python version, OS, and POET version
3. Provide minimal reproducible example
4. Include relevant error messages

### Submitting Changes

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Make your changes
4. Run tests and linting
5. Commit with clear message
6. Push and create Pull Request

### Code Style

We use:
- **Ruff** for linting and formatting
- **MyPy** for type checking
- **Black** code style (via Ruff)

```bash
# Format code
ruff format .

# Check linting
ruff check .

# Type check
mypy src/
```

## Adding Knowledge Packs

Knowledge packs are the core extension mechanism for POET.

### Pack Structure

```
packs/<pack-id>/
├── pack.yaml          # Required: Pack definition
├── README.md          # Recommended: Documentation
├── recipes/           # Observability recipes
│   └── *.md
└── snippets/          # Code snippets
    └── *.*
```

### pack.yaml Schema

```yaml
id: my-pack-id                    # Unique identifier (kebab-case)
name: My Knowledge Pack           # Human-readable name
version: "1.0.0"                  # Semantic version
description: |
  Detailed description of what this pack covers.
author: Your Name
tags:
  - relevant
  - tags

failure_modes:
  - id: failure-mode-id
    name: Failure Mode Name
    description: What can go wrong
    severity: critical|high|medium|low
    symptoms:
      - Observable symptom 1
      - Observable symptom 2
    root_causes:
      - Potential cause 1
    mitigation_strategies:
      - How to fix or prevent
    tags:
      - categorization

test_templates:
  - id: test-id
    name: Test Name
    description: What this tests
    failure_mode_id: failure-mode-id  # Links to failure mode
    priority: high
    setup_steps:
      - Step 1
    execution_steps:
      - Step 2
    assertions:
      - description: What to check
        expression: "python_expression"
    cleanup_steps:
      - Step 3
    requires_privileged: false
    fallback_available: true

references:
  - https://relevant-documentation.com
```

### Validation

```bash
# Validate all packs
poet packs validate

# Validate specific pack
poet packs validate --pack my-pack-id
```

### Best Practices

1. **Be Specific**: Focus on one domain per pack
2. **Include Fallbacks**: For privileged operations, provide simulator alternatives
3. **Document Well**: Include README with examples
4. **Test Templates**: Provide actionable test templates, not just theory
5. **Tag Appropriately**: Use consistent tags for discoverability

## Adding Extractors

Extractors are tools that gather data from systems (DTrace, eBPF, etc.).

### Extractor Interface

```python
from abc import ABC, abstractmethod
from typing import Optional
from dataclasses import dataclass

@dataclass
class ExtractorResult:
    data: dict
    duration_seconds: float
    privileged: bool

class BaseExtractor(ABC):
    @abstractmethod
    def is_available(self) -> bool:
        """Check if this extractor can run on current system."""
        pass
    
    @abstractmethod
    def extract(self, target: str, duration: int) -> ExtractorResult:
        """Run extraction and return results."""
        pass
    
    @property
    @abstractmethod
    def requires_privileged(self) -> bool:
        """Whether this extractor needs elevated permissions."""
        pass
```

### Providing Fallbacks

Always provide a simulator fallback:

```python
def create_extractor(prefer_privileged: bool = True) -> BaseExtractor:
    if prefer_privileged and DTraceExtractor().is_available():
        return DTraceExtractor()
    return SimulatorExtractor()
```

## Code of Conduct

- Be respectful and inclusive
- Focus on constructive feedback
- Help others learn

## Questions?

Open a GitHub Discussion or reach out to the maintainers.

---

Thank you for contributing to POET!
