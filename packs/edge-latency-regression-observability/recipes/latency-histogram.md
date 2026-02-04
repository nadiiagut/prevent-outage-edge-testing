# Latency Histogram Observability Recipe

Configure Prometheus histograms for latency tracking and regression detection.

## Metrics

### Request Latency Histogram

```yaml
- name: http_request_duration_seconds
  type: histogram
  help: HTTP request latency in seconds
  labels:
    - method
    - path
    - status_code
  buckets:
    - 0.005   # 5ms
    - 0.01    # 10ms
    - 0.025   # 25ms
    - 0.05    # 50ms
    - 0.1     # 100ms
    - 0.25    # 250ms
    - 0.5     # 500ms
    - 1.0     # 1s
    - 2.5     # 2.5s
    - 5.0     # 5s
    - 10.0    # 10s
```

### Syscall Latency (from DTrace/eBPF)

```yaml
- name: syscall_duration_microseconds
  type: histogram
  help: Syscall latency in microseconds
  labels:
    - syscall
    - process
  buckets:
    - 1
    - 5
    - 10
    - 50
    - 100
    - 500
    - 1000
    - 5000
    - 10000
```

### Connection Establishment

```yaml
- name: tcp_connection_duration_seconds
  type: histogram
  help: TCP connection establishment time
  labels:
    - remote_host
    - tls
  buckets:
    - 0.001
    - 0.005
    - 0.01
    - 0.025
    - 0.05
    - 0.1
    - 0.25
    - 0.5
    - 1.0
```

## Percentile Queries

### P99 Latency

```promql
histogram_quantile(0.99, 
  sum(rate(http_request_duration_seconds_bucket[5m])) by (le, path)
)
```

### P99/P50 Ratio (Latency Spread)

```promql
histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))
/
histogram_quantile(0.50, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))
```

## Alerts

### P99 Latency Regression

```yaml
alert: P99LatencyRegression
expr: |
  histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket[5m])) by (le, path))
  >
  1.5 * histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket[5m] offset 1d)) by (le, path))
for: 10m
labels:
  severity: warning
annotations:
  summary: P99 latency 50% higher than yesterday
  description: "Path {{ $labels.path }} P99 is {{ $value | humanizeDuration }}"
```

### Latency SLO Breach

```yaml
alert: LatencySLOBreach
expr: |
  histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))
  > 0.5
for: 5m
labels:
  severity: critical
annotations:
  summary: P99 latency exceeds 500ms SLO
```

### Latency Spread Warning

```yaml
alert: HighLatencySpread
expr: |
  histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))
  /
  histogram_quantile(0.50, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))
  > 20
for: 10m
labels:
  severity: warning
annotations:
  summary: P99/P50 ratio exceeds 20x
  description: High tail latency variance indicates inconsistent performance
```

## Grafana Dashboard Panels

### Latency Heatmap

```json
{
  "type": "heatmap",
  "title": "Request Latency Heatmap",
  "targets": [
    {
      "expr": "sum(increase(http_request_duration_seconds_bucket[1m])) by (le)",
      "format": "heatmap",
      "legendFormat": "{{le}}"
    }
  ],
  "yAxis": {
    "format": "s",
    "logBase": 2
  },
  "color": {
    "mode": "spectrum",
    "scheme": "Oranges"
  }
}
```

### Percentile Time Series

```json
{
  "type": "timeseries",
  "title": "Latency Percentiles",
  "targets": [
    {
      "expr": "histogram_quantile(0.50, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))",
      "legendFormat": "P50"
    },
    {
      "expr": "histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))",
      "legendFormat": "P95"
    },
    {
      "expr": "histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))",
      "legendFormat": "P99"
    }
  ],
  "fieldConfig": {
    "defaults": {
      "unit": "s"
    }
  }
}
```

## Implementation Notes

- Use histogram over summary for better aggregation across instances
- Choose bucket boundaries based on your SLOs (more buckets near SLO threshold)
- Consider high-cardinality labels carefully (path normalization)
- For DTrace/eBPF data, export via node_exporter textfile collector
