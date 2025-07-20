class BehavioralSummaryGenerator:
    """Compose human readable financial behavior summaries."""

    # The generator currently has no state, so we rely solely on the input
    # data when constructing summaries. By omitting ``__init__`` we keep the
    # class lightweight and avoid unused placeholder code.

    def generate(self, profile, analytics_data):
        region = profile.get("region", "unknown")
        cohort = profile.get("cohort", "unknown")
        behavior = profile.get("behavior", "neutral")

        summary = []

        behavior_counts = analytics_data.get("behaviors", {})

        summary.append(f"You belong to cohort: {cohort}")
        if behavior in behavior_counts:
            summary.append((f"Your behavior '{behavior}' is common in your region."))
        else:
            summary.append(f"Your behavior '{behavior}' is rare for {region}.")

        success_rate = analytics_data.get("challenge_success_rate", 0)
        goal_rate = analytics_data.get("goal_completion_rate", 0)

        summary.append(
            ("Average challenge success in " + f"{region}: {int(success_rate * 100)}%")
        )

        goal_summary = "Goal completion in your category: " + f"{int(goal_rate * 100)}%"
        summary.append(goal_summary)

        return summary
