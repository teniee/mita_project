
from app.services.core.engine.expense_journal import ExpenseJournal

def test_expense_journal_add_get():
    journal = ExpenseJournal()
    journal.add_entry('user123', 'expense_added', {'category': 'Food', 'amount': 50})
    history = journal.get_history('user123')
    assert isinstance(history, list)
    assert any(entry['action'] == 'expense_added' and entry['data']['amount'] == 50 for entry in history)
