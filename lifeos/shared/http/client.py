import httpx
from urllib.parse import urlparse
from typing import Any, List, Optional


class SecurityError(Exception):
    """Raised when an outbound HTTP request violates sandbox boundary constraints."""
    pass


class ScopedHTTPClient:
    """
    HTTP client wrapper enforcing per-agent outbound domain allowlisting.
    Prevents unauthorized outbound connections from domain agents.
    """

    def __init__(
        self,
        allowed_hosts: List[str],
        timeout: float = 30.0,
        headers: Optional[dict] = None
    ):
        self.allowed_hosts = [h.lower() for h in allowed_hosts]
        self.timeout = timeout
        self.headers = headers or {}
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                headers=self.headers
            )
        return self._client

    def _verify_host(self, url: str) -> None:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        if not host:
            raise SecurityError(f"Cannot resolve host from URL: {url}")

        # Check exact host match or wildcard matching (e.g. *.supabase.co)
        matched = False
        for allowed in self.allowed_hosts:
            if allowed.startswith("*."):
                root_domain = allowed[2:]
                if host == root_domain or host.endswith("." + root_domain):
                    matched = True
                    break
            elif host == allowed:
                matched = True
                break

        if not matched:
            raise SecurityError(
                f"Security Boundary Violation: Host '{host}' is not in the allowed outbound whitelist for this agent: {self.allowed_hosts}"
            )

    async def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        self._verify_host(url)
        client = await self._get_client()
        return await client.request(method, url, **kwargs)

    async def get(self, url: str, **kwargs: Any) -> httpx.Response:
        return await self.request("GET", url, **kwargs)

    async def post(self, url: str, **kwargs: Any) -> httpx.Response:
        return await self.request("POST", url, **kwargs)

    async def patch(self, url: str, **kwargs: Any) -> httpx.Response:
        return await self.request("PATCH", url, **kwargs)

    async def delete(self, url: str, **kwargs: Any) -> httpx.Response:
        return await self.request("DELETE", url, **kwargs)

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
