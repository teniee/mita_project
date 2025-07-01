import random
import datetime
from typing import List, Dict

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
    "investment contribution": "fixed"
}

class CalendarDay:
    def __init__(self, date: datetime.date):
        self.date: datetime.date = date
        self.day_type: str = self._get_day_type(date)
        self.planned_budget: Dict[str, float] = {}
        self.actual_spending: Dict[str, float] = {}
        self.recommendations: List[str] = []
        self.status: str = "green"

    def _get_day_type(self, date: datetime.date) -> str:
        return "weekend" if date.weekday() >= 5 else "weekday"

    def to_dict(self) -> Dict:
        return {
            "date": self.date.strftime("%Y-%m-%d"),
            "day_type": self.day_type,
            "planned_budget": self.planned_budget,
            "actual_spending": self.actual_spending,
            "recommendations": self.recommendations,
            "status": self.status
        }

def distribute_budget_over_days(days: List[CalendarDay], category: str, total: float) -> None:
    behavior = CATEGORY_BEHAVIOR.get(category, "spread")
    num_days = len(days)

    if behavior == "fixed":
        index = 0 if category in ["rent", "mortgage", "school fees"] else min(4, num_days - 1)
        days[index].planned_budget[category] = round(total, 2)

    elif behavior == "spread":
        weekday_days = [d for d in days if d.day_type == "weekday"]
        spread_days = weekday_days[::2] or days
        per_day = round(total / len(spread_days), 2)
        for day in spread_days:
            day.planned_budget[category] = per_day

    elif behavior == "clustered":
        candidate_days = [d for d in days if d.day_type == "weekend"]
        if len(candidate_days) < 4:
            candidate_days += random.sample(days, min(4 - len(candidate_days), len(days)))
        selected_days = random.sample(candidate_days, min(4, len(candidate_days)))
        chunk = round(total / len(selected_days), 2)
        for day in selected_days:
            day.planned_budget[category] = chunk