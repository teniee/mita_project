from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.api.users.schemas import UserUpdateIn
from app.db.models import User


def update_user_profile(current_user: User, data: UserUpdateIn, db: Session) -> User:
    if data.email and current_user.email != data.email:
        existing_user = db.query(User).filter(User.email == data.email).first()
        if existing_user:
            raise HTTPException(status_code=400, detail="Email already in use.")
        current_user.email = data.email

    if data.country:
        current_user.country = data.country

    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return current_user
