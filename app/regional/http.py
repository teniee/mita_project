"""Fetching from the official providers: timeouts, retries, spacing.

* timeouts on every request; retries with exponential backoff and jitter on
  429, 5xx, Eurostat's 413 ``ASYNCHRONOUS_RESPONSE`` and network errors;
  ``Retry-After`` honoured (bounded);
* one request at a time, with a minimum interval per provider (Eurostat
  asks for one extraction at a time; the OECD publishes a limit of 60 data
  downloads per hour — MITA stays far below it with one request per dataset);
* a fixed, honest ``User-Agent``; nothing about any user is ever sent — the
  URL carries only dataset codes, countries and periods.

The client is injectable so tests replay recorded real responses.
"""

from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, Optional

import httpx2

from app.regional.catalog import EUROSTAT, OECD, WORLD_BANK

logger = logging.getLogger("app.regional")

USER_AGENT = "MITA-Finance-regional-ingest/2.8 (official statistics, batch)"
ACCEPT_JSON = "application/json"
TIMEOUT_SECONDS = 60.0
MAX_ATTEMPTS = 4
MAX_RETRY_AFTER = 120.0
# Minimum seconds between two requests to the same provider.
MIN_INTERVAL = {EUROSTAT: 2.0, WORLD_BANK: 1.0, OECD: 75.0}
RETRYABLE = {413, 429, 500, 502, 503, 504}


class ProviderError(RuntimeError):
    """A provider did not answer usably after the retries."""


@dataclass
class Fetcher:
    client: Optional[httpx2.Client] = None
    sleep: Callable[[float], None] = time.sleep
    clock: Callable[[], float] = time.monotonic
    requests: int = 0
    _last: Dict[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.client is None:
            self.client = httpx2.Client(
                timeout=TIMEOUT_SECONDS,
                headers={"User-Agent": USER_AGENT},
                follow_redirects=False,
            )

    def _space(self, provider: str) -> None:
        last = self._last.get(provider)
        gap = MIN_INTERVAL.get(provider, 1.0)
        if last is not None:
            wait = gap - (self.clock() - last)
            if wait > 0:
                self.sleep(wait)

    def get(
        self, provider: str, url: str, *, headers: Optional[dict] = None
    ) -> httpx2.Response:
        error: Optional[str] = None
        for attempt in range(1, MAX_ATTEMPTS + 1):
            self._space(provider)
            self._last[provider] = self.clock()
            self.requests += 1
            try:
                response = self.client.get(url, headers=headers or {})
            except (httpx2.TimeoutException, httpx2.TransportError) as exc:
                error = type(exc).__name__
                response = None
            if response is not None:
                if response.status_code == 200:
                    return response
                error = f"HTTP {response.status_code}"
                if response.status_code not in RETRYABLE:
                    break
            if attempt == MAX_ATTEMPTS:
                break
            delay = min(60.0, 2.0**attempt) + random.uniform(0, 1)
            retry_after = response.headers.get("Retry-After") if response else None
            if retry_after and retry_after.isdigit():
                delay = max(delay, min(MAX_RETRY_AFTER, float(retry_after)))
            logger.warning(
                "regional fetch retry",
                extra={
                    "event": "regional_fetch_retry",
                    "provider": provider,
                    "attempt": attempt,
                    "reason": error,
                },
            )
            self.sleep(delay)
        raise ProviderError(f"{provider}: {error}")
