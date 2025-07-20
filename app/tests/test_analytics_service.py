import datetime

from app.services.analytics_service import get_monthly_trend


class DummyDB:
    def execute(self, stmt):
        class Result:
            def all(self):
                return [
                    (datetime.date(2025, 1, 1), 12.5),
                    (datetime.date(2025, 1, 2), 7.5),
                ]

        return Result()


def test_get_monthly_trend_formats_result():
    result = get_monthly_trend("u1", DummyDB())
    assert result == [
        {"date": "2025-01-01", "amount": 12.5},
        {"date": "2025-01-02", "amount": 7.5},
    ]
