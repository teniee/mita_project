#!/usr/bin/env python3
"""Synthetic capacity benchmark for the MCP query paths — LOCAL databases only.

    # once, as a local superuser
    createdb -O test mita_capacity
    DATABASE_URL=postgresql://test:test@localhost:5432/mita_capacity alembic upgrade head

    python scripts/mcp/benchmark_capacity.py \\
        --database-url postgresql://test:test@localhost:5432/mita_capacity \\
        --generate --runs 3 --out /tmp/capacity.json

Generates 1,000 users × ~6 months: ~600,000 transactions (1% soft-deleted),
a daily plan for every user (184 days × 8 categories ≈ 1.47M rows), goals,
scheduled obligations and ~500,000 analytics events — deterministically
(hash-based, no randomness). Then times the real MCP query layer (the same
functions the tools call, inside a READ ONLY transaction, process TZ = UTC)
for 50 users per operation, counts SQL statements, EXPLAIN-ANALYZEs the
heaviest statement of each operation and reports table/index sizes.

Refuses any database that is not on localhost and named *capacity*.
Never point it at staging or production.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, List
from urllib.parse import urlparse

os.environ["TZ"] = "UTC"
time.tzset()
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("SECRET_KEY", "benchmark_secret_key_minimum_32_chars_x")
os.environ.setdefault("JWT_SECRET", "benchmark_jwt_secret_minimum_32_chars_xx")

NOW = datetime(2026, 10, 11, 9, 0, tzinfo=timezone.utc)
USERS = 1000
TX_PER_USER = 600
SAMPLE_EVERY = 20  # → 50 users per operation
CATEGORIES = (
    "groceries",
    "dining",
    "transportation",
    "gas",
    "shopping",
    "entertainment",
    "utilities",
    "subscriptions",
)
PLAN_CATEGORIES = (
    "groceries",
    "dining out",
    "transport public",
    "transport gas",
    "clothing",
    "entertainment events",
    "utilities",
    "savings goal based",
)


def guard(url: str) -> None:
    parsed = urlparse(url)
    if parsed.hostname not in {"localhost", "127.0.0.1"} or "capacity" not in (
        parsed.path or ""
    ):
        raise SystemExit(
            "benchmark refuses this database: it must be on localhost and named *capacity*"
        )


GENERATE_SQL = [
    "DELETE FROM users WHERE email LIKE '%@capacity.invalid'",
    "DELETE FROM analytics.events WHERE server_version = 'capacity'",
    """
    INSERT INTO users (id, email, password_hash, timezone, currency, monthly_income,
        savings_goal, has_onboarded, token_version, failed_login_attempts, email_verified,
        notifications_enabled, dark_mode_enabled, created_at, updated_at, country, name)
    SELECT md5('cap-user-' || g)::uuid, 'cap' || g || '@capacity.invalid', 'x',
        (ARRAY['UTC','Europe/Sofia','America/New_York'])[1 + g % 3], 'EUR',
        2000 + (g % 50) * 100, 200, true, 1, 0, false, true, false,
        timestamptz '2026-04-20 00:00+00', now(), 'ZZ', 'Capacity ' || g
    FROM generate_series(1, {users}) g
    """,
    """
    INSERT INTO transactions (id, user_id, category, amount, currency, merchant,
        is_recurring, spent_at, created_at, updated_at, deleted_at)
    SELECT md5('cap-tx-' || u || '-' || i)::uuid, md5('cap-user-' || u)::uuid,
        (ARRAY{categories})[1 + abs(hashtext('c' || u || '-' || i)) % 8],
        round((1 + abs(hashtext('a' || u || '-' || i)) % 20000) / 100.0, 2), 'EUR',
        'Merchant ' || (abs(hashtext('m' || u || '-' || i)) % 300),
        false,
        timestamptz '2026-05-01 00:00+00'
          + make_interval(secs => abs(hashtext('t' || u || '-' || i)) % (163 * 86400)),
        now(), now(),
        CASE WHEN i % 100 = 0 THEN now() END
    FROM generate_series(1, {users}) u, generate_series(1, {tx_per_user}) i
    """,
    """
    INSERT INTO daily_plan (id, user_id, date, category, planned_amount, daily_budget,
        spent_amount, status)
    SELECT gen_random_uuid(), md5('cap-user-' || u)::uuid, d, c,
        CASE c WHEN 'savings goal based' THEN 6.50 ELSE 9.75 END,
        CASE c WHEN 'savings goal based' THEN 6.50 ELSE 9.75 END, 0, 'green'
    FROM generate_series(1, {users}) u,
         generate_series(timestamptz '2026-05-01 00:00+00', timestamptz '2026-10-31 00:00+00',
                         interval '1 day') d,
         unnest(ARRAY{plan_categories}) c
    """,
    """
    INSERT INTO goals (id, user_id, title, target_amount, saved_amount, status, progress,
        target_date, created_at, last_updated, priority)
    SELECT md5('cap-goal-' || u || '-' || k)::uuid, md5('cap-user-' || u)::uuid,
        'Goal ' || k, 1000 * k, 100 * k, 'active', 10,
        CASE WHEN k = 1 THEN date '2027-06-30' END, now(), now(), 'medium'
    FROM generate_series(1, {users}) u, generate_series(1, 2) k
    """,
    """
    INSERT INTO scheduled_expenses (id, user_id, category, amount, merchant,
        scheduled_date, recurrence, status, created_at, updated_at)
    SELECT md5('cap-sched-' || u || '-' || k)::uuid, md5('cap-user-' || u)::uuid,
        (ARRAY['rent','subscriptions','insurance'])[k],
        (ARRAY[700, 15.99, 240])[k], 'Payee ' || k,
        (ARRAY[date '2026-11-01', date '2026-10-15', date '2026-10-20'])[k],
        (ARRAY['monthly','weekly','once'])[k], 'pending', now(), now()
    FROM generate_series(1, {users}) u, generate_series(1, 3) k
    """,
    """
    INSERT INTO analytics_identities (user_id, user_key)
    SELECT md5('cap-user-' || u)::uuid, left(md5('cap-key-' || u), 32)
    FROM generate_series(1, 600) u
    """,
    """
    INSERT INTO analytics.events (occurred_at, user_key, session_key, event_name, feature,
        tool_name, intent_code, status, error_code, latency_ms, surface,
        server_version, tool_contract_version, properties)
    SELECT timestamptz '2026-05-01 00:00+00'
             + make_interval(secs => abs(hashtext('e' || u || '-' || n)) % (163 * 86400)),
        CASE WHEN u <= 600 THEN left(md5('cap-key-' || u), 32) END,
        left(md5('cap-s-' || u || '-' || (n / 4)), 32),
        CASE WHEN n % 50 = 0 THEN 'tool_call_failed' ELSE 'tool_call_succeeded' END,
        (ARRAY['transactions','summary','budget_status','history','goals','recurring',
               'forecast','setup'])[1 + abs(hashtext('f' || u || '-' || n)) % 8],
        'tool', 'intent',
        CASE WHEN n % 50 = 0 THEN 'error' ELSE 'ok' END,
        CASE WHEN n % 50 = 0 THEN 'validation' END,
        20 + abs(hashtext('l' || u || '-' || n)) % 400, 'chatgpt', 'capacity', '2.0', '{{}}'
    FROM generate_series(1, {users}) u, generate_series(1, 500) n
    """,
    "ANALYZE",
]


def generate(engine) -> Dict[str, float]:
    from sqlalchemy import text

    timings = {}
    constants = {
        "users": USERS,
        "tx_per_user": TX_PER_USER,
        "categories": list(CATEGORIES),
        "plan_categories": list(PLAN_CATEGORIES),
    }
    with engine.connect() as conn:
        for template in GENERATE_SQL:
            sql = template.format(**constants)  # nosec B608 - module constants only
            started = time.perf_counter()
            conn.execute(text(sql))
            conn.commit()
            timings[" ".join(sql.split())[:60]] = round(
                time.perf_counter() - started, 1
            )
    return timings


@contextmanager
def statement_counter(engine):
    from sqlalchemy import event

    statements: List[str] = []

    def before(conn, cursor, statement, parameters, context, executemany):
        statements.append((statement, parameters))

    event.listen(engine, "before_cursor_execute", before)
    try:
        yield statements
    finally:
        event.remove(engine, "before_cursor_execute", before)


def operations() -> Dict[str, Callable]:
    from datetime import date

    from app.mcp.queries import (
        budget_draft,
        calendar,
        goals,
        history,
        ledger,
        plan,
        recurring,
    )
    from app.mcp.queries import setup as setup_queries

    def summary(s, ctx):
        y, m = ctx.today.year, ctx.today.month
        plan.budget_status(s, ctx, y, m, with_redistribution=False)
        ledger.totals_by_category(s, ctx, date(y, m, 1), ctx.today)

    def climate(s, ctx):
        obligations = budget_draft.obligations_for_month(
            s, ctx, ctx.today.year, ctx.today.month
        )
        history.climate(s, ctx, history.window(ctx, 6), (len(obligations), 0))

    return {
        "current_month_summary": summary,
        "list_transactions_30d": lambda s, ctx: ledger.list_entries(
            s, ctx, date(2026, 9, 12), ctx.today, limit=50
        ),
        "category_breakdown_30d": lambda s, ctx: ledger.totals_by_category(
            s, ctx, date(2026, 9, 12), ctx.today
        ),
        "budget_status": lambda s, ctx: plan.budget_status(s, ctx, 2026, 10),
        "forecast": lambda s, ctx: plan.month_forecast(s, ctx, 2026, 10),
        "six_month_history": lambda s, ctx: history.spending_history(
            s, ctx, history.window(ctx, 6)
        ),
        "category_history": lambda s, ctx: history.spending_history(
            s, ctx, history.window(ctx, 6), category="groceries"
        ),
        "financial_climate": climate,
        "recurring": lambda s, ctx: recurring.recurring_expenses(s, ctx),
        "goals": lambda s, ctx: goals.list_goals(s, ctx, ("active",)),
        "setup_status": lambda s, ctx: setup_queries.setup_state(s, ctx),
        "budget_preview": lambda s, ctx: budget_draft.build_draft(s, ctx, 2026, 10),
        "calendar_month": lambda s, ctx: calendar.calendar_month(s, ctx, 2026, 10),
    }


def percentile(values: List[float], q: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round(q * (len(ordered) - 1))))
    return round(ordered[index], 2)


def run_benchmark(engine, runs: int) -> Dict:
    from uuid import UUID

    from sqlalchemy import text
    from sqlalchemy.orm import Session

    from app.mcp.queries.periods import load_user_context

    with engine.connect() as conn:
        ids = [
            UUID(row[0])
            for row in conn.execute(
                text(
                    "SELECT id::text FROM users WHERE email LIKE '%@capacity.invalid' "
                    "ORDER BY email"
                )
            )
        ][::SAMPLE_EVERY]
    results = {}
    explains = {}
    for name, op in operations().items():
        timings: List[float] = []
        counts: List[int] = []
        heaviest = None
        for _ in range(runs):
            for user_id in ids:
                with Session(engine) as session, statement_counter(
                    engine
                ) as statements:
                    session.execute(text("SET TRANSACTION READ ONLY"))
                    ctx = load_user_context(session, user_id, now=NOW)
                    started = time.perf_counter()
                    op(session, ctx)
                    elapsed = (time.perf_counter() - started) * 1000
                    session.rollback()
                timings.append(elapsed)
                counts.append(len(statements) - 3)  # minus SET + user + profile lookups
                if heaviest is None and statements:
                    heaviest = statements
        results[name] = {
            "samples": len(timings),
            "p50_ms": percentile(timings, 0.50),
            "p95_ms": percentile(timings, 0.95),
            "p99_ms": percentile(timings, 0.99),
            "max_ms": round(max(timings), 2),
            "sql_statements": statistics.mode(counts),
        }
        explains[name] = explain_heaviest(engine, heaviest)
    return {"operations": results, "explain": explains}


def explain_heaviest(engine, statements) -> Dict:
    """EXPLAIN ANALYZE every statement of one run; keep the slowest one."""
    from sqlalchemy import text

    worst = None
    with engine.connect() as conn:
        for statement, parameters in statements or []:
            if not statement.lstrip().upper().startswith("SELECT"):
                continue
            raw = conn.connection.cursor()
            try:
                raw.execute(
                    "EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + statement, parameters
                )
                plan = raw.fetchone()[0][0]
            finally:
                raw.close()
            elapsed = plan["Execution Time"]
            if worst is None or elapsed > worst["execution_ms"]:
                nodes = []

                def walk(node):
                    label = node["Node Type"]
                    if node.get("Index Name"):
                        label += f" using {node['Index Name']}"
                    elif node.get("Relation Name"):
                        label += f" on {node['Relation Name']}"
                    nodes.append(label)
                    for child in node.get("Plans", []):
                        walk(child)

                walk(plan["Plan"])
                worst = {
                    "execution_ms": round(elapsed, 3),
                    "plan_nodes": nodes,
                    "statement": " ".join(statement.split())[:240],
                }
        conn.rollback()
        conn.execute(text("SELECT 1"))
    return worst or {}


def analytics_overview(engine, runs: int) -> Dict:
    import importlib.util

    from sqlalchemy import text

    spec = importlib.util.spec_from_file_location(
        "analytics_report", Path(__file__).with_name("analytics_report.py")
    )
    report = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(report)
    timings = []
    with engine.connect() as conn:
        for _ in range(max(runs, 3)):
            started = time.perf_counter()
            report.build_report(
                lambda sql: [dict(r._mapping) for r in conn.execute(text(sql))]
            )
            timings.append((time.perf_counter() - started) * 1000)
    return {
        "samples": len(timings),
        "p50_ms": percentile(timings, 0.5),
        "max_ms": round(max(timings), 2),
    }


def sizes(engine) -> Dict:
    from sqlalchemy import text

    with engine.connect() as conn:
        database = conn.execute(
            text("SELECT pg_database_size(current_database())")
        ).scalar_one()
        rows = conn.execute(
            text(
                "SELECT n.nspname || '.' || c.relname, c.reltuples::bigint, "
                "pg_table_size(c.oid), pg_indexes_size(c.oid) FROM pg_class c "
                "JOIN pg_namespace n ON n.oid = c.relnamespace WHERE c.relkind = 'r' "
                "AND c.relname IN ('transactions','daily_plan','events','goals',"
                "'scheduled_expenses','users') ORDER BY 3 DESC"
            )
        ).all()
    mb = 1024 * 1024
    return {
        "database_mb": round(database / mb, 1),
        "tables": {
            name: {
                "rows": int(tuples),
                "table_mb": round(table / mb, 1),
                "index_mb": round(index / mb, 1),
            }
            for name, tuples, table, index in rows
        },
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--generate", action="store_true")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--out")
    args = parser.parse_args(argv)
    guard(args.database_url)
    from sqlalchemy import create_engine

    engine = create_engine(
        args.database_url.replace("postgresql+asyncpg://", "postgresql://"),
        connect_args={"options": "-c timezone=UTC"},
    )
    output = {"generated": generate(engine) if args.generate else None}
    output.update(run_benchmark(engine, args.runs))
    output["analytics_overview"] = analytics_overview(engine, args.runs)
    output["sizes"] = sizes(engine)
    text = json.dumps(output, indent=2, default=str)
    if args.out:
        Path(args.out).write_text(text)
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
