# Edge HTTP Cache Correctness

Knowledge pack for validating HTTP caching behavior at edge servers (CDN, reverse proxy).

## Overview

This pack provides tests and observability recipes for common HTTP caching failure modes:

- **Vary Header Handling**: Ensure cache correctly splits responses based on `Vary` header
- **Conditional Requests**: Validate `If-None-Match` and `If-Modified-Since` behavior
- **Stale Content**: Test `stale-while-revalidate` and `stale-if-error` directives
- **Cache Key Correctness**: Detect cache key collisions and misconfigurations

## Failure Modes

| ID | Severity | Description |
|----|----------|-------------|
| `stale-on-revalidate-fail` | High | Stale content served indefinitely on origin failure |
| `vary-header-cache-split` | Critical | Wrong content served due to Vary header issues |
| `conditional-request-bypass` | Medium | 304 responses not generated for valid conditionals |
| `cache-key-collision` | Critical | Different resources sharing same cache key |

## Usage

```bash
# Generate tests for a caching feature
poet build --jira-text "Implement cache invalidation API with Vary support"

# View pack details
poet packs show edge-http-cache-correctness
```

## Test Templates

### Vary Accept-Encoding Test

Validates that the cache correctly splits responses based on `Accept-Encoding`:

```python
def test_vary_accept_encoding():
    # Request with gzip
    r1 = requests.get(url, headers={"Accept-Encoding": "gzip"})
    assert r1.headers.get("Content-Encoding") == "gzip"
    
    # Request without compression
    r2 = requests.get(url, headers={"Accept-Encoding": "identity"})
    assert r2.headers.get("Content-Encoding") != "gzip"
    
    # Both should be cache hits
    assert "hit" in r2.headers.get("X-Cache", "").lower()
```

### Conditional Request Test

Validates 304 Not Modified responses:

```python
def test_conditional_304():
    # Get resource and ETag
    r1 = requests.get(url)
    etag = r1.headers["ETag"]
    
    # Conditional request
    r2 = requests.get(url, headers={"If-None-Match": etag})
    assert r2.status_code == 304
    assert len(r2.content) == 0
```

## Recipes

- `cache-metrics.md`: Prometheus metrics for cache hit ratio, revalidation rate
- `vary-debugging.md`: Debugging Vary header issues

## Snippets

- `cache_test_client.py`: HTTP client with cache inspection helpers
- `vary_normalizer.py`: Vary header normalization utilities

## References

- [RFC 7234 - HTTP Caching](https://httpwg.org/specs/rfc7234.html)
- [MDN - HTTP Caching](https://developer.mozilla.org/en-US/docs/Web/HTTP/Caching)
- [Fastly - Vary Header Best Practices](https://www.fastly.com/blog/best-practices-using-vary-header)
