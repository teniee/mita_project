### behavioral_budget_allocator.py — REFACTORED


class BehavioralBudgetAllocator:
    def __init__(self, profile, category_weights, total_amount):
        self.profile = profile
        self.category_weights = category_weights
        self.total_amount = total_amount

    def generate_distribution(self):
        adjusted_weights = self._adjust_weights()
        total_weight = sum(adjusted_weights.values())

        return {
            category: round((weight / total_weight) * self.total_amount, 2)
            for category, weight in adjusted_weights.items()
        }

    def _adjust_weights(self):
        behavior = self.profile.get("behavior", "neutral")
        weights = self.category_weights.copy()

        if behavior == "impulsive":
            for cat in weights:
                if cat in ["entertainment", "shopping"]:
                    weights[cat] *= 1.5
        elif behavior == "frugal":
            for cat in weights:
                if cat in ["savings", "debt"]:
                    weights[cat] *= 1.5
        return weights
