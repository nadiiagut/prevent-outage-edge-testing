# POET - Prevent Outage Edge Testing

Obligation-based testing framework for CDN/edge proxy systems.

## Installation

```bash
pip install -e ".[dev]"
```

## Quick Start

```bash
poet init                              # Detect system capabilities
poet learn from-tests ./tests/         # Learn patterns from existing tests
poet gate run --all                    # Run release gates
```

## Obligations (What Must Be True)

Portable definitions of correctness properties. Define *what* must be true, not *how* to test it.

| Domain | Examples |
|--------|----------|
| `routing` | backend.selection, fanout.bound, healthcheck.respect |
| `cache` | key.stability, vary.honored |
| `protocol` | http.status, content.length |
| `security` | tls.chain.valid, mtls.client.verified |
| `resilience` | timeout.enforced, retry.bounded |
| `observability` | access.logged, metrics.exposed |
| `state` | config.reload.atomic, ratelimit.enforced |

See [obligations/index.md](obligations/index.md) for full list.

## Recipes (How to Test It)

Environment-specific instructions for verifying obligations. Generated recipes are starting points—you must bind to your config and capture evidence.

## Obligation Coverage

**"100% obligation coverage"** = every obligation has at least one passing test with evidence.

- NOT code coverage or a guarantee of zero outages
- IS a structured gate that blocks releases missing critical checks

## Project Structure

```
├── obligations/       # Portable obligation specs (YAML)
├── mappings/          # Internal pattern → obligation mappings
├── knowledge/learned/ # Extracted patterns from test suites
├── packs/             # Knowledge packs (failure modes, recipes)
└── src/               # CLI and library code
```

## License

MIT
