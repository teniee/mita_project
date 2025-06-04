
from fastapi import APIRouter
from app.schemas.expense import ExpenseEntry, ExpenseHistoryRequest, ExpenseOut, ExpenseHistoryOut
from app.services.expense_service import add_user_expense, get_user_expense_history
from app.utils.response_wrapper import success_response

router = APIRouter(prefix="/expense", tags=["expense"])

@router.post("/add", response_model=ExpenseOut)
async def add_expense(entry: ExpenseEntry):
    result = add_user_expense(entry.dict())
    return success_response(result)

@router.post("/history", response_model=ExpenseHistoryOut)
async def get_history(request: ExpenseHistoryRequest):
    result = get_user_expense_history(request.user_id)
    return success_response(result)