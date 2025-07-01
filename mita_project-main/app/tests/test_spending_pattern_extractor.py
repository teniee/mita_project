from app.engine.behavior.spending_pattern_extractor import extract_patterns


def test_extract_patterns_identifies_weekend_spender(monkeypatch):
    def fake_get_calendar_for_user(user_id: str, year: int, month: int):
        cal = {}
        for day in range(1, 15):
            key = f"2023-05-{day:02d}"
            if day in (6, 7, 13):
                cal[key] = {"shopping": 120}
            else:
                cal[key] = {"shopping": 10}
        return cal

    monkeypatch.setattr(
        "app.engine.behavior.spending_pattern_extractor.get_calendar_for_user",
        fake_get_calendar_for_user,
    )
    patterns = extract_patterns("u1", 2023, 5)
    assert "weekend_spender" in patterns["patterns"]
