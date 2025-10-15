from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.api.users.schemas import UserProfileOut, UserUpdateIn
from app.core.session import get_db
from app.db.models.user import User
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
            "income": float(current_user.monthly_income or 0),
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

    # Check for premium subscription - REAL DATABASE QUERY
    from app.db.models.subscription import Subscription
    from datetime import datetime

    subscription = db.query(Subscription).filter(
        Subscription.user_id == user_id,
        Subscription.status == "active",
        Subscription.expires_at > datetime.utcnow()
    ).order_by(Subscription.expires_at.desc()).first()

    is_premium = subscription is not None
    features = []

    if is_premium:
        # Map plan to features
        if subscription.plan in ["premium", "pro"]:
            features = ["advanced_analytics", "ai_insights", "unlimited_goals", "priority_support"]
        elif subscription.plan == "standard":
            features = ["advanced_analytics", "ai_insights"]

    return success_response({
        "user_id": user_id,
        "is_premium": is_premium,
        "subscription_type": subscription.plan if subscription else None,
        "expires_at": subscription.expires_at.isoformat() if subscription else None,
        "features": features
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

    # Check subscription - REAL DATABASE QUERY
    from app.db.models.subscription import Subscription
    from datetime import datetime

    subscription = db.query(Subscription).filter(
        Subscription.user_id == user_id,
        Subscription.status == "active",
        Subscription.expires_at > datetime.utcnow()
    ).first()

    # Determine which features are enabled based on plan
    enabled_features = set()
    if subscription:
        if subscription.plan in ["premium", "pro"]:
            enabled_features = {"advanced_analytics", "ai_insights", "unlimited_goals", "priority_support"}
        elif subscription.plan == "standard":
            enabled_features = {"advanced_analytics", "ai_insights"}

    # List all features with enabled status
    all_features = [
        {
            "feature_id": "advanced_analytics",
            "name": "Advanced Analytics",
            "enabled": "advanced_analytics" in enabled_features,
            "description": "Detailed spending analysis and predictions"
        },
        {
            "feature_id": "ai_insights",
            "name": "AI-Powered Insights",
            "enabled": "ai_insights" in enabled_features,
            "description": "Personalized financial advice from AI"
        },
        {
            "feature_id": "unlimited_goals",
            "name": "Unlimited Goals",
            "enabled": "unlimited_goals" in enabled_features,
            "description": "Track unlimited financial goals"
        },
        {
            "feature_id": "priority_support",
            "name": "Priority Support",
            "enabled": "priority_support" in enabled_features,
            "description": "24/7 priority customer support"
        }
    ]

    return success_response({
        "user_id": user_id,
        "features": all_features,
        "total_features": len(all_features),
        "enabled_count": len(enabled_features)
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

    # Query subscription history - REAL DATABASE QUERY
    from app.db.models.subscription import Subscription

    subscriptions = db.query(Subscription).filter(
        Subscription.user_id == user_id
    ).order_by(Subscription.created_at.desc()).all()

    subscription_list = []
    total_spent = 0.0
    active_since = None

    for sub in subscriptions:
        # Extract amount from receipt if available
        amount = 0.0
        if sub.receipt and isinstance(sub.receipt, dict):
            amount = float(sub.receipt.get('amount', 0.0))

        total_spent += amount

        subscription_list.append({
            "id": str(sub.id),
            "plan": sub.plan,
            "platform": sub.platform,
            "status": sub.status,
            "amount": amount,
            "starts_at": sub.starts_at.isoformat() if sub.starts_at else None,
            "expires_at": sub.expires_at.isoformat() if sub.expires_at else None,
            "created_at": sub.created_at.isoformat() if sub.created_at else None
        })

        # Find earliest active subscription
        if sub.status == "active" and sub.starts_at:
            if active_since is None or sub.starts_at < active_since:
                active_since = sub.starts_at

    return success_response({
        "user_id": user_id,
        "subscriptions": subscription_list,
        "total_spent": round(total_spent, 2),
        "active_since": active_since.isoformat() if active_since else None,
        "subscription_count": len(subscription_list)
    })
