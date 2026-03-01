from collections import defaultdict


class CohortDriftTracker:
    def __init__(self):
        self.history = defaultdict(dict)  # user_id -> {"YYYY-MM": cohort_str}

    def log_month(self, user_id: str, year: int, month: int, cohort: str):
        key = f"{year}-{month:02d}"
        self.history[user_id][key] = cohort

    def get_drift(self, user_id: str):
        months = sorted(self.history[user_id].keys())
        if len(months) < 2:
            return []

        drifts = []
        for i in range(1, len(months)):
            prev, curr = months[i - 1], months[i]
            if self.history[user_id][prev] != self.history[user_id][curr]:
                drifts.append(
                    {
                        "from": self.history[user_id][prev],
                        "to": self.history[user_id][curr],
                        "month": curr,
                    }
                )
        return drifts

    def get_current(self, user_id: str):
        return (
            sorted(self.history[user_id].items())[-1] if self.history[user_id] else None
        )
