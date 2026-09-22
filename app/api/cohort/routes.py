import math
from decimal import ROUND_HALF_UP, Decimal
from statistics import median_low
from typing import Optional, Tuple

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.cohort.schemas import CohortOut, DriftOut, DriftRequest, ProfileRequest
from app.api.dependencies import get_current_user
from app.core.session import get_db
from app.db.models.user import User
from app.services.cohort_service import assign_user_cohort, get_user_drift
from app.services.core.income_classification_service import IncomeClassificationService
from app.utils.response_wrapper import success_response

router = APIRouter(prefix="/cohort", tags=["cohort"])

# Smallest number of contributing peers whose statistic may be published.
#
# "Anonymized peer comparison" (README.md) and "aggregated and anonymized"
# (PRIVACY_POLICY.md) were the promise; the endpoint had no minimum at all, so
# a cohort of one published that person's exact 30-day spending as the "peer
# average", and a cohort of two was solvable from the average and the median.
# The repository defines no threshold to inherit — the only one that existed
# was an unnamed `if peer_users:`, i.e. k = 1 — so this is a new constant.
#
# 10 is the conservative end of the usual statistical-disclosure minimum cell
# size (5-10). It is NOT what stops differencing — the published contract
# below does that — and it is deliberately not tuned to make the feature light
# up for MITA's current user count: below it, the honest
# "insufficient_peer_data" answer the clients already render is the answer.
MIN_PEER_COHORT = 10

# The one peer statistic published, peer_median, is rounded to this many
# dollars. $100 keeps the published median within 0.2-1.8% of the true one
# across the five tiers while leaving a caller who can steer one input no more
# than the member's $100 bucket. Rounding must not be made finer to "improve
# accuracy": it is the only thing between the median and a real member's total.
PEER_MEDIAN_INCREMENT = Decimal("100")

# Pinned: see the comment in get_peer_comparison. Never user.region.
PEER_COHORT_REGION = "US"


def _peer_income_tiers() -> tuple:
    """The five cohort tiers as monthly (lower, upper] bounds, exact Decimals.

    Edges come from the pinned region's income ladder (annual, so divided by
    12). The bottom tier starts above 0: an income of 0, a negative or a NULL
    one is "no income on record", which is also what makes the caller's own
    request answer "Set monthly income" — such users are no one's peers. The
    top tier has no upper bound (None).

    Membership is decided ONLY by _peer_tier() and the SQL filter in
    _peer_spending_by_user(), both reading these bounds with the same `>` /
    `<=`, so a caller and a peer on the same finite income always land in the
    same tier. An exact edge (3000.00) belongs to the tier below it. (A NaN or
    Infinity income gets the caller no comparison; PostgreSQL orders both
    above every number, so as a peer such a user counts in the top tier.)
    """
    ladder = IncomeClassificationService().get_tier_thresholds(PEER_COHORT_REGION)
    edges = [
        Decimal(str(ladder[key])) / 12
        for key in ("low", "lower_middle", "middle", "upper_middle")
    ]
    lowers = [Decimal("0")] + edges
    uppers = edges + [None]
    return tuple(zip(lowers, uppers))


_PEER_INCOME_TIERS = _peer_income_tiers()


def _peer_tier(monthly_income) -> Optional[Tuple[Decimal, Optional[Decimal]]]:
    """The (lower, upper] tier `monthly_income` falls in, or None if no income."""
    if monthly_income is None:
        return None
    income = Decimal(str(monthly_income))
    # PATCH /users/me accepts NaN and Infinity (JSON `NaN` parses, float allows
    # it). Neither is an income, and Decimal('NaN') > 0 raises.
    if not income.is_finite():
        return None
    for lower, upper in _PEER_INCOME_TIERS:
        if income > lower and (upper is None or income <= upper):
            return lower, upper
    return None


def _tier_bracket_label(lower: Decimal, upper: Optional[Decimal]) -> str:
    """Human label for the tier, stable for everyone inside it."""
    if lower == 0:
        return f"Up to ${upper:,.0f}/month"
    if upper is None:
        return f"Above ${lower:,.0f}/month"
    return f"${lower:,.0f} - ${upper:,.0f}/month"


def _peer_spending_by_user(db: Session, caller_id, caller_income, since) -> dict:
    """{peer user id: 30-day spending} for the caller's tier, caller excluded.

    Only peers who actually CONTRIBUTED — at least one non-deleted transaction
    since `since` — appear. A tier member with no spending contributes no
    figure and does not count towards MIN_PEER_COHORT.

    One query, always run. Looking the tier's members up first and skipping
    the spending query when there were none made an empty tier answer
    measurably faster (X-Response-Time-MS), which told a single caller that
    somebody had an income in a tier where nobody had contributed yet.
    """
    from sqlalchemy import func

    from app.db.models import User as UserModel
    from app.db.models.transaction import Transaction

    tier = _peer_tier(caller_income)
    if tier is None:
        return {}
    lower, upper = tier

    bracket_filters = [
        UserModel.id != caller_id,
        UserModel.monthly_income > lower,
    ]
    if upper is not None:
        bracket_filters.append(UserModel.monthly_income <= upper)

    rows = (
        db.query(Transaction.user_id, func.sum(Transaction.amount))
        .join(UserModel, UserModel.id == Transaction.user_id)
        .filter(
            *bracket_filters,
            Transaction.deleted_at.is_(None),
            Transaction.spent_at >= since,
        )
        .group_by(Transaction.user_id)
        .all()
    )
    # A NaN or infinite total (numeric allows both) is not a figure: counting
    # it would let one bad row 500 the whole tier's comparison.
    return {
        user_id: total
        for user_id, total in rows
        if total is not None and math.isfinite(total)
    }


def _round_to_increment(value) -> Decimal:
    """Round half-up to the nearest PEER_MEDIAN_INCREMENT dollars."""
    steps = (Decimal(str(value)) / PEER_MEDIAN_INCREMENT).quantize(
        Decimal("1"), rounding=ROUND_HALF_UP
    )
    return steps * PEER_MEDIAN_INCREMENT


def _peer_comparison_payload(
    your_spending: float, peer_totals, income_bracket: str
) -> Optional[dict]:
    """The published comparison, or None when the cohort is too small.

    What is published, and why nothing else is:

    * peer_median — median_low of the contributors' 30-day totals, rounded to
      PEER_MEDIAN_INCREMENT. median_low is always ONE member's figure, never
      the mean of two: a caller who controls one input (a second account in
      the tier) sees the published value follow a clamp of their own figure,
      which gives away at most the neighbouring member's rounding bucket. An
      interpolated median is linear in that input and gives it away exactly.
    * peer_average — withheld (None). A mean is linear in every member, so
      deterministic rounding cannot hide it from a caller who controls one
      member: stepping that member a cent at a time finds two rounding edges,
      and those give the cohort's exact size and exact sum at ANY increment.
      From there a single member joining, leaving or spending is exact.
    * percentile — withheld (None). Ranking the caller's spending against the
      raw totals turns the caller's own spending into a search probe: sweeping
      it walked every member's exact total out, one rank step at a time.
    * comparison and savings_potential — computed from the PUBLISHED median
      and the caller's own spending only, never from the raw cohort. They are
      then arithmetic on what the response already says, and sweeping one's
      own spending cannot reveal anything the median does not.
    * peer_count — the constant MIN_PEER_COHORT, meaning "at least this many".
      Any count that moves with membership (exact, or rounded to a multiple)
      shows the moment one person joins or leaves at some boundary.
    """
    if len(peer_totals) < MIN_PEER_COHORT:
        return None

    peer_median = float(_round_to_increment(median_low(peer_totals)))

    if your_spending < peer_median * 0.9:
        comparison = "well_below_average"
    elif your_spending < peer_median:
        comparison = "below_average"
    elif your_spending <= peer_median * 1.1:
        comparison = "average"
    elif your_spending <= peer_median * 1.3:
        comparison = "above_average"
    else:
        comparison = "well_above_average"

    savings_potential = max(your_spending - peer_median, 0.0)

    return {
        "your_spending": round(your_spending, 2),
        "peer_average": None,
        "peer_median": peer_median,
        "percentile": None,
        "comparison": comparison,
        "savings_potential": round(savings_potential, 2),
        "peer_count": MIN_PEER_COHORT,
        "income_bracket": income_bracket,
        "analysis_period_days": 30,
        "note": (
            f"Median of at least {MIN_PEER_COHORT} people in your income tier, "
            f"rounded to the nearest ${PEER_MEDIAN_INCREMENT:,.0f}"
        ),
    }


@router.post("/assign", response_model=CohortOut)
def assign_cohort(
    payload: ProfileRequest, user=Depends(get_current_user)  # noqa: B008
):
    cohort = assign_user_cohort(payload.profile)
    return success_response({"cohort": cohort})


@router.post("/drift", response_model=DriftOut)
def drift(payload: DriftRequest, user=Depends(get_current_user)):  # noqa: B008
    drift = get_user_drift(user.id)
    return success_response({"drift": drift})


@router.get("/insights")
def cohort_insights(
    user=Depends(get_current_user),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
):
    """Get cohort-based insights for the user"""
    from collections import defaultdict
    from datetime import datetime, timedelta, timezone

    from app.db.models import Transaction
    from app.db.models import User as UserModel

    # Get user's monthly income for cohort classification
    user_data = db.query(UserModel).filter(UserModel.id == user.id).first()
    user_income = (
        float(user_data.monthly_income) if user_data and user_data.monthly_income else 0
    )

    # Calculate user's actual spending (last 30 days)
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    user_transactions = (
        db.query(Transaction)
        .filter(
            Transaction.user_id == user.id,
            Transaction.deleted_at.is_(None),
            Transaction.spent_at >= thirty_days_ago,
        )
        .all()
    )

    user_total_spending = sum(
        t.amount for t in user_transactions if t.amount is not None
    ) or Decimal("0")

    # Get spending by category
    category_spending = defaultdict(lambda: Decimal("0"))
    for txn in user_transactions:
        if txn.amount is not None:
            cat = txn.category or "other"
            category_spending[cat] += txn.amount

    # Determine cohort type based on spending vs income ratio
    if user_income > 0:
        spending_ratio = float(user_total_spending) / user_income
        if spending_ratio < 0.5:
            cohort_type = "conservative_saver"
        elif spending_ratio < 0.75:
            cohort_type = "moderate_spender"
        elif spending_ratio < 0.9:
            cohort_type = "balanced_spender"
        else:
            cohort_type = "high_spender"
    else:
        cohort_type = "unclassified"

    # Calculate peer comparison (simplified - would need actual peer data)
    # For now, use statistical estimates based on income tier
    estimated_peer_spending = user_income * 0.7 if user_income > 0 else 2500

    # Generate insights based on real data.
    # user_total_spending is Decimal; estimated_peer_spending is float —
    # mixing them in arithmetic raised TypeError -> 500. Compare in float.
    insights_list = []
    if user_income > 0:
        diff_percent = (
            (float(user_total_spending) - estimated_peer_spending)
            / estimated_peer_spending
            * 100
        )
        if diff_percent < -10:
            insights_list.append(
                f"You spend {abs(diff_percent):.0f}% less than estimated peers in your income bracket"
            )
        elif diff_percent > 10:
            insights_list.append(
                f"You spend {diff_percent:.0f}% more than estimated peers in your income bracket"
            )
        else:
            insights_list.append("Your spending is aligned with your income bracket")

    # Category-specific insights
    if category_spending:
        top_category = max(category_spending.items(), key=lambda x: x[1])
        insights_list.append(
            f"Your highest spending category is {top_category[0]} at ${top_category[1]:.2f}"
        )

    # Recommendations based on actual data
    recommendations_list = []
    if user_income > 0 and float(user_total_spending) > user_income * 0.9:
        recommendations_list.append(
            "Consider reducing discretionary spending to build emergency fund"
        )
    if len(user_transactions) > 50:
        recommendations_list.append(
            "High transaction frequency - consider consolidating purchases"
        )
    if not recommendations_list:
        recommendations_list.append(
            "Keep tracking expenses for personalized recommendations"
        )

    return success_response(
        {
            "cohort_type": cohort_type,
            "peer_comparison": {
                "estimated_peer_spending": round(estimated_peer_spending, 2),
                "user_spending": round(user_total_spending, 2),
                "percentile": 50,  # Would need actual peer data to calculate
            },
            "insights": (
                insights_list
                if insights_list
                else ["Continue tracking to generate insights"]
            ),
            "recommendations": recommendations_list,
            "based_on_income": user_income,
            "analysis_period_days": 30,
        }
    )


@router.get("/income_classification")
def income_classification(
    user=Depends(get_current_user),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
):
    """Get income classification analysis for the user"""
    from collections import defaultdict
    from datetime import datetime, timedelta, timezone

    from app.db.models import Transaction
    from app.db.models import User as UserModel

    # Get user's actual monthly income from profile
    user_data = db.query(UserModel).filter(UserModel.id == user.id).first()
    monthly_income = (
        float(user_data.monthly_income) if user_data and user_data.monthly_income else 0
    )

    # Classify income tier
    if monthly_income == 0:
        income_tier = "unknown"
        confidence = 0.0
    elif monthly_income < 30000:
        income_tier = "low_income"
        confidence = 0.9
    elif monthly_income < 60000:
        income_tier = "lower_middle_income"
        confidence = 0.9
    elif monthly_income < 100000:
        income_tier = "middle_income"
        confidence = 0.9
    elif monthly_income < 200000:
        income_tier = "upper_middle_income"
        confidence = 0.9
    else:
        income_tier = "high_income"
        confidence = 0.9

    # Analyze spending patterns from last 90 days
    ninety_days_ago = datetime.now(timezone.utc) - timedelta(days=90)
    transactions = (
        db.query(Transaction)
        .filter(
            Transaction.user_id == user.id,
            Transaction.deleted_at.is_(None),
            Transaction.spent_at >= ninety_days_ago,
        )
        .all()
    )

    # Calculate category distribution
    category_totals = defaultdict(lambda: Decimal("0"))
    total_spending = Decimal("0")

    for txn in transactions:
        if txn.amount is not None:
            amount = txn.amount
            total_spending += amount
            cat = txn.category or "other"
            category_totals[cat] += amount

    # Calculate percentages
    category_percentages = {}
    if total_spending > 0:
        for cat, amount in category_totals.items():
            category_percentages[cat] = round(
                (float(amount) / float(total_spending)) * 100, 1
            )

    # Determine spending pattern consistency
    if len(transactions) < 10:
        spending_pattern = "insufficient_data"
    elif len(set([t.spent_at.date() for t in transactions])) > 60:
        spending_pattern = "consistent"
    else:
        spending_pattern = "irregular"

    # Calculate savings rate. total_spending is Decimal; monthly_income is
    # float — keep the arithmetic in float to avoid a Decimal/float TypeError.
    if monthly_income > 0:
        monthly_spending = float(total_spending) / 3  # 90 days / 3 months
        savings_rate = ((monthly_income - monthly_spending) / monthly_income) * 100
        if savings_rate < 0:
            savings_rate_label = "negative"
        elif savings_rate < 10:
            savings_rate_label = "low"
        elif savings_rate < 20:
            savings_rate_label = "moderate"
        else:
            savings_rate_label = "high"
    else:
        savings_rate = 0
        savings_rate_label = "unknown"

    # Generate recommendations
    recommendations = []
    if monthly_income > 0:
        if savings_rate < 10:
            recommendations.append(
                f"Current savings rate: {savings_rate:.1f}%. Aim for at least 20% savings"
            )
        elif savings_rate >= 20:
            recommendations.append(f"Excellent savings rate of {savings_rate:.1f}%!")

        if float(total_spending) / 3 > monthly_income * 0.9:
            recommendations.append(
                "Spending exceeds 90% of income - consider budget review"
            )

    if not recommendations:
        recommendations.append("Continue tracking for personalized recommendations")

    return success_response(
        {
            "income_tier": income_tier,
            "annual_income": monthly_income * 12 if monthly_income > 0 else None,
            "classification_confidence": confidence,
            "factors": {
                "spending_patterns": spending_pattern,
                "savings_rate": savings_rate_label,
                "savings_rate_percent": (
                    round(savings_rate, 1) if monthly_income > 0 else None
                ),
            },
            "spending_distribution": category_percentages,
            "recommendations": recommendations,
            "analysis_period_days": 90,
            "transactions_analyzed": len(transactions),
        }
    )


@router.get("/peer_comparison")
def get_peer_comparison(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get peer comparison data based on user's cohort"""
    from datetime import datetime, timedelta, timezone

    from sqlalchemy import func

    from app.db.models import User as UserModel
    from app.db.models.transaction import Transaction

    # Get user's monthly income for cohort determination
    user_data = db.query(UserModel).filter(UserModel.id == user.id).first()
    user_income = (
        float(user_data.monthly_income) if user_data and user_data.monthly_income else 0
    )

    # Get user's spending for last 30 days
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    user_spending = (
        db.query(func.sum(Transaction.amount))
        .filter(
            Transaction.user_id == user.id,
            # A deleted transaction is not spending. Without this the Peer
            # Insights screen showed a user $208 after they had deleted an $8
            # expense down to $200 — money the ledger, dashboard and calendar
            # all agreed was gone.
            Transaction.deleted_at.is_(None),
            Transaction.spent_at >= thirty_days_ago,
        )
        .scalar()
        or 0.0
    )
    user_spending = float(user_spending)

    # Cohort = the caller's income TIER, not a window around their own income.
    #
    # A ±20% window centred on the caller is attacker-steerable: monthly_income
    # is writable through PATCH /api/users/me, so sweeping it and watching the
    # response walked the window one person at a time. Tiers are server-defined
    # and disjoint, so editing income INSIDE a tier changes nothing. The caller
    # can still pick which of the five tiers to look at by editing income —
    # that is five fixed cohorts, each seeing what every member of it sees, not
    # a window that can be slid past one person.
    #
    # The region is PINNED (PEER_COHORT_REGION). Income ladders are per-region,
    # so reading user.region (client-settable, users_service.py) would make the
    # brackets overlap again and reopen the differencing attack.
    tier = _peer_tier(user_data.monthly_income if user_data else None)
    if tier is not None:
        peer_totals = list(
            _peer_spending_by_user(
                db, user.id, user_data.monthly_income, thirty_days_ago
            ).values()
        )
        payload = _peer_comparison_payload(
            user_spending, peer_totals, _tier_bracket_label(*tier)
        )
        if payload is not None:
            return success_response(payload)

    # Fallback if no peers or no income data
    return success_response(
        {
            "your_spending": round(user_spending, 2),
            "peer_average": None,
            "peer_median": None,
            "percentile": None,
            "comparison": "insufficient_peer_data",
            "savings_potential": 0,
            "peer_count": 0,
            "note": (
                "Need more users in database for peer comparison"
                if user_income > 0
                else "Set monthly income for peer comparison"
            ),
        }
    )
