class BehavioralSummaryGenerator:
    """Compose human readable financial behavior summaries."""

    def __init__(self) -> None:
        """Initialize the generator with no state for now."""
        pass

    def generate(self, profile, analytics_data):
        region = profile.get("region", "unknown")
        cohort = profile.get("cohort", "unknown")
        behavior = profile.get("behavior", "neutral")

        summary = []

        behavior_counts = analytics_data.get("behaviors", {})

        summary.append(f"Ты относишься к когорте: {cohort}")
        if behavior in behavior_counts:
            summary.append(
                (
                    f"Твоё поведение — '{behavior}' "
                    + "— распространено в твоём регионе."
                )
            )
        else:
            summary.append(
                f"Твоё поведение — '{behavior}' " + f"— редкое для {region}."
            )

        success_rate = analytics_data.get("challenge_success_rate", 0)
        goal_rate = analytics_data.get("goal_completion_rate", 0)

        summary.append(
            (
                "Средняя успешность челленджей в регионе "
                + f"{region}: {int(success_rate * 100)}%"
            )
        )

        goal_summary = (
            "Выполнение целей в твоей категории: " + f"{int(goal_rate * 100)}%"
        )
        summary.append(goal_summary)

        return summary
