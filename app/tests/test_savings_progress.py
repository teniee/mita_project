from app.services.core.api.analytics_engine import calculate_monthly_savings_progress


def test_savings_progress():
    current_month = [
        {"planned_budget": {"food": 100}, "actual_spent": {"food": 50}},
        {"planned_budget": {"food": 100}, "actual_spent": {"food": 80}},
    ]
    previous_month = [
        {"planned_budget": {"food": 100}, "actual_spent": {"food": 70}},
        {"planned_budget": {"food": 100}, "actual_spent": {"food": 90}},
    ]
    result = calculate_monthly_savings_progress(current_month, previous_month)
    assert isinstance(result, dict)
    assert "current_saved" in result
