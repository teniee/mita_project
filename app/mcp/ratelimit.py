"""In-process sliding-window rate limits.

Per replica, by design: the MCP service is stateless and these limits exist to
stop a runaway client or a credential-stuffing burst, not to meter usage. The
shared account lockout (5 failures → 30 min, in the database) is what bounds
password guessing across replicas.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from typing import Deque, Dict, Optional

MAX_TRACKED_KEYS = 50_000


class SlidingWindowLimiter:
    def __init__(self, limit: int, window_seconds: float = 60.0) -> None:
        self.limit = limit
        self.window = window_seconds
        self._hits: Dict[str, Deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str, *, now: Optional[float] = None) -> bool:
        now = time.monotonic() if now is None else now
        cutoff = now - self.window
        with self._lock:
            if len(self._hits) > MAX_TRACKED_KEYS:
                self._evict(cutoff)
            hits = self._hits[key]
            while hits and hits[0] <= cutoff:
                hits.popleft()
            if len(hits) >= self.limit:
                return False
            hits.append(now)
            return True

    def _evict(self, cutoff: float) -> None:
        for key in [k for k, v in self._hits.items() if not v or v[-1] <= cutoff]:
            del self._hits[key]

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


def client_ip_from_headers(
    forwarded_for: str, peer: Optional[str], trusted_hops: int
) -> str:
    """Client address behind ``trusted_hops`` proxies (Railway adds one).

    Only the entry the trusted proxy appended is used: everything to its left
    is client-supplied and can be forged.
    """
    hops = [p.strip() for p in (forwarded_for or "").split(",") if p.strip()]
    if trusted_hops > 0 and len(hops) >= trusted_hops:
        return hops[-trusted_hops]
    return peer or "unknown"


class OAuthEndpointRateLimit:
    """Per-IP limit on the unauthenticated OAuth endpoints (/register, /token,
    /authorize, /revoke). Dynamic client registration in particular is open
    to the internet; without this, anyone could fill mcp_oauth_clients."""

    PATHS = ("/register", "/token", "/authorize", "/revoke")

    def __init__(self, app, *, per_minute: int, trusted_hops: int) -> None:
        self.app = app
        self.trusted_hops = trusted_hops
        self.limiters = {path: SlidingWindowLimiter(per_minute) for path in self.PATHS}

    async def __call__(self, scope, receive, send) -> None:
        limiter = (
            self.limiters.get(scope.get("path", ""))
            if scope["type"] == "http"
            else None
        )
        if limiter is not None:
            headers = dict(scope.get("headers") or [])
            ip = client_ip_from_headers(
                headers.get(b"x-forwarded-for", b"").decode("latin-1"),
                (scope.get("client") or (None,))[0],
                self.trusted_hops,
            )
            if not limiter.allow(ip):
                body = (
                    b'{"error":"rate_limited","error_description":"Too many requests"}'
                )
                await send(
                    {
                        "type": "http.response.start",
                        "status": 429,
                        "headers": [
                            (b"content-type", b"application/json"),
                            (b"retry-after", b"60"),
                            (b"cache-control", b"no-store"),
                            (b"content-length", str(len(body)).encode()),
                        ],
                    }
                )
                await send({"type": "http.response.body", "body": body})
                return
        await self.app(scope, receive, send)
