from app.services.core.engine.goal_tracking import calculate_goal_progress


def test_goal_progress():
    goal = {"name": "Trip", "target_amount": 1000}
    calendar = {i: {"savings": 100} for i in range(1, 6)}
    result = calculate_goal_progress(goal, calendar)
    assert result["percent_complete"] == 50.0
    assert result["status"] == "in_progress"
