# Fault Injection Campaign Metrics

Prometheus metrics for tracking fault injection test campaigns.

## Metrics

### Injection Statistics

```yaml
- name: fault_injection_total
  type: counter
  help: Total faults injected
  labels:
    - fault_type   # eio, enospc, timeout, partial_write
    - target       # syscall or file pattern
    - campaign_id

- name: fault_injection_triggered_total
  type: counter
  help: Faults that were triggered (not skipped by probability)
  labels:
    - fault_type
    - target

- name: fault_injection_errors_handled_total
  type: counter
  help: Injected faults that application handled correctly
  labels:
    - fault_type
    - handling_result  # logged, retried, failed_gracefully, crashed
```

### Application Response

```yaml
- name: error_handling_latency_seconds
  type: histogram
  help: Time to handle injected error
  labels:
    - fault_type
    - handler
  buckets:
    - 0.001
    - 0.01
    - 0.1
    - 1.0
    - 10.0

- name: retry_attempts_total
  type: counter
  help: Retry attempts triggered by fault injection
  labels:
    - operation
    - final_result  # success, exhausted, timeout

- name: circuit_breaker_state_changes_total
  type: counter
  help: Circuit breaker state transitions during fault injection
  labels:
    - breaker_name
    - from_state
    - to_state
```

### Data Integrity

```yaml
- name: data_corruption_detected_total
  type: counter
  help: Data corruption incidents detected during fault campaign
  labels:
    - detection_method  # checksum, validation, reconciliation
    - severity         # recoverable, unrecoverable

- name: data_loss_bytes_total
  type: counter
  help: Bytes of data lost due to fault injection
  labels:
    - data_type
```

## Campaign Dashboard

### Fault Injection Rate

```promql
rate(fault_injection_triggered_total[5m])
```

### Error Handling Success Rate

```promql
sum(rate(fault_injection_errors_handled_total{handling_result=~"logged|retried|failed_gracefully"}[5m]))
/
sum(rate(fault_injection_errors_handled_total[5m]))
```

### Time to Recovery

```promql
histogram_quantile(0.99, 
  sum(rate(error_handling_latency_seconds_bucket[5m])) by (le, fault_type)
)
```

## Alerts

### Unhandled Fault Detected

```yaml
alert: FaultInjectionCausedCrash
expr: |
  increase(fault_injection_errors_handled_total{handling_result="crashed"}[5m]) > 0
for: 0m
labels:
  severity: critical
annotations:
  summary: Application crashed during fault injection
  description: "Fault type {{ $labels.fault_type }} caused crash"
```

### Data Corruption Detected

```yaml
alert: DataCorruptionDuringFaultTest
expr: |
  increase(data_corruption_detected_total[5m]) > 0
for: 0m
labels:
  severity: critical
annotations:
  summary: Data corruption detected during fault campaign
```

### Retry Exhaustion

```yaml
alert: RetryExhaustionHigh
expr: |
  rate(retry_attempts_total{final_result="exhausted"}[5m])
  /
  rate(retry_attempts_total[5m])
  > 0.1
for: 5m
labels:
  severity: warning
annotations:
  summary: >10% of operations exhausting retries
```

## Campaign Report Template

```markdown
# Fault Injection Campaign Report

## Campaign Details
- **ID**: {{ campaign_id }}
- **Duration**: {{ start_time }} - {{ end_time }}
- **Target Service**: {{ service_name }}

## Faults Injected
| Fault Type | Count | Triggered | Handled | Crashed |
|------------|-------|-----------|---------|---------|
| EIO        | {{ eio_total }} | {{ eio_triggered }} | {{ eio_handled }} | {{ eio_crashed }} |
| ENOSPC     | {{ enospc_total }} | {{ enospc_triggered }} | {{ enospc_handled }} | {{ enospc_crashed }} |
| Timeout    | {{ timeout_total }} | {{ timeout_triggered }} | {{ timeout_handled }} | {{ timeout_crashed }} |

## Error Handling Metrics
- **Success Rate**: {{ success_rate }}%
- **P99 Recovery Time**: {{ p99_recovery }}ms
- **Data Corruption Incidents**: {{ corruption_count }}

## Findings
{{ findings }}

## Recommendations
{{ recommendations }}
```

## Integration with CI/CD

```yaml
# Example GitHub Actions step
- name: Run Fault Injection Tests
  run: |
    poet build --jira-text "${{ github.event.pull_request.body }}"
    pytest generated/tests/ --fault-injection-mode=simulator
  env:
    POET_METRICS_ENDPOINT: ${{ secrets.PROMETHEUS_PUSHGATEWAY }}
```
