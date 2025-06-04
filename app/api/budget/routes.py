
from fastapi import APIRouter, Depends
from app.core.db import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from app.api.budget.services import fetch_spent_by_category, fetch_remaining_budget
from app.services.auth_dependency import get_current_user
from app.core.db import get_db
from app.db.models.user import User  # предполагается, что User определён в models

router = APIRouter(prefix="/budget", tags=["budget"])

@router.get("/spent")
async def spent(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return fetch_spent_by_category(db, user.id, 2025, 5)

@router.get("/remaining")
async def remaining(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return fetch_remaining_budget(db, user.id, 2025, 5)