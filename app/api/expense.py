from app.utils.response_wrapper import success_response

from fastapi import APIRouter
from app.schemas.expense import ExpenseEntry, ExpenseHistoryRequest
from app.services.core.engine.expense_journal import ExpenseJournal

router = APIRouter()
journal = ExpenseJournal()

@router.post("/add")
def add_expense(entry: ExpenseEntry):
    return journal.add_entry(**entry.dict())

@router.post("/history")
def get_expense_history(request: ExpenseHistoryRequest):
    return journal.get_history(request.user_id)