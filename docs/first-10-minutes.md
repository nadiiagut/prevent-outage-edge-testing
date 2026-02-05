# Your First 10 Minutes with POET

A step-by-step walkthrough to get you from zero to running release gates.

---

## 1. Install (1 min)

```bash
git clone https://github.com/yourorg/prevent-outage-edge-testing.git
cd prevent-outage-edge-testing
pip install -e "."
```

Verify installation:

```bash
poet --version
```

---

## 2. Start Demo Target (2 min)

The repo includes a Docker-based demo environment with NGINX edge proxy.

```bash
cd demo
make up
```

This starts:
- NGINX edge proxy on `localhost:8080`
- Two healthy upstream servers
- One faulty upstream (for fault injection tests)

**No Docker?** Use any HTTP server as target:

```bash
# Minimal stub with Python
python -m http.server 8080
```

---

## 3. Initialize POET (30 sec)

```bash
cd ..  # Back to repo root
poet init
```

This detects your system capabilities and creates `.poet/profile.json`.

**Output:**
```
✓ System profile created
  OS: darwin/arm64
  Docker: available
  tcpdump: available
  
Profile saved to .poet/profile.json
```

---

## 4. Build from Jira Text (1 min)

Paste a feature description to generate a test plan:

```bash
poet build --jira-text "Add cache bypass for authenticated requests.

Acceptance criteria:
- Requests with Authorization header must not be served from cache
- Requests without Authorization header should use normal caching
- Cache-Control: private responses must not be cached"
```

**Output:**
```
✓ Build Complete

Title: Add cache bypass for authenticated requests
Test Cases: 3
Failure Modes: 2
Packs Used: 1

Output:
  📄 generated/TESTPLAN.md
  🧪 generated/tests/
  📊 generated/observability/
```

---

## 5. Inspect Outputs (2 min)

### TESTPLAN.md

```bash
cat generated/TESTPLAN.md
```

You'll see:
- **Failure Modes Covered** — What can go wrong
- **Test Cases** — Step-by-step tests with assertions
- **Setup/Execution/Assertions** — Concrete steps

### Observability Runbook

```bash
ls generated/observability/
cat generated/observability/*.md
```

Shows what metrics/logs to collect as evidence.

### Starter Tests

```bash
ls generated/tests/
```

Pytest scaffolds with TODO markers — you complete these.

---

## 6. Run Release Gates (1 min)

```bash
poet gate run --all
```

**Output:**
```
✓ PASS Contract Tests (contract)
  ✓ PASS cache.key.stability
    Cache key includes all relevant dimensions
  ✓ PASS cache.vary.honored
    Vary header respected in cache key

◐ PARTIAL Observability (observability)
  ✓ PASS access.logged
    Access logs configured
  − SKIP metrics.exported
    No Prometheus endpoint detected

Gate Results
────────────
◐ PARTIAL

Gates: 1 passed, 0 failed, 1 partial
Duration: 234ms

Reports saved:
  JSON: .poet/reports/latest.json
  HTML: .poet/reports/latest.html
```

---

## 7. Interpreting Results

| Status | Meaning | Action |
|--------|---------|--------|
| **✓ PASS** | All checks passed with evidence | Ready to proceed |
| **✗ FAIL** | One or more checks failed | Fix before release |
| **◐ PARTIAL** | Some checks passed, some skipped | Review skipped items |
| **− SKIP** | Check couldn't run (missing capability) | Optional: add capability |
| **⚠ ERROR** | Check threw an error | Debug the check |

### PARTIAL is OK (sometimes)

PARTIAL means some checks passed but others were skipped. Common reasons:

- **Missing tool** — e.g., no Prometheus for metrics checks
- **Missing evidence** — tests ran but didn't capture artifacts
- **Environment mismatch** — check requires Docker but none available

**Review skipped checks:**

```bash
poet gate report
```

If skipped checks are not relevant to your deployment, PARTIAL is acceptable.

---

## 8. Where to Go Next

### Learn More

| Topic | Link |
|-------|------|
| All input modes | [docs/inputs.md](inputs.md) |
| Jira integration | [docs/jira.md](jira.md) |
| Output artifacts | [docs/outputs.md](outputs.md) |

### Explore

```bash
# List all obligations
poet obligations list

# Show specific obligation
poet obligations show cache.key.stability

# List knowledge packs
poet packs list

# Show pack details
poet packs show edge-http-cache-correctness
```

### Build with Explanation

See why POET selected specific packs:

```bash
poet build --jira-text "..." --explain
```

### Run Demo Tests

```bash
cd demo
make test
```

---

## Quick Reference

```bash
# Build
poet build --jira-text "..."           # From text
poet build --jira-file spec.md         # From file
poet build --explain                   # Show reasoning

# Gates
poet gate run --all                    # Run all gates
poet gate report                       # Show latest report

# Browse
poet obligations list                  # List obligations
poet packs list                        # List packs
```

---

## Troubleshooting

### "No packs matched"

Your description is too vague. Add domain keywords:

```diff
- Fix the bug
+ Fix cache key collision causing wrong content
```

### "poet: command not found"

Install wasn't in PATH:

```bash
pip install -e "."
# Or use full path
python -m prevent_outage_edge_testing.cli.main --help
```

### Demo won't start

Check Docker is running:

```bash
docker ps
```

---

**Total time: ~10 minutes**

You now have a test plan, starter tests, and gate results. Next: implement the tests and collect evidence!
