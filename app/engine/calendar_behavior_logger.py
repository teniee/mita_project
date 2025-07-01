
from collections import defaultdict

class CalendarBehaviorLogger:
    def __init__(self):
        self.daily_flags = defaultdict(lambda: defaultdict(int))  # region -> flag_type -> count

    def log_day(self, region: str, over_budget: bool, dipped_to_zero: bool, spike: bool):
        if over_budget:
            self.daily_flags[region]["over_budget"] += 1
        if dipped_to_zero:
            self.daily_flags[region]["zero_balance_days"] += 1
        if spike:
            self.daily_flags[region]["spending_spike"] += 1

    def summarize(self):
        return {
            region: dict(flags)
            for region, flags in self.daily_flags.items()
        }
