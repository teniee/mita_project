import datetime
import hashlib
import random
from decimal import ROUND_HALF_UP, Decimal
from typing import Dict, List

CATEGORY_BEHAVIOR: Dict[str, str] = {
    "groceries": "spread",
    "coffee": "spread",  # Daily habit - spread across weekdays
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


def split_amount_exactly(total, parts: int) -> List[Decimal]:
    """Split ``total`` across ``parts`` rows so the parts re-sum to it exactly.

    ``round(total / n, 2)`` per row does not conserve money: $100.00 over 22
    weekdays became $100.10 and $1000.00 became $999.90, so a month's persisted
    daily_plan rows never summed back to the allocation they came from. The
    remainder is spread one cent at a time over the leading rows, the same
    integer-cent discipline `_allocate_cents_with_caps` uses in the real-time
    rebalancer.
    """
    if parts <= 0:
        return []
    if not isinstance(total, Decimal):
        total = Decimal(str(total))
    total_cents = int((total * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    sign = -1 if total_cents < 0 else 1
    magnitude = abs(total_cents)
    base, remainder = divmod(magnitude, parts)
    return [
        Decimal(sign * (base + (1 if index < remainder else 0))) / Decimal(100)
        for index in range(parts)
    ]


def distribute_budget_over_days(
    days: List[CalendarDay], category: str, total: float, user_frequency: int = None
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
        days[index].planned_budget[category] = split_amount_exactly(total, 1)[0]

    elif behavior == "spread":
        weekday_days = [d for d in days if d.day_type == "weekday"]

        if user_frequency and user_frequency > 0:
            # User specified how many times they spend in this category
            # Allocate budget to that many days (capped at available weekdays)
            num_spread_days = min(int(user_frequency), len(weekday_days))
            spread_days = (
                weekday_days[:num_spread_days] if num_spread_days > 0 else weekday_days
            )
        else:
            # Fallback: spread across all weekdays if no frequency specified
            spread_days = weekday_days if weekday_days else days

        if len(spread_days) == 0:
            spread_days = days  # Fallback to all days if no weekdays

        for day, share in zip(
            spread_days, split_amount_exactly(total, len(spread_days))
        ):
            day.planned_budget[category] = share

    elif behavior == "clustered":
        # Use user frequency for clustered items too
        if user_frequency and user_frequency > 0:
            num_cluster_days = min(int(user_frequency), num_days)
        else:
            num_cluster_days = 4  # Default fallback

        # Build a deterministic RNG seeded on year+month+category so results
        # are stable across re-runs but differ per calendar period and category
        if days:
            d = getattr(days[0], "date", None)
            year_val = d.year if d else 2025
            month_val = d.month if d else 1
        else:
            year_val, month_val = 2025, 1

        seed_str = f"{year_val}{month_val}{category}"
        seed_int = int(
            hashlib.md5(seed_str.encode(), usedforsecurity=False).hexdigest(), 16
        ) % (2**31)
        rng = random.Random(seed_int)

        candidate_days = [d for d in days if d.day_type == "weekend"]
        if len(candidate_days) < num_cluster_days:
            # Add weekdays if not enough weekend days
            remaining_needed = num_cluster_days - len(candidate_days)
            weekday_candidates = [d for d in days if d.day_type == "weekday"]
            if weekday_candidates:
                candidate_days += rng.sample(
                    weekday_candidates, min(remaining_needed, len(weekday_candidates))
                )

        selected_days = rng.sample(
            candidate_days, min(num_cluster_days, len(candidate_days))
        )
        if not selected_days:
            # Reachable only via a user_frequency in (0, 1), which int()s to 0.
            # The previous `total / len(selected_days)` raised ZeroDivisionError
            # here; keep failing loudly rather than silently dropping the whole
            # category's budget, which is what an empty zip() would do.
            raise ValueError(
                f"no days available to distribute {category!r} over "
                f"(frequency={user_frequency!r}, days={num_days})"
            )
        # Deterministic order so the cent remainder lands on the same days on
        # every regeneration of this month (rng.sample order is stable for the
        # seed, but sorting keeps the plan readable and replay-safe).
        selected_days.sort(key=lambda day: day.date)
        for day, share in zip(
            selected_days, split_amount_exactly(total, len(selected_days))
        ):
            day.planned_budget[category] = share
