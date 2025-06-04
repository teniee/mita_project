from sqlalchemy.orm import Session
from app.db.models import User
from app.api.users.schemas import UserUpdateIn

def update_user_profile(user: User, data: UserUpdateIn, db: Session) -> User:
    if data.email:
        user.email = data.email
    if data.country:
        user.country = data.country
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
