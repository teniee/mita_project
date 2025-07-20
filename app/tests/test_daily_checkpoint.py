from app.services.core.analytics.daily_checkpoint import get_today_budget


def test_get_today_budget():
    calendar = [
        {
            "date": "2023-04-01",
            "planned_budget": {"food": 50, "transport": 20},
            "actual_spent": {"food": 30, "transport": 5},
        }
    ]
    result = get_today_budget(calendar, "2023-04-01")
    assert isinstance(result, dict)
    assert result["remaining_budget"]["food"] == 20
    assert result["remaining_budget"]["transport"] == 15
