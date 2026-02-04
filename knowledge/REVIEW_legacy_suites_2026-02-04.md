# Human Review Summary: Legacy Test Suite Knowledge Extraction

**Date:** 2026-02-04  
**Sources:** Two internal CDN edge proxy test suites (17,721 tests total)  
**Method:** Static analysis only (no test execution)

---

## Executive Summary

Extracted **15 reusable insights** from two CDN edge proxy test suites. **8 reinforce existing obligations**, **2 are new candidates**, and **5 were intentionally not generalized**.

**No contradictions found** between the two suites - they test complementary aspects of edge proxy behavior.

---

## New Knowledge Added

### Proposed New Obligations

| ID | Title | Evidence | Confidence |
|----|-------|----------|------------|
| INS-004 | **Stale-While-Revalidate** | Suite B: 8 tests | HIGH |
| INS-012 | **Cache Date Header Validation** | Suite A: 12 tests | HIGH |

**INS-004: Stale-While-Revalidate**
- **Invariant:** During SWR window, only ONE request should go to origin; others get stale content
- **Failure mode defended:** Origin thundering herd on cache expiry
- **Recommendation:** Create new obligation `cache.stale.while.revalidate`

**INS-012: Cache Date Header Validation**
- **Invariant:** Date header MUST be between request start and response end times
- **Failure mode defended:** Clock skew causing cache invalidation issues
- **Recommendation:** Create new obligation `protocol.date.header.valid`

---

## Existing Knowledge Reinforced

| Obligation | Insights | Total Evidence |
|------------|----------|----------------|
| `resilience.graceful.degradation` | INS-001, INS-005, INS-011 | 70+ tests |
| `resilience.retry.bounded` | INS-008 | 8 tests |
| `routing.healthcheck.respect` | INS-007 | 6 tests |
| `state.ratelimit.enforced` | INS-002 | 5 tests |
| `observability.access.logged` | INS-009, INS-015 | 35 tests |
| `protocol.content.length` | INS-010 | 15 tests |
| `cache.key.stability` | INS-003 | 12 tests |
| `cache.vary.honored` | INS-006 | 6 tests |

### Strongest Reinforcement: `resilience.graceful.degradation`

Three independent insights from both suites converge on this obligation:
1. **Backup origin failover** (Suite A: 47 tests)
2. **Override 5xx with cached content** (Suite B: 3 tests)
3. **Stale on not found** (Suite A: 20 tests)

---

## Intentionally Not Generalized

| Item | Reason |
|------|--------|
| DSCP Value Configuration | Network-specific QoS marking |
| Unix Socket Helpers | Internal architecture-specific |
| Custom Rule Execution Timing | Implementation-specific |
| Bloom Filter Hit Count | Implementation-specific cache optimization |
| Piggyback Tries Configuration | Implementation-specific cache fill |

These are **historical reference only** - valuable for understanding specific systems but not portable.

---

## Contradictions Found

**None.** The two suites test complementary aspects:
- **Suite A:** Heavy focus on rewrite rules, failover chains, access logging
- **Suite B:** Heavy focus on cache behavior, stale handling, async patterns

---

## Quality Bar Verification

| Criterion | Status |
|-----------|--------|
| No existing knowledge weakened | ✅ PASS |
| Every reusable rule has ≥2 locations OR very strong single evidence | ✅ PASS |
| Contradictions preserved, not normalized | ✅ PASS (none found) |
| Uncertainty explicit | ✅ PASS |

---

## Recommended Actions

1. **Create** obligation `cache.stale.while.revalidate` based on INS-004
2. **Create** obligation `protocol.date.header.valid` based on INS-012
3. **Update** `resilience.graceful.degradation` with specific mechanisms from INS-001, INS-005, INS-011
4. **Review** pack `edge-latency-regression-observability` for SWR timing patterns
