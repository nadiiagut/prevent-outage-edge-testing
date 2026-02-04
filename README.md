# POET - Prevent Outage Edge Testing

**P**ortable **O**bligation **E**vidence **T**esting

A knowledge amplifier that transfers senior outage experience into reusable testing obligations, evidence requirements, and release gates.

> **This tool does not prevent outages.** It structures release confidence using obligations and evidence. It is not a test generator—it helps you understand *what* to test and *what evidence* to capture.

## What You Get

- **Obligations**: Portable definitions of what must be true (e.g., "same request routes to same backend")
- **Evidence requirements**: What to capture for debugging (logs, metrics, packet captures)
- **Release gates**: Pass/fail checks before deployment

Preview real outputs: [examples/](examples/)
- [TESTPLAN.cache-change.md](examples/TESTPLAN.cache-change.md) - Generated test plan
- [observability_runbook.md](examples/observability_runbook.md) - What signals to collect
- [gate_report.json](examples/gate_report.json) - Release gate results

## Quick Start (Users)

Users consume obligations and run gates. No legacy test suite required.

```bash
# 1. Install
pip install -e "."

# 2. Try the demo environment
cd demo && make up

# 3. Initialize and run gates
poet init
poet obligations list
poet gate run --all
```

## Demo Environment

A Docker-based NGINX edge proxy with upstreams for testing obligations locally:

```bash
cd demo
make up      # Start NGINX edge + 2 upstreams + 1 faulty upstream
make test    # Run basic obligation checks
make down    # Stop
```

See [demo/README.md](demo/README.md) for details.

## Top Obligations for Edge Proxies

| Obligation | What It Checks | Risk |
|------------|----------------|------|
| `routing.backend.selection` | Same request → same backend | high |
| `routing.fanout.bound` | Retries don't amplify load | high |
| `cache.vary.honored` | Vary header respected | high |
| `protocol.http.status` | Correct 5xx on failures | high |
| `resilience.timeout.enforced` | Slow backends don't block | high |
| `observability.access.logged` | Every request logged | high |

Run `poet obligations list` for all 17 obligations.

## Maintainer Workflow

Maintainers extract knowledge from existing test suites and commit it for users.

```bash
# Extract patterns from legacy tests (maintainer only)
poet learn from-tests /path/to/legacy/tests/

# Review extracted knowledge
cat knowledge/learned/*.json

# Commit to repo for users
git add knowledge/learned/
git commit -m "Add learned patterns from project X"
```

Users do NOT need access to legacy tests—they use the committed knowledge.

## Obligation Coverage

**"100% obligation coverage"** = every selected obligation has at least one passing test with evidence.

Evidence may include:
- Access logs with cache status, backend ID, timing
- Prometheus metrics snapshots
- Request/response captures
- Packet captures (tcpdump) for protocol issues

This is NOT:
- Code coverage
- A guarantee of zero outages
- AI writing tests for you

## Directory Structure

```
├── obligations/       # Portable obligation specs (YAML) - THE CORE PRODUCT
├── examples/          # Real POET output examples
├── demo/              # Docker-based test environment
├── mappings/          # Internal pattern → obligation mappings
├── packs/             # Knowledge packs (failure modes, recipes)
├── knowledge/learned/ # Extracted patterns (git-ignored, maintainer-generated)
├── .poet/             # Local runtime data (git-ignored)
│   ├── evidence/      # Captured evidence per test run
│   └── reports/       # Gate reports (JSON, HTML)
└── src/               # CLI and library code
```

### What goes where

| Directory | Committed? | Who creates it |
|-----------|------------|----------------|
| `obligations/` | Yes | Project maintainers |
| `examples/` | Yes | Project maintainers |
| `knowledge/learned/` | No (git-ignored) | Maintainers run `poet learn` |
| `.poet/` | No (git-ignored) | CLI creates at runtime |

## CLI Commands

```bash
poet init                    # Detect system capabilities
poet obligations list        # List all obligations
poet obligations show <id>   # Show obligation details
poet gate run --all          # Run all release gates
poet gate report             # Show latest gate report
poet learn from-tests <path> # Extract patterns (maintainers)
```

## Roadmap

- [ ] Additional demo environments (HAProxy, Envoy)
- [ ] HAProxy ↔ NGINX obligation translation
- [ ] Baseline/performance budget tooling
- [ ] Better pack explainability (why this obligation matters)
- [ ] Evidence viewer UI

## License

MIT
