# Cache Metrics Observability Recipe

Prometheus/OpenMetrics configuration for monitoring HTTP cache correctness.

## Metrics

### Cache Hit Ratio

```yaml
- name: http_cache_hits_total
  type: counter
  help: Total cache hits by status
  labels:
    - cache_status  # hit, miss, stale, revalidated
    - content_type
    - pop           # Point of presence

- name: http_cache_hit_ratio
  type: gauge
  help: Cache hit ratio (computed)
  labels:
    - pop
```

### Revalidation Metrics

```yaml
- name: http_cache_revalidations_total
  type: counter
  help: Cache revalidation attempts
  labels:
    - result  # success, origin_error, timeout

- name: http_cache_stale_served_total
  type: counter
  help: Stale content served due to origin issues
  labels:
    - reason  # stale_while_revalidate, stale_if_error
```

### Vary Header Metrics

```yaml
- name: http_cache_vary_splits_total
  type: counter
  help: Cache entries split by Vary header
  labels:
    - vary_header  # accept-encoding, accept-language, etc.
```

## Alerts

### Low Cache Hit Ratio

```yaml
alert: CacheHitRatioLow
expr: |
  sum(rate(http_cache_hits_total{cache_status="hit"}[5m])) /
  sum(rate(http_cache_hits_total[5m])) < 0.7
for: 10m
labels:
  severity: warning
annotations:
  summary: Cache hit ratio below 70%
  description: Cache hit ratio is {{ $value | humanizePercentage }}
```

### High Stale Serving Rate

```yaml
alert: StaleServingRateHigh
expr: |
  rate(http_cache_stale_served_total[5m]) > 100
for: 5m
labels:
  severity: high
annotations:
  summary: High rate of stale content being served
  description: Serving {{ $value }} stale responses/second
```

### Revalidation Failures

```yaml
alert: RevalidationFailureSpike
expr: |
  rate(http_cache_revalidations_total{result="origin_error"}[5m]) /
  rate(http_cache_revalidations_total[5m]) > 0.1
for: 5m
labels:
  severity: high
annotations:
  summary: >10% of revalidations failing
```

## Grafana Dashboard

```json
{
  "panels": [
    {
      "title": "Cache Hit Ratio",
      "type": "gauge",
      "targets": [
        {
          "expr": "http_cache_hit_ratio",
          "legendFormat": "{{ pop }}"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "thresholds": {
            "steps": [
              {"color": "red", "value": 0},
              {"color": "yellow", "value": 0.7},
              {"color": "green", "value": 0.9}
            ]
          },
          "unit": "percentunit"
        }
      }
    }
  ]
}
```

## Implementation Notes

- Collect metrics at the edge proxy (Nginx, Varnish, HAProxy, Envoy)
- Use `Cache-Status` header (RFC 9211) for detailed cache state
- Sample high-volume endpoints to avoid metric cardinality explosion
