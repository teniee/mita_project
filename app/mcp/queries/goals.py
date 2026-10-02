"""Savings goals with the forecast engine's deterministic projection."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import List, Optional, Sequence

from sqlalchemy.orm import Session

from app.db.models import Goal
from app.mcp.queries.periods import UserContext
from app.services.core.engine.budget_forecast_engine import (
    GoalData,
    GoalForecast,
    compute_forecast,
)

GOAL_STATUSES = ("active", "paused", "completed", "cancelled")


@dataclass(frozen=True)
class GoalView:
    title: str
    category: Optional[str]
    status: str
    priority: Optional[str]
    target_amount: Decimal
    saved_amount: Decimal
    monthly_contribution: Optional[Decimal]
    target_date: Optional[date]
    forecast: Optional[GoalForecast]  # only for active goals


def list_goals(
    db: Session, ctx: UserContext, statuses: Sequence[str]
) -> List[GoalView]:
    rows = (
        db.query(Goal)
        .filter(
            Goal.user_id == ctx.user_id,
            Goal.deleted_at.is_(None),
            Goal.status.in_(list(statuses)),
        )
        .order_by(Goal.status, Goal.target_date.is_(None), Goal.target_date, Goal.title)
        .all()
    )
    active = [g for g in rows if g.status == "active"]
    forecasts = {}
    if active:
        # compute_forecast with no plan rows returns only the goal projections.
        result = compute_forecast(
            daily_plans=[],
            goals=[
                GoalData(
                    goal_id=str(g.id),
                    title=g.title,
                    target_amount=Decimal(str(g.target_amount)),
                    saved_amount=Decimal(str(g.saved_amount or 0)),
                    monthly_contribution=(
                        Decimal(str(g.monthly_contribution))
                        if g.monthly_contribution is not None
                        else None
                    ),
                    target_date=g.target_date,
                )
                for g in active
            ],
            year=ctx.today.year,
            month=ctx.today.month,
            today=ctx.today,
        )
        forecasts = {f.goal_id: f for f in result.goals}

    return [
        GoalView(
            title=g.title,
            category=g.category,
            status=g.status,
            priority=g.priority,
            target_amount=Decimal(str(g.target_amount)),
            saved_amount=Decimal(str(g.saved_amount or 0)),
            monthly_contribution=(
                Decimal(str(g.monthly_contribution))
                if g.monthly_contribution is not None
                else None
            ),
            target_date=g.target_date,
            forecast=forecasts.get(str(g.id)),
        )
        for g in rows
    ]
