from collections import defaultdict


class PushAnalyticsTracker:
    def __init__(self):
        self.push_stats = defaultdict(
            lambda: {"delivered": 0, "opened": 0, "ignored": 0}
        )

    def log_delivery(self, region: str):
        self.push_stats[region]["delivered"] += 1

    def log_opened(self, region: str):
        self.push_stats[region]["opened"] += 1

    def log_ignored(self, region: str):
        self.push_stats[region]["ignored"] += 1

    def get_report(self):
        report = {}
        for region, stats in self.push_stats.items():
            total = stats["delivered"]
            report[region] = {
                "delivered": total,
                "opened": stats["opened"],
                "ignored": stats["ignored"],
                "open_rate": round(stats["opened"] / total, 2) if total else 0,
                "ignore_rate": round(stats["ignored"] / total, 2) if total else 0,
            }
        return report
