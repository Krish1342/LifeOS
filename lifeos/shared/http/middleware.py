import time

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    In-memory token bucket rate limiter and response latency tracker.
    Protects Orchestrator endpoints from denial of service and API flooding.
    """

    def __init__(self, app, max_requests: int = 120, window_seconds: float = 60.0):
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._clients: dict[str, tuple[int, float]] = {}  # ip -> (count, window_start)

    def _is_rate_limited(self, ip: str) -> bool:
        now = time.time()
        count, window_start = self._clients.get(ip, (0, now))

        if now - window_start > self.window_seconds:
            # Window expired, reset
            self._clients[ip] = (1, now)
            return False

        if count >= self.max_requests:
            return True

        self._clients[ip] = (count + 1, window_start)
        return False

    async def dispatch(self, request: Request, call_next) -> Response:
        client_ip = request.client.host if request.client else "127.0.0.1"

        # Rate check
        if self._is_rate_limited(client_ip):
            return JSONResponse(
                status_code=429,
                content={"error": "Too Many Requests", "message": "Rate limit exceeded. Please slow down."}
            )

        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        response.headers["X-Response-Time-Ms"] = str(elapsed_ms)
        return response
