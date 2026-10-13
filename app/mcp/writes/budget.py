"""Saving a reviewed monthly budget: exactly the previewed plan, or nothing.

``save_monthly_budget`` carries only a signed token naming the month and the
digest of the reviewed draft. Under the per-user ledger lock the draft is
rebuilt from the same database facts; if its digest differs (income, savings
target or obligations changed, or the engine changed) nothing is written and
the user must preview again. Otherwise ``monthly_plan_service.replace_month_plan``
makes it the month's base plan (goal reservations kept, spend and
redistribution re-derived from the ledger) in the caller's transaction.
"""

from __future__ import annotations

import hmac
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.db.models import DailyPlan, User
from app.mcp.crypto import DataKeys
from app.mcp.errors import ValidationError
from app.mcp.queries import budget_draft
from app.mcp.queries.periods import UserContext
from app.services.core.engine.expense_tracker import lock_user_ledger
from app.services.core.engine.realtime_rebalancer import REALTIME_ADJUSTMENT_KEY
from app.services.monthly_plan_service import (
    month_base_plan,
    month_bounds,
    replace_month_plan,
)

INVALID_DRAFT = (
    "This budget preview cannot be used for this account (it was changed, copied "
    "incompletely or belongs to another preview). Preview the budget again."
)
EXPIRED_DRAFT = "This budget preview has expired. Preview the budget again."
CHANGED_DRAFT = (
    "The user's income, savings target or recurring obligations changed since the "
    "preview, so it no longer matches what MITA would save. Preview again and let "
    "the user review the new figures."
)


@dataclass(frozen=True)
class SaveOutcome:
    status: str  # saved | replaced | already_saved
    draft: budget_draft.BudgetDraft
    # True when expenses already recorded this month overspent a day of the new
    # plan and the rebuild's automatic redistribution moved money between
    # categories (the base plan is still exactly the draft).
    redistributed: bool = False


def verified_draft(
    db: Session, ctx: UserContext, keys: DataKeys, token: str, now: datetime
) -> budget_draft.BudgetDraft:
    claims = keys.open_budget_draft(ctx.user_id, token)
    if claims is None:
        raise ValidationError(INVALID_DRAFT)
    if claims.expires_at < int(now.astimezone(timezone.utc).timestamp()):
        raise ValidationError(EXPIRED_DRAFT)
    year, month = budget_draft.target_month(
        ctx, f"{claims.year:04d}-{claims.month:02d}"
    )
    lock_user_ledger(db, ctx.user_id)  # nothing moves under us from here on
    draft = budget_draft.build_draft(db, ctx, year, month)
    if not hmac.compare_digest(draft.digest[:16], claims.digest):
        raise ValidationError(CHANGED_DRAFT)
    return draft


def save(db: Session, ctx: UserContext, draft: budget_draft.BudgetDraft) -> SaveOutcome:
    """Write the draft as the month's base plan. Does not commit."""
    current = month_base_plan(db, ctx.user_id, draft.year, draft.month)
    if current == draft.calendar_entries():
        return SaveOutcome("already_saved", draft)
    replace_month_plan(db, ctx.user_id, draft.year, draft.month, draft.calendar_map)
    user = db.get(User, ctx.user_id)
    if not user.has_onboarded:
        # The app's onboarding sets this once income and a plan are saved; a
        # budget saved in ChatGPT is the same milestone (the app then opens on
        # the dashboard instead of re-running onboarding over this plan).
        user.has_onboarded = True
    return SaveOutcome(
        "replaced" if current else "saved",
        draft,
        redistributed=_has_realtime_adjustment(db, ctx, draft.year, draft.month),
    )


def _has_realtime_adjustment(
    db: Session, ctx: UserContext, year: int, month: int
) -> bool:
    start, end = month_bounds(year, month)
    markers = (
        db.query(DailyPlan.plan_json)
        .filter(
            DailyPlan.user_id == ctx.user_id,
            DailyPlan.date >= start,
            DailyPlan.date < end,
            DailyPlan.goal_id.is_(None),
        )
        .all()
    )
    for (plan_json,) in markers:
        if isinstance(plan_json, dict) and str(
            plan_json.get(REALTIME_ADJUSTMENT_KEY, "0")
        ) not in ("0", "0.00"):
            return True
    return False
