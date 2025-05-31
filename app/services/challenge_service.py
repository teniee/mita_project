"""
app/services/challenge_service.py

Full challenge business‑logic module.
Contains:

* check_eligibility   – returns challenges that a user can join.
* evaluate_challenge  – alias to keep old imports alive.
* run_streak_challenge – checks “N‑day streak” progress.

DB models required (see bottom of this file).
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.schemas.challenge import (
    ChallengeBrief,
    ChallengeEligibilityResponse,
)

# ------------------------------------------------------------------ #
#  Internal helpers
# ------------------------------------------------------------------ #


def _month_between(target: str, start: str, end: str) -> bool:
    """Compare 'YYYY-MM' strings without parsing."""
    return start <= target <= end


def _date_range(start: date, end: date) -> List[date]:
    days = (end - start).days + 1
    return [start + timedelta(days=i) for i in range(days)]


# ------------------------------------------------------------------ #
#  Eligibility
# ------------------------------------------------------------------ #


def check_eligibility(user_id: str, current_month: str, db: Session) -> ChallengeEligibilityResponse:
    """
    User is eligible for challenges that:

    * are active in current_month
    * the user has NOT joined already
    """
    from app.db import models  # local import to avoid circular deps

    active_challenges = (
        db.execute(
            select(models.Challenge).where(
                and_(
                    models.Challenge.start_month <= current_month,
                    models.Challenge.end_month >= current_month,
                )
            )
        )
        .scalars()
        .all()
    )

    available: List[ChallengeBrief] = []

    for ch in active_challenges:
        joined = db.scalar(
            select(func.count())
            .select_from(models.ChallengeParticipation)
            .where(
                and_(
                    models.ChallengeParticipation.user_id == user_id,
                    models.ChallengeParticipation.challenge_id == ch.id,
                    models.ChallengeParticipation.month == current_month,
                )
            )
        )
        if joined == 0:
            available.append(
                ChallengeBrief(
                    challenge_id=ch.id,
                    name=ch.name,
                    description=ch.description,
                )
            )

    eligible = bool(available)
    reason = "" if eligible else "No joinable challenges this month"

    return ChallengeEligibilityResponse(
        user_id=user_id,
        current_month=current_month,
        eligible=eligible,
        reason=reason,
        available_challenges=available,
    )


# old import compatibility
evaluate_challenge = check_eligibility


# ------------------------------------------------------------------ #
#  Streak‑challenge logic
# ------------------------------------------------------------------ #


def _current_streak(user_id: str, start_from: date, db: Session) -> Tuple[int, bool]:
    """
    Calculates streak length from start_from (inclusive) to today.
    Returns (streak_length, broken_flag).
    """
    from app.db import models

    today = date.today()
    days = _date_range(start_from, today)

    spent_days = db.execute(
        select(models.Transaction.spent_at)
        .where(
            and_(
                models.Transaction.user_id == user_id,
                models.Transaction.spent_at >= start_from,
                models.Transaction.spent_at <= today,
            )
        )
    ).scalars().all()

    spent_set = {d.date() for d in spent_days}

    streak = 0
    broken = False
    for d in days:
        if d in spent_set:
            streak += 1
        else:
            broken = True
            break
    return streak, broken


def run_streak_challenge(
    user_id: str,
    challenge_id: str,
    required_days: int,
    db: Session,
) -> Dict[str, int | bool]:
    """
    Checks if the user has an unbroken spending streak of `required_days`
    (e.g., “log expenses 7 days in a row”).
    """
    from app.db import models  # local to avoid circular deps

    # Fetch challenge start date or default to first day of this month
    ch = db.get(models.Challenge, challenge_id)
    if not ch:
        raise ValueError("Challenge not found")

    start_date = date.fromisoformat(ch.start_month + "-01")
    streak, broken = _current_streak(user_id, start_date, db)

    completed = streak >= required_days and not broken

    return {
        "user_id": user_id,
        "challenge_id": challenge_id,
        "streak": streak,
        "completed": completed,
    }


# ------------------------------------------------------------------ #
#  DB models reference (must be present in app.db.models)
# ------------------------------------------------------------------ #

"""
class Challenge(Base):
    __tablename__ = "challenges"
    id            = Column(String, primary_key=True)
    name          = Column(String, nullable=False)
    description   = Column(Text, nullable=False)
    start_month   = Column(String, nullable=False)  # "2025-05"
    end_month     = Column(String, nullable=False)  # "2025-12"

class ChallengeParticipation(Base):
    __tablename__ = "challenge_participations"
    id           = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id      = Column(String, nullable=False)
    challenge_id = Column(String, ForeignKey("challenges.id"), nullable=False)
    month        = Column(String, nullable=False)  # "2025-05"

class Transaction(Base):
    __tablename__ = "transactions"
    id        = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id   = Column(String, nullable=False)
    amount    = Column(Numeric(12, 2), nullable=False)
    spent_at  = Column(Date, nullable=False)
"""
