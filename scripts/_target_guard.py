"""Fail-closed guard: automated suites must never create data in production.

Production accumulated 78+ synthetic accounts and irreversible ledger drift because
the E2E and smoke scripts defaulted to the live Railway host. Any script or test
that registers a user, submits onboarding, or writes financial data must route its
target through :func:`assert_writable_target`, which refuses to return unless the
caller supplied an explicit, non-production URL.

There is deliberately NO override for write targets. A flag that can be set is a
flag that gets set in CI. Read-only probes against production (health, version)
are still fine - use :func:`is_production` and keep the request read-only.
"""

from __future__ import annotations

import os
from urllib.parse import urlparse

__all__ = [
    "PRODUCTION_HOSTS",
    "ProductionTargetError",
    "is_production",
    "assert_writable_target",
    "writable_target_from_env",
]

# Exact hostnames, matched case-insensitively after stripping a trailing dot.
# Substring matching is deliberately avoided: it both over-matches (a staging host
# containing the string) and under-matches (a new alias). Add aliases here.
PRODUCTION_HOSTS = frozenset(
    {
        "mita-production-production.up.railway.app",
        "mita-production.up.railway.app",
        "mitafinance.com",
        "www.mitafinance.com",
        "api.mitafinance.com",
    }
)

ENV_VAR = "MITA_TEST_BASE_URL"


class ProductionTargetError(RuntimeError):
    """Raised when an automated writer is pointed at production, or at nothing."""


def _host_of(base_url: str) -> str:
    parsed = urlparse(base_url.strip())
    if not parsed.scheme or not parsed.netloc:
        raise ProductionTargetError(
            f"Not a usable base URL: {base_url!r}. "
            "Expected something like http://localhost:8000"
        )
    if parsed.scheme not in ("http", "https"):
        raise ProductionTargetError(
            f"Unsupported scheme {parsed.scheme!r} in {base_url!r}"
        )
    return (parsed.hostname or "").rstrip(".").lower()


def is_production(base_url: str) -> bool:
    """True when base_url points at a known production host."""
    try:
        return _host_of(base_url) in PRODUCTION_HOSTS
    except ProductionTargetError:
        return False


def assert_writable_target(base_url: str | None, *, purpose: str) -> str:
    """Return a normalised base URL that is safe to create data against.

    Fails closed on a missing, empty, malformed, or production target. `purpose`
    names the caller so the error says which suite was about to write.
    """
    if base_url is None or not str(base_url).strip():
        raise ProductionTargetError(
            f"{purpose} needs an explicit target and none was given.\n"
            f"Pass --base-url or set {ENV_VAR} to a disposable host "
            f"(local, ephemeral, or staging). There is no default: defaulting is "
            f"exactly how production accumulated synthetic accounts."
        )

    normalised = str(base_url).strip().rstrip("/")
    host = _host_of(normalised)

    if host in PRODUCTION_HOSTS:
        raise ProductionTargetError(
            f"{purpose} refuses to run against production ({host}).\n"
            f"This suite registers accounts and writes financial data; doing that "
            f"in production corrupts real ledgers and cannot be undone.\n"
            f"Point {ENV_VAR} at a disposable backend instead. This block has no "
            f"override by design."
        )
    return normalised


def writable_target_from_env(*, purpose: str) -> str:
    """Resolve a safe write target from the environment, or fail closed."""
    return assert_writable_target(os.environ.get(ENV_VAR), purpose=purpose)
