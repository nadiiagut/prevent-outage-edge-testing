# Jira Integration Guide

This guide covers how to use POET with Jira tickets to generate test plans.

---

## Three Ways to Use Jira with POET

### A) Paste Jira Text (No Auth Required)

Copy the ticket description from Jira and pass it directly to POET. No authentication needed.

```bash
poet build --jira-text "Add cache bypass for authenticated requests.

Acceptance criteria:
- Requests with Authorization header must not be served from cache
- Requests without Authorization header should use normal caching
- Cache-Control: private responses must not be cached"
```

**Best for:** Quick one-off test plans, tickets you already have open.

---

### B) Jira API (Planned)

> 🚧 **Coming soon** — Direct Jira API integration is on the roadmap.

Once implemented, you'll be able to fetch tickets directly:

```bash
# Future syntax (not yet implemented)
export JIRA_TOKEN="your-api-token-here"
poet build --jira-key EDGE-123 \
           --jira-url https://yourcompany.atlassian.net \
           --jira-token-env JIRA_TOKEN
```

**For now:** Export your ticket to markdown and use `--jira-file` (Option C below).

---

### C) Offline Mode (Export to Markdown)

Export the ticket to a file, then run POET on the file. Works without network access.

**Step 1:** Export from Jira (copy to file or use Jira export)

```bash
# Create a file with the ticket content
cat > EDGE-123.md << 'EOF'
# EDGE-123: Add stale-while-revalidate support

## Summary
Add SWR support for /api/* endpoints to reduce origin load.

## Description
When cache is stale, serve stale content immediately while revalidating 
in the background. This prevents thundering herd on cache expiry.

## Acceptance Criteria
- [ ] Stale content served within 10ms when SWR window is active
- [ ] Only ONE background request sent to origin per cache key
- [ ] SWR window configurable (default: 60 seconds)
- [ ] X-Cache header indicates "HIT-STALE" for stale responses
EOF
```

**Step 2:** Run POET on the file

```bash
poet build --jira-file EDGE-123.md --jira-key EDGE-123 --title "SWR Support"
```

**Best for:** Air-gapped environments, reviewing before submission, version-controlled specs.

---

## Required and Optional Fields

POET extracts signals from Jira content to select relevant packs and generate test cases.

### Required Fields

| Field | What POET Looks For | Example |
|-------|---------------------|---------|
| **Summary/Title** | Feature name, affected component | "Add cache bypass for auth requests" |
| **Description** | Technical details, scope, constraints | "When Authorization header present..." |

### Strongly Recommended

| Field | What POET Looks For | Example |
|-------|---------------------|---------|
| **Acceptance Criteria** | Testable assertions, expected behavior | "- [ ] X-Cache: MISS for auth requests" |

### Optional (Improves Pack Selection)

| Field | What POET Looks For | Example |
|-------|---------------------|---------|
| **Components** | System area (cache, routing, TLS) | "edge-cache", "load-balancer" |
| **Labels** | Keywords for pack matching | "performance", "security", "breaking-change" |
| **Environment** | Target deployment context | "production", "staging" |

---

## Examples

### Example 1: Inline Text

```bash
poet build --jira-text "Implement rate limiting for /api/v2/* endpoints.

Rate limit: 100 requests per minute per client IP.
Exceeded requests should return 429 Too Many Requests.
Must not affect /api/v1/* endpoints.

Acceptance criteria:
- 429 returned after 100 requests in 60 seconds
- X-RateLimit-Remaining header shows remaining quota
- Rate limit resets after 60 seconds
- /api/v1/* endpoints unaffected"
```

### Example 2: From File with Metadata

```bash
poet build --jira-file specs/EDGE-456.md \
           --jira-key EDGE-456 \
           --title "Rate Limiting v2 API" \
           --output ./generated/edge-456
```

### Example 3: CI/CD with Exported Tickets

```bash
# In CI pipeline (ticket exported to file)
poet build --jira-file ./specs/$JIRA_TICKET.md \
           --jira-key $JIRA_TICKET \
           --output ./test-plans/$JIRA_TICKET
```

### Example 4: Batch Processing (with exported files)

```bash
# Process multiple exported tickets
for ticket in EDGE-100 EDGE-101 EDGE-102; do
  poet build --jira-file ./specs/$ticket.md \
             --jira-key $ticket \
             --output ./plans/$ticket
done
```

---

## Understanding Pack Selection

POET analyzes your Jira content to select relevant knowledge packs.

### How It Works

1. **Keyword extraction** — Identifies domain terms (cache, routing, TLS, timeout)
2. **Pattern matching** — Matches against learned patterns from legacy tests
3. **Obligation mapping** — Maps features to relevant obligations
4. **Pack selection** — Chooses packs that cover identified failure modes

### See the Explanation

Use `--explain` to see why POET selected specific packs:

```bash
poet build --jira-text "Add cache bypass for auth requests" --explain
```

**Output:**

```
Pack Selection Explanation
==========================

Matched keywords:
  - "cache" → edge-http-cache-correctness (confidence: 0.95)
  - "bypass" → edge-http-cache-correctness (confidence: 0.80)
  - "auth" → edge-http-cache-correctness (confidence: 0.70)

Matched obligations:
  - cache.key.stability (from "cache bypass")
  - cache.vary.honored (from "Authorization header")

Selected packs:
  1. edge-http-cache-correctness
     - Failure modes: cache-key-collision, vary-header-cache-split
     - Test templates: 3 applicable
     - Recipes: 2 applicable

Not selected (no signals):
  - fault-injection-io (no fault injection keywords)
  - edge-latency-regression-observability (no latency keywords)
```

### Improving Pack Selection

If POET misses relevant packs:

1. **Add keywords** — Include domain terms in description ("cache", "timeout", "retry")
2. **Be specific** — "HTTP 503 on backend failure" is better than "handle errors"
3. **List failure scenarios** — "Must not cause thundering herd" triggers resilience packs

---

## Common Mistakes & Troubleshooting

### 1. Missing Acceptance Criteria

**Problem:** POET generates generic test cases.

**Symptom:**
```
Warning: No acceptance criteria found. Using default assertions.
```

**Fix:** Add explicit acceptance criteria:

```diff
- Handle cache correctly for authenticated users.
+ Handle cache correctly for authenticated users.
+ 
+ Acceptance criteria:
+ - Requests with Authorization header return X-Cache: MISS
+ - Requests without Authorization header can return X-Cache: HIT
```

---

### 2. Unclear Scope

**Problem:** POET selects too many or wrong packs.

**Symptom:**
```
Selected packs: 5 (edge-http-cache-correctness, fault-injection-io, 
                   edge-latency-regression-observability, ...)
```

**Fix:** Be specific about what's changing:

```diff
- Improve caching performance.
+ Add stale-while-revalidate for /api/* endpoints only.
+ Does NOT affect /static/* or /images/* caching behavior.
```

---

### 3. Wrong Environment Assumptions

**Problem:** Generated tests assume wrong infrastructure.

**Symptom:** Tests reference NGINX when you use HAProxy.

**Fix:** Specify environment in description:

```diff
+ Environment: HAProxy 2.8 with stick tables
+ 
  Add rate limiting for API endpoints.
```

Or use `--config` to provide context (when supported):

```bash
poet build --jira-file spec.md --config haproxy.cfg
```

---

### 4. No Packs Selected

**Problem:** POET doesn't find relevant packs.

**Symptom:**
```
Warning: No packs matched. Generating minimal test plan.
```

**Causes:**
- Description too vague
- Feature outside current pack coverage
- Missing domain keywords

**Fix:** Add explicit domain terms:

```diff
- Fix the bug where users see wrong content.
+ Fix cache key collision where users see wrong content.
+ Affected: edge proxy cache layer
+ Symptoms: X-Cache: HIT but wrong response body
```

---

### 5. API Token Issues

**Problem:** Jira API returns 401/403.

**Symptom:**
```
Error: Jira API authentication failed (401)
```

**Fixes:**

1. **Check token is set:**
   ```bash
   echo $JIRA_TOKEN | head -c 10  # Should show first 10 chars
   ```

2. **Check token permissions:** API token needs read access to the project

3. **Check URL format:**
   ```bash
   # Correct
   --jira-url https://company.atlassian.net
   
   # Wrong (no trailing slash, no /rest/api)
   --jira-url https://company.atlassian.net/
   --jira-url https://company.atlassian.net/rest/api/3
   ```

4. **Use offline mode as fallback:**
   ```bash
   # Export ticket manually, then:
   poet build --jira-file exported-ticket.md
   ```

---

## Quick Reference

```bash
# Inline text (simplest)
poet build --jira-text "Your ticket description here"

# From file
poet build --jira-file ticket.md --jira-key PROJ-123

# From Jira API
export JIRA_TOKEN="your-token"
poet build --jira-key PROJ-123 --jira-url https://company.atlassian.net --jira-token-env JIRA_TOKEN

# With explanation
poet build --jira-text "..." --explain

# Custom output directory
poet build --jira-text "..." --output ./my-test-plan
```

---

## See Also

- [README.md](../README.md) — Project overview
- [examples/TESTPLAN.cache-change.md](../examples/TESTPLAN.cache-change.md) — Sample output
- `poet build --help` — Full CLI options
