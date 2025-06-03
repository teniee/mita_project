# isort: off
from app.services.core.analytics.calendar_anomaly_detector import (
    detect_anomalies,
)
from app.services.core.analytics.monthly_aggregator import (
    aggregate_monthly_data,
)

# isort: on


class AnalyticsEngine:
    def __init__(self):
        pass

    def get_monthly_summary(self, calendar: list, month: str) -> dict:
        return aggregate_monthly_data(calendar, month)

    def get_anomalies(self, calendar: list, threshold: float = 2.5) -> list:
        return detect_anomalies(calendar, threshold)
