from app.engine.challenge_engine_auto import auto_run_challenge_streak


def test_streak_progress_basic():
    calendar = [{"date": f"2025-01-{i:02d}", "status": {}} for i in range(1, 6)]
    result = auto_run_challenge_streak(calendar, "u1", {"last_claimed": "2025-01-01"})
    assert isinstance(result, dict)
    assert "streak_days" in result
