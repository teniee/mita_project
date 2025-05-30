
from app.services.core.analytics.progress_tracker import calculate_monthly_savings_progress

def test_progress_tracker_track():
    current_month = [
        {"planned_budget": {"food": 100}, "actual_spent": {"food": 80}},
        {"planned_budget": {"food": 100}, "actual_spent": {"food": 70}},
    ]
    previous_month = [
        {"planned_budget": {"food": 100}, "actual_spent": {"food": 90}},
        {"planned_budget": {"food": 100}, "actual_spent": {"food": 95}},
    ]
    result = calculate_monthly_savings_progress(current_month, previous_month)
    assert isinstance(result, dict)
    assert "percent_change" in result
