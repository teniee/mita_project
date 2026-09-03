"""Regressions for the monthly plan rollover gap.

Before this fix, onboarding wrote daily_plan rows for exactly one month — the
month the user onboarded in — and nothing ever created the next one. On the 1st
of the following month an account went blank all at once:

* GET /api/calendar/saved/{y}/{m} returned {"calendar": []};
* GET /api/dashboard fell through to its monthly_income/30 placeholder;
* POST /api/transactions/check-affordability answered "No budget set".

There is no scheduler in the deployed environment (start.sh runs uvicorn only),
so correctness cannot depend on one. app/services/monthly_plan_service.py
materializes the month lazily on the first read that needs it, and these tests
pin that behavior.

Requires: PostgreSQL at DATABASE_URL (test_mita) with migrations at head — the
concurrency and no-duplicate tests are meaningless without
uq_daily_plan_user_date_category, and SQLite would not enforce it.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.db.models import DailyPlan, Transaction, User
from app.services.calendar_service_real import save_calendar_for_user
from app.services.core.engine.calendar_engine import split_amount_exactly
from app.services.monthly_plan_service import (
    ensure_month_plan,
    month_bounds,
    month_has_plan,
)

# A fixed reference month keeps these tests independent of the wall clock: the
# suite must not start failing on the 1st of a month or in a leap year.
AUG = (2026, 8)
SEP = (2026, 9)

# What an August onboarding leaves behind, in the planner's own vocabulary
# (spaces, not identifiers) — see app/config/category_aliases.py.
AUGUST_PLAN = {
    "groceries": Decimal("450.00"),
    "dining out": Decimal("240.00"),
    "coffee": Decimal("88.00"),
    "transport public": Decimal("120.00"),
    "entertainment events": Decimal("160.00"),
    "rent": Decimal("1500.00"),
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client():
    from app.main import app

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


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
        email=f"rollover_{uuid4().hex[:10]}@mita.app",
        password_hash="hashed_password_123",
        has_onboarded=True,
        timezone="UTC",
        country="US",
        region="US",
        monthly_income=Decimal("5200.00"),
    )
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    yield u
    # No automatic cleanup exists in this suite — every fixture removes its own
    # rows or the next test sees them.
    db_session.rollback()
    db_session.query(Transaction).filter_by(user_id=u.id).delete()
    db_session.query(DailyPlan).filter_by(user_id=u.id).delete()
    db_session.query(User).filter_by(id=u.id).delete()
    db_session.commit()


@pytest.fixture
def authed(client, user):
    from app.api.dependencies import get_current_user
    from app.main import app

    app.dependency_overrides[get_current_user] = lambda: user
    try:
        yield client
    finally:
        app.dependency_overrides.pop(get_current_user, None)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _seed_month(db_session, user, year, month, plan=None, frequencies=None):
    """Persist a month exactly the way onboarding does — through the canonical
    save_calendar_for_user, not by hand-writing rows.

    ``frequencies`` mirrors onboarding's spending_habits: it is how a category
    ends up covering fewer days than the month has (coffee_per_week and
    friends), which is a distinct case from a category that simply spreads
    across every weekday.
    """
    import calendar as calendar_module

    from app.services.core.engine.calendar_engine import (
        CalendarDay,
        distribute_budget_over_days,
    )

    plan = plan or AUGUST_PLAN
    frequencies = frequencies or {}
    days_in_month = calendar_module.monthrange(year, month)[1]
    days = [CalendarDay(date(year, month, d)) for d in range(1, days_in_month + 1)]
    for category, total in plan.items():
        distribute_budget_over_days(days, category, total, frequencies.get(category))

    calendar_map = {
        day.date.isoformat(): dict(day.planned_budget)
        for day in days
        if day.planned_budget
    }
    save_calendar_for_user(db_session, user.id, calendar_map)
    db_session.expire_all()
    return calendar_map


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


def _row_day(row):
    return row.date.date() if hasattr(row.date, "date") else row.date


def _totals_by_category(rows):
    totals = {}
    for row in rows:
        totals[row.category] = totals.get(row.category, Decimal("0.00")) + Decimal(
            str(row.planned_amount or 0)
        )
    return totals


def _month_planned_total(rows):
    return sum((Decimal(str(r.planned_amount or 0)) for r in rows), Decimal("0.00"))


def _month_spent_total(rows):
    return sum((Decimal(str(r.spent_amount or 0)) for r in rows), Decimal("0.00"))


def _fingerprint(rows):
    """Value-identity of a month: what it would mean for it to be 'unchanged'."""
    return sorted(
        (
            _row_day(r).isoformat(),
            r.category,
            str(Decimal(str(r.planned_amount or 0))),
            str(Decimal(str(r.daily_budget or 0))),
        )
        for r in rows
    )


# ---------------------------------------------------------------------------
# The reported defect
# ---------------------------------------------------------------------------


class TestFirstRequestOfANewMonth:
    def test_august_account_has_no_september_until_it_is_asked_for(
        self, db_session, user
    ):
        """The defect itself, as a precondition."""
        _seed_month(db_session, user, *AUG)
        assert month_has_plan(db_session, user.id, *AUG)
        assert not month_has_plan(db_session, user.id, *SEP)
        assert _rows(db_session, user, *SEP) == []

    def test_first_september_request_creates_a_persisted_plan(self, db_session, user):
        _seed_month(db_session, user, *AUG)

        result = ensure_month_plan(db_session, user.id, *SEP)

        assert result.created is True
        assert result.exists is True
        assert result.source == "rollover"
        assert result.template_month == AUG

        rows = _rows(db_session, user, *SEP)
        assert rows, "September rows must be persisted, not computed in memory"
        assert result.row_count == len(rows)
        # Every day of the month is inside the month it was generated for.
        assert all(_row_day(r).year == 2026 and _row_day(r).month == 9 for r in rows)

    def test_september_rows_survive_a_new_session(self, db_session, user):
        """Persisted server-side, not memoized in the process."""
        import app.core.session as session_module

        _seed_month(db_session, user, *AUG)
        ensure_month_plan(db_session, user.id, *SEP)
        before = _fingerprint(_rows(db_session, user, *SEP))

        fresh = session_module.create_sync_session()
        try:
            start, end = month_bounds(*SEP)
            rows = (
                fresh.query(DailyPlan)
                .filter(
                    DailyPlan.user_id == user.id,
                    DailyPlan.date >= start,
                    DailyPlan.date < end,
                )
                .all()
            )
            assert _fingerprint(rows) == before
        finally:
            fresh.close()

    def test_rows_are_written_at_exactly_midnight_utc(self, db_session, user):
        """uq_daily_plan_user_date_category is on the raw timestamptz, so two
        rows for the same day at different times do NOT conflict. Every writer
        in this codebase stores midnight UTC; a generated month that did not
        would create a silent parallel duplicate month."""
        _seed_month(db_session, user, *AUG)
        ensure_month_plan(db_session, user.id, *SEP)

        for row in _rows(db_session, user, *SEP):
            stamp = row.date
            assert stamp.hour == 0 and stamp.minute == 0 and stamp.second == 0
            assert stamp.microsecond == 0
            assert stamp.utcoffset() == timedelta(0)

    def test_no_row_has_a_null_category(self, db_session, user):
        """PostgreSQL unique constraints are NULLS DISTINCT, so a NULL category
        would let unlimited duplicates accumulate for the same day."""
        _seed_month(db_session, user, *AUG)
        ensure_month_plan(db_session, user.id, *SEP)
        assert all(r.category for r in _rows(db_session, user, *SEP))

    def test_daily_budget_is_written_alongside_planned_amount(self, db_session, user):
        """The calendar day 'limit' and every spending check read daily_budget;
        writing planned_amount alone made the API report a 0 limit."""
        _seed_month(db_session, user, *AUG)
        ensure_month_plan(db_session, user.id, *SEP)
        for row in _rows(db_session, user, *SEP):
            assert row.daily_budget == row.planned_amount


class TestIdempotency:
    def test_second_request_returns_the_same_persisted_plan(self, db_session, user):
        _seed_month(db_session, user, *AUG)

        first = ensure_month_plan(db_session, user.id, *SEP)
        snapshot = _fingerprint(_rows(db_session, user, *SEP))

        second = ensure_month_plan(db_session, user.id, *SEP)

        assert first.created is True
        assert second.created is False
        assert second.source == "existing"
        assert second.exists is True
        assert _fingerprint(_rows(db_session, user, *SEP)) == snapshot
        assert second.row_count == first.row_count
        assert second.planned_total == first.planned_total

    def test_repeated_requests_never_duplicate_rows(self, db_session, user):
        _seed_month(db_session, user, *AUG)
        for _ in range(5):
            ensure_month_plan(db_session, user.id, *SEP)

        rows = _rows(db_session, user, *SEP)
        keys = [(_row_day(r), r.category) for r in rows]
        assert len(keys) == len(set(keys))

    def test_an_existing_month_is_never_regenerated(self, db_session, user):
        """A user who edited their September budget must not have it silently
        rebuilt by an ordinary read."""
        _seed_month(db_session, user, *AUG)
        _seed_month(db_session, user, *SEP, plan={"groceries": Decimal("999.00")})
        snapshot = _fingerprint(_rows(db_session, user, *SEP))

        result = ensure_month_plan(db_session, user.id, *SEP)

        assert result.created is False
        assert result.source == "existing"
        assert _fingerprint(_rows(db_session, user, *SEP)) == snapshot

    def test_a_month_holding_only_transaction_ghost_rows_is_still_generated(
        self, db_session, user
    ):
        """rebuild_month_plan invents planned_amount=0 rows for spend that has
        no plan behind it. An EXISTS-style guard would read those as "September
        is planned" and lock the user into a $0 budget forever."""
        from app.services.core.engine.expense_tracker import (
            TRANSACTION_GENERATED_PLAN_KEY,
        )

        _seed_month(db_session, user, *AUG)
        db_session.add(
            DailyPlan(
                user_id=user.id,
                date=date(2026, 9, 4),
                category="groceries",
                planned_amount=Decimal("0.00"),
                daily_budget=Decimal("0.00"),
                spent_amount=Decimal("31.00"),
                plan_json={TRANSACTION_GENERATED_PLAN_KEY: True},
            )
        )
        db_session.commit()

        assert not month_has_plan(db_session, user.id, *SEP)
        result = ensure_month_plan(db_session, user.id, *SEP)
        assert result.created is True
        assert result.planned_total > Decimal("0.00")


class TestMoneyConservation:
    def test_split_amount_exactly_conserves_every_split(self):
        for total in ("100.00", "1000.00", "333.33", "0.07", "0.01", "1500.00"):
            for parts in range(1, 32):
                shares = split_amount_exactly(Decimal(total), parts)
                assert len(shares) == parts
                assert sum(shares, Decimal("0.00")) == Decimal(total), (
                    total,
                    parts,
                )

    def test_month_totals_conserve_to_the_cent(self, db_session, user):
        _seed_month(db_session, user, *AUG)
        august_totals = _totals_by_category(_rows(db_session, user, *AUG))

        ensure_month_plan(db_session, user.id, *SEP)
        september_totals = _totals_by_category(_rows(db_session, user, *SEP))

        assert september_totals.keys() == august_totals.keys()
        for category, august_total in august_totals.items():
            assert september_totals[category] == august_total, category

        assert _month_planned_total(
            _rows(db_session, user, *SEP)
        ) == _month_planned_total(_rows(db_session, user, *AUG))

    def test_the_seeded_august_month_itself_conserves(self, db_session, user):
        """Guards the distributor fix at its source: the same layout onboarding
        performs must already re-sum to the allocation it was given."""
        _seed_month(db_session, user, *AUG)
        totals = _totals_by_category(_rows(db_session, user, *AUG))
        for category, expected in AUGUST_PLAN.items():
            assert totals[category] == expected, category


class TestRolloverSemantics:
    def test_prior_month_spending_is_not_copied_forward(self, db_session, user):
        _seed_month(db_session, user, *AUG)
        august = _rows(db_session, user, *AUG)
        august[0].spent_amount = Decimal("77.00")
        august[1].spent_amount = Decimal("13.50")
        db_session.commit()

        ensure_month_plan(db_session, user.id, *SEP)

        assert _month_spent_total(_rows(db_session, user, *SEP)) == Decimal("0.00")
        # ...and August's own spend is untouched.
        assert _month_spent_total(_rows(db_session, user, *AUG)) == Decimal("90.50")

    def test_new_month_spend_comes_from_that_month_s_transactions_only(
        self, db_session, user
    ):
        _seed_month(db_session, user, *AUG)

        db_session.add(
            Transaction(
                user_id=user.id,
                category="groceries",
                amount=Decimal("40.00"),
                spent_at=datetime(2026, 8, 12, 12, 0, tzinfo=timezone.utc),
            )
        )
        db_session.add(
            Transaction(
                user_id=user.id,
                category="groceries",
                amount=Decimal("25.00"),
                spent_at=datetime(2026, 9, 9, 12, 0, tzinfo=timezone.utc),
            )
        )
        db_session.commit()

        ensure_month_plan(db_session, user.id, *SEP)

        assert _month_spent_total(_rows(db_session, user, *SEP)) == Decimal("25.00")

    def test_deleted_transactions_do_not_affect_the_new_month(self, db_session, user):
        _seed_month(db_session, user, *AUG)

        db_session.add(
            Transaction(
                user_id=user.id,
                category="groceries",
                amount=Decimal("60.00"),
                spent_at=datetime(2026, 9, 10, 12, 0, tzinfo=timezone.utc),
                deleted_at=datetime(2026, 9, 11, 9, 0, tzinfo=timezone.utc),
            )
        )
        db_session.add(
            Transaction(
                user_id=user.id,
                category="groceries",
                amount=Decimal("15.00"),
                spent_at=datetime(2026, 9, 10, 13, 0, tzinfo=timezone.utc),
            )
        )
        db_session.commit()

        ensure_month_plan(db_session, user.id, *SEP)

        assert _month_spent_total(_rows(db_session, user, *SEP)) == Decimal("15.00")

    def test_a_skipped_month_rolls_the_last_real_month_forward(self, db_session, user):
        """A user last seen in June, returning in September."""
        _seed_month(db_session, user, 2026, 6)

        result = ensure_month_plan(db_session, user.id, *SEP)

        assert result.created is True
        assert result.template_month == (2026, 6)
        assert _totals_by_category(
            _rows(db_session, user, *SEP)
        ) == _totals_by_category(_rows(db_session, user, 2026, 6))
        # The skipped months stay empty — the user was not budgeting then.
        assert _rows(db_session, user, 2026, 7) == []
        assert _rows(db_session, user, 2026, 8) == []

    def test_december_rolls_into_january_of_the_next_year(self, db_session, user):
        _seed_month(db_session, user, 2026, 12)

        result = ensure_month_plan(db_session, user.id, 2027, 1)

        assert result.created is True
        assert result.template_month == (2026, 12)
        rows = _rows(db_session, user, 2027, 1)
        assert rows
        assert all(_row_day(r).year == 2027 and _row_day(r).month == 1 for r in rows)
        assert _totals_by_category(rows) == _totals_by_category(
            _rows(db_session, user, 2026, 12)
        )
        assert len({_row_day(r).day for r in rows}) <= 31

    def test_plan_shape_is_preserved_but_adapts_to_the_month_s_weekdays(
        self, db_session, user
    ):
        """August has 21 weekdays, September 22.

        A category the user genuinely spends on a limited number of days (a
        coffee_per_week pattern) must keep that count. A category that simply
        covered every weekday must re-spread over the target month's weekdays
        rather than carrying "21" forward as a frequency — which would take the
        first 21 weekdays and leave the last one with no grocery budget.
        """
        import calendar as calendar_module

        # groceries spreads over every weekday; coffee is frequency-limited
        # (the shape onboarding's coffee_per_week produces).
        _seed_month(
            db_session,
            user,
            *AUG,
            plan={"groceries": Decimal("420.00"), "coffee": Decimal("100.00")},
            frequencies={"coffee": 12},
        )
        aug = _rows(db_session, user, *AUG)
        aug_days = {}
        for r in aug:
            aug_days[r.category] = aug_days.get(r.category, 0) + 1

        aug_weekdays = sum(
            1
            for d in range(1, calendar_module.monthrange(*AUG)[1] + 1)
            if date(AUG[0], AUG[1], d).weekday() < 5
        )
        sep_weekdays = sum(
            1
            for d in range(1, calendar_module.monthrange(*SEP)[1] + 1)
            if date(SEP[0], SEP[1], d).weekday() < 5
        )
        assert aug_days["groceries"] == aug_weekdays
        assert aug_days["coffee"] == 12 < aug_weekdays
        assert sep_weekdays != aug_weekdays, "fixture assumes the counts differ"

        ensure_month_plan(db_session, user.id, *SEP)

        sep_days = {}
        for r in _rows(db_session, user, *SEP):
            sep_days[r.category] = sep_days.get(r.category, 0) + 1

        assert sep_days["groceries"] == sep_weekdays, (
            "an unconstrained spread category must cover the new month's "
            "weekdays, not be front-loaded onto the old month's count"
        )
        assert (
            sep_days["coffee"] == aug_days["coffee"]
        ), "a frequency-limited category must keep its own cadence"
        # ...and both still conserve exactly.
        totals = _totals_by_category(_rows(db_session, user, *SEP))
        assert totals["groceries"] == Decimal("420.00")
        assert totals["coffee"] == Decimal("100.00")

    def test_february_length_is_respected_in_both_directions(self, db_session, user):
        """31-day month into a 28-day one and back out again, still to the cent."""
        _seed_month(db_session, user, 2027, 1)
        ensure_month_plan(db_session, user.id, 2027, 2)
        february = _rows(db_session, user, 2027, 2)
        assert february
        assert max(_row_day(r).day for r in february) <= 28
        assert _totals_by_category(february) == _totals_by_category(
            _rows(db_session, user, 2027, 1)
        )

        ensure_month_plan(db_session, user.id, 2027, 3)
        assert _totals_by_category(_rows(db_session, user, 2027, 3)) == (
            _totals_by_category(february)
        )

    def test_history_before_the_first_budgeted_month_is_not_back_filled(
        self, db_session, user
    ):
        _seed_month(db_session, user, *AUG)

        result = ensure_month_plan(db_session, user.id, 2026, 5)

        assert result.created is False
        assert result.exists is False
        assert result.source == "unavailable"
        assert _rows(db_session, user, 2026, 5) == []

    def test_a_historical_month_that_has_a_plan_is_returned_unchanged(
        self, db_session, user
    ):
        _seed_month(db_session, user, 2026, 6)
        _seed_month(db_session, user, *AUG)
        june = _fingerprint(_rows(db_session, user, 2026, 6))

        ensure_month_plan(db_session, user.id, *SEP)
        ensure_month_plan(db_session, user.id, 2026, 6)

        assert _fingerprint(_rows(db_session, user, 2026, 6)) == june

    def test_a_temporary_rebalance_does_not_become_the_new_baseline(
        self, db_session, user
    ):
        """Real-time redistribution cuts donor categories for the rest of the
        month and records a signed delta. That is a correction to August, not a
        new budget: rolling the post-rebalance number forward would compound the
        cut every month and a PROTECTED donor would never recover."""
        from app.services.core.engine.realtime_rebalancer import (
            record_realtime_adjustment,
        )

        _seed_month(db_session, user, *AUG)
        rows = _rows(db_session, user, *AUG)
        donor = next(r for r in rows if r.category == "dining out")
        cut = Decimal("5.00")
        donor.planned_amount = Decimal(str(donor.planned_amount)) - cut
        donor.daily_budget = donor.planned_amount
        record_realtime_adjustment(donor, -cut)
        db_session.commit()

        ensure_month_plan(db_session, user.id, *SEP)

        september = _totals_by_category(_rows(db_session, user, *SEP))
        assert september["dining out"] == AUGUST_PLAN["dining out"]

    def test_goal_reservation_rows_are_not_rolled_forward(self, db_session, user):
        """goal_savings rows are owned by GoalBudgetSyncService, which recreates
        them per month from the goal's own target date. Copying one forward
        would double-book the contribution once goal sync ran."""
        _seed_month(db_session, user, *AUG)
        from app.db.models.goal import Goal

        goal = Goal(
            id=uuid4(),
            user_id=user.id,
            title="Emergency fund",
            target_amount=Decimal("3000.00"),
            saved_amount=Decimal("0.00"),
            status="active",
        )
        db_session.add(goal)
        db_session.flush()
        db_session.add(
            DailyPlan(
                user_id=user.id,
                goal_id=goal.id,
                date=date(2026, 8, 20),
                category="goal_savings",
                planned_amount=Decimal("10.00"),
                daily_budget=Decimal("10.00"),
                spent_amount=Decimal("0.00"),
            )
        )
        db_session.commit()

        ensure_month_plan(db_session, user.id, *SEP)

        september = _rows(db_session, user, *SEP)
        assert all(r.category != "goal_savings" for r in september)
        assert all(r.goal_id is None for r in september)

        db_session.query(DailyPlan).filter_by(goal_id=goal.id).delete()
        db_session.query(Goal).filter_by(id=goal.id).delete()
        db_session.commit()


class TestNoPriorMonth:
    def test_a_user_with_income_but_no_month_gets_one_from_their_profile(
        self, db_session, user
    ):
        today = datetime.now(timezone.utc).date()

        result = ensure_month_plan(db_session, user.id, today.year, today.month)

        assert result.created is True
        assert result.source == "profile"
        assert result.planned_total > Decimal("0.00")
        # Plan vocabulary, so category_aliases keeps matching for affordability.
        assert "groceries" in result.categories

    def test_a_user_with_no_income_gets_nothing_rather_than_a_zero_budget(
        self, db_session, user
    ):
        user.monthly_income = Decimal("0.00")
        db_session.commit()
        today = datetime.now(timezone.utc).date()

        result = ensure_month_plan(db_session, user.id, today.year, today.month)

        assert result.created is False
        assert result.exists is False
        assert result.source == "unavailable"
        assert _rows(db_session, user, today.year, today.month) == []

    def test_past_months_are_not_generated_for_a_user_with_no_history(
        self, db_session, user
    ):
        result = ensure_month_plan(db_session, user.id, 2020, 3)
        assert result.created is False
        assert _rows(db_session, user, 2020, 3) == []


class TestAtomicity:
    def test_a_failed_generation_leaves_no_partial_month(self, db_session, user):
        """A month must never become half-visible. If the spend rebuild fails
        after the plan rows are written, the whole attempt is discarded — a
        partially-populated September renders as a short, weekday-misaligned
        calendar with no error indication, which is worse than the empty one
        this service exists to fix."""
        import app.services.monthly_plan_service as mps

        _seed_month(db_session, user, *AUG)

        boom = RuntimeError("simulated failure inside the spend rebuild")
        original = mps.rebuild_month_plan

        def exploding(*args, **kwargs):
            raise boom

        mps.rebuild_month_plan = exploding
        try:
            with pytest.raises(RuntimeError):
                ensure_month_plan(db_session, user.id, *SEP)
        finally:
            mps.rebuild_month_plan = original

        db_session.rollback()
        assert _rows(db_session, user, *SEP) == [], "partial month was persisted"
        # August is untouched by the failed attempt.
        assert month_has_plan(db_session, user.id, *AUG)

        # And the next attempt still succeeds.
        result = ensure_month_plan(db_session, user.id, *SEP)
        assert result.created is True
        assert result.exists is True

    def test_the_safe_wrapper_degrades_instead_of_raising(self, db_session, user):
        """Read paths must not 500 because a plan could not be built."""
        import app.services.monthly_plan_service as mps

        _seed_month(db_session, user, *AUG)
        original = mps.rebuild_month_plan
        mps.rebuild_month_plan = lambda *a, **k: (_ for _ in ()).throw(
            RuntimeError("boom")
        )
        try:
            assert mps.ensure_month_plan_safe(db_session, user.id, *SEP) is None
        finally:
            mps.rebuild_month_plan = original

        assert _rows(db_session, user, *SEP) == []
        # The session is still usable afterwards.
        assert month_has_plan(db_session, user.id, *AUG)


class TestConcurrentInitialization:
    def test_racing_requests_produce_exactly_one_month(self, db_session, user):
        """The mobile app fires calendar + dashboard + budget reads in one
        Future.wait on cold start, so this race is the normal case, not an edge
        case. A SQLAlchemy Session is not thread-safe — each worker builds its
        own, as the connection pool (size 5 + 10 overflow) allows."""
        import app.core.session as session_module

        _seed_month(db_session, user, *AUG)
        db_session.commit()

        # Read the id ONCE, on this thread. Touching `user` from the workers
        # would lazy-load an expired attribute through the fixture's session,
        # which is not thread-safe and fails with "This session is provisioning
        # a new connection" long before ensure_month_plan is reached.
        user_id = user.id

        def worker(_):
            session = session_module.create_sync_session()
            try:
                result = ensure_month_plan(session, user_id, *SEP)
                return (result.created, result.exists, str(result.planned_total))
            finally:
                session.close()

        with ThreadPoolExecutor(max_workers=6) as pool:
            results = list(pool.map(worker, range(6)))

        # No caller saw an error, and every caller got a real month back.
        assert all(exists for _created, exists, _total in results)
        # Exactly one of them did the work.
        assert sum(1 for created, _e, _t in results if created) == 1
        # All callers agree on the same persisted plan.
        assert len({total for _c, _e, total in results}) == 1

        rows = _rows(db_session, user, *SEP)
        keys = [(_row_day(r), r.category) for r in rows]
        assert len(keys) == len(set(keys)), "duplicate (day, category) rows"

    def test_a_lost_race_never_leaks_an_integrity_error(self, db_session, user):
        """Even if the advisory lock were unavailable, the unique constraint
        must be absorbed rather than surfacing as a 500."""
        import app.core.session as session_module
        from app.db.models.daily_plan import DailyPlan as DP

        _seed_month(db_session, user, *AUG)
        db_session.commit()
        user_id = user.id

        other = session_module.create_sync_session()
        try:
            ensure_month_plan(other, user_id, *SEP)
        finally:
            other.close()

        db_session.expire_all()
        result = ensure_month_plan(db_session, user.id, *SEP)
        assert result.exists is True
        assert result.created is False
        assert db_session.query(DP).filter_by(user_id=user.id).count() > 0


# ---------------------------------------------------------------------------
# The read paths, end to end
# ---------------------------------------------------------------------------


class TestReadPathsMaterializeTheMonth:
    def test_saved_calendar_returns_september_instead_of_an_empty_list(
        self, authed, db_session, user
    ):
        _seed_month(db_session, user, *AUG)

        resp = authed.get("/api/calendar/saved/2026/9")
        assert resp.status_code == 200, resp.text
        calendar = resp.json()["data"]["calendar"]

        assert calendar, "the reported defect: an empty September calendar"
        db_rows = _rows(db_session, user, *SEP)
        assert {day["date"] for day in calendar} == {
            _row_day(r).isoformat() for r in db_rows
        }
        # The response must match what is in the database, to the cent.
        api_total = sum(Decimal(str(day["total"])) for day in calendar)
        assert api_total == _month_planned_total(db_rows)

    def test_dashboard_reports_real_targets_not_zero(self, authed, db_session, user):
        today = datetime.now(timezone.utc).date()
        previous = date(today.year, today.month, 1) - timedelta(days=1)
        _seed_month(db_session, user, previous.year, previous.month)

        resp = authed.get("/api/dashboard")
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]

        targets = data["daily_targets"]
        assert targets
        assert sum(Decimal(str(t["limit"])) for t in targets) > Decimal("0.00")

        rows = _rows(db_session, user, today.year, today.month)
        assert rows, "the dashboard must have materialized the current month"
        today_rows = [r for r in rows if _row_day(r) == today]
        assert sum(Decimal(str(t["limit"])) for t in targets) == sum(
            Decimal(str(r.planned_amount or 0)) for r in today_rows
        )

    def test_affordability_uses_the_newly_rolled_month(self, authed, db_session, user):
        today = datetime.now(timezone.utc).date()
        previous = date(today.year, today.month, 1) - timedelta(days=1)
        _seed_month(db_session, user, previous.year, previous.month)

        resp = authed.post(
            "/api/transactions/check-affordability",
            json={"category": "food", "amount": 5.00},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]

        assert "No budget set" not in data["impact_message"]
        assert Decimal(str(data["daily_budget"])) > Decimal("0.00")

        assert month_has_plan(db_session, user.id, today.year, today.month)

    def test_budget_live_status_reports_a_daily_budget(self, authed, db_session, user):
        today = datetime.now(timezone.utc).date()
        previous = date(today.year, today.month, 1) - timedelta(days=1)
        _seed_month(db_session, user, previous.year, previous.month)

        resp = authed.get("/api/budget/live_status")
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert Decimal(str(data["daily_budget"])) > Decimal("0.00")
        assert data["status"] != "neutral"

    def test_repeated_reads_do_not_rewrite_the_month(self, authed, db_session, user):
        _seed_month(db_session, user, *AUG)

        assert authed.get("/api/calendar/saved/2026/9").status_code == 200
        snapshot = _fingerprint(_rows(db_session, user, *SEP))

        for _ in range(3):
            assert authed.get("/api/calendar/saved/2026/9").status_code == 200

        assert _fingerprint(_rows(db_session, user, *SEP)) == snapshot

    def test_a_september_transaction_moves_only_september(
        self, authed, db_session, user
    ):
        today = datetime.now(timezone.utc).date()
        previous = date(today.year, today.month, 1) - timedelta(days=1)
        _seed_month(db_session, user, previous.year, previous.month)

        assert (
            authed.get(
                "/api/calendar/saved/{}/{}".format(today.year, today.month)
            ).status_code
            == 200
        )

        prior_before = _month_planned_total(
            _rows(db_session, user, previous.year, previous.month)
        )
        prior_spent_before = _month_spent_total(
            _rows(db_session, user, previous.year, previous.month)
        )

        resp = authed.post(
            "/api/transactions/",
            json={
                "amount": 21.00,
                "category": "food",
                "description": "rollover month spend",
                "spent_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        assert resp.status_code in (200, 201), resp.text

        current_rows = _rows(db_session, user, today.year, today.month)
        assert _month_spent_total(current_rows) == Decimal("21.00")

        prior_rows = _rows(db_session, user, previous.year, previous.month)
        assert _month_spent_total(prior_rows) == prior_spent_before
        assert _month_planned_total(prior_rows) == prior_before


class TestDayBudgetEqualsCategorySum:
    """The Calendar day-details "$79 budget / $0 categories" report.

    The day-details screen showed Budget $79.00 on 2026-08-04, 2026-08-05 and
    2026-08-18 while its Category Breakdown accounted for none of it. Those
    three days have very different persisted plans, so an identical figure on
    all three could not have come from any of them — it was
    POST /calendar/shell's monthly-total-over-30 preview.

    The API contract these tests pin: for every day the saved calendar returns,

        day["limit"] == SUM(day["planned_budget"][*]["planned"])
                     == SUM(persisted planned_amount for that day)

    so a client that renders the card from one and the list from the other
    cannot show them disagreeing.
    """

    REPORTED_DAYS = ("2026-08-04", "2026-08-05", "2026-08-18")

    def _saved(self, authed, year, month):
        resp = authed.get(f"/api/calendar/saved/{year}/{month}")
        assert resp.status_code == 200, resp.text
        return resp.json()["data"]["calendar"]

    def test_every_day_limit_equals_its_category_sum(self, authed, db_session, user):
        _seed_month(db_session, user, *AUG)

        days = self._saved(authed, *AUG)
        assert days

        db_rows = _rows(db_session, user, *AUG)
        db_by_day = {}
        for row in db_rows:
            key = _row_day(row).isoformat()
            db_by_day[key] = db_by_day.get(key, Decimal("0.00")) + Decimal(
                str(row.planned_amount or 0)
            )

        for day in days:
            cat_sum = sum(
                (Decimal(str(v["planned"])) for v in day["planned_budget"].values()),
                Decimal("0.00"),
            )
            assert Decimal(str(day["limit"])) == cat_sum, day["date"]
            assert cat_sum == db_by_day[day["date"]], day["date"]

    def test_the_three_reported_days_are_not_all_the_same_figure(
        self, authed, db_session, user
    ):
        """The tell that $79 was an average rather than a real day budget."""
        _seed_month(db_session, user, *AUG)
        by_date = {
            d["date"]: Decimal(str(d["limit"])) for d in self._saved(authed, *AUG)
        }

        reported = [by_date[d] for d in self.REPORTED_DAYS if d in by_date]
        assert len(reported) == 3
        assert len(set(reported)) > 1, (
            "these three days have different plans; one shared figure across "
            "them can only be an average"
        )

    def test_no_day_reports_a_budget_it_cannot_account_for(
        self, authed, db_session, user
    ):
        """A day carrying no categories must report a zero limit, never a
        month-average stand-in."""
        _seed_month(db_session, user, *AUG)

        for day in self._saved(authed, *AUG):
            if not day["planned_budget"]:
                assert Decimal(str(day["limit"])) == Decimal("0.00"), day["date"]

    def test_month_total_conserves_across_the_api(self, authed, db_session, user):
        _seed_month(db_session, user, *AUG)

        api_total = sum(
            (
                Decimal(str(v["planned"]))
                for day in self._saved(authed, *AUG)
                for v in day["planned_budget"].values()
            ),
            Decimal("0.00"),
        )
        assert api_total == _month_planned_total(_rows(db_session, user, *AUG))
        assert api_total == sum(AUGUST_PLAN.values(), Decimal("0.00"))

    def test_a_rolled_forward_september_satisfies_the_same_invariant(
        self, authed, db_session, user
    ):
        _seed_month(db_session, user, *AUG)

        days = self._saved(authed, *SEP)
        assert days, "September must be materialized by the read"

        db_rows = _rows(db_session, user, *SEP)
        db_by_day = {}
        for row in db_rows:
            key = _row_day(row).isoformat()
            db_by_day[key] = db_by_day.get(key, Decimal("0.00")) + Decimal(
                str(row.planned_amount or 0)
            )

        for day in days:
            cat_sum = sum(
                (Decimal(str(v["planned"])) for v in day["planned_budget"].values()),
                Decimal("0.00"),
            )
            assert Decimal(str(day["limit"])) == cat_sum == db_by_day[day["date"]]

    def test_shell_preview_is_not_a_day_budget(self, authed, db_session, user):
        """/calendar/shell is a planning preview: one figure for every day.

        It must stay clearly distinguishable from a real plan — the client
        tags it `is_preview` and refuses to present it as a day's budget.
        """
        resp = authed.post(
            "/api/calendar/shell",
            json={
                "year": 2026,
                "month": 8,
                "income": 6000.0,
                "savings_target": 1200.0,
                "fixed": {"rent": 1800.0, "utilities": 300.0},
                "weights": {"food": 0.15, "transportation": 0.15},
            },
        )
        assert resp.status_code == 200, resp.text
        calendar = resp.json()["data"]["calendar"]

        # Every day identical — this is exactly why it cannot be a day budget.
        limits = {Decimal(str(d["limit"])) for d in calendar}
        assert len(limits) == 1

        # August has 31 days; the hardcoded 30 dropped the 31st entirely.
        assert len(calendar) == 31

        # Weights are FRACTIONS. income * 0.15 = 900/month = 29.03/day, not
        # the 0.29/day the extra /100 produced.
        first = calendar[0]["planned_budget"]
        assert Decimal(str(first["food"])) > Decimal("1.00"), first
