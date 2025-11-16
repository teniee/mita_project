from decimal import Decimal
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.cohort.schemas import CohortOut, DriftOut, DriftRequest, ProfileRequest
from app.api.dependencies import get_current_user
from app.services.cohort_service import assign_user_cohort, get_user_drift
from app.utils.response_wrapper import success_response
from app.core.session import get_db
from app.db.models.user import User

router = APIRouter(prefix="/cohort", tags=["cohort"])


@router.post("/assign", response_model=CohortOut)
async def assign_cohort(
    payload: ProfileRequest, user=Depends(get_current_user)  # noqa: B008
):
    cohort = assign_user_cohort(payload.profile)
    return success_response({"cohort": cohort})


@router.post("/drift", response_model=DriftOut)
async def drift(payload: DriftRequest, user=Depends(get_current_user)):  # noqa: B008
    drift = get_user_drift(user.id)
    return success_response({"drift": drift})


@router.get("/insights")
async def cohort_insights(
    user=Depends(get_current_user),  # noqa: B008
    db: Session = Depends(get_db)  # noqa: B008
):
    """Get cohort-based insights for the user"""
    from app.db.models import Transaction, User as UserModel
    from datetime import datetime, timedelta
    from collections import defaultdict

    # Get user's monthly income for cohort classification
    user_data = db.query(UserModel).filter(UserModel.id == user.id).first()
    user_income = float(user_data.monthly_income) if user_data and user_data.monthly_income else 0

    # Calculate user's actual spending (last 30 days)
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    user_transactions = db.query(Transaction).filter(
        Transaction.user_id == user.id,
        Transaction.spent_at >= thirty_days_ago
    ).all()

    user_total_spending = sum(t.amount for t in user_transactions if t.amount is not None) or Decimal('0')

    # Get spending by category
    category_spending = defaultdict(lambda: Decimal('0'))
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

    # Generate insights based on real data
    insights_list = []
    if user_income > 0:
        diff_percent = ((user_total_spending - estimated_peer_spending) / estimated_peer_spending * 100)
        if diff_percent < -10:
            insights_list.append(f"You spend {abs(diff_percent):.0f}% less than estimated peers in your income bracket")
        elif diff_percent > 10:
            insights_list.append(f"You spend {diff_percent:.0f}% more than estimated peers in your income bracket")
        else:
            insights_list.append("Your spending is aligned with your income bracket")

    # Category-specific insights
    if category_spending:
        top_category = max(category_spending.items(), key=lambda x: x[1])
        insights_list.append(f"Your highest spending category is {top_category[0]} at ${top_category[1]:.2f}")

    # Recommendations based on actual data
    recommendations_list = []
    if user_income > 0 and user_total_spending > user_income * 0.9:
        recommendations_list.append("Consider reducing discretionary spending to build emergency fund")
    if len(user_transactions) > 50:
        recommendations_list.append("High transaction frequency - consider consolidating purchases")
    if not recommendations_list:
        recommendations_list.append("Keep tracking expenses for personalized recommendations")

    return success_response({
        "cohort_type": cohort_type,
        "peer_comparison": {
            "estimated_peer_spending": round(estimated_peer_spending, 2),
            "user_spending": round(user_total_spending, 2),
            "percentile": 50  # Would need actual peer data to calculate
        },
        "insights": insights_list if insights_list else ["Continue tracking to generate insights"],
        "recommendations": recommendations_list,
        "based_on_income": user_income,
        "analysis_period_days": 30
    })


@router.get("/income_classification")
async def income_classification(
    user=Depends(get_current_user),  # noqa: B008
    db: Session = Depends(get_db)  # noqa: B008
):
    """Get income classification analysis for the user"""
    from app.db.models import Transaction, User as UserModel
    from datetime import datetime, timedelta
    from collections import defaultdict

    # Get user's actual monthly income from profile
    user_data = db.query(UserModel).filter(UserModel.id == user.id).first()
    monthly_income = float(user_data.monthly_income) if user_data and user_data.monthly_income else 0

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
    ninety_days_ago = datetime.utcnow() - timedelta(days=90)
    transactions = db.query(Transaction).filter(
        Transaction.user_id == user.id,
        Transaction.spent_at >= ninety_days_ago
    ).all()

    # Calculate category distribution
    category_totals = defaultdict(lambda: Decimal('0'))
    total_spending = Decimal('0')

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
            category_percentages[cat] = round((float(amount) / float(total_spending)) * 100, 1)

    # Determine spending pattern consistency
    if len(transactions) < 10:
        spending_pattern = "insufficient_data"
    elif len(set([t.spent_at.date() for t in transactions])) > 60:
        spending_pattern = "consistent"
    else:
        spending_pattern = "irregular"

    # Calculate savings rate
    if monthly_income > 0:
        monthly_spending = total_spending / 3  # 90 days / 3 months
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
            recommendations.append(f"Current savings rate: {savings_rate:.1f}%. Aim for at least 20% savings")
        elif savings_rate >= 20:
            recommendations.append(f"Excellent savings rate of {savings_rate:.1f}%!")

        if total_spending / 3 > monthly_income * 0.9:
            recommendations.append("Spending exceeds 90% of income - consider budget review")

    if not recommendations:
        recommendations.append("Continue tracking for personalized recommendations")

    return success_response({
        "income_tier": income_tier,
        "annual_income": monthly_income * 12 if monthly_income > 0 else None,
        "classification_confidence": confidence,
        "factors": {
            "spending_patterns": spending_pattern,
            "savings_rate": savings_rate_label,
            "savings_rate_percent": round(savings_rate, 1) if monthly_income > 0 else None
        },
        "spending_distribution": category_percentages,
        "recommendations": recommendations,
        "analysis_period_days": 90,
        "transactions_analyzed": len(transactions)
    })


@router.get("/peer_comparison")
async def get_peer_comparison(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get peer comparison data based on user's cohort"""
    from app.db.models.transaction import Transaction
    from app.db.models import User as UserModel
    from datetime import datetime, timedelta
    from sqlalchemy import func

    # Get user's monthly income for cohort determination
    user_data = db.query(UserModel).filter(UserModel.id == user.id).first()
    user_income = float(user_data.monthly_income) if user_data and user_data.monthly_income else 0

    # Get user's spending for last 30 days
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    user_spending = db.query(func.sum(Transaction.amount)).filter(
        Transaction.user_id == user.id,
        Transaction.spent_at >= thirty_days_ago
    ).scalar() or 0.0
    user_spending = float(user_spending)

    # Get all users in similar income bracket (within 20%)
    if user_income > 0:
        lower_bound = user_income * 0.8
        upper_bound = user_income * 1.2

        # Find users in same income bracket
        peer_users = db.query(UserModel.id).filter(
            UserModel.id != user.id,
            UserModel.monthly_income >= lower_bound,
            UserModel.monthly_income <= upper_bound
        ).all()

        peer_user_ids = [p.id for p in peer_users]

        if peer_user_ids:
            # Calculate actual peer spending
            peer_spending_data = db.query(func.sum(Transaction.amount)).filter(
                Transaction.user_id.in_(peer_user_ids),
                Transaction.spent_at >= thirty_days_ago
            ).group_by(Transaction.user_id).all()

            if peer_spending_data:
                peer_amounts = [float(s) for s in peer_spending_data if s]
                if peer_amounts:
                    peer_average = sum(peer_amounts) / len(peer_amounts)
                    peer_median = sorted(peer_amounts)[len(peer_amounts) // 2]

                    # Calculate user's percentile
                    below_user = sum(1 for amt in peer_amounts if amt < user_spending)
                    percentile = int((below_user / len(peer_amounts)) * 100) if peer_amounts else 50

                    # Determine comparison
                    if user_spending < peer_median * 0.9:
                        comparison = "well_below_average"
                    elif user_spending < peer_median:
                        comparison = "below_average"
                    elif user_spending <= peer_median * 1.1:
                        comparison = "average"
                    elif user_spending <= peer_median * 1.3:
                        comparison = "above_average"
                    else:
                        comparison = "well_above_average"

                    # Calculate potential savings
                    if user_spending > peer_median:
                        savings_potential = user_spending - peer_median
                    else:
                        savings_potential = 0

                    return success_response({
                        "your_spending": round(user_spending, 2),
                        "peer_average": round(peer_average, 2),
                        "peer_median": round(peer_median, 2),
                        "percentile": percentile,
                        "comparison": comparison,
                        "savings_potential": round(savings_potential, 2),
                        "peer_count": len(peer_user_ids),
                        "income_bracket": f"${lower_bound:.0f} - ${upper_bound:.0f}",
                        "analysis_period_days": 30
                    })

    # Fallback if no peers or no income data
    return success_response({
        "your_spending": round(user_spending, 2),
        "peer_average": None,
        "peer_median": None,
        "percentile": None,
        "comparison": "insufficient_peer_data",
        "savings_potential": 0,
        "peer_count": 0,
        "note": "Need more users in database for peer comparison" if user_income > 0 else "Set monthly income for peer comparison"
    })
