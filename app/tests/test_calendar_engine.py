
from app.engine.calendar_engine import CalendarEngine


def test_calendar_engine_days():
    income = 3000
    fixed_expenses = {"rent": 1200, "utilities": 200}
    flexible_categories = {"groceries": 0.5, "entertainment": 0.5}

    engine = CalendarEngine(income, fixed_expenses, flexible_categories)
    calendar = engine.generate_calendar(2023, 1)

    # Verify correct number of days
    assert len(calendar) == 31

    first_day = calendar["2023-01-01"]
    assert "rent" in first_day["planned_budget"]
    assert "groceries" in first_day["planned_budget"]

    # Entertainment should appear on at least one day
    assert any(
        "entertainment" in day["planned_budget"] for day in calendar.values()
    )
