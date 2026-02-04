# CDN/Edge Proxy Obligation Taxonomy

A portable set of obligations that CDN and edge proxy systems must satisfy.

## Domains

| Domain | Description | Count |
|--------|-------------|-------|
| [routing](routing/) | Request routing, backend selection | 3 |
| [cache](cache/) | Cache behavior, keys, TTL | 2 |
| [protocol](protocol/) | HTTP compliance, status codes | 2 |
| [security](security/) | TLS, mTLS, client identity | 3 |
| [resilience](resilience/) | Timeouts, retries, circuit breakers | 3 |
| [observability](observability/) | Logs, metrics, tracing | 2 |
| [state](state/) | Session tables, config reload | 2 |

## Obligation Index

### routing

| ID | Title | Risk |
|----|-------|------|
| [routing.backend.selection](routing/backend.selection.yaml) | Backend Selection Consistency | high |
| [routing.fanout.bound](routing/fanout.bound.yaml) | Request Fanout is Bounded | high |
| [routing.healthcheck.respect](routing/healthcheck.respect.yaml) | Unhealthy Backends Not Selected | high |

### cache

| ID | Title | Risk |
|----|-------|------|
| [cache.key.stability](cache/key.stability.yaml) | Cache Key Stability | high |
| [cache.vary.honored](cache/vary.honored.yaml) | Vary Header Honored | high |

### protocol

| ID | Title | Risk |
|----|-------|------|
| [protocol.http.status](protocol/http.status.yaml) | HTTP Status Code Accuracy | high |
| [protocol.content.length](protocol/content.length.yaml) | Content-Length Accuracy | high |

### security

| ID | Title | Risk |
|----|-------|------|
| [security.tls.chain.valid](security/tls.chain.valid.yaml) | TLS Certificate Chain Valid | high |
| [security.mtls.client.verified](security/mtls.client.verified.yaml) | mTLS Client Certificate Verified | high |
| [security.client.ip.preserved](security/client.ip.preserved.yaml) | True Client IP Preserved | medium |

### resilience

| ID | Title | Risk |
|----|-------|------|
| [resilience.timeout.enforced](resilience/timeout.enforced.yaml) | Timeout Enforcement | high |
| [resilience.retry.bounded](resilience/retry.bounded.yaml) | Retry Count Bounded | high |
| [resilience.graceful.degradation](resilience/graceful.degradation.yaml) | Graceful Degradation | high |

### observability

| ID | Title | Risk |
|----|-------|------|
| [observability.access.logged](observability/access.logged.yaml) | Access Logs Complete | high |
| [observability.metrics.exposed](observability/metrics.exposed.yaml) | Metrics Endpoint Available | medium |

### state

| ID | Title | Risk |
|----|-------|------|
| [state.config.reload.atomic](state/config.reload.atomic.yaml) | Config Reload Atomic | high |
| [state.ratelimit.enforced](state/ratelimit.enforced.yaml) | Rate Limits Enforced | high |

## Usage

Each obligation file defines:
- **pass_criteria**: What must be true for the obligation to pass
- **suggested_checks**: How to verify the obligation
- **required_signals**: What data/access is needed
- **evidence_to_capture**: What to save for debugging failures

## Adding New Obligations

1. Create `obligations/<domain>/<obligation_id>.yaml`
2. Follow the schema in existing files
3. Update this index
