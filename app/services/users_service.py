from sqlalchemy.ext.asyncio import AsyncSession

from app.api.users.schemas import UserUpdateIn
from app.db.models import User


async def update_user_profile(user: User, data: UserUpdateIn, db: AsyncSession) -> User:
    # Basic fields
    if data.email is not None:
        user.email = data.email
    if data.country is not None:
        user.country = data.country
    if data.timezone is not None:
        user.timezone = data.timezone

    # Profile fields
    if data.name is not None:
        user.name = data.name
    if data.income is not None:
        user.monthly_income = data.income
    if data.savings_goal is not None:
        user.savings_goal = data.savings_goal
    if data.budget_method is not None:
        user.budget_method = data.budget_method
    if data.currency is not None:
        user.currency = data.currency
    if data.region is not None:
        user.region = data.region

    # Preferences
    if data.notifications_enabled is not None:
        user.notifications_enabled = data.notifications_enabled
    if data.dark_mode_enabled is not None:
        user.dark_mode_enabled = data.dark_mode_enabled

    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user
