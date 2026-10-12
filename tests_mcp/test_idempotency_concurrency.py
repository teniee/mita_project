"""Two identical add_transaction calls racing, on real pooled connections.

The rest of the suite shares one connection inside a rolled-back
transaction, which cannot exercise a race. This test uses the production
session factories (separate connections, real commits) and deletes what it
created.

Policy under test: the idempotency record is inserted before the rows, in
the same transaction, so the second identical call blocks on its primary key
until the first commits, then replays it — exactly one expense, both callers
see the same result.
"""

import asyncio
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import text

from app.core.password_security import hash_password_sync
from app.mcp.db import read_only_session, write_session
from app.mcp.server import build_service
from tests_mcp.conftest import (
    PASSWORD,
    make_settings,
    mcp_client,
    mint_token,
    started,
    structured,
)


@pytest.fixture
async def committed_user():
    from app.core import async_session
    from app.db.models import User

    user = User(
        id=uuid.uuid4(),
        email=f"race_{uuid.uuid4().hex[:10]}@example.test",
        password_hash=hash_password_sync(PASSWORD),
        timezone="UTC",
        currency="EUR",
        token_version=1,
        failed_login_attempts=0,
        has_onboarded=True,
    )
    async with write_session() as session:
        session.add(user)
    try:
        yield user
    finally:
        async with write_session() as session:
            for table in ("transactions", "daily_plan", "redistribution_events"):
                await session.execute(
                    text(f"DELETE FROM {table} WHERE user_id = :u"),  # nosec B608
                    {"u": user.id},
                )
            await session.execute(
                text("DELETE FROM users WHERE id = :u"), {"u": user.id}
            )
        await async_session.close_database()
        async_session.AsyncSessionLocal = None


async def test_racing_identical_calls_record_one_expense(committed_user, monkeypatch):
    from app.mcp.writes import transactions as writes_module

    real_insert = writes_module.insert
    calls = []

    def slow_insert(db, rows):
        # Hold the first transaction open AFTER it claimed the key: a
        # database-side sleep yields the event loop, so the twin call runs,
        # finds no committed record and must block on the key's primary key.
        calls.append(1)
        db.execute(text("SELECT pg_sleep(0.4)"))
        real_insert(db, rows)

    monkeypatch.setattr(writes_module, "insert", slow_insert)
    service = build_service(
        make_settings(), session_scope=read_only_session, write_scope=write_session
    )
    token = mint_token(service, committed_user)
    args = {
        "amount": "42.00",
        "category": "groceries",
        "merchant": "Race Market",
        "idempotency_key": "race-" + uuid.uuid4().hex,
    }
    async with started(service):
        async with mcp_client(service, token) as first, mcp_client(
            service, token
        ) as second:
            a, b = await asyncio.gather(
                first.call_tool("add_transaction", args),
                second.call_tool("add_transaction", args),
            )
    results = [structured(a), structured(b)]
    assert sorted(r["status"] for r in results) == ["already_recorded", "recorded"]
    assert results[0]["transactions"] == results[1]["transactions"]

    async with write_session() as session:
        amounts = (
            (
                await session.execute(
                    text(
                        "SELECT amount FROM transactions WHERE user_id = :u AND deleted_at IS NULL"
                    ),
                    {"u": committed_user.id},
                )
            )
            .scalars()
            .all()
        )
        records = await session.scalar(
            text("SELECT count(*) FROM mcp_idempotency_keys WHERE user_id = :u"),
            {"u": committed_user.id},
        )
    assert amounts == [Decimal("42.00")]
    assert records == 1
    assert len(calls) == 1  # the twin never reached the ledger: it replayed
