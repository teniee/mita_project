
class BehavioralSummaryGenerator:
    def __init__(self):
        pass

    def generate(self, profile, analytics_data):
        region = profile.get("region", "unknown")
        cohort = profile.get("cohort", "unknown")
        behavior = profile.get("behavior", "neutral")

        summary = []

        cohort_counts = analytics_data.get("cohorts", {})
        behavior_counts = analytics_data.get("behaviors", {})

        summary.append(f"Ты относишься к когорте: {cohort}")
        if behavior in behavior_counts:
            summary.append(f"Твоё поведение — '{behavior}' — распространено в твоём регионе.")
        else:
            summary.append(f"Твоё поведение — '{behavior}' — редкое для {region}.")

        success_rate = analytics_data.get("challenge_success_rate", 0)
        goal_rate = analytics_data.get("goal_completion_rate", 0)

        summary.append(f"Средняя успешность челленджей в регионе {region}: {int(success_rate * 100)}%")
        summary.append(f"Выполнение целей в твоей категории: {int(goal_rate * 100)}%")

        return summary
