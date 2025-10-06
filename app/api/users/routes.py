from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.api.users.schemas import UserProfileOut, UserUpdateIn
from app.core.session import get_db
from app.services.users_service import update_user_profile
from app.utils.response_wrapper import success_response

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserProfileOut, summary="Get current user's profile")
async def get_profile(current_user=Depends(get_current_user)):
    return success_response(
        {
            "id": current_user.id,
            "email": current_user.email,
            "country": current_user.country,
            "created_at": current_user.created_at.isoformat(),
            "timezone": current_user.timezone,
        }
    )


@router.patch(
    "/me", response_model=UserProfileOut, summary="Update current user's profile"
)
async def update_profile(
    data: UserUpdateIn,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    user = update_user_profile(current_user, data, db)
    return success_response(
        {
            "id": user.id,
            "email": user.email,
            "country": user.country,
            "timezone": user.timezone,
            "updated_at": user.updated_at.isoformat(),
        }
    )


# NEW ENDPOINTS for premium/subscription management

@router.get("/{user_id}/premium-status")
async def get_user_premium_status(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get premium subscription status for user"""
    # Verify user can access this data (self or admin)
    if current_user.id != user_id:
        # Check if admin
        pass  # Add admin check if needed

    # Check for premium subscription
    # TODO: Query Subscription model when implemented
    return success_response({
        "user_id": user_id,
        "is_premium": False,
        "subscription_type": None,
        "expires_at": None,
        "features": []
    })


@router.get("/{user_id}/premium-features")
async def get_user_premium_features(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get available premium features for user"""
    # Verify access
    if current_user.id != user_id:
        pass  # Add admin check

    # List of premium features
    premium_features = [
        {
            "feature_id": "advanced_analytics",
            "name": "Advanced Analytics",
            "enabled": False,
            "description": "Detailed spending analysis and predictions"
        },
        {
            "feature_id": "ai_insights",
            "name": "AI-Powered Insights",
            "enabled": False,
            "description": "Personalized financial advice from AI"
        },
        {
            "feature_id": "unlimited_goals",
            "name": "Unlimited Goals",
            "enabled": False,
            "description": "Track unlimited financial goals"
        },
        {
            "feature_id": "priority_support",
            "name": "Priority Support",
            "enabled": False,
            "description": "24/7 priority customer support"
        }
    ]

    return success_response({
        "user_id": user_id,
        "features": premium_features,
        "total_features": len(premium_features)
    })


@router.get("/{user_id}/subscription-history")
async def get_subscription_history(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get subscription payment history"""
    # Verify access
    if current_user.id != user_id:
        pass  # Add admin check

    # TODO: Query SubscriptionHistory model
    return success_response({
        "user_id": user_id,
        "subscriptions": [],
        "total_spent": 0.0,
        "active_since": None
    })
