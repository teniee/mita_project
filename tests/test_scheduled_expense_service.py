"""
Integration tests for scheduled_expense_service.py.

Uses SQLite in-memory database with real SQL — no mocking.
Pattern: same as test_redistribution_audit_log.py and test_rebalancer_integration.py.

Run: pytest tests/test_scheduled_expense_service.py -v
"""
from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.services.scheduled_expense_service import (
    cancel_scheduled_expense,
    create_scheduled_expense,
    get_all_expenses,
    get_expense_by_id,
    get_pending_expenses,
    get_impact,
)

# ─── Test database setup ─────────────────────────────────────────────────────

DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def db() -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.execute(text("PRAGMA foreign_keys = OFF"))
        # users table (FK target)
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                email TEXT,
                has_onboarded INTEGER DEFAULT 0,
                notifications_enabled INTEGER DEFAULT 1
            )
        """))
        # transactions table (FK target for scheduled_expenses.transaction_id)
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS transactions (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                category TEXT NOT NULL,
                amount NUMERIC(12,2) NOT NULL,
                description TEXT,
                merchant TEXT,
                spent_at DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                deleted_at DATETIME
            )
        """))
        # daily_plan table
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS daily_plan (
                id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
                user_id TEXT NOT NULL,
                date DATETIME NOT NULL,
                category TEXT,
                planned_amount NUMERIC(12,2) DEFAULT 0,
                spent_amount NUMERIC(12,2) DEFAULT 0,
                daily_budget NUMERIC(12,2),
                status TEXT DEFAULT 'green',
                goal_id TEXT,
                plan_json TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """))
        # scheduled_expenses table
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS scheduled_expenses (
                id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
                user_id TEXT NOT NULL,
                category TEXT NOT NULL,
                amount NUMERIC(12,2) NOT NULL,
                description TEXT,
                merchant TEXT,
                scheduled_date DATE NOT NULL,
                recurrence TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                reminder_sent_at DATETIME,
                processed_at DATETIME,
                transaction_id TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                deleted_at DATETIME
            )
        """))

    async with async_session() as session:
        yield session

    await engine.dispose()


USER_ID = uuid.uuid4()
TODAY = date(2026, 3, 20)


# ─── TestCreate ───────────────────────────────────────────────────────────────


class TestCreate:
    @pytest.mark.asyncio
    async def test_create_returns_expense(self, db: AsyncSession):
        expense = await create_scheduled_expense(
            db=db,
            user_id=USER_ID,
            category="insurance",
            amount=Decimal("300.00"),
            scheduled_date=date(2026, 3, 25),
        )
        await db.commit()

        assert expense.id is not None
        assert expense.category == "insurance"
        assert Decimal(str(expense.amount)) == Decimal("300.00")
        assert expense.status == "pending"

    @pytest.mark.asyncio
    async def test_create_all_fields(self, db: AsyncSession):
        expense = await create_scheduled_expense(
            db=db,
            user_id=USER_ID,
            category="utilities",
            amount=Decimal("75.50"),
            scheduled_date=date(2026, 3, 28),
            description="Monthly electricity bill",
            merchant="Power Company",
            recurrence="monthly",
        )
        await db.commit()

        assert expense.description == "Monthly electricity bill"
        assert expense.merchant == "Power Company"
        assert expense.recurrence == "monthly"

    @pytest.mark.asyncio
    async def test_create_status_is_pending(self, db: AsyncSession):
        expense = await create_scheduled_expense(
            db=db,
            user_id=USER_ID,
            category="insurance",
            amount=Decimal("100"),
            scheduled_date=date(2026, 3, 25),
        )
        await db.commit()
        assert expense.status == "pending"

    @pytest.mark.asyncio
    async def test_multiple_expenses_different_users(self, db: AsyncSession):
        user_a = uuid.uuid4()
        user_b = uuid.uuid4()

        await create_scheduled_expense(db, user_a, "insurance", Decimal("100"), date(2026, 3, 25))
        await create_scheduled_expense(db, user_b, "rent", Decimal("200"), date(2026, 3, 28))
        await db.commit()

        a_expenses = await get_all_expenses(db, user_a)
        b_expenses = await get_all_expenses(db, user_b)

        assert len(a_expenses) == 1
        assert len(b_expenses) == 1
        assert a_expenses[0].category == "insurance"
        assert b_expenses[0].category == "rent"


# ─── TestGet ──────────────────────────────────────────────────────────────────


class TestGet:
    @pytest.mark.asyncio
    async def test_get_by_id_found(self, db: AsyncSession):
        expense = await create_scheduled_expense(
            db=db, user_id=USER_ID, category="phone",
            amount=Decimal("50"), scheduled_date=date(2026, 3, 25),
        )
        await db.commit()

        fetched = await get_expense_by_id(db, expense.id, USER_ID)
        assert fetched is not None
        assert fetched.id == expense.id

    @pytest.mark.asyncio
    async def test_get_by_id_wrong_user_returns_none(self, db: AsyncSession):
        expense = await create_scheduled_expense(
            db=db, user_id=USER_ID, category="phone",
            amount=Decimal("50"), scheduled_date=date(2026, 3, 25),
        )
        await db.commit()

        other_user = uuid.uuid4()
        fetched = await get_expense_by_id(db, expense.id, other_user)
        assert fetched is None

    @pytest.mark.asyncio
    async def test_get_all_returns_all_active(self, db: AsyncSession):
        for i in range(3):
            await create_scheduled_expense(
                db=db, user_id=USER_ID, category="insurance",
                amount=Decimal("100"), scheduled_date=date(2026, 3, 25 - i),
            )
        await db.commit()

        all_expenses = await get_all_expenses(db, USER_ID)
        assert len(all_expenses) == 3

    @pytest.mark.asyncio
    async def test_get_all_with_status_filter(self, db: AsyncSession):
        pending = await create_scheduled_expense(
            db=db, user_id=USER_ID, category="insurance",
            amount=Decimal("100"), scheduled_date=date(2026, 3, 25),
        )
        await db.commit()

        only_pending = await get_all_expenses(db, USER_ID, status="pending")
        assert len(only_pending) >= 1
        assert all(e.status == "pending" for e in only_pending)

    @pytest.mark.asyncio
    async def test_get_pending_filters_by_date(self, db: AsyncSession):
        await create_scheduled_expense(
            db=db, user_id=USER_ID, category="early",
            amount=Decimal("50"), scheduled_date=date(2026, 3, 21),
        )
        await create_scheduled_expense(
            db=db, user_id=USER_ID, category="late",
            amount=Decimal("50"), scheduled_date=date(2026, 3, 30),
        )
        await db.commit()

        # Only up to March 25
        filtered = await get_pending_expenses(
            db, USER_ID, from_date=date(2026, 3, 20), to_date=date(2026, 3, 25)
        )
        assert all(e.scheduled_date <= date(2026, 3, 25) for e in filtered)


# ─── TestCancel ───────────────────────────────────────────────────────────────


class TestCancel:
    @pytest.mark.asyncio
    async def test_cancel_sets_status(self, db: AsyncSession):
        expense = await create_scheduled_expense(
            db=db, user_id=USER_ID, category="insurance",
            amount=Decimal("300"), scheduled_date=date(2026, 3, 25),
        )
        await db.commit()

        cancelled = await cancel_scheduled_expense(db, expense.id, USER_ID)
        await db.commit()

        assert cancelled is not None
        assert cancelled.status == "cancelled"
        assert cancelled.deleted_at is not None

    @pytest.mark.asyncio
    async def test_cancel_not_found_returns_none(self, db: AsyncSession):
        fake_id = uuid.uuid4()
        result = await cancel_scheduled_expense(db, fake_id, USER_ID)
        assert result is None

    @pytest.mark.asyncio
    async def test_cancel_idempotent(self, db: AsyncSession):
        """Cancelling an already-cancelled (soft-deleted) expense returns None — no error."""
        expense = await create_scheduled_expense(
            db=db, user_id=USER_ID, category="insurance",
            amount=Decimal("100"), scheduled_date=date(2026, 3, 25),
        )
        await db.commit()

        cancelled = await cancel_scheduled_expense(db, expense.id, USER_ID)
        await db.commit()
        assert cancelled is not None
        assert cancelled.status == "cancelled"

        # Second cancel — expense is soft-deleted, get_expense_by_id returns None
        result = await cancel_scheduled_expense(db, expense.id, USER_ID)
        assert result is None  # Not found (soft-deleted) — no exception raised

    @pytest.mark.asyncio
    async def test_cancelled_not_in_pending(self, db: AsyncSession):
        """Cancelled expenses must not appear in get_pending_expenses."""
        expense = await create_scheduled_expense(
            db=db, user_id=USER_ID, category="insurance",
            amount=Decimal("100"), scheduled_date=date(2026, 3, 25),
        )
        await db.commit()

        await cancel_scheduled_expense(db, expense.id, USER_ID)
        await db.commit()

        pending = await get_pending_expenses(db, USER_ID)
        pending_ids = [str(e.id) for e in pending]
        assert str(expense.id) not in pending_ids


# ─── TestImpact ───────────────────────────────────────────────────────────────


class TestImpact:
    @pytest.mark.asyncio
    async def test_impact_no_data(self, db: AsyncSession):
        """Empty DB — both limits are zero, no impacts."""
        result = await get_impact(db, USER_ID, 2026, 3)
        assert result.total_committed == Decimal("0")
        assert result.base_safe_daily_limit == Decimal("0")
        assert result.adjusted_safe_daily_limit == Decimal("0")
        assert result.impacts == []

    @pytest.mark.asyncio
    async def test_impact_includes_pending_expenses(self, db: AsyncSession):
        """Pending expense reduces adjusted_safe_daily_limit."""
        # Insert DailyPlan rows using UUID hex format (no dashes) for SQLite compatibility
        user_hex = USER_ID.hex  # SQLAlchemy UUID(as_uuid=True) stores as CHAR(32) in SQLite
        for day in range(20, 32):
            await db.execute(text("""
                INSERT INTO daily_plan (id, user_id, date, category, planned_amount, spent_amount)
                VALUES (:id, :user_id, :date, :category, :planned, :spent)
            """), {
                "id": uuid.uuid4().hex,
                "user_id": user_hex,
                "date": f"2026-03-{day:02d} 00:00:00",
                "category": "dining_out",
                "planned": 10.0,
                "spent": 0.0,
            })
        await db.flush()

        expense = await create_scheduled_expense(
            db=db, user_id=USER_ID, category="insurance",
            amount=Decimal("60"), scheduled_date=date(2026, 3, 25),
        )
        await db.commit()

        result = await get_impact(db, USER_ID, 2026, 3)
        # 12 days × 10 = 120 remaining. 60 committed. adjusted = 60/12 = 5.00
        assert result.total_committed == Decimal("60.00")
        assert result.adjusted_safe_daily_limit == Decimal("5.00")
        assert len(result.impacts) == 1

    @pytest.mark.asyncio
    async def test_impact_excludes_cancelled_expenses(self, db: AsyncSession):
        """Cancelled expenses must not affect the impact calculation."""
        expense = await create_scheduled_expense(
            db=db, user_id=USER_ID, category="insurance",
            amount=Decimal("300"), scheduled_date=date(2026, 3, 25),
        )
        await db.commit()
        await cancel_scheduled_expense(db, expense.id, USER_ID)
        await db.commit()

        result = await get_impact(db, USER_ID, 2026, 3)
        assert result.total_committed == Decimal("0")

    @pytest.mark.asyncio
    async def test_impact_user_isolation(self, db: AsyncSession):
        """Another user's scheduled expenses don't affect current user's impact."""
        other_user = uuid.uuid4()
        await create_scheduled_expense(
            db=db, user_id=other_user, category="insurance",
            amount=Decimal("500"), scheduled_date=date(2026, 3, 25),
        )
        await db.commit()

        result = await get_impact(db, USER_ID, 2026, 3)
        assert result.total_committed == Decimal("0")
