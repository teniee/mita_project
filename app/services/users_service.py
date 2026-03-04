from sqlalchemy.orm import Session

from app.api.users.schemas import UserUpdateIn
from app.db.models import User


def update_user_profile(user: User, data: UserUpdateIn, db: Session) -> User:
    """
    Update user profile.
    NOTE: user object may be from async session, so we query fresh from sync session.
    """
    # CRITICAL FIX: Query user fresh in sync session to avoid async/sync session conflict
    # The user object passed in might be attached to an async session from get_current_user
    db_user = db.query(User).filter(User.id == user.id).first()

    if not db_user:
        raise ValueError(f"User {user.id} not found in database")

    # Basic fields
    if data.email is not None:
        db_user.email = data.email
    if data.country is not None:
        db_user.country = data.country
    if data.timezone is not None:
        db_user.timezone = data.timezone

    # Profile fields
    if data.name is not None:
        db_user.name = data.name
    if data.income is not None:
        db_user.monthly_income = data.income
    if data.savings_goal is not None:
        db_user.savings_goal = data.savings_goal
    if data.budget_method is not None:
        db_user.budget_method = data.budget_method
    if data.currency is not None:
        db_user.currency = data.currency
    if data.region is not None:
        db_user.region = data.region

    # Preferences
    if data.notifications_enabled is not None:
        db_user.notifications_enabled = data.notifications_enabled
    if data.dark_mode_enabled is not None:
        db_user.dark_mode_enabled = data.dark_mode_enabled

    # No need to db.add() since db_user is already in session from query
    db.commit()
    db.refresh(db_user)
    return db_user
