from collections import defaultdict


class UIAnalyticsLogger:
    def __init__(self):
        self.ui_events = defaultdict(
            lambda: defaultdict(int)
        )  # region -> event_type -> count

    def log_event(self, user_id: str, region: str, event_type: str):
        self.ui_events[region][event_type] += 1

    def get_summary(self):
        return {region: dict(events) for region, events in self.ui_events.items()}
