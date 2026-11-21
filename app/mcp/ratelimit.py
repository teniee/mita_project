"""In-process sliding-window rate limits.

Per replica, by design: the MCP service is stateless and these limits exist to
stop a runaway client or a credential-stuffing burst, not to meter usage. The
shared account lockout (5 failures → 30 min, in the database) is what bounds
password guessing across replicas.
"""

from __future__ import annotations

import ipaddress
import threading
import time
from collections import defaultdict, deque
from typing import Deque, Dict, Iterable, Optional, Tuple

MAX_TRACKED_KEYS = 50_000
# The one bucket for every request whose client-address header is present but
# repeated or not one IP address: Railway's edge always writes exactly one
# valid value, so such a request did not come from it, and it must not be
# able to pick a bucket of its own.
UNUSABLE_CLIENT_ADDRESS = "unusable-client-address-header"


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


def _ip_key(value: str) -> Optional[str]:
    """One IP address in canonical form, or None. An IPv4 address written as
    IPv6 (``::ffff:a.b.c.d``) is that IPv4 address: one client, one bucket."""
    try:
        ip = ipaddress.ip_address(value.strip())
    except ValueError:
        return None
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        return str(ip.ipv4_mapped)
    return str(ip)


def client_address(
    headers: Iterable[Tuple[bytes, bytes]], peer: Optional[str], trusted_header: str
) -> str:
    """The address a per-IP limit counts a request against.

    ``trusted_header`` is the header the proxy in front writes over whatever
    the client sent. Railway's HTTP edge sets ``X-Real-IP`` to the client's
    address (docs.railway.com, "Specs & Limits"); on staging it replaced forged,
    repeated, comma-separated and IPv6 values alike. ``X-Forwarded-For`` is
    never read: Railway sends it as "<client>, <edge address>", and the edge
    address changes from request to request; counting by it spread one client
    over a bucket per edge address and put everyone behind one edge address
    in the same bucket.

    A request without the header did not come through the edge (a local run,
    a test, the private network) and counts against ``peer``, the TCP peer,
    which uvicorn does not rewrite from forwarded headers (``__main__.py``).
    A header that is present but repeated or not one IP address is not
    Railway's: all such requests share ``UNUSABLE_CLIENT_ADDRESS``.
    """
    if trusted_header:
        name = trusted_header.encode("latin-1")
        values = [value for key, value in headers if key.lower() == name]
        if values:
            key = _ip_key(values[0].decode("latin-1")) if len(values) == 1 else None
            return key or UNUSABLE_CLIENT_ADDRESS
    if not peer:
        return "unknown"
    return _ip_key(peer) or peer


class OAuthEndpointRateLimit:
    """Per-IP limit on the unauthenticated OAuth endpoints (/register, /token,
    /authorize, /revoke). Dynamic client registration in particular is open
    to the internet; without this, anyone could fill mcp_oauth_clients."""

    PATHS = ("/register", "/token", "/authorize", "/revoke")

    def __init__(self, app, *, per_minute: int, client_ip_header: str) -> None:
        self.app = app
        self.client_ip_header = client_ip_header
        self.limiters = {path: SlidingWindowLimiter(per_minute) for path in self.PATHS}

    async def __call__(self, scope, receive, send) -> None:
        limiter = (
            self.limiters.get(scope.get("path", ""))
            if scope["type"] == "http"
            else None
        )
        if limiter is not None:
            ip = client_address(
                scope.get("headers") or [],
                (scope.get("client") or (None,))[0],
                self.client_ip_header,
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
