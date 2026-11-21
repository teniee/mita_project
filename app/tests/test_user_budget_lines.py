"""F-11: budget lines the user names and sets themselves — the shared rules.

The ChatGPT tools are covered in ``tests_mcp/test_user_budget_lines.py``; this
file pins the shared money code they rely on: the engine keeps the user's
lines exactly and allocates only the rest (``generate_budget_from_answers``),
the rebalancer never moves money into or out of a user line, such a line is
never a bill (R3), the rollover carries it, and migration 0040.

Requires: PostgreSQL at DATABASE_URL (test_mita) with migrations at head.

Reference profile (the owner's acceptance case): income 2000, rent 340,
savings 500 — MITA's own Fuel line ("transport gas") is 90.00.
"""

from __future__ import annotations

import importlib.util
import os
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.db.models import DailyPlan, Transaction, User
from app.services.core.engine.budget_forecast_engine import (
    commitment_expectations,
    is_bill_line,
)
from app.services.core.engine.budget_logic import generate_budget_from_answers
from app.services.core.engine.expense_tracker import rebuild_month_plan
from app.services.core.engine.realtime_rebalancer import REALTIME_ADJUSTMENT_KEY
from app.services.core.engine.user_budget_lines import (
    PlanDoesNotFit,
    is_user_line,
    label_of,
    line_key,
)
from app.services.monthly_plan_service import (
    allocations_from_profile,
    ensure_month_plan,
    month_bounds,
    month_calendar,
    replace_month_plan,
)

D = Decimal
AUG = (2026, 8)
SEP = (2026, 9)

# MITA's own allocation for the reference profile, unchanged by F-11.
AUTOMATIC = {
    "groceries": D("180.00"),
    "dining out": D("120.00"),
    "transport public": D("210.00"),
    "transport gas": D("90.00"),
    "entertainment events": D("80.00"),
    "clothing": D("36.00"),
    "hobbies": D("24.00"),
    "insurance medical": D("96.00"),
    "out of pocket medical": D("64.00"),
}


def _answers(manual=None, replaced=None):
    answers = {
        "region": "US",
        "income": {"monthly_income": 2000.0, "additional_income": 0},
        "fixed_expenses": {"rent": 340.0},
        "spending_habits": {},
        "goals": {"savings_goal_amount_per_month": 500.0},
    }
    if manual is not None:
        answers["manual_allocations"] = {k: str(v) for k, v in manual.items()}
    if replaced is not None:
        answers["replaced_buckets"] = list(replaced)
    return answers


def _breakdown(result):
    return {
        k: D(str(v)).quantize(D("0.01"))
        for k, v in result["discretionary_breakdown"].items()
    }


class TestEngine:
    def test_automatic_budget_is_unchanged(self):
        result = generate_budget_from_answers(_answers())
        assert _breakdown(result) == AUTOMATIC
        assert D(str(result["discretionary_total"])) == D("1160.00")
        assert "manual_allocations" not in result

    def test_users_fuel_is_kept_and_replaces_mitas(self):
        result = generate_budget_from_answers(
            _answers({"my:Fuel": D("200")}, ["transport gas"])
        )
        assert result["manual_allocations"] == {"my:Fuel": 200.0}
        # 2000 - 340 - 500 - 200 = 960; MITA's other lines (810) fit as they were.
        assert D(str(result["discretionary_total"])) == D("960.00")
        assert _breakdown(result) == {
            k: v for k, v in AUTOMATIC.items() if k != "transport gas"
        }

    def test_a_line_mita_has_no_equivalent_for_replaces_nothing(self):
        result = generate_budget_from_answers(_answers({"my:Cigarettes": D("200")}))
        assert set(_breakdown(result)) == set(AUTOMATIC)

    def test_owner_example_560_left_for_mita(self):
        manual = {
            "my:Fuel": D("200"),
            "my:Cigarettes": D("200"),
            "my:Coffee and walks": D("100"),
            "my:Groceries": D("50"),
            "my:Cat food": D("50"),
        }
        result = generate_budget_from_answers(
            _answers(manual, ["transport gas", "groceries"])
        )
        # income 2000 - savings 500 - bills 340 - the user's 600 = 560
        assert D(str(result["discretionary_total"])) == D("560.00")
        breakdown = _breakdown(result)
        assert "transport gas" not in breakdown and "groceries" not in breakdown
        assert sum(breakdown.values()) <= D("560.00")  # scaled down, never up

    def test_a_plan_over_the_income_is_refused_not_shrunk(self):
        with pytest.raises(PlanDoesNotFit) as refused:
            generate_budget_from_answers(
                _answers({"my:Cigarettes": D("900"), "my:Fuel": D("400")})
            )
        assert refused.value.conflict.details() == {
            "stated_monthly_income": "2000.00",
            "bills_and_fixed_payments": "340.00",
            "savings_target": "500.00",
            "amounts_set_by_user": "1300.00",
            "exceeds_income_by": "140.00",
        }

    def test_line_keys(self):
        assert line_key("  Cat   food ") == "my:Cat food"
        assert line_key("my:Fuel") == "my:Fuel"
        assert is_user_line("my:Fuel") and not is_user_line("transport gas")
        assert label_of("my:Cat food") == "Cat food"
        for bad in ("", "   ", "x" * 41, "bad\x00name"):
            with pytest.raises(ValueError):
                line_key(bad)


def test_a_user_line_is_never_a_bill():
    assert not is_bill_line("my:Rent")
    base = {"rent": D("340"), "my:Cigarettes": D("200")}
    assert commitment_expectations(base, {}) == {"rent": D("340")}


# ---------------------------------------------------------------------------
# Real PostgreSQL
# ---------------------------------------------------------------------------


@pytest.fixture
def db_session():
    import app.core.session as session_module

    gen = session_module.get_db()
    db = next(gen)
    try:
        yield db
    finally:
        gen.close()


@pytest.fixture
def user(db_session):
    u = User(
        id=uuid4(),
        email=f"f11_{uuid4().hex[:10]}@mita.app",
        password_hash="hashed_password_123",
        has_onboarded=True,
        timezone="UTC",
        country="US",
        region="US",
        monthly_income=D("2000.00"),
    )
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    yield u
    db_session.rollback()
    db_session.query(Transaction).filter_by(user_id=u.id).delete()
    db_session.query(DailyPlan).filter_by(user_id=u.id).delete()
    db_session.query(User).filter_by(id=u.id).delete()
    db_session.commit()


def _seed(db_session, user, year, month, lines, replaced=()):
    allocation = allocations_from_profile(
        monthly_income=D("2000"),
        savings_goal=D("500"),
        region="US",
        fixed_expenses={"rent": D("340")},
        manual_allocations=lines,
        replaced_buckets=replaced,
    )
    replace_month_plan(
        db_session,
        user.id,
        year,
        month,
        month_calendar(year, month, allocation.allocations),
    )
    db_session.commit()
    return allocation


def _rows(db_session, user, year, month):
    db_session.expire_all()
    start, end = month_bounds(year, month)
    return (
        db_session.query(DailyPlan)
        .filter(
            DailyPlan.user_id == user.id,
            DailyPlan.date >= start,
            DailyPlan.date < end,
        )
        .all()
    )


def _layout(rows, category):
    def day(row):
        return row.date.date() if hasattr(row.date, "date") else row.date

    return sorted(
        (day(r), D(str(r.planned_amount))) for r in rows if r.category == category
    )


def _spend(db_session, user, category, amount, day):
    db_session.add(
        Transaction(
            user_id=user.id,
            category=category,
            amount=D(amount),
            spent_at=datetime(day.year, day.month, day.day, 12, 0, tzinfo=timezone.utc),
        )
    )
    db_session.commit()
    rebuild_month_plan(db_session, user.id, day)
    db_session.expire_all()


class TestRebalancing:
    def test_a_user_line_is_never_a_donor(self, db_session, user):
        _seed(db_session, user, *AUG, {"my:Cigarettes": D("200")})
        before = _layout(_rows(db_session, user, *AUG), "my:Cigarettes")
        # Far over groceries' slice: MITA covers it from its own lines only.
        _spend(db_session, user, "groceries", "150.00", date(2026, 8, 3))
        rows = _rows(db_session, user, *AUG)
        assert _layout(rows, "my:Cigarettes") == before
        assert any(
            (r.plan_json or {}).get(REALTIME_ADJUSTMENT_KEY)
            for r in rows
            if r.category in {"dining out", "entertainment events", "hobbies"}
        )

    def test_an_overspent_user_line_is_not_covered_by_other_lines(
        self, db_session, user
    ):
        _seed(db_session, user, *AUG, {"my:Cigarettes": D("200")})
        before = {
            c: _layout(_rows(db_session, user, *AUG), c)
            for c in {r.category for r in _rows(db_session, user, *AUG)}
        }
        _spend(db_session, user, "my:Cigarettes", "60.00", date(2026, 8, 3))
        rows = _rows(db_session, user, *AUG)
        for category, layout in before.items():
            assert _layout(rows, category) == layout, category
        assert not any((r.plan_json or {}).get(REALTIME_ADJUSTMENT_KEY) for r in rows)
        line = [r for r in rows if r.category == "my:Cigarettes"]
        assert sum((D(str(r.planned_amount)) for r in line), D("0")) == D("200.00")


def test_rollover_carries_user_lines_and_not_the_lines_they_replace(db_session, user):
    _seed(db_session, user, *AUG, {"my:Fuel": D("200")}, ["transport gas"])
    result = ensure_month_plan(db_session, user.id, *SEP)
    assert result.created and result.source == "rollover"
    totals = {}
    for row in _rows(db_session, user, *SEP):
        totals[row.category] = totals.get(row.category, D("0")) + D(
            str(row.planned_amount)
        )
    assert totals["my:Fuel"] == D("200.00")
    assert "transport gas" not in totals


# ---------------------------------------------------------------------------
# Migration 0040
# ---------------------------------------------------------------------------

SCHEMA = "test_mig0040"
MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "0040_mcp_budget_lines.py"
)


def _sync_url():
    url = os.environ.get("DATABASE_URL", "")
    for prefix in ("postgresql+asyncpg://", "postgres://"):
        if url.startswith(prefix):
            url = "postgresql://" + url[len(prefix) :]
    return url.split("?")[0]


@pytest.mark.skipif(
    "postgres" not in os.environ.get("DATABASE_URL", ""),
    reason="migration 0040 creates a PostgreSQL table",
)
def test_migration_0040_creates_and_drops_the_table():
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from app.db.models.base import Base

    spec = importlib.util.spec_from_file_location("mig0040", MIGRATION)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = sa.create_engine(
        _sync_url(), connect_args={"options": f"-csearch_path={SCHEMA}"}
    )

    def run(step):
        with engine.begin() as conn:
            with Operations.context(MigrationContext.configure(conn)):
                step()

    try:
        with engine.begin() as conn:
            conn.execute(sa.text(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE"))
            conn.execute(sa.text(f"CREATE SCHEMA {SCHEMA}"))
        Base.metadata.create_all(engine)
        with engine.begin() as conn:
            conn.execute(sa.text("DROP TABLE mcp_budget_lines"))  # the pre-0040 shape
        user_id = uuid4()
        with Session(engine) as session:
            session.add(
                User(
                    id=user_id,
                    email=f"m40_{user_id.hex[:8]}@x.invalid",
                    password_hash="x",
                )
            )
            session.commit()

        run(migration.upgrade)
        with engine.begin() as conn:
            conn.execute(
                sa.text(
                    "INSERT INTO mcp_budget_lines (user_id, line_key) VALUES (:u, 'my:Fuel')"
                ),
                {"u": user_id},
            )
            assert (
                conn.execute(sa.text("SELECT replaces FROM mcp_budget_lines")).scalar()
                == []
            )
            conn.execute(sa.text("DELETE FROM users"))  # cascades
            assert (
                conn.execute(sa.text("SELECT count(*) FROM mcp_budget_lines")).scalar()
                == 0
            )

        run(migration.downgrade)
        with engine.begin() as conn:
            assert "mcp_budget_lines" not in sa.inspect(conn).get_table_names()
    finally:
        with engine.begin() as conn:
            conn.execute(sa.text(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE"))
        engine.dispose()
