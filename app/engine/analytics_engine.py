from collections import defaultdict


class AnalyticsEngine:
    def __init__(self):
        self.data = defaultdict(lambda: defaultdict(list))  # region -> metric -> values

    def log_behavior(
        self, user_id, region, cohort, behavior_tag, challenge_success, goal_completed
    ):
        self.data[region]["cohort"].append(cohort)
        self.data[region]["behavior"].append(behavior_tag)
        self.data[region]["challenge_success"].append(challenge_success)
        self.data[region]["goal_completed"].append(goal_completed)

    def summarize(self):
        report = {}
        for region, metrics in self.data.items():
            report[region] = {
                "cohorts": self._top_values(metrics["cohort"]),
                "behaviors": self._top_values(metrics["behavior"]),
                "challenge_success_rate": self._rate(metrics["challenge_success"]),
                "goal_completion_rate": self._rate(metrics["goal_completed"]),
            }
        return report

    def _rate(self, values):
        if not values:
            return 0.0
        return round(sum(values) / len(values), 2)

    def _top_values(self, lst):
        from collections import Counter

        return dict(Counter(lst).most_common(3))
