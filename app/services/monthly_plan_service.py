"""Lazy, idempotent materialization of a user's monthly budget plan.

WHY THIS EXISTS
---------------
Onboarding persisted exactly one month of ``daily_plan`` rows — the month the
user onboarded in — and nothing ever created the next one. An account onboarded
in August had zero rows for September, so on 1 September the whole product went
blank at once: ``/api/calendar/saved/{y}/{m}`` returned ``{"calendar": []}``, the
dashboard fell through to its ``monthly_income / 30`` placeholder and rendered
"$0 of $0" for a user whose income it knew, and spending prevention — the stated
core differentiator — answered "no budget set" for every category. No scheduler
existed to fill the gap, and ``POST /calendar/generate`` computed a projection it
never wrote down.

CORRECTNESS DOES NOT DEPEND ON A SCHEDULER. The month is materialized lazily, on
the first request that needs it, by :func:`ensure_month_plan`. A cron job may be
added later purely to warm months ahead of the first read; if it never runs, or
runs twice, or races a user request, the result is identical.

THIS IS NOT A SECOND BUDGET ALGORITHM. Every number it writes comes from the
existing canonical path:

* per-category monthly totals come from the user's own most recent persisted
  month (:func:`_base_month_allocations`) or, when they have none, from
  ``generate_budget_from_answers`` — the same function onboarding calls;
* those totals are laid out over the target month's days by
  ``distribute_budget_over_days`` — the same distributor onboarding calls, with
  the same weekday/weekend and fixed/spread/clustered behavior;
* the rows are written by ``save_calendar_for_user`` — the same upsert
  onboarding calls;
* spend for the new month is accrued by ``rebuild_month_plan`` — the same ledger
  rebuild a transaction write calls.
"""

from __future__ import annotations

import calendar as calendar_module
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, time, timezone
from decimal import Decimal
from typing import Dict, Optional, Tuple
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models.daily_plan import DailyPlan
from app.db.models.user import User
from app.services.calendar_service_real import save_calendar_for_user
from app.services.core.engine.calendar_engine import (
    CATEGORY_BEHAVIOR,
    CalendarDay,
    distribute_budget_over_days,
)
from app.services.core.engine.expense_tracker import (
    TRANSACTION_GENERATED_PLAN_KEY,
    local_day_of,
    lock_user_ledger,
    rebuild_month_plan,
    user_timezone_of,
)
from app.services.core.engine.realtime_rebalancer import REALTIME_ADJUSTMENT_KEY

logger = logging.getLogger(__name__)

ZERO = Decimal("0.00")

# How far back to look for a month to roll forward from. A user who returns
# after two years gets a plan rebuilt from their profile rather than from a
# stale allocation that predates every income change they have made since.
MAX_TEMPLATE_LOOKBACK_MONTHS = 24

# How many candidate plan rows to inspect when locating a template month. The
# SQL filter (planned_amount != 0, goal_id IS NULL) already removes ordinary
# transaction-ghost rows, which carry a zero allocation; only a ghost the
# rebalancer has credited survives it, and those are a handful per month. A
# couple of hundred rows therefore reaches years back. If a pathological
# account ever exhausted it, the effect is a graceful fall back to the
# profile-derived plan, and _find_template_month logs that it happened.
TEMPLATE_SCAN_ROW_LIMIT = 400


@dataclass
class MonthPlanResult:
    """Outcome of :func:`ensure_month_plan`.

    ``created`` is the one bit callers act on: it is True only when this call is
    the one that materialized the month. Everything else is diagnostics.
    """

    year: int
    month: int
    exists: bool
    created: bool
    source: str  # "existing" | "rollover" | "profile" | "unavailable"
    template_month: Optional[Tuple[int, int]] = None
    row_count: int = 0
    planned_total: Decimal = ZERO
    categories: Dict[str, Decimal] = field(default_factory=dict)
    reason: str = ""


# ---------------------------------------------------------------------------
# Month arithmetic
# ---------------------------------------------------------------------------


def month_bounds(year: int, month: int) -> Tuple[datetime, datetime]:
    """Half-open ``[start, next_start)`` naive-UTC bounds of a calendar month.

    Naive datetimes mean UTC everywhere in this codebase, and the sync engine
    pins ``timezone=UTC`` on the session, so these compare correctly against the
    timestamptz ``daily_plan.date`` column. Half-open is deliberate: an
    inclusive end built from ``day_to_range`` misses a row stored at
    23:59:59.5 on the last day.
    """
    _validate_month(year, month)
    start = datetime.combine(date(year, month, 1), time.min)
    if month == 12:
        end = datetime.combine(date(year + 1, 1, 1), time.min)
    else:
        end = datetime.combine(date(year, month + 1, 1), time.min)
    return start, end


def _validate_month(year: int, month: int) -> None:
    if not 1 <= month <= 12:
        raise ValueError(f"month must be 1-12, got {month}")
    if not 1900 <= year <= 9999:
        raise ValueError(f"year out of range: {year}")


def _month_index(year: int, month: int) -> int:
    """Months since year 0 — makes ordering and 'N months earlier' trivial."""
    return year * 12 + (month - 1)


def _previous_month(year: int, month: int) -> Tuple[int, int]:
    return (year - 1, 12) if month == 1 else (year, month - 1)


# ---------------------------------------------------------------------------
# Reading what is already persisted
# ---------------------------------------------------------------------------


def _is_transaction_generated(row: DailyPlan) -> bool:
    """True for a row ``rebuild_month_plan`` invented to hold orphan spend.

    Those rows exist so that a transaction in a month with no plan is not lost.
    They carry ``planned_amount = 0`` and are NOT evidence that a budget exists —
    treating them as such is precisely how "the month has rows, so it must be
    fine" would keep the September bug alive after the fix.
    """
    metadata = row.plan_json if isinstance(row.plan_json, dict) else {}
    return metadata.get(TRANSACTION_GENERATED_PLAN_KEY) is True


def _base_planned_amount(row: DailyPlan) -> Decimal:
    """This row's allocation with any in-month rebalance backed out.

    Real-time redistribution writes a signed delta into ``plan_json`` when it
    moves money between categories for the rest of a month. That delta is a
    correction to THIS month only. Rolling the post-rebalance number forward
    would make a one-off August overspend permanently shrink the September
    dining budget and permanently inflate whatever category absorbed it — the
    cut would compound every month, and a PROTECTED category shaved as a
    last-resort donor would never recover. Read through it.
    """
    planned = Decimal(str(row.planned_amount or 0))
    metadata = row.plan_json if isinstance(row.plan_json, dict) else {}
    raw_adjustment = metadata.get(REALTIME_ADJUSTMENT_KEY)
    if raw_adjustment is None:
        return planned
    try:
        return planned - Decimal(str(raw_adjustment))
    except Exception:  # noqa: BLE001 - a corrupt marker must not lose the row
        logger.warning(
            "monthly_plan: unreadable realtime adjustment %r on plan row %s",
            raw_adjustment,
            row.id,
        )
        return planned


def _month_rows(db: Session, user_id: UUID, year: int, month: int):
    start, end = month_bounds(year, month)
    return (
        db.query(DailyPlan)
        .filter(
            DailyPlan.user_id == user_id,
            DailyPlan.date >= start,
            DailyPlan.date < end,
        )
        .order_by(DailyPlan.date, DailyPlan.category)
        .all()
    )


def _budget_rows(rows) -> list:
    """Rows that represent an actual budget allocation for the month.

    Excludes:
    * transaction-generated rows (zero allocation, see above);
    * goal reservations (``goal_id`` set) — ``GoalBudgetSyncService`` owns those
      and re-creates them per month from the goal's own target date. A month
      that has only goal rows has no budget, and copying a goal row forward
      would double-book the contribution once goal sync ran on the new month.
    """
    return [
        row
        for row in rows
        if row.goal_id is None
        and not _is_transaction_generated(row)
        and Decimal(str(row.planned_amount or 0)) != 0
    ]


def month_has_plan(db: Session, user_id: UUID, year: int, month: int) -> bool:
    """True when this month already holds a real, non-derived budget."""
    return bool(_budget_rows(_month_rows(db, user_id, year, month)))


def _weekday_count(year: int, month: int) -> int:
    days_in_month = calendar_module.monthrange(year, month)[1]
    return sum(
        1 for day in range(1, days_in_month + 1) if date(year, month, day).weekday() < 5
    )


def _base_month_allocations(
    db: Session, user_id: UUID, year: int, month: int
) -> Tuple[Dict[str, Decimal], Dict[str, int]]:
    """Per-category monthly totals and frequency hints from a persisted month.

    Returns ``({category: monthly_total}, {category: frequency_hint})``. The
    hints are fed back to ``distribute_budget_over_days`` so the rolled-forward
    month keeps the SHAPE of the plan the user has, not just its totals: a
    category clustered onto three days stays on three days instead of reverting
    to the engine's default of four.

    One exception, and it is the reason this is not simply a day count. A
    "spread" category with no frequency covers EVERY weekday; August had 21 and
    September has 22. Carrying "21" forward as a frequency would make the
    distributor take the first 21 weekdays and leave the last one with no
    grocery budget at all. So a spread category that used every weekday of its
    own month is recorded as unconstrained (no hint) and re-spreads over
    however many weekdays the target month has, while one that used fewer — a
    real ``coffee_per_week`` pattern — keeps its count.
    """
    totals: Dict[str, Decimal] = {}
    day_counts: Dict[str, int] = {}
    for row in _budget_rows(_month_rows(db, user_id, year, month)):
        category = (row.category or "").strip()
        if not category:
            continue
        totals[category] = totals.get(category, ZERO) + _base_planned_amount(row)
        day_counts[category] = day_counts.get(category, 0) + 1

    # A category whose rebalance history nets it to zero or below carries no
    # budget forward; it would only add a noise row.
    positive = {c: t for c, t in totals.items() if t > ZERO}

    template_weekdays = _weekday_count(year, month)
    frequencies: Dict[str, int] = {}
    for category in positive:
        count = day_counts[category]
        behavior = CATEGORY_BEHAVIOR.get(category, "spread")
        if behavior == "spread" and count >= template_weekdays:
            continue  # unconstrained — let the target month set its own width
        frequencies[category] = count
    return positive, frequencies


def _candidate_budget_days(db: Session, user_id: UUID, *, before=None, ascending=True):
    """Days that could carry a real budget, cheaply narrowed in SQL.

    ``planned_amount != 0`` and ``goal_id IS NULL`` are expressible in SQL and
    remove almost everything; the transaction-ghost test lives in ``plan_json``
    and is applied in Python by the caller so this stays dialect-neutral (some
    suites run on SQLite, which has no JSONB operators).
    """
    query = db.query(DailyPlan.date, DailyPlan.plan_json).filter(
        DailyPlan.user_id == user_id,
        DailyPlan.goal_id.is_(None),
        DailyPlan.planned_amount.isnot(None),
        DailyPlan.planned_amount != 0,
    )
    if before is not None:
        query = query.filter(DailyPlan.date < before)
    order = DailyPlan.date.asc() if ascending else DailyPlan.date.desc()
    return query.order_by(order)


def _first_real_budget_month(rows) -> Optional[Tuple[int, int]]:
    """First (date, plan_json) pair in the given order that is a real plan row."""
    for value, plan_json in rows:
        metadata = plan_json if isinstance(plan_json, dict) else {}
        if metadata.get(TRANSACTION_GENERATED_PLAN_KEY) is True:
            # A ghost row can carry a NON-ZERO amount: the rebalancer credits
            # the overspent bucket, and on a real account that produced a
            # transaction-generated "food" row holding $42.50. Filtering on
            # planned_amount alone would read it as a budget.
            continue
        day = value.date() if hasattr(value, "date") else value
        return day.year, day.month
    return None


def _earliest_plan_month(db: Session, user_id: UUID) -> Optional[Tuple[int, int]]:
    """First month this user has any budget in, or None if they have none."""
    return _first_real_budget_month(
        _candidate_budget_days(db, user_id, ascending=True).limit(
            TEMPLATE_SCAN_ROW_LIMIT
        )
    )


def _find_template_month(
    db: Session, user_id: UUID, year: int, month: int
) -> Optional[Tuple[int, int]]:
    """Most recent month before the target that carries a real budget.

    Taking the latest qualifying row rather than stepping back a month at a time
    is what makes a skipped-month return work in one round trip: a user last
    seen in June asking for September rolls June forward, and the two empty
    months in between are simply not there. It crosses the year boundary for
    free, so January's template is the previous December.

    Bounded by MAX_TEMPLATE_LOOKBACK_MONTHS: a user returning after two years
    is better served by a plan rebuilt from their current profile than by an
    allocation that predates every income change they have made since.
    """
    target_start, _ = month_bounds(year, month)
    lookback_index = _month_index(year, month) - MAX_TEMPLATE_LOOKBACK_MONTHS
    lookback_start, _ = month_bounds(lookback_index // 12, lookback_index % 12 + 1)

    rows = (
        _candidate_budget_days(db, user_id, before=target_start, ascending=False)
        .filter(DailyPlan.date >= lookback_start)
        .limit(TEMPLATE_SCAN_ROW_LIMIT)
        .all()
    )
    template = _first_real_budget_month(rows)
    if template is None and len(rows) == TEMPLATE_SCAN_ROW_LIMIT:
        logger.warning(
            "monthly_plan: template scan for user=%s %s-%02d hit the %d-row "
            "limit without finding a real budget month; falling back to the "
            "user profile",
            user_id,
            year,
            month,
            TEMPLATE_SCAN_ROW_LIMIT,
        )
    return template


# ---------------------------------------------------------------------------
# Reconstructing allocations for a user with no prior month
# ---------------------------------------------------------------------------


def _profile_allocations(user: User) -> Dict[str, Decimal]:
    """Monthly per-category totals from the user's persisted profile.

    Onboarding does not keep the answers payload — only ``monthly_income``,
    ``region``/``country``, ``savings_goal`` and ``timezone`` survive on the
    users row. This rebuilds the smallest answers dict that the CANONICAL
    ``generate_budget_from_answers`` accepts and takes its
    ``discretionary_breakdown``, so a user who somehow has income but no month
    at all still gets the same tier-and-region weighted split onboarding would
    have produced, rather than a second, divergent allocation invented here.
    """
    from app.services.core.engine.budget_logic import generate_budget_from_answers

    income = Decimal(str(user.monthly_income or 0))
    if income <= ZERO:
        return {}

    savings_goal = Decimal(str(user.savings_goal or 0))
    if savings_goal >= income:
        # Not a reason to fail: a goal that swallows the whole income means no
        # discretionary plan, and generate_budget_from_answers would clamp it
        # anyway. Clamp here so the intent stays visible.
        savings_goal = ZERO

    answers = {
        "region": user.region or user.country or "US",
        "income": {
            "monthly_income": float(income),
            "additional_income": 0,
        },
        "fixed_expenses": {},
        "spending_habits": {},
        "goals": {"savings_goal_amount_per_month": float(savings_goal)},
    }

    budget = generate_budget_from_answers(answers)
    breakdown = budget.get("discretionary_breakdown") or {}
    allocations = {
        str(category): Decimal(str(amount))
        for category, amount in breakdown.items()
        if Decimal(str(amount)) > ZERO
    }

    goal_amount = Decimal(str(budget.get("savings_goal") or 0))
    if goal_amount > ZERO:
        # Same bucket name the planner and the priority registry use, so it is
        # SACRED to the redistributor from the moment it is written.
        allocations["savings goal based"] = goal_amount

    return allocations


# ---------------------------------------------------------------------------
# Laying allocations out over a month
# ---------------------------------------------------------------------------


def _build_month_calendar(
    year: int,
    month: int,
    allocations: Dict[str, Decimal],
    frequencies: Optional[Dict[str, int]] = None,
) -> Dict[str, Dict[str, Decimal]]:
    """``{"YYYY-MM-DD": {category: Decimal}}`` for one month.

    Delegates every placement decision to ``distribute_budget_over_days``: which
    days a "fixed" category lands on, which weekdays a "spread" one covers, and
    which deterministic pseudo-random days a "clustered" one clusters into.
    Amounts stay Decimal end to end; the distributor splits each total into
    integer cents that re-sum to it exactly.
    """
    frequencies = frequencies or {}
    days_in_month = calendar_module.monthrange(year, month)[1]
    days = [
        CalendarDay(date(year, month, day_number))
        for day_number in range(1, days_in_month + 1)
    ]

    for category, total in allocations.items():
        if total <= ZERO:
            continue
        distribute_budget_over_days(days, category, total, frequencies.get(category))

    calendar_map: Dict[str, Dict[str, Decimal]] = {}
    for day in days:
        allocated = {
            category: amount
            for category, amount in day.planned_budget.items()
            if Decimal(str(amount)) != 0
        }
        if allocated:
            calendar_map[day.date.isoformat()] = allocated
    return calendar_map


def _summarize(rows) -> Tuple[int, Decimal, Dict[str, Decimal]]:
    budget_rows = _budget_rows(rows)
    categories: Dict[str, Decimal] = {}
    total = ZERO
    for row in budget_rows:
        amount = Decimal(str(row.planned_amount or 0))
        categories[row.category or ""] = (
            categories.get(row.category or "", ZERO) + amount
        )
        total += amount
    return len(budget_rows), total, categories


def _result_for_rows(
    rows, year: int, month: int, *, created: bool, source: str, reason: str, **extra
) -> MonthPlanResult:
    """Describe a month from the rows that are actually persisted for it."""
    row_count, planned_total, categories = _summarize(rows)
    return MonthPlanResult(
        year=year,
        month=month,
        exists=bool(_budget_rows(rows)),
        created=created,
        source=source,
        row_count=row_count,
        planned_total=planned_total,
        categories=categories,
        reason=reason,
        **extra,
    )


def _not_generated(year: int, month: int, reason: str) -> MonthPlanResult:
    """A month deliberately left alone. Callers fall back to their own empty
    response — the same one they returned before this service existed."""
    return MonthPlanResult(
        year=year,
        month=month,
        exists=False,
        created=False,
        source="unavailable",
        reason=reason,
    )


# ---------------------------------------------------------------------------
# The canonical entry point
# ---------------------------------------------------------------------------


def ensure_month_plan(
    db: Session,
    user_id: UUID,
    year: int,
    month: int,
    *,
    commit: bool = True,
) -> MonthPlanResult:
    """Guarantee a persisted, complete plan for ``(year, month)``; return it.

    Idempotent and safe under concurrent callers. Serialization uses
    ``lock_user_ledger`` — the SAME per-user ``pg_advisory_xact_lock`` every
    ledger mutation takes — so materializing a month cannot interleave with a
    transaction write racing it; two locks would deadlock, one cannot.

    The fast path takes no lock: a month that already has a budget is returned
    from a plain read, which is what almost every request hits. Only the first
    request of a new month pays for the lock, and the check is repeated once the
    lock is held so the loser of a race writes nothing.

    Never generates:

    * a month that already has a budget — an existing September is returned
      untouched, never regenerated, so a read can never rewrite history;
    * a month earlier than the user's first budgeted month — the app must not
      invent a budget for a period the user was not using it;
    * anything at all for a user with no income on file and no prior month —
      there is no honest number to write, and zero rows would be a lie that
      looks like a budget.
    """
    _validate_month(year, month)

    # Fast path — no lock, no write, no transaction escalation.
    rows = _month_rows(db, user_id, year, month)
    if _budget_rows(rows):
        return _result_for_rows(
            rows,
            year,
            month,
            created=False,
            source="existing",
            reason="month already materialized",
        )

    try:
        return _materialize_month(db, user_id, year, month, commit=commit)
    except IntegrityError:
        # uq_daily_plan_user_date_category fired: another writer materialized
        # the same month between our check and our insert. Their rows are as
        # good as ours would have been — adopt them rather than surfacing a
        # 500 for what is a completely ordinary race.
        db.rollback()
        logger.info(
            "monthly_plan: lost insert race for user=%s %s-%02d; "
            "adopting the committed month",
            user_id,
            year,
            month,
        )
        return _result_for_rows(
            _month_rows(db, user_id, year, month),
            year,
            month,
            created=False,
            source="existing",
            reason="materialized concurrently by another request",
        )


def _materialize_month(
    db: Session,
    user_id: UUID,
    year: int,
    month: int,
    *,
    commit: bool,
) -> MonthPlanResult:
    lock_user_ledger(db, user_id)

    # Re-check under the lock. Everything before this point was advisory.
    rows = _month_rows(db, user_id, year, month)
    if _budget_rows(rows):
        return _result_for_rows(
            rows,
            year,
            month,
            created=False,
            source="existing",
            reason="materialized concurrently by another request",
        )

    # Re-queried in THIS session on purpose: get_current_user does not preload
    # region/country, so reading them off the dependency-injected instance can
    # raise DetachedInstanceError once its session is gone.
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        return _not_generated(year, month, "user not found")

    allocations: Dict[str, Decimal] = {}
    frequencies: Dict[str, int] = {}
    template_month: Optional[Tuple[int, int]] = None
    source = "unavailable"

    earliest = _earliest_plan_month(db, user_id)
    target_index = _month_index(year, month)

    if earliest is not None and target_index < _month_index(*earliest):
        # Before the user had any budget at all. Leaving history empty is the
        # honest answer; back-filling it would fabricate a plan the user never
        # had and silently rewrite what the calendar shows for that month.
        return _not_generated(
            year,
            month,
            f"{year}-{month:02d} precedes the user's first budgeted month "
            f"{earliest[0]}-{earliest[1]:02d}; history is not back-filled",
        )

    if earliest is not None:
        template_month = _find_template_month(db, user_id, year, month)
        if template_month is not None:
            allocations, frequencies = _base_month_allocations(
                db, user_id, *template_month
            )
            source = "rollover"

    if not allocations:
        # No prior month to roll forward (a fresh account, or one whose only
        # months were emptied). Fall back to the profile — but never backwards:
        # a user with no history at all gets the current month onward, not a
        # reconstructed past.
        if earliest is None:
            today_local = local_day_of(datetime.now(timezone.utc), user.timezone)
            if target_index < _month_index(today_local.year, today_local.month):
                return _not_generated(
                    year,
                    month,
                    "user has no persisted plan; past months are not "
                    "generated retroactively",
                )
        allocations = _profile_allocations(user)
        frequencies = {}
        # A template month whose categories all net to zero (fully unwound by
        # redistribution) is not a template. Drop it so the result does not
        # report "rolled forward from" a month it did not use.
        template_month = None
        source = "profile" if allocations else "unavailable"

    if not allocations:
        return _not_generated(
            year,
            month,
            "no prior month to roll forward and no monthly income on file; "
            "nothing to generate",
        )

    calendar_map = _build_month_calendar(year, month, allocations, frequencies)
    if not calendar_map:
        return _not_generated(
            year, month, "allocations produced no positive daily amounts"
        )

    intended_total = sum(allocations.values(), ZERO)
    laid_out_total = sum(
        (
            Decimal(str(amount))
            for day in calendar_map.values()
            for amount in day.values()
        ),
        ZERO,
    )
    if laid_out_total != intended_total:
        # The distributor allocates integer cents and must conserve exactly.
        # If it ever does not, writing the month would persist money that was
        # created or destroyed by rounding — refuse rather than commit it.
        raise ValueError(
            "month plan does not conserve money: "
            f"allocated {laid_out_total} from {intended_total} "
            f"for user {user_id} {year}-{month:02d}"
        )

    # One unit of work from here: the plan rows and the spend rebuild land
    # together or not at all. A reader must never see a month that has some of
    # its days — a half-written September renders as a short, weekday-misaligned
    # calendar with no error, which is worse than the empty one this fixes.
    # Rolling back here rather than leaving it to the caller keeps that
    # guarantee a property of this function.
    try:
        save_calendar_for_user(db, user_id, calendar_map, commit=False)

        # Accrue this month's OWN spend. rebuild_month_plan zeroes spent_amount
        # and re-derives it from non-deleted transactions inside this month
        # only, then replays any overspend through the redistributor and stamps
        # day statuses. Prior-month actuals cannot leak in: it never reads
        # outside the month, and nothing above copied spent_amount from the
        # template.
        rebuild_month_plan(
            db,
            user_id,
            date(year, month, 1),
            tz=user_timezone_of(db, user_id),
            commit=False,
        )

        if commit:
            db.commit()
        else:
            db.flush()
    except Exception:
        # IntegrityError is re-raised for ensure_month_plan to absorb as a lost
        # race; anything else propagates to the caller. Either way the partial
        # month is gone. Only roll back a transaction we own.
        if commit:
            db.rollback()
        raise

    result = _result_for_rows(
        _month_rows(db, user_id, year, month),
        year,
        month,
        created=True,
        source=source,
        template_month=template_month,
        reason=(
            f"rolled forward from {template_month[0]}-{template_month[1]:02d}"
            if template_month
            else "generated from user profile"
        ),
    )

    logger.info(
        "monthly_plan: materialized user=%s %s-%02d source=%s template=%s "
        "rows=%d planned_total=%s",
        user_id,
        year,
        month,
        source,
        f"{template_month[0]}-{template_month[1]:02d}" if template_month else "-",
        result.row_count,
        result.planned_total,
    )
    return result


# ---------------------------------------------------------------------------
# The boundary the read paths call
# ---------------------------------------------------------------------------
#
# Read paths call ONLY these. They never raise: a GET that renders a budget
# must not turn into a 500 because a plan could not be built. The generators
# below have real failure modes a read cannot control —
# generate_budget_from_answers raises ValueError("Fixed expenses exceed
# income."), build-time money conservation is asserted, and the DB can deadlock
# or time out — and on any of them the correct behavior is the one the endpoint
# already had before this service existed: return what is persisted, which may
# be nothing. The difference from the old silent-empty bug is that this is
# logged at ERROR with the user and month, instead of vanishing.


def ensure_month_plan_safe(
    db: Session,
    user_id: UUID,
    year: int,
    month: int,
) -> Optional[MonthPlanResult]:
    """``ensure_month_plan`` that degrades instead of raising. Returns None on
    failure, having rolled the session back to a usable state."""
    try:
        return ensure_month_plan(db, user_id, year, month)
    except Exception:  # noqa: BLE001 - a read path must never 500 over this
        logger.exception(
            "monthly_plan: could not materialize %s-%02d for user %s; "
            "serving whatever is persisted",
            year,
            month,
            user_id,
        )
        try:
            db.rollback()
        except Exception:  # noqa: BLE001 - already failing; keep the original
            logger.warning("monthly_plan: rollback after failure also failed")
        return None


def ensure_months_span_safe(
    db: Session,
    user_id: UUID,
    months,
) -> None:
    """Materialize several months. Used by readers whose window crosses a month
    boundary — the dashboard's 7-day strip reaches into the previous month for
    the first six days of every month, and ensuring only the current one would
    leave that strip on its ``monthly_income / 30`` placeholder."""
    for year, month in dict.fromkeys(months):
        ensure_month_plan_safe(db, user_id, year, month)


async def ensure_month_plan_async(
    db,
    user_id: UUID,
    year: int,
    month: int,
) -> Optional[MonthPlanResult]:
    """``ensure_month_plan_safe`` for the async routers.

    ``AsyncSession.run_sync`` hands over the greenlet-bridged sync ``Session``
    that the ledger code (``lock_user_ledger``, ``rebuild_month_plan``) is
    written against — the same bridge ``POST /transactions`` already commits
    through. The commit is deliberate and must stay: ``get_async_db`` does not
    commit on exit, so without it every generated row would be discarded when
    the request ended.
    """
    return await db.run_sync(
        lambda sync_session: ensure_month_plan_safe(sync_session, user_id, year, month)
    )


async def ensure_months_span_async(db, user_id: UUID, months) -> None:
    """``ensure_months_span_safe`` for the async routers (one bridge hop)."""
    await db.run_sync(
        lambda sync_session: ensure_months_span_safe(sync_session, user_id, months)
    )


def months_covering(days) -> list:
    """``(year, month)`` pairs covering an iterable of dates, in order."""
    return list(dict.fromkeys((day.year, day.month) for day in days))
