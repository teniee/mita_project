from app.logic.behavioral_budget_allocator import BehavioralBudgetAllocator


def test_behavioral_allocator():
    profile = {"behavior": "neutral"}
    category_weights = {"groceries": 1.0, "entertainment": 1.0}
    total_amount = 5000
    allocator = BehavioralBudgetAllocator(profile, category_weights, total_amount)
    result = allocator.generate_distribution()
    assert isinstance(result, dict)
    assert sum(result.values()) == total_amount
