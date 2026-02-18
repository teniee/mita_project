import datetime
import random
from typing import Dict, List

CATEGORY_BEHAVIOR: Dict[str, str] = {
    "groceries": "spread",
    "dining out": "clustered",
    "delivery": "clustered",
    "rent": "fixed",
    "mortgage": "fixed",
    "utilities": "fixed",
    "home repairs": "clustered",
    "transport public": "spread",
    "transport gas": "clustered",
    "taxi ridehailing": "clustered",
    "car maintenance": "clustered",
    "subscriptions software": "fixed",
    "media streaming": "fixed",
    "cloud storage": "fixed",
    "clothing": "clustered",
    "tech gadgets": "clustered",
    "home goods": "clustered",
    "insurance medical": "fixed",
    "out of pocket medical": "clustered",
    "gym fitness": "fixed",
    "entertainment events": "clustered",
    "gaming": "clustered",
    "hobbies": "clustered",
    "flights": "fixed",
    "hotels": "fixed",
    "local transport": "spread",
    "courses online": "fixed",
    "books": "clustered",
    "school fees": "fixed",
    "savings emergency": "spread",
    "savings goal based": "spread",
    "debt repayment": "fixed",
    "investment contribution": "fixed",
}


class CalendarDay:
    def __init__(self, date: datetime.date):
        self.date: datetime.date = date
        self.day_type: str = self._get_day_type(date)
        self.planned_budget: Dict[str, float] = {}
        self.actual_spending: Dict[str, float] = {}
        self.recommendations: List[str] = []
        self.status: str = "green"
        self.total: float = 0.0  # Total planned budget for the day

    def _get_day_type(self, date: datetime.date) -> str:
        return "weekend" if date.weekday() >= 5 else "weekday"

    def to_dict(self) -> Dict:
        return {
            "date": self.date.strftime("%Y-%m-%d"),
            "day_type": self.day_type,
            "planned_budget": self.planned_budget,
            "actual_spending": self.actual_spending,
            "recommendations": self.recommendations,
            "status": self.status,
            "total": self.total,
        }


def distribute_budget_over_days(
    days: List[CalendarDay],
    category: str,
    total: float,
    user_frequency: int = None
) -> None:
    """
    Distribute budget across days based on category behavior and user frequency.

    Args:
        days: List of CalendarDay objects
        category: Spending category
        total: Total monthly budget for this category
        user_frequency: Number of times per month user expects to spend in this category
                       (e.g., coffee_per_week * 4, transport_per_month, etc.)
    """
    behavior = CATEGORY_BEHAVIOR.get(category, "spread")
    num_days = len(days)

    if behavior == "fixed":
        index = (
            0
            if category in ["rent", "mortgage", "school fees"]
            else min(4, num_days - 1)
        )
        days[index].planned_budget[category] = round(total, 2)

    elif behavior == "spread":
        weekday_days = [d for d in days if d.day_type == "weekday"]

        # FIX: Use actual user frequency instead of hardcoded [::2] pattern
        if user_frequency and user_frequency > 0:
            # User specified how many times they spend in this category
            # Allocate budget to that many days (capped at available weekdays)
            num_spread_days = min(int(user_frequency), len(weekday_days))
            spread_days = weekday_days[:num_spread_days] if num_spread_days > 0 else weekday_days
        else:
            # Fallback: spread across all weekdays if no frequency specified
            spread_days = weekday_days if weekday_days else days

        if len(spread_days) == 0:
            spread_days = days  # Fallback to all days if no weekdays

        per_day = round(total / len(spread_days), 2)
        for day in spread_days:
            day.planned_budget[category] = per_day

    elif behavior == "clustered":
        # Use user frequency for clustered items too
        if user_frequency and user_frequency > 0:
            num_cluster_days = min(int(user_frequency), num_days)
        else:
            num_cluster_days = 4  # Default fallback

        candidate_days = [d for d in days if d.day_type == "weekend"]
        if len(candidate_days) < num_cluster_days:
            # Add weekdays if not enough weekend days
            remaining_needed = num_cluster_days - len(candidate_days)
            weekday_candidates = [d for d in days if d.day_type == "weekday"]
            if weekday_candidates:
                candidate_days += random.sample(
                    weekday_candidates,
                    min(remaining_needed, len(weekday_candidates))
                )

        selected_days = random.sample(candidate_days, min(num_cluster_days, len(candidate_days)))
        chunk = round(total / len(selected_days), 2)
        for day in selected_days:
            day.planned_budget[category] = chunk
