
from app.engine.calendar_engine import CalendarEngine

def test_calendar_engine_days():
    income = 3000
    fixed_expenses = {"rent": 1200, "utilities": 200}
    flexible_categories = {"groceries": 500, "entertainment": 300}
    engine = CalendarEngine(income, fixed_expenses, flexible_categories)
    assert hasattr(engine, 'generate_calendar')
