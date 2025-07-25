from datetime import date

from sqlalchemy.orm import Session

from app.core.session import get_db
from app.db.models import User
from app.engine.calendar_engine_behavioral import build_calendar
from app.services.auth_jwt_service import hash_password
from app.services.budget_planner import generate_budget_from_answers
from app.services.calendar_service_real import save_calendar_for_user
from app.services.expense_tracker import record_expense


def create_test_user():
    db: Session = next(get_db())
    existing = db.query(User).filter(User.email == "test@example.com").first()
    if existing:
        print("Test user already exists.")
        return existing

    user = User(
        is_premium=True,
        email="test@example.com",
        hashed_password=hash_password(
            "oPh-TW4BNM9vQc2S8DkP0XYhIMeJBS5vMBRT6s9aQ1_rBjhsSTP3adTUxKMZ-cvq6UabCJSEpUaaBMzqAHXbzA"
        ),
        full_name="Test User",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    user_id = user.id
    print(f"Test user created with ID: {user_id}")

    # Example answers used to generate a budget and calendar
    answers = {
        "income": {"monthly_income": 5000, "additional_income": 0},
        "fixed_expenses": {
            "rent": 1200,
            "utilities": 250,
            "insurance": 200,
            "loan": 300,
            "other": 150,
        },
        "savings_target": 500,
        "spending_habits": {
            "restaurants_frequency": "medium",
            "travel_frequency": "low",
            "entertainment_frequency": "medium",
            "shopping_frequency": "medium",
        },
        "region": "US-CA",
        "mode": "default",
        "year": 2025,
        "month": 5,
        "db": db,
    }

    budget = generate_budget_from_answers(answers)
    calendar = build_calendar({**answers, **budget})
    save_calendar_for_user(db, user_id, calendar)

    # Example expense entry for demo purposes
    record_expense(db, user_id, date(2025, 5, 3), "restaurants", 35.50, "Lunch at cafe")

    print("Calendar and test transaction initialized.")
    return user


if __name__ == "__main__":
    create_test_user()
