from typing import Dict


class ProgressTracker:
    def __init__(self):
        # format: {user_id: {"YYYY-MM": {"spent": x, "saved": y}}}
        self.history = {}

    def log_month(
        self,
        user_id: str,
        year: int,
        month: int,
        calendar: Dict,
        income: float,
        country: str,
        region: str,
    ):
        key = f"{year}-{month:02d}"
        total_spent = sum(day["total"] for day in calendar.values())
        saved = round(income - total_spent, 2)

        if user_id not in self.history:
            self.history[user_id] = {}

        self.history[user_id][key] = {
            "spent": round(total_spent, 2),
            "saved": saved,
            "country": country,
            "region": region,
        }

    def get_month_data(self, user_id: str, year: int, month: int):
        key = f"{year}-{month:02d}"
        return self.history.get(user_id, {}).get(key)

    def compare_to_last(self, user_id: str, year: int, month: int):
        from datetime import datetime

        from dateutil.relativedelta import relativedelta

        this_key = f"{year}-{month:02d}"
        dt = datetime(year, month, 1) - relativedelta(months=1)
        last_key = f"{dt.year}-{dt.month:02d}"

        this_data = self.history.get(user_id, {}).get(this_key)
        last_data = self.history.get(user_id, {}).get(last_key)

        if not this_data or not last_data:
            return None

        return {
            "spent_change": round(this_data["spent"] - last_data["spent"], 2),
            "saved_change": round(this_data["saved"] - last_data["saved"], 2),
        }
