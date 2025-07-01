
from app.services.core.engine.expense_journal import ExpenseJournal

journal = ExpenseJournal()

def add_user_expense(data: dict):
    return journal.add_entry(**data)

def get_user_expense_history(user_id: str):
    return journal.get_history(user_id)
