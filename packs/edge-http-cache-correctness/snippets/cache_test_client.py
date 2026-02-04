# cache_test_client.py
# HTTP client with cache inspection helpers for testing cache correctness.
"""
Provides a CacheTestClient that wraps httpx with cache-specific utilities:
- Parse and validate Cache-Status headers (RFC 9211)
- Track cache hit/miss sequences
- Generate conditional requests automatically
- Validate Vary header compliance

Usage:
    client = CacheTestClient(base_url="https://edge.example.com")
    
    # Simple cache test
    r1 = client.get("/resource")
    assert r1.cache_status.hit is False  # Initial miss
    
    r2 = client.get("/resource")
    assert r2.cache_status.hit is True   # Should be cached
    
    # Conditional request
    r3 = client.conditional_get("/resource", etag=r1.headers["ETag"])
    assert r3.status_code == 304
"""

from dataclasses import dataclass
from typing import Optional
import re

import httpx


@dataclass
class CacheStatus:
    """Parsed Cache-Status header (RFC 9211)."""
    
    raw: str
    hit: bool = False
    fwd: Optional[str] = None  # miss, stale, request, etc.
    fwd_status: Optional[int] = None
    stored: bool = False
    collapsed: bool = False
    ttl: Optional[int] = None
    key: Optional[str] = None
    detail: Optional[str] = None
    
    @classmethod
    def parse(cls, header: Optional[str]) -> "CacheStatus":
        """Parse Cache-Status header value."""
        if not header:
            return cls(raw="", hit=False)
        
        status = cls(raw=header)
        
        # Check for hit
        status.hit = "hit" in header.lower() and "fwd=" not in header.lower()
        
        # Parse fwd parameter
        fwd_match = re.search(r'fwd=(\w+)', header)
        if fwd_match:
            status.fwd = fwd_match.group(1)
        
        # Parse fwd-status
        fwd_status_match = re.search(r'fwd-status=(\d+)', header)
        if fwd_status_match:
            status.fwd_status = int(fwd_status_match.group(1))
        
        # Parse stored
        status.stored = "stored" in header.lower()
        
        # Parse collapsed
        status.collapsed = "collapsed" in header.lower()
        
        # Parse ttl
        ttl_match = re.search(r'ttl=(\d+)', header)
        if ttl_match:
            status.ttl = int(ttl_match.group(1))
        
        # Parse detail
        detail_match = re.search(r'detail="([^"]*)"', header)
        if detail_match:
            status.detail = detail_match.group(1)
        
        return status


@dataclass
class CacheResponse:
    """HTTP response with cache inspection."""
    
    response: httpx.Response
    cache_status: CacheStatus
    
    @property
    def status_code(self) -> int:
        return self.response.status_code
    
    @property
    def headers(self) -> httpx.Headers:
        return self.response.headers
    
    @property
    def content(self) -> bytes:
        return self.response.content
    
    @property
    def text(self) -> str:
        return self.response.text
    
    @property
    def elapsed(self):
        return self.response.elapsed
    
    def is_cache_hit(self) -> bool:
        """Check if response was served from cache."""
        return self.cache_status.hit
    
    def is_stale(self) -> bool:
        """Check if response was stale."""
        return self.cache_status.fwd == "stale"


class CacheTestClient:
    """HTTP client for cache testing."""
    
    def __init__(
        self,
        base_url: str,
        timeout: float = 30.0,
        cache_status_header: str = "Cache-Status",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.cache_status_header = cache_status_header
        self._client = httpx.Client(timeout=timeout)
        self._request_history: list[CacheResponse] = []
    
    def _wrap_response(self, response: httpx.Response) -> CacheResponse:
        """Wrap httpx response with cache inspection."""
        cache_header = response.headers.get(self.cache_status_header)
        cache_status = CacheStatus.parse(cache_header)
        wrapped = CacheResponse(response=response, cache_status=cache_status)
        self._request_history.append(wrapped)
        return wrapped
    
    def get(
        self,
        path: str,
        headers: Optional[dict] = None,
        **kwargs,
    ) -> CacheResponse:
        """Send GET request and return wrapped response."""
        url = f"{self.base_url}{path}"
        response = self._client.get(url, headers=headers, **kwargs)
        return self._wrap_response(response)
    
    def conditional_get(
        self,
        path: str,
        etag: Optional[str] = None,
        last_modified: Optional[str] = None,
        **kwargs,
    ) -> CacheResponse:
        """Send conditional GET with If-None-Match or If-Modified-Since."""
        headers = kwargs.pop("headers", {}) or {}
        
        if etag:
            headers["If-None-Match"] = etag
        if last_modified:
            headers["If-Modified-Since"] = last_modified
        
        return self.get(path, headers=headers, **kwargs)
    
    def get_with_vary(
        self,
        path: str,
        accept_encoding: Optional[str] = None,
        accept_language: Optional[str] = None,
        user_agent: Optional[str] = None,
        **kwargs,
    ) -> CacheResponse:
        """Send GET with Vary-related headers."""
        headers = kwargs.pop("headers", {}) or {}
        
        if accept_encoding:
            headers["Accept-Encoding"] = accept_encoding
        if accept_language:
            headers["Accept-Language"] = accept_language
        if user_agent:
            headers["User-Agent"] = user_agent
        
        return self.get(path, headers=headers, **kwargs)
    
    def clear_history(self) -> None:
        """Clear request history."""
        self._request_history.clear()
    
    def get_hit_ratio(self) -> float:
        """Calculate cache hit ratio from history."""
        if not self._request_history:
            return 0.0
        hits = sum(1 for r in self._request_history if r.is_cache_hit())
        return hits / len(self._request_history)
    
    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._client.close()
    
    def __enter__(self) -> "CacheTestClient":
        return self
    
    def __exit__(self, *args) -> None:
        self.close()


# Example usage
if __name__ == "__main__":
    # This is an example - adjust URL for your environment
    with CacheTestClient(base_url="http://localhost:8080") as client:
        # Test cache population
        r1 = client.get("/test-resource")
        print(f"First request: hit={r1.is_cache_hit()}, status={r1.cache_status.raw}")
        
        # Test cache hit
        r2 = client.get("/test-resource")
        print(f"Second request: hit={r2.is_cache_hit()}, status={r2.cache_status.raw}")
        
        # Test conditional
        if "ETag" in r1.headers:
            r3 = client.conditional_get("/test-resource", etag=r1.headers["ETag"])
            print(f"Conditional: status_code={r3.status_code}")
        
        print(f"Overall hit ratio: {client.get_hit_ratio():.1%}")
