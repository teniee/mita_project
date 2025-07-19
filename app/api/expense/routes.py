from fastapi import APIRouter, Depends
from app.api.dependencies import get_current_user

from app.schemas.expense import (
    ExpenseEntry,
    ExpenseHistoryOut,
    ExpenseOut,
)
from app.services.expense_service import (  # noqa: E501
    add_user_expense,
    get_user_expense_history,
)
from app.utils.response_wrapper import success_response

router = APIRouter(prefix="/expense", tags=["expense"])


@router.post("/add", response_model=ExpenseOut)
async def add_expense(entry: ExpenseEntry, user=Depends(get_current_user)):
    data = entry.dict()
    data["user_id"] = user.id
    result = add_user_expense(data)
    return success_response(result)


@router.post("/history", response_model=ExpenseHistoryOut)
async def get_history(user=Depends(get_current_user)):
    result = get_user_expense_history(user.id)
    return success_response(result)
