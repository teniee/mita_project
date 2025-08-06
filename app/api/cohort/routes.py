from fastapi import APIRouter, Depends

from app.api.cohort.schemas import CohortOut, DriftOut, DriftRequest, ProfileRequest
from app.api.dependencies import get_current_user
from app.services.cohort_service import assign_user_cohort, get_user_drift
from app.utils.response_wrapper import success_response
from sqlalchemy.orm import Session
from app.core.session import get_db

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
    try:
        # Mock implementation - replace with actual cohort analysis
        insights = {
            "cohort_type": "moderate_spender",
            "peer_comparison": {
                "average_spending": 2500.00,
                "user_spending": 2200.00,
                "percentile": 65
            },
            "insights": [
                "You spend 12% less than similar users in your cohort",
                "Your grocery spending is above average for your income level",
                "Consider increasing savings rate to match top performers"
            ],
            "recommendations": [
                "Set up automatic savings transfers",
                "Review subscription services",
                "Consider meal planning to reduce food costs"
            ]
        }
        return success_response(insights)
    except Exception as e:
        return success_response({
            "cohort_type": "unknown",
            "peer_comparison": {},
            "insights": ["Unable to generate insights at this time"],
            "recommendations": ["Continue tracking expenses for better insights"]
        })


@router.get("/income_classification")
async def income_classification(
    user=Depends(get_current_user),  # noqa: B008
    db: Session = Depends(get_db)  # noqa: B008
):
    """Get income classification analysis for the user"""
    try:
        # Mock implementation - replace with actual income analysis
        classification = {
            "income_tier": "middle_income",
            "classification_confidence": 0.85,
            "factors": {
                "spending_patterns": "consistent",
                "category_distribution": "balanced",
                "savings_rate": "moderate"
            },
            "peer_group": {
                "average_income": 65000,
                "spending_categories": {
                    "housing": 30,
                    "food": 15,
                    "transportation": 12,
                    "entertainment": 8,
                    "savings": 20,
                    "other": 15
                }
            },
            "recommendations": [
                "Your spending pattern suggests middle-income stability",
                "Consider increasing emergency fund to 6 months of expenses",
                "You're on track with recommended savings rate"
            ]
        }
        return success_response(classification)
    except Exception as e:
        return success_response({
            "income_tier": "unknown",
            "classification_confidence": 0.0,
            "factors": {},
            "peer_group": {},
            "recommendations": ["Continue tracking expenses for income classification"]
        })
