# Pack Impact Report: Legacy Test Suite Knowledge Extraction

**Date:** 2026-02-04  
**Knowledge Artifact:** `knowledge/learned/extraction_2026-02-04_cdn_edge_proxy.json`

---

## Summary

This report identifies which packs should be extended, which new packs should be created, and which obligations gain stronger evidence based on the extracted knowledge.

**Action Required:** Review only - no modifications made.

---

## Packs to Extend

### 1. `edge-latency-regression-observability`

**Current Focus:** Latency measurement and regression detection

**Proposed Extensions:**
| Extension | Source Insight | Rationale |
|-----------|----------------|-----------|
| Stale-While-Revalidate timing | INS-004 | SWR window timing is critical for latency regression |
| Write timeout logging | INS-009 | Client writeable wait time affects perceived latency |

**Specific Additions:**
- Recipe: `swr_timing_validation` - Validate SWR window behavior under load
- Snippet: `swr_concurrent_client_test.py` - 10-client concurrent request pattern

---

### 2. `fault-injection-io`

**Current Focus:** I/O fault injection for resilience testing

**Proposed Extensions:**
| Extension | Source Insight | Rationale |
|-----------|----------------|-----------|
| Origin 5xx injection | INS-001, INS-005 | Test backup origin failover |
| Origin timeout injection | INS-008 | Test bounded retry behavior |

**Specific Additions:**
- Recipe: `origin_5xx_failover_test` - Inject 503 on primary, verify backup used
- Recipe: `origin_timeout_retry_test` - Inject timeout, verify bounded retry

---

## New Packs to Create

### 1. `cache-staleness-behavior` (PROPOSED)

**Rationale:** Multiple insights (INS-004, INS-005, INS-011) relate to cache staleness handling, which is not covered by existing packs.

**Proposed Structure:**
```
packs/cache-staleness-behavior/
├── pack.yaml
├── recipes/
│   ├── stale_while_revalidate.yaml
│   ├── override_5xx_with_stale.yaml
│   └── stale_on_not_found.yaml
└── snippets/
    ├── swr_test_harness.py
    └── stale_header_validator.py
```

**Obligations Covered:**
- `cache.stale.while.revalidate` (NEW)
- `resilience.graceful.degradation` (existing, reinforced)

---

### 2. `protocol-header-validation` (PROPOSED)

**Rationale:** INS-010 and INS-012 relate to HTTP header correctness, which is foundational but not explicitly covered.

**Proposed Structure:**
```
packs/protocol-header-validation/
├── pack.yaml
├── recipes/
│   ├── content_length_match.yaml
│   └── date_header_range.yaml
└── snippets/
    └── header_validator.py
```

**Obligations Covered:**
- `protocol.content.length` (existing, reinforced)
- `protocol.date.header.valid` (NEW)

---

## Obligations Gaining Stronger Evidence

| Obligation | Previous Evidence | New Evidence | Total | Status |
|------------|-------------------|--------------|-------|--------|
| `resilience.graceful.degradation` | Moderate | +70 tests | Strong | **Significantly reinforced** |
| `observability.access.logged` | Moderate | +35 tests | Strong | **Significantly reinforced** |
| `protocol.content.length` | Low | +15 tests | Moderate | Reinforced |
| `cache.key.stability` | Low | +12 tests | Moderate | Reinforced |
| `resilience.retry.bounded` | Low | +8 tests | Moderate | Reinforced |
| `routing.healthcheck.respect` | Low | +6 tests | Moderate | Reinforced |
| `cache.vary.honored` | Low | +6 tests | Moderate | Reinforced |
| `state.ratelimit.enforced` | Low | +5 tests | Moderate | Reinforced |

---

## New Obligations to Create

### 1. `cache.stale.while.revalidate`

```yaml
id: cache.stale.while.revalidate
title: Stale-While-Revalidate Behavior
description: During revalidation, serve stale content to concurrent requests while one request refreshes cache
risk: high
safe_in_prod: true

required_signals:
  - Cache status header (X-Cache or equivalent)
  - Origin request count during SWR window
  - Response Age header

pass_criteria:
  - Only ONE request goes to origin during SWR window
  - Concurrent requests receive stale content with Warning header
  - Fresh content served after revalidation completes

suggested_checks:
  - name: swr_single_origin_request
    method: concurrent_http
  - name: swr_stale_response_validation
    method: header_check

evidence_to_capture:
  - Origin request timestamps
  - Cache status per response
  - Warning headers
```

### 2. `protocol.date.header.valid`

```yaml
id: protocol.date.header.valid
title: Date Header Validity
description: Date header in responses must be within valid time range
risk: medium
safe_in_prod: true

required_signals:
  - Response Date header
  - Request timestamp
  - Response timestamp

pass_criteria:
  - Date header >= request start time
  - Date header <= response end time
  - Date header format is RFC 1123 compliant

suggested_checks:
  - name: date_header_range
    method: timestamp_comparison
  - name: date_header_format
    method: regex

evidence_to_capture:
  - Request start timestamp
  - Response Date header value
  - Response end timestamp
```

---

## Action Items (DO NOT EXECUTE - REVIEW ONLY)

1. [ ] Review proposed pack extensions with team
2. [ ] Decide on new pack creation (`cache-staleness-behavior`, `protocol-header-validation`)
3. [ ] Create new obligations if approved
4. [ ] Update existing obligation evidence references

---

## Verification Checklist

- [x] No existing packs modified
- [x] No existing obligations weakened
- [x] All proposals based on multi-source evidence
- [x] Environment-specific patterns excluded from pack proposals
