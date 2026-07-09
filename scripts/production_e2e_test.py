#!/usr/bin/env python3
"""Full production end-to-end journey with exact financial assertions.

Covers the complete core MVP journey (fable-5 mandate, end-to-end-test-matrix
B1-B7 + A6-A25):

  register -> login -> onboarding -> dashboard -> calendar
  -> create txn (42.00) -> list -> get -> exact dashboard/calendar recalc
  -> update (100.00) -> exact recalc -> category change -> recalc
  -> delete -> exact reversal
  -> refresh rotation -> old refresh rejected
  -> logout -> access+refresh rejected
  -> re-login -> onboarded data persisted

Usage:
    python scripts/production_e2e_test.py \
        --base-url https://mita-production-production.up.railway.app

Creates one throwaway `e2e_<ts>@mita-audit.dev` account per run.
Exit code 0 = all checks pass.
"""

import argparse
import json
import secrets
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

RESULTS = []


def record(name, ok, detail=""):
    RESULTS.append((name, ok, detail))
    print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}")
    return ok


def http(method, url, body=None, token=None):
    req = urllib.request.Request(url, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    data = json.dumps(body).encode() if body is not None else None
    try:
        with urllib.request.urlopen(req, data=data, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode() or "{}")
        except Exception:
            return e.code, {}
    except Exception as e:
        return 0, {"error": str(e)}


def unwrap(body):
    return body.get("data", body) if isinstance(body, dict) else body


def find_tokens(body):
    seen, stack = set(), [body]
    access = refresh = None
    while stack:
        cur = stack.pop()
        if id(cur) in seen or not isinstance(cur, dict):
            continue
        seen.add(id(cur))
        access = access or cur.get("access_token")
        refresh = refresh or cur.get("refresh_token")
        stack.extend(v for v in cur.values() if isinstance(v, dict))
    return access, refresh


def dashboard_numbers(base, token):
    status, body = http("GET", f"{base}/api/dashboard", token=token)
    if status != 200:
        return None, None
    data = unwrap(body)
    return float(data.get("balance", "nan")), float(data.get("spent", "nan"))


def calendar_today_spent(base, token, now, today_key):
    status, body = http(
        "GET", f"{base}/api/calendar/saved/{now.year}/{now.month}", token=token
    )
    if status != 200:
        return None
    days = unwrap(body)
    days = days.get("calendar", days) if isinstance(days, dict) else days
    today = next((d for d in days if d.get("date") == today_key), None)
    return float(today.get("spent", 0)) if today else None


def approx(a, b, eps=0.01):
    return a is not None and b is not None and abs(a - b) <= eps


def run(base):
    ts = int(time.time())
    email = f"e2e_{ts}_{secrets.token_hex(3)}@mita-audit.dev"
    password = "E2e!" + secrets.token_hex(8)
    now = datetime.now(timezone.utc)
    today_key = now.strftime("%Y-%m-%d")

    print(f"run: {email} against {base}")

    # 1. Register
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
    if not record("1 register", status in (200, 201) and access, f"status={status}"):
        return finish()

    # 2. Login
    status, body = http(
        "POST", f"{base}/api/auth/login", {"email": email, "password": password}
    )
    la, lr = find_tokens(body)
    if record("2 login", status == 200 and la and lr, f"status={status}"):
        access, refresh = la, lr

    # 3. Onboarding (B1: income 6000, fixed 1700, savings 400 -> disc 3900)
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
    record("3 onboarding submit", status == 200, f"status={status}")

    # 4/5. Dashboard + calendar baseline (B2: balance 6000, spent 0)
    balance, spent = dashboard_numbers(base, access)
    record("4 dashboard baseline balance=6000", approx(balance, 6000.0), f"{balance}")
    record("5 dashboard baseline spent=0", approx(spent, 0.0), f"{spent}")
    cal_spent = calendar_today_spent(base, access, now, today_key)
    record("5b calendar today spent=0", approx(cal_spent, 0.0), f"{cal_spent}")

    # 6. Create transaction 42.00 (B4)
    status, body = http(
        "POST",
        f"{base}/api/transactions/",
        {
            "amount": 42.00,
            "category": "food",
            "description": "e2e journey txn",
            "spent_at": now.isoformat(),
        },
        token=access,
    )
    data = unwrap(body)
    txn = data.get("transaction", data) if isinstance(data, dict) else {}
    txn_id = str(txn.get("id") or txn.get("transaction_id") or "")
    record("6 create txn 42.00", status in (200, 201) and txn_id, f"status={status}")

    # 7. List includes it (DEF-001 regression: was 500)
    status, body = http("GET", f"{base}/api/transactions/", token=access)
    listed = unwrap(body)
    listed = listed.get("transactions", listed) if isinstance(listed, dict) else listed
    in_list = isinstance(listed, list) and any(
        str(t.get("id")) == txn_id for t in listed
    )
    record(
        "7 txn list 200 + contains txn", status == 200 and in_list, f"status={status}"
    )

    # 8. Get by id (DEF-001 regression: was 500)
    status, _ = http("GET", f"{base}/api/transactions/{txn_id}", token=access)
    record("8 txn get 200", status == 200, f"status={status}")

    # 9/10. Exact recalc after create (B4: 5958 / 42 / 42)
    balance, spent = dashboard_numbers(base, access)
    record("9 balance 5958 after create", approx(balance, 5958.0), f"{balance}")
    record("10 spent 42 after create", approx(spent, 42.0), f"{spent}")
    cal_spent = calendar_today_spent(base, access, now, today_key)
    record("10b calendar today spent 42", approx(cal_spent, 42.0), f"{cal_spent}")

    # 11. Update 42 -> 100 (DEF-002 regression: was 500; B5: 5900/100/100)
    status, _ = http(
        "PUT", f"{base}/api/transactions/{txn_id}", {"amount": 100.00}, token=access
    )
    record("11 txn update 200", status == 200, f"status={status}")
    balance, spent = dashboard_numbers(base, access)
    record("12 balance 5900 after edit", approx(balance, 5900.0), f"{balance}")
    record("13 spent 100 after edit", approx(spent, 100.0), f"{spent}")
    cal_spent = calendar_today_spent(base, access, now, today_key)
    record("13b calendar today spent 100", approx(cal_spent, 100.0), f"{cal_spent}")

    # 14. Category change moves the accrual
    status, _ = http(
        "PUT",
        f"{base}/api/transactions/{txn_id}",
        {"category": "entertainment"},
        token=access,
    )
    record("14 category change 200", status == 200, f"status={status}")
    balance, spent = dashboard_numbers(base, access)
    record("15 totals unchanged by category move", approx(spent, 100.0), f"{spent}")

    # 16. Delete (DEF-001 regression: was 500; B6: back to 6000/0/0)
    status, _ = http("DELETE", f"{base}/api/transactions/{txn_id}", token=access)
    record("16 txn delete 200", status == 200, f"status={status}")
    balance, spent = dashboard_numbers(base, access)
    record("17 balance 6000 after delete", approx(balance, 6000.0), f"{balance}")
    record("17b spent 0 after delete", approx(spent, 0.0), f"{spent}")
    cal_spent = calendar_today_spent(base, access, now, today_key)
    record("17c calendar today spent 0", approx(cal_spent, 0.0), f"{cal_spent}")
    status, _ = http("GET", f"{base}/api/transactions/{txn_id}", token=access)
    record("17d deleted txn get -> 404", status == 404, f"status={status}")

    # 18/19. Refresh rotation + old refresh rejected
    old_refresh = refresh
    status, body = http(
        "POST", f"{base}/api/auth/refresh-token", {"refresh_token": refresh}
    )
    na, nr = find_tokens(body)
    if record("18 refresh rotates", status == 200 and na and nr, f"status={status}"):
        access, refresh = na, nr
    status, _ = http(
        "POST", f"{base}/api/auth/refresh-token", {"refresh_token": old_refresh}
    )
    record("19 old refresh rejected", status in (400, 401, 403), f"status={status}")

    # 20-22. Logout kills both tokens (the client sends its refresh token so
    # the server can blacklist the whole session)
    status, _ = http(
        "POST",
        f"{base}/api/auth/logout",
        {"refresh_token": refresh},
        token=access,
    )
    record("20 logout 200", status == 200, f"status={status}")
    status, _ = http("GET", f"{base}/api/dashboard", token=access)
    record("21 access rejected after logout", status in (401, 403), f"status={status}")
    status, _ = http(
        "POST", f"{base}/api/auth/refresh-token", {"refresh_token": refresh}
    )
    record(
        "22 refresh rejected after logout",
        status in (400, 401, 403),
        f"status={status}",
    )

    # 23/24. Re-login recovers persisted state
    status, body = http(
        "POST", f"{base}/api/auth/login", {"email": email, "password": password}
    )
    access, _ = find_tokens(body)
    record("23 re-login", status == 200 and access, f"status={status}")
    balance, spent = dashboard_numbers(base, access)
    record(
        "24 persisted state recovered (balance 6000)",
        approx(balance, 6000.0),
        f"{balance}",
    )

    return finish()


def finish():
    failed = [r for r in RESULTS if not r[1]]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} checks passed")
    if failed:
        print("FAILED:")
        for name, _, detail in failed:
            print(f"  - {name}  {detail}")
    return 1 if failed else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--base-url",
        default="https://mita-production-production.up.railway.app",
    )
    args = parser.parse_args()
    sys.exit(run(args.base_url.rstrip("/")))
