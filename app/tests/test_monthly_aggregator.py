
from app.services.core.analytics.monthly_aggregator import aggregate_monthly_data

def test_monthly_aggregator_aggregate():
    calendar = [
        {
            "date": "2025-04-01",
            "planned_budget": {"food": 100},
            "actual_spent": {"food": 80}
        },
        {
            "date": "2025-04-15",
            "planned_budget": {"food": 200},
            "actual_spent": {"food": 220}
        }
    ]
    result = aggregate_monthly_data(calendar, "2025-04")
    assert isinstance(result, dict)
    assert "food" in result
    assert result["food"]["planned"] == 300
    assert result["food"]["spent"] == 300
    assert result["food"]["savings"] == 0
