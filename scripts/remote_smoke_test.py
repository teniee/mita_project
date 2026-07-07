#!/usr/bin/env python3
"""Remote smoke test for a DEPLOYED MITA backend.

Runs the full closed-beta journey against a live base URL and fails loudly
on any contract violation:

    GET / and /health (incl. deployed commit, alembic revision, redis)
    -> register -> login -> onboarding (budget generation)
    -> create transaction -> saved calendar (today present, YYYY-MM-DD keys,
    every limit > 0, today's spent reflects the transaction) -> calendar day
    detail -> refresh token (rotation) -> old refresh token rejected
    -> rotated access token works -> logout -> access token rejected after
    logout -> 404 stays 404 -> bad credentials stay 4xx (never 500)
    -> security headers present -> plain HTTP does not serve the API.

Stdlib only (urllib) so it runs on a bare CI runner:

    python scripts/remote_smoke_test.py --base-url https://<deployed-host>

Exit code 0 = deployed backend serves the verified behavior.
Creates exactly one throwaway user per run (smoke.<timestamp>@mita-smoketest.dev).
"""

import argparse
import calendar as _calendar
import json
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

DATE_KEY = re.compile(r"^\d{4}-\d{2}-\d{2}$")
# Alembic head this repo ships; the deployed DB must match (drift detector).
EXPECTED_ALEMBIC = "0034"
RESULTS = []
LAST_HEADERS = {}


def record(name, ok, detail=""):
    RESULTS.append((name, ok, detail))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  — {detail}" if detail else ""))
    return ok


def info(name, detail):
    print(f"INFO  {name}  — {detail}")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def http(method, url, body=None, token=None, timeout=30, follow_redirects=True):
    """Return (status, parsed-json-or-None). Never raises on HTTP errors.

    Response headers of the last call land in LAST_HEADERS.
    """
    global LAST_HEADERS
    headers = {"Accept": "application/json"}
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    opener = (
        urllib.request.build_opener()
        if follow_redirects
        else urllib.request.build_opener(_NoRedirect())
    )
    try:
        with opener.open(req, timeout=timeout) as resp:
            raw = resp.read()
            status = resp.status
            # Lowercase keys: proxies (Railway edge) may lowercase names
            LAST_HEADERS = {k.lower(): v for k, v in resp.headers.items()}
    except urllib.error.HTTPError as e:
        raw = e.read()
        status = e.code
        LAST_HEADERS = (
            {k.lower(): v for k, v in e.headers.items()} if e.headers else {}
        )
    except Exception as e:  # network-level failure
        LAST_HEADERS = {}
        return 0, {"_transport_error": str(e)}
    try:
        return status, json.loads(raw) if raw else None
    except ValueError:
        return status, {"_raw": raw[:300].decode(errors="replace")}


def unwrap(payload):
    """The API wraps most bodies as {"success":.., "data": {...}}."""
    if (
        isinstance(payload, dict)
        and "data" in payload
        and isinstance(payload["data"], (dict, list))
    ):
        return payload["data"]
    return payload


def find_tokens(payload):
    """Locate access/refresh tokens regardless of wrapper nesting."""
    seen, stack = set(), [payload]
    while stack:
        node = stack.pop()
        if id(node) in seen or not isinstance(node, dict):
            continue
        seen.add(id(node))
        if "access_token" in node:
            return node.get("access_token"), node.get("refresh_token")
        stack.extend(v for v in node.values() if isinstance(v, dict))
    return None, None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    args = parser.parse_args()
    base = args.base_url.rstrip("/")

    now = datetime.now(timezone.utc)
    today_key = now.date().isoformat()
    # A real TLD — EmailStr rejects reserved special-use domains (.test etc.)
    email = f"smoke.{int(time.time())}@mita-smoketest.dev"
    password = "Sm0ke!Test#2026x"
    tx_amount = 23.75

    # 1-2. Liveness. On failure include the body — a Railway edge
    # "Application not found" is very different from an app-level 404.
    status, body = http("GET", f"{base}/")
    record("GET /", status == 200, f"status={status} body={str(body)[:200]}")
    root_headers = dict(LAST_HEADERS)
    status, health = http("GET", f"{base}/health")
    record("GET /health", status == 200, f"status={status} body={str(health)[:200]}")

    # 2b. Deployed-instance diagnostics (added to /health for remote
    # verification: commit provenance, migration head, dependency status).
    h = health if isinstance(health, dict) else {}
    cfg = h.get("config", {}) if isinstance(h.get("config"), dict) else {}
    info("deployed commit", h.get("commit", "<absent>"))
    info("environment", cfg.get("environment", "<absent>"))
    info("health status", h.get("status", "<absent>"))
    record(
        "health: database connected",
        h.get("database") == "connected",
        f"database={h.get('database')} error={h.get('database_error')}",
    )
    record(
        "health: alembic revision matches repo head",
        h.get("alembic_revision") == EXPECTED_ALEMBIC,
        f"deployed={h.get('alembic_revision', '<absent>')} expected={EXPECTED_ALEMBIC}",
    )
    record(
        "health: redis connected",
        h.get("redis") == "connected",
        f"redis={h.get('redis', '<absent>')}",
    )
    record(
        "health: environment is production",
        cfg.get("environment") == "production",
        f"environment={cfg.get('environment', '<absent>')}",
    )

    # 2c. Security headers on a real response.
    missing_headers = [
        name
        for name in (
            "strict-transport-security",
            "x-content-type-options",
            "x-frame-options",
            "content-security-policy",
        )
        if name not in root_headers
    ]
    record("security headers present", not missing_headers, f"missing={missing_headers}")

    # 2d. Docs surface: whatever the policy, it must never 500.
    status, _ = http("GET", f"{base}/docs")
    record(
        "GET /docs never 500 (policy: open or 404)",
        status in (200, 401, 403, 404),
        f"status={status}",
    )

    # 2e. Plain HTTP must not silently serve the API (redirect or refuse).
    if base.startswith("https://"):
        status, _ = http(
            "GET", "http://" + base[len("https://"):] + "/health",
            follow_redirects=False,
        )
        location = LAST_HEADERS.get("location", "") if LAST_HEADERS else ""
        record(
            "plain HTTP redirects to HTTPS or is refused",
            status in (0, 301, 302, 307, 308) and (status == 0 or location.startswith("https://")),
            f"status={status} location={location}",
        )

    # 3. Register
    status, body = http(
        "POST",
        f"{base}/api/auth/register",
        {
            "email": email,
            "password": password,
            "country": "US",
            "annual_income": 72000,
            "timezone": "UTC",
        },
    )
    access, refresh = find_tokens(body)
    if not record(
        "register returns token pair",
        status in (200, 201) and access and refresh,
        f"status={status}",
    ):
        finish()

    # 4. Login with the same credentials
    status, body = http(
        "POST", f"{base}/api/auth/login", {"email": email, "password": password}
    )
    la, lr = find_tokens(body)
    if record(
        "login returns token pair", status == 200 and la and lr, f"status={status}"
    ):
        access, refresh = la, lr

    # 5. Onboarding -> budget generation
    status, body = http(
        "POST",
        f"{base}/api/onboarding/submit",
        {
            "income": {"monthly_income": 6000.0, "additional_income": 0.0},
            "fixed_expenses": {"rent": 1500.0, "utilities": 200.0},
            "spending_habits": {"dining_out_per_month": 8},
            "goals": {"savings_goal_amount_per_month": 400.0},
            "region": "US-CA",
        },
        token=access,
    )
    record("onboarding submit (budget generation)", status == 200, f"status={status}")

    # 6. Create transaction (today)
    status, body = http(
        "POST",
        f"{base}/api/transactions/",
        {
            "amount": tx_amount,
            "category": "food",
            "description": "remote smoke test",
            "spent_at": now.isoformat(),
        },
        token=access,
    )
    record("create transaction", status in (200, 201), f"status={status}")

    # 7. Saved calendar — the calendar-fix acceptance gate
    status, body = http(
        "GET", f"{base}/api/calendar/saved/{now.year}/{now.month}", token=access
    )
    days = unwrap(body)
    days = days.get("calendar", days) if isinstance(days, dict) else days
    days = days if isinstance(days, list) else []
    n_days = _calendar.monthrange(now.year, now.month)[1]
    record(
        "saved calendar returns the full month",
        status == 200 and len(days) == n_days,
        f"status={status} days={len(days)}/{n_days}",
    )
    bad_keys = [
        d.get("date") for d in days if not DATE_KEY.match(str(d.get("date", "")))
    ]
    record("all date keys are YYYY-MM-DD", not bad_keys, f"bad={bad_keys[:3]}")
    zero_limits = [d.get("date") for d in days if not (float(d.get("limit", 0)) > 0)]
    record(
        "every day has a non-zero limit (traffic light live)",
        bool(days) and not zero_limits,
        f"zero-limit days={zero_limits[:5]}",
    )
    today = next((d for d in days if d.get("date") == today_key), None)
    record("today exists in calendar", today is not None, today_key)
    record(
        "transaction reflected in today's spent",
        bool(today) and float(today.get("spent", 0)) >= tx_amount,
        f"spent={today.get('spent') if today else None} >= {tx_amount}",
    )

    # 8. Day detail (Decimal-serialization regression)
    status, _ = http(
        "GET",
        f"{base}/api/calendar/day/{now.year}/{now.month}/{now.day}",
        token=access,
    )
    record("calendar day detail (no Decimal 500)", status == 200, f"status={status}")

    # 9. Refresh token rotation
    old_refresh = refresh
    status, body = http(
        "POST", f"{base}/api/auth/refresh-token", {"refresh_token": refresh}
    )
    na, nr = find_tokens(body)
    if record(
        "refresh token rotates pair", status == 200 and na and nr, f"status={status}"
    ):
        access = na
        status, _ = http(
            "GET", f"{base}/api/calendar/saved/{now.year}/{now.month}", token=access
        )
        record("rotated access token works", status == 200, f"status={status}")

        # 9b. The rotated-out refresh token is blacklisted server-side;
        # reusing it must fail. This is the live proof that Redis-backed
        # revocation works in the deployed environment (the blacklist
        # check fails open when Redis is down).
        status, _ = http(
            "POST", f"{base}/api/auth/refresh-token", {"refresh_token": old_refresh}
        )
        record(
            "old refresh token rejected after rotation (revocation live)",
            400 <= status < 500,
            f"status={status}",
        )

    # 10. Logout, then the access token used for it must be dead.
    status, _ = http("POST", f"{base}/api/auth/logout", {}, token=access)
    record("logout", status == 200, f"status={status}")
    status, _ = http(
        "GET", f"{base}/api/calendar/saved/{now.year}/{now.month}", token=access
    )
    record(
        "access token rejected after logout (blacklist live)",
        status in (401, 403),
        f"status={status}",
    )

    # 11. Error-path contracts: 4xx must not become 500
    status, _ = http("GET", f"{base}/api/definitely-not-a-route-xyz")
    record("unknown route -> 404 (not 500)", status == 404, f"status={status}")
    status, _ = http(
        "POST",
        f"{base}/api/auth/login",
        {"email": email, "password": "wrong-password-123"},
    )
    record("bad credentials -> 4xx (not 500)", 400 <= status < 500, f"status={status}")
    status, _ = http("POST", f"{base}/api/auth/register", {"email": "not-an-email"})
    record(
        "invalid register payload -> 4xx (not 500)",
        400 <= status < 500,
        f"status={status}",
    )
    status, _ = http("GET", f"{base}/api/calendar/saved/{now.year}/{now.month}")
    record(
        "protected route without token -> 401/403",
        status in (401, 403),
        f"status={status}",
    )
    # Malformed JSON body must be a client error, not a crash.
    req = urllib.request.Request(
        f"{base}/api/auth/login",
        data=b"{not-json",
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            status = resp.status
    except urllib.error.HTTPError as e:
        status = e.code
    except Exception:
        status = 0
    record("malformed JSON body -> 4xx (not 500)", 400 <= status < 500, f"status={status}")

    finish()


def finish():
    failed = [r for r in RESULTS if not r[1]]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} checks passed")
    if failed:
        print("FAILED checks:")
        for name, _, detail in failed:
            print(f"  - {name}: {detail}")
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
