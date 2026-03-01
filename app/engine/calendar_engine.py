import calendar
from datetime import date
from typing import Dict

CATEGORY_BEHAVIOR = {
    "rent": "fixed",
    "food": "spread",
    "entertainment": "clustered",
    "transport": "spread",
    "utilities": "fixed",
    "shopping": "clustered",
}


class CalendarDay:
    def __init__(self, date_str: str, is_weekend: bool):
        self.date = date_str
        self.day_type = "weekend" if is_weekend else "weekday"
        self.planned_budget = {}
        self.total = 0.0

    def add(self, category: str, amount: float):
        self.planned_budget[category] = self.planned_budget.get(category, 0.0) + amount
        self.total = round(sum(self.planned_budget.values()), 2)

    def to_dict(self):
        return {
            "date": self.date,
            "type": self.day_type,
            "planned_budget": self.planned_budget,
            "total": self.total,
        }


class CalendarEngine:
    def __init__(self, income, fixed_expenses, flexible_categories, region="US-CA"):
        self.income = income
        self.fixed_expenses = fixed_expenses
        self.flexible_categories = flexible_categories
        self.region = region

    def generate_calendar(self, year, month) -> Dict[str, Dict]:
        num_days = calendar.monthrange(year, month)[1]
        calendar_data: Dict[str, CalendarDay] = {}

        for day in range(1, num_days + 1):
            dt = date(year, month, day)
            key = dt.isoformat()
            is_weekend = dt.weekday() >= 5
            calendar_data[key] = CalendarDay(key, is_weekend)

        # Apply fixed expenses to first day
        first_day_key = date(year, month, 1).isoformat()
        for cat, amt in self.fixed_expenses.items():
            calendar_data[first_day_key].add(cat, amt)

        # Flexible budget total
        total_flexible = sum(self.flexible_categories.values())
        remaining = self.income - sum(self.fixed_expenses.values())

        # Spread flexible budget according to behavior
        for cat, weight in self.flexible_categories.items():
            behavior = CATEGORY_BEHAVIOR.get(cat, "spread")
            daily_amount = (remaining * weight) / total_flexible / num_days

            if behavior == "spread":
                for day in calendar_data.values():
                    day.add(cat, daily_amount)

            elif behavior == "clustered":
                for idx, day in enumerate(calendar_data.values()):
                    if idx % 7 in [4, 5]:  # Friday, Saturday
                        day.add(cat, daily_amount * 2)

            elif behavior == "fixed":
                calendar_data[first_day_key].add(
                    cat, remaining * weight / total_flexible
                )

        return {k: v.to_dict() for k, v in calendar_data.items()}
