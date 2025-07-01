from sqlalchemy.orm import Session

from app.api.users.schemas import UserUpdateIn
from app.db.models import User


def update_user_profile(user: User, data: UserUpdateIn, db: Session) -> User:
    if data.email:
        user.email = data.email
    if data.country:
        user.country = data.country
    if data.timezone:
        user.timezone = data.timezone
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
