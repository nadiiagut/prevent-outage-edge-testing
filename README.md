# POET - Prevent Outage Edge Testing

**P**ortable **O**bligation **E**vidence **T**esting

POET helps you build test plans and release gates from feature descriptions. It encodes senior engineering knowledge about edge proxy failure modes into reusable obligations, then matches your feature to relevant test cases, observability recipes, and evidence requirements.

> 🚀 **New here?** Start with the **[First 10 Minutes Guide](docs/first-10-minutes.md)** — install, build, and run gates in one walkthrough.

---

## What POET is NOT

- **Not a zero-outage guarantee** — POET structures confidence, it doesn't eliminate risk
- **Not code coverage** — Obligation coverage means "every selected obligation has evidence," not "every line is tested"
- **Not a test generator** — POET tells you *what* to test and *what evidence* to capture; you write the tests
- **Not AI magic** — Knowledge comes from real legacy test suites, curated by humans

---

## Concepts

| Term | Definition |
|------|------------|
| **Obligation** | A portable rule that must be true (e.g., "same request routes to same backend"). |
| **Evidence** | Artifacts proving an obligation is met (logs, metrics, packet captures). |
| **Pack** | A bundle of failure modes, test templates, and recipes for a specific domain. |
| **Gate** | A pass/fail check that runs before deployment, verifying obligations have evidence. |

---

## Quick Start — FOR USERS

Users build test plans from feature descriptions. No legacy tests required.

### 1. Install

```bash
pip install -e "."
poet init
```

### 2. Build a Test Plan

```bash
poet build --jira-text "Add cache bypass for authenticated requests."
```

### 3. Review Outputs

```bash
ls generated/
# TESTPLAN.md          - Structured test plan
# tests/               - Pytest starter files
# observability/       - Monitoring recipes
```

### 4. Run Release Gates

```bash
poet gate run --all
poet gate report
```

---

## Use POET with Jira Tickets

Generate a test plan directly from a Jira ticket:

### Option A: Paste ticket content

```bash
poet build --jira-text "
EDGE-234: Purge propagation fix

Description: Updated purge logic to reduce stale data after invalidation.

Acceptance Criteria:
- No stale content served after purge completes
- Cache headers remain valid
- Purge propagates to all edge nodes within 30 seconds
"
```

### Option B: Export ticket to markdown file

Save your ticket as `EDGE-234.md`, then:

```bash
poet build --jira-file ./EDGE-234.md --jira-key EDGE-234
```

### Option C: Jira API (if configured)

```bash
export JIRA_TOKEN="your-api-token"
poet build --jira-key EDGE-234 \
           --jira-url https://example.atlassian.net \
           --jira-token-env JIRA_TOKEN
```

### Expected Ticket Fields

| Field | Required | Used For |
|-------|----------|----------|
| **Summary/Title** | Yes | Test plan title, keyword extraction |
| **Description** | Yes | Feature analysis, pack selection |
| **Acceptance Criteria** | Recommended | Assertion generation |
| **Components** | Optional | Domain detection (cache, routing) |
| **Labels** | Optional | Pack filtering |

### See Pack Selection Reasoning

```bash
poet build --jira-text "..." --explain
```

📖 **[Full Jira Guide](docs/jira.md)** — Troubleshooting, field mapping, API setup

---

## Quick Start — FOR MAINTAINERS

Maintainers extract knowledge from legacy test suites, review it, and commit curated patterns for users.

### 1. Learn from Existing Tests

```bash
poet learn from-tests /path/to/legacy/tests/
```

This writes raw patterns to `.poet/learned/` (git-ignored).

### 2. Review Extracted Knowledge

```bash
poet learn show
cat .poet/learned/*.json
```

### 3. Curate and Commit

After human review, move validated patterns to `knowledge/curated/`:

```bash
# Review and sanitize (remove proprietary references)
cp .poet/learned/extraction_*.json knowledge/curated/

# Commit curated knowledge
git add knowledge/curated/
git commit -m "Add curated patterns from project X"
git push
```

**Users never need access to legacy tests** — they use the committed curated knowledge.

---

## Supported Input Modes

| Mode | Command | Status |
|------|---------|--------|
| **Jira text** | `poet build --jira-text "..."` | ✅ Supported |
| **Jira file** | `poet build --jira-file spec.txt` | ✅ Supported |
| **Jira API** | `poet build --jira-key PROJ-123 --jira-url ...` | ✅ Supported |
| **Markdown spec** | `poet build --jira-file spec.md` | ✅ Supported |
| **OpenAPI/Swagger** | `poet build --openapi api.yaml` | 🚧 Planned |
| **Config profile** | `poet build --config nginx.conf` | 🚧 Planned |
| **Existing tests** | `poet learn from-tests ./tests/` | ✅ Supported (maintainers) |

📖 **[Full Jira Integration Guide](docs/jira.md)** — Three ways to use Jira, pack selection, troubleshooting

📖 **[All Input Modes](docs/inputs.md)** — Markdown specs, OpenAPI, system profiles, direct selection

---

## Output Artifacts

| Artifact | Location | Description |
|----------|----------|-------------|
| `TESTPLAN.md` | `generated/TESTPLAN.md` | Structured test plan with failure modes, test cases, assertions |
| `tests/` | `generated/tests/` | Pytest starter files (you complete them) |
| `observability/` | `generated/observability/` | Runbooks for what signals to collect |
| `snippets/` | `generated/snippets/` | Code helpers (latency analyzer, fault injector) |
| Gate report | `.poet/reports/latest.json` | Pass/fail results with evidence paths |

📖 **[Output Artifacts Guide](docs/outputs.md)** — TESTPLAN structure, test scaffolds, runbooks, gate reports

---

## Full Example: Jira → Test Plan

**Input** (Jira description):

```
Add cache bypass for authenticated requests.

Acceptance criteria:
- Requests with Authorization header must not be served from cache
- Requests without Authorization header should use normal caching
- Cache-Control: private responses must not be cached
```

**Command**:

```bash
poet build --jira-text "Add cache bypass for authenticated requests.

Acceptance criteria:
- Requests with Authorization header must not be served from cache
- Requests without Authorization header should use normal caching
- Cache-Control: private responses must not be cached" \
  --title "Auth Cache Bypass" --jira-key CACHE-456
```

**Outputs**:

```
generated/
├── TESTPLAN.md              # 3 test cases covering cache bypass
├── tests/
│   └── test_cache_bypass.py # Pytest starters
├── observability/
│   └── cache-metrics.md     # What Prometheus metrics to check
└── snippets/
    └── cache_validator.py   # Helper to verify cache headers
```

**TESTPLAN.md excerpt**:

```markdown
## Test Cases

### 1. Authorization Header Bypasses Cache
**Priority:** critical
**Failure Mode:** `cache-key-collision`

**Assertions:**
- [ ] Request with Authorization header returns X-Cache: MISS
- [ ] Subsequent identical request also returns X-Cache: MISS
- [ ] Request without Authorization returns X-Cache: HIT (after warm)
```

---

## Repository Layout

```
├── obligations/           # Portable obligation specs (YAML) — COMMITTED
├── packs/                 # Knowledge packs (failure modes, recipes) — COMMITTED
├── mappings/              # Internal pattern → obligation mappings — COMMITTED
├── examples/              # Sample POET outputs — COMMITTED
├── demo/                  # Docker test environment — COMMITTED
├── knowledge/
│   ├── curated/           # Reviewed, reusable patterns — COMMITTED
│   └── *.md               # Human review summaries — COMMITTED
├── .poet/                 # Runtime data — GIT-IGNORED (CLI creates)
│   ├── learned/           # Raw extracted patterns (pre-review)
│   ├── evidence/          # Captured evidence per test run
│   └── reports/           # Gate reports (JSON, HTML)
└── src/                   # CLI and library code — COMMITTED
```

### What Gets Committed?

| Directory | Committed? | Who Creates It |
|-----------|------------|----------------|
| `obligations/` | ✅ Yes | Project maintainers |
| `packs/` | ✅ Yes | Project maintainers |
| `examples/` | ✅ Yes | Project maintainers |
| `knowledge/curated/` | ✅ Yes | Maintainers (after review) |
| `.poet/learned/` | ❌ No | `poet learn` (raw output) |
| `.poet/` | ❌ No | CLI at runtime |

---

## CLI Reference

```bash
# Setup
poet init                              # Detect system capabilities

# Browse obligations
poet obligations list                  # List all 17 obligations
poet obligations list --domain cache   # Filter by domain
poet obligations show <id>             # Show obligation details

# Browse packs
poet packs list                        # List all knowledge packs
poet packs show <pack-id>              # Show pack details
poet packs validate                    # Validate all packs

# Build test plans (USERS)
poet build --jira-text "..."           # From inline text
poet build --jira-file spec.md         # From file (txt, md)
poet build --openapi api.yaml          # From OpenAPI spec (experimental)
poet build --obligations "cache.*"     # Direct obligation selection
poet build --packs edge-http-cache-correctness  # Specific packs
poet build --explain                   # Show pack selection reasoning
poet build --title "My Feature"        # Set title
poet build --jira-key PROJ-123         # Set Jira key

# Run gates (USERS)
poet gate list                         # List available gates
poet gate run --all                    # Run all gates
poet gate run --gate contract          # Run specific gate
poet gate report                       # Show latest report
poet gate report --json                # JSON output

# Learn from tests (MAINTAINERS)
poet learn from-tests /path/to/tests/  # Extract patterns
poet learn show                        # Display learned patterns
poet learn show --section fixtures     # Show specific section
```

---

## Roadmap

- [x] OpenAPI/Swagger input mode (experimental)
- [ ] Config file analysis (nginx.conf, haproxy.cfg)
- [ ] Additional demo environments (HAProxy, Envoy)
- [ ] Evidence viewer UI
- [ ] Jira API integration

---

## Contributing

1. Fork the repo
2. Create a feature branch
3. Add tests for new functionality
4. Submit a PR

For knowledge contributions, run `poet learn from-tests` on your test suite, review and sanitize the output, then submit the curated `knowledge/curated/*.json` files.

---

## License

MIT
