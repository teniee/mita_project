# isort: off
from app.services.core.analytics.calendar_anomaly_detector import (
    detect_anomalies,
)
from app.services.core.analytics.monthly_aggregator import (
    aggregate_monthly_data,
)
from app.services.core.analytics.progress_tracker import (
    calculate_monthly_savings_progress,
)

# isort: on


class AnalyticsEngine:
    """High level API aggregating analytics helpers."""

    # The engine simply proxies helper functions. An explicit ``__init__`` is
    # not needed, which keeps the class lightweight.

    def get_monthly_summary(self, calendar: list, month: str) -> dict:
        return aggregate_monthly_data(calendar, month)

    def get_anomalies(self, calendar: list, threshold: float = 2.5) -> list:
        return detect_anomalies(calendar, threshold)

    def get_savings_progress(self, current_month: list, previous_month: list) -> dict:
        return calculate_monthly_savings_progress(current_month, previous_month)


# Re-export helper functions for convenience
__all__ = [
    "aggregate_monthly_data",
    "detect_anomalies",
    "calculate_monthly_savings_progress",
    "AnalyticsEngine",
]
