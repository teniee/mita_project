#!/usr/bin/env python3
"""Create a fully featured demo account through the REAL MITA API.

Uses only public API calls (register, onboarding, transactions, goals,
scheduled expenses), so every number in the account is produced by MITA's own
canonical code paths — the same ones the mobile app uses.

    python scripts/mcp/seed_review_account.py --base-url http://localhost:8000 \\
        --email review+chatgpt@<your-domain> --password '<strong password>'

This script is an automated writer, so it goes through scripts/_target_guard.py
and REFUSES production hosts, with no override (see that module for why). The
production OpenAI review account is created by the owner by hand in the app
with the same data — docs/chatgpt-app/review/review-account.md lists it.

Credentials are taken from arguments and never printed or written to disk.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _target_guard import ProductionTargetError, assert_writable_target  # noqa: E402

# The review dataset. Keep in sync with docs/chatgpt-app/review/review-account.md.
# One goal only: a second active goal currently fails with HTTP 500
# (goal_budget_sync writes one "goal_savings" row per goal per day, which
# collides with uq_daily_plan_user_date_category) — see security/data findings.
ONBOARDING = {
    "income": {"monthly_income": 4200.0, "additional_income": 0.0},
    "fixed_expenses": {"rent": 1100.0, "utilities": 150.0},
    "spending_habits": {"dining_out_per_month": 6},
    "goals": {"savings_goal_amount_per_month": 300.0},
    "region": "US-CA",
}
# (days ago, amount, category, merchant, marked recurring)
EXPENSES = [
    (0, 18.40, "groceries", "Fresh Market", False),
    (1, 6.20, "dining", "Corner Cafe", False),
    (2, 54.90, "groceries", "Fresh Market", False),
    (3, 15.99, "subscriptions", "StreamFlix", True),
    (4, 38.00, "transportation", "City Transit", False),
    (5, 72.35, "dining", "Bistro 21", False),
    (6, 41.10, "groceries", "Green Grocer", False),
    (8, 120.00, "shopping", "Outdoor Store", False),
    (9, 9.50, "dining", "Corner Cafe", False),
    (11, 63.25, "groceries", "Fresh Market", False),
    (12, 45.00, "utilities", "City Power", False),
    (13, 25.00, "entertainment", "Cinema Plaza", False),
]
GOALS = [
    {
        "title": "Emergency fund",
        "category": "Emergency",
        "target_amount": 3000.0,
        "saved_amount": 900.0,
        "monthly_contribution": 300.0,
        "priority": "high",
        "target_offset_days": 240,
    },
]


def http(method: str, url: str, body=None, token: str | None = None):
    req = urllib.request.Request(url, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    data = json.dumps(body).encode() if body is not None else None
    try:
        with urllib.request.urlopen(
            req, data=data, timeout=30
        ) as resp:  # nosec B310 - guarded target
            return resp.status, json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as exc:
        return exc.code, {}


def access_token(body) -> str | None:
    stack = [body]
    while stack:
        cur = stack.pop()
        if isinstance(cur, dict):
            if cur.get("access_token"):
                return cur["access_token"]
            stack.extend(cur.values())
    return None


def step(name: str, ok: bool, status: int) -> None:
    print(f"{'ok  ' if ok else 'FAIL'} {name} (HTTP {status})")
    if not ok:
        raise SystemExit(1)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument(
        "--existing",
        action="store_true",
        help="log in to an already seeded account and add only goals + scheduled "
        "expenses (run again after the account has been granted Premium)",
    )
    args = parser.parse_args()
    try:
        base = assert_writable_target(args.base_url, purpose="seed_review_account")
    except ProductionTargetError as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2

    if args.existing:
        status, body = http(
            "POST",
            f"{base}/api/auth/login",
            {"email": args.email, "password": args.password},
        )
        token = access_token(body)
        step("login", status == 200 and bool(token), status)
    else:
        status, body = http(
            "POST",
            f"{base}/api/auth/register",
            {
                "email": args.email,
                "password": args.password,
                "country": "US",
                "timezone": "UTC",
            },
        )
        token = access_token(body)
        step("register", status in (200, 201) and bool(token), status)

        status, _ = http("POST", f"{base}/api/onboarding/submit", ONBOARDING, token)
        step("onboarding", status == 200, status)

        today = datetime.now(timezone.utc).date()
        month_start = today.replace(day=1)
        for days_ago, amount, category, merchant, recurring in EXPENSES:
            # Keep the demo inside the current month (that is the month the
            # onboarding plan covers); early in a month several land on the 1st.
            day = max(today - timedelta(days=days_ago), month_start)
            spent_at = datetime.combine(day, time(12), timezone.utc)
            status, _ = http(
                "POST",
                f"{base}/api/transactions/",
                {
                    "amount": amount,
                    "category": category,
                    "merchant": merchant,
                    "spent_at": spent_at.isoformat(),
                    "is_recurring": recurring,
                },
                token,
            )
            step(f"expense {category} {amount:.2f}", status in (200, 201), status)

    for goal in GOALS:
        payload = {k: v for k, v in goal.items() if k != "target_offset_days"}
        payload["target_date"] = (
            date.today() + timedelta(days=goal["target_offset_days"])
        ).isoformat()
        status, _ = http("POST", f"{base}/api/goals/", payload, token)
        if status == 402:
            # Creating goals is a Premium feature (app/api/goals/routes.py).
            print(
                f"SKIP goal {goal['title']}: the account is not Premium. Grant Premium "
                "(review-account.md) and rerun with --existing."
            )
            continue
        step(f"goal {goal['title']}", status in (200, 201), status)

    first_of_next = (date.today().replace(day=1) + timedelta(days=32)).replace(day=1)
    for payload in (
        {
            "category": "rent",
            "amount": "1100.00",
            "merchant": "Maple Apartments",
            "scheduled_date": first_of_next.isoformat(),
            "recurrence": "monthly",
        },
        {
            "category": "insurance",
            "amount": "240.00",
            "merchant": "SafeCar Insurance",
            "scheduled_date": (date.today() + timedelta(days=20)).isoformat(),
            "recurrence": "once",
        },
    ):
        status, _ = http("POST", f"{base}/api/scheduled-expenses/", payload, token)
        step(f"scheduled {payload['category']}", status in (200, 201), status)

    print("review account ready")
    return 0


if __name__ == "__main__":
    sys.exit(main())
