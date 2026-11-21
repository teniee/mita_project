#!/usr/bin/env python3
"""Seed ONE clearly fake account into an isolated STAGING database.

    DATABASE_URL=<staging db> STAGING_TEST_PASSWORD=<generated> \\
        PYTHONPATH=. python scripts/mcp/seed_staging_db.py

Runs in the API environment (requirements.txt) and writes only through MITA's
canonical engine paths, so every figure is what MITA itself computes:
the month plan via monthly_plan_service.ensure_month_plan (the same
generate_budget_from_answers + distribute_budget_over_days path onboarding
uses), expenses via expense_tracker.commit_transaction_to_ledger, the soft
delete via rebuild_month_plan.

Safety: refuses known production database hosts, refuses to run if the test
account already exists (never overwrites), takes the password from the
environment and never prints it.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, time, timedelta, timezone
from decimal import Decimal
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

EMAIL = "staging-review@example.test"
TZ = "Europe/Sofia"
PRODUCTION_DB_MARKERS = ("supabase.co", "pooler.supabase.com", "atdcxppfflmiwjwjuqyl")

# (days before today, amount, category, merchant, marked recurring, soft-deleted)
EXPENSES = [
    (0, "18.40", "groceries", "Staging Fresh Market", False, False),
    (0, "6.20", "dining", "Staging Corner Cafe", False, False),
    (1, "54.90", "groceries", "Staging Fresh Market", False, False),
    (1, "15.99", "subscriptions", "Staging StreamFlix", True, False),
    (2, "38.00", "transportation", "Staging City Transit", False, False),
    (2, "72.35", "dining", "Staging Bistro 21", False, False),
    (3, "41.10", "groceries", "Staging Green Grocer", False, False),
    (3, "999.99", "shopping", "Staging DELETED Purchase", False, True),
]


def refuse(message: str) -> None:
    print(f"refused: {message}", file=sys.stderr)
    raise SystemExit(2)


def main() -> int:
    url = os.environ.get("DATABASE_URL", "")
    password = os.environ.get("STAGING_TEST_PASSWORD", "")
    host = (urlparse(url).hostname or "").lower()
    if not url or any(marker in url for marker in PRODUCTION_DB_MARKERS):
        refuse("DATABASE_URL is missing or points at production")
    if not (host.endswith(".proxy.rlwy.net") or host in ("localhost", "127.0.0.1")):
        refuse(f"unexpected database host {host!r}; staging seeding only")
    if len(password) < 16:
        refuse("STAGING_TEST_PASSWORD must be set (>= 16 chars)")

    from app.core.password_security import hash_password_sync
    from app.core.session import _initialize_sync_session
    from app.db.models import Goal, ScheduledExpense, Transaction, User
    from app.services.core.engine.expense_tracker import (
        commit_transaction_to_ledger,
        rebuild_month_plan,
    )
    from app.services.monthly_plan_service import ensure_month_plan

    _initialize_sync_session()
    from app.core import session as session_module

    db = session_module.SessionLocal()
    try:
        if db.query(User).filter(User.email == EMAIL).first() is not None:
            refuse(f"{EMAIL} already exists; not overwriting")

        user = User(
            email=EMAIL,
            password_hash=hash_password_sync(password),
            name="Staging Review",
            country="US",
            region="US",
            timezone=TZ,
            currency="EUR",
            monthly_income=Decimal("4200.00"),
            savings_goal=Decimal("300.00"),
            has_onboarded=True,
            email_verified=True,
            token_version=1,
            failed_login_attempts=0,
        )
        db.add(user)
        db.commit()

        today = datetime.now(timezone.utc).astimezone(ZoneInfo(TZ)).date()
        plan = ensure_month_plan(db, user.id, today.year, today.month)
        db.commit()

        deleted = None
        for days_ago, amount, category, merchant, recurring, soft_delete in EXPENSES:
            day = max(today - timedelta(days=days_ago), today.replace(day=1))
            spent_at = datetime.combine(day, time(12), ZoneInfo(TZ)).astimezone(
                timezone.utc
            )
            txn = Transaction(
                user_id=user.id,
                amount=Decimal(amount),
                category=category,
                merchant=merchant,
                currency="EUR",
                is_recurring=recurring,
                spent_at=spent_at,
            )
            commit_transaction_to_ledger(db, txn, run_side_effects=False)
            if soft_delete:
                deleted = txn

        if deleted is not None:
            deleted.deleted_at = datetime.now(timezone.utc)
            db.flush()
            rebuild_month_plan(db, user.id, today, tz=TZ, commit=True)

        db.add(
            Goal(
                user_id=user.id,
                title="Staging emergency fund",
                category="Emergency",
                target_amount=Decimal("3000.00"),
                saved_amount=Decimal("900.00"),
                monthly_contribution=Decimal("300.00"),
                target_date=today + timedelta(days=240),
                status="active",
                priority="high",
                progress=Decimal("30.00"),
            )
        )
        first_next = (today.replace(day=1) + timedelta(days=32)).replace(day=1)
        db.add_all(
            [
                ScheduledExpense(
                    user_id=user.id,
                    category="rent",
                    amount=Decimal("1100.00"),
                    merchant="Staging Maple Apartments",
                    scheduled_date=first_next,
                    recurrence="monthly",
                    status="pending",
                ),
                ScheduledExpense(
                    user_id=user.id,
                    category="insurance",
                    amount=Decimal("240.00"),
                    merchant="Staging SafeCar Insurance",
                    scheduled_date=today + timedelta(days=20),
                    recurrence="once",
                    status="pending",
                ),
            ]
        )
        db.commit()

        live = sum(Decimal(a) for _, a, *_rest, d in EXPENSES if not d)
        print(f"seeded {EMAIL} (tz {TZ}, EUR) for {today:%Y-%m}")
        print(
            f"plan: source={plan.source} planned_total={plan.planned_total} rows={plan.row_count}"
        )
        print(
            f"expenses: {sum(1 for e in EXPENSES if not e[5])} live totalling {live}, 1 soft-deleted"
        )
        print("goal: 1, scheduled: rent monthly + insurance once")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
