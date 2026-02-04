# Makefile for POET (Prevent Outage Edge Testing)
#
# Usage:
#   make install    - Install dependencies
#   make test       - Run tests
#   make lint       - Run linting
#   make format     - Format code
#   make clean      - Clean build artifacts

.PHONY: install install-dev test test-cov lint format clean build docs help

PYTHON := python3
PYTEST := pytest
RUFF := ruff

# Default target
help:
	@echo "POET Development Commands"
	@echo ""
	@echo "  make install      Install production dependencies"
	@echo "  make install-dev  Install development dependencies"
	@echo "  make test         Run test suite"
	@echo "  make test-cov     Run tests with coverage"
	@echo "  make lint         Run linting checks"
	@echo "  make format       Format code"
	@echo "  make typecheck    Run type checking"
	@echo "  make clean        Clean build artifacts"
	@echo "  make build        Build package"
	@echo "  make validate     Validate all knowledge packs"
	@echo ""

# Installation
install:
	poetry install --only main

install-dev:
	poetry install

# Testing
test:
	$(PYTEST) tests/ -v

test-cov:
	$(PYTEST) tests/ -v --cov=prevent_outage_edge_testing --cov-report=html --cov-report=term

test-fast:
	$(PYTEST) tests/ -v -x --tb=short

# Code quality
lint:
	$(RUFF) check src/ tests/

format:
	$(RUFF) format src/ tests/
	$(RUFF) check --fix src/ tests/

typecheck:
	mypy src/

# All checks
check: lint typecheck test

# Clean
clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf .pytest_cache/
	rm -rf .ruff_cache/
	rm -rf .mypy_cache/
	rm -rf htmlcov/
	rm -rf .coverage
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete

# Build
build: clean
	poetry build

# POET-specific commands
validate:
	poet packs validate

init-local:
	poet init

# Development helpers
dev-server:
	@echo "No dev server for CLI tool"

shell:
	poetry shell

update-deps:
	poetry update

# Documentation
docs:
	@echo "Documentation generation not yet configured"
	@echo "Consider adding mkdocs or sphinx"

# CI helpers
ci-test:
	$(PYTEST) tests/ -v --junitxml=test-results.xml

ci-lint:
	$(RUFF) check src/ tests/ --output-format=github

# Release
version:
	@poetry version

bump-patch:
	poetry version patch

bump-minor:
	poetry version minor

bump-major:
	poetry version major
