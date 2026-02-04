# POET Demo Environment

A minimal NGINX edge proxy setup for testing POET obligations.

## Architecture

```
                    ┌─────────────┐
                    │   Client    │
                    └──────┬──────┘
                           │ :8080
                    ┌──────▼──────┐
                    │  NGINX Edge │
                    │   (proxy)   │
                    └──────┬──────┘
           ┌───────────────┼───────────────┐
           │               │               │
    ┌──────▼──────┐ ┌──────▼──────┐ ┌──────▼──────┐
    │  upstream1  │ │  upstream2  │ │   faulty    │
    │  (healthy)  │ │  (healthy)  │ │ (503/slow)  │
    └─────────────┘ └─────────────┘ └─────────────┘
```

## Quick Start

```bash
# Start the demo environment
make up

# Run basic tests
make test

# View logs
make logs

# Stop
make down
```

## Endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /` | Load-balanced to upstream1 or upstream2 |
| `GET /echo?key=value` | Echo request details, consistent hash routing |
| `GET /cached/` | Cached responses (60s TTL) |
| `GET /faulty/` | Routes to faulty upstream (503 errors) |
| `GET /health` | Health check |
| `GET /metrics` | Prometheus metrics stub |

## Testing Obligations

### routing.backend.selection

Same URL should route to same backend:

```bash
# All 5 requests should show same server
for i in {1..5}; do
  curl -s http://localhost:8080/echo?key=test1 | jq -r .server
done
```

### protocol.http.status

Faulty endpoint returns 503:

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8080/faulty/
# Expected: 503
```

### resilience.timeout.enforced

Slow endpoint triggers timeout:

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8080/faulty/slow
# Expected: 504
```

## Response Headers

The edge proxy adds these headers for observability:

- `X-Backend-Server`: IP:port of selected upstream
- `X-Request-ID`: Unique request identifier
- `X-Upstream-ID`: Name of upstream that served the request
