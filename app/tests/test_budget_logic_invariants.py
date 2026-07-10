"""Financial invariants for generate_budget_from_answers (V2 / INV-1..7).

The engine previously did all money math in binary float and rounded with
round() (half-to-even), so sub-cent inputs violated the reconciliation
invariant and .xx5 boundaries rounded the wrong way. It now computes in
Decimal with ROUND_HALF_UP.
"""

import random
from decimal import Decimal

import pytest

from app.services.core.engine.budget_logic import generate_budget_from_answers


def build_answers(monthly=6000.0, additional=0.0, fixed=None, savings=0.0):
    return {
        "region": "US",
        "income": {"monthly_income": monthly, "additional_income": additional},
        "fixed_expenses": fixed or {},
        "spending_habits": {},
        "goals": {"savings_goal_amount_per_month": savings},
    }


def D(x):
    return Decimal(str(x))


def reconciles(plan):
    """INV-6: total_income == fixed + savings + discretionary to the cent."""
    return D(plan["total_income"]) == D(plan["fixed_expenses_total"]) + D(
        plan["savings_goal"]
    ) + D(plan["discretionary_total"])


class TestDeterministicCases:
    def test_b1_normal(self):
        plan = generate_budget_from_answers(
            build_answers(6000, 0, {"rent": 1500.0, "utilities": 200.0}, savings=400.0)
        )
        assert D(plan["total_income"]) == Decimal("6000.00")
        assert D(plan["fixed_expenses_total"]) == Decimal("1700.00")
        assert D(plan["savings_goal"]) == Decimal("400.00")
        assert D(plan["discretionary_total"]) == Decimal("3900.00")
        assert reconciles(plan)

    def test_b8_income_fully_consumed_by_fixed(self):
        plan = generate_budget_from_answers(
            build_answers(2000, 0, {"rent": 2000.0}, savings=400.0)
        )
        assert D(plan["discretionary_total"]) == Decimal("0.00")
        assert D(plan["savings_goal"]) == Decimal("0.00")  # clamped
        assert reconciles(plan)

    def test_b9_fixed_exceeds_income(self):
        with pytest.raises(ValueError, match="Fixed expenses exceed income"):
            generate_budget_from_answers(build_answers(2000, 0, {"rent": 2500.0}))

    def test_b10_savings_clamped(self):
        plan = generate_budget_from_answers(
            build_answers(3000, 0, {"rent": 2800.0}, savings=500.0)
        )
        assert D(plan["savings_goal"]) == Decimal("200.00")  # clamped down
        assert D(plan["discretionary_total"]) == Decimal("0.00")
        assert reconciles(plan)

    def test_zero_income(self):
        plan = generate_budget_from_answers(build_answers(0, 0, {}, savings=0))
        assert D(plan["total_income"]) == Decimal("0.00")
        assert reconciles(plan)

    def test_negative_income_rejected(self):
        with pytest.raises(ValueError):
            generate_budget_from_answers(build_answers(-1000))


class TestDecimalPrecision:
    def test_float_artifact_inputs(self):
        # 0.1 + 0.2 must be exactly 0.30, not 0.30000000000000004
        plan = generate_budget_from_answers(build_answers(0.1, 0.2))
        assert D(plan["total_income"]) == Decimal("0.30")
        assert reconciles(plan)

    def test_half_cent_rounds_half_up(self):
        # 100.005 -> 100.01 (ROUND_HALF_UP), not 100.00 (banker's / float repr)
        plan = generate_budget_from_answers(build_answers("100.005"))
        assert D(plan["total_income"]) == Decimal("100.01")
        assert reconciles(plan)

    def test_xx5_boundary_savings(self):
        plan = generate_budget_from_answers(build_answers(1000, 0, {}, savings="1.005"))
        assert D(plan["savings_goal"]) == Decimal("1.01")
        assert reconciles(plan)

    def test_reconciliation_property_random_2dp(self):
        rng = random.Random(20260710)
        for _ in range(300):
            monthly = round(rng.uniform(0, 20000), 2)
            additional = round(rng.uniform(0, 5000), 2)
            fixed = {
                f"cat{i}": round(rng.uniform(0, 2000), 2)
                for i in range(rng.randint(0, 5))
            }
            savings = round(rng.uniform(0, 3000), 2)
            answers = build_answers(monthly, additional, fixed, savings)
            try:
                plan = generate_budget_from_answers(answers)
            except ValueError:
                continue  # fixed > income — correctly rejected
            assert reconciles(plan), (
                f"reconciliation failed for {answers}: {plan['total_income']} != "
                f"{plan['fixed_expenses_total']} + {plan['savings_goal']} + "
                f"{plan['discretionary_total']}"
            )

    def test_breakdown_never_exceeds_discretionary(self):
        # INV-7: allocations only downscale, and their 2-dp sum stays within
        # discretionary + a cent-per-category rounding envelope.
        plan = generate_budget_from_answers(
            build_answers(
                5000,
                0,
                {"rent": 4000.0},
                savings=900.0,
            )
        )
        breakdown_sum = sum(D(v) for v in plan["discretionary_breakdown"].values())
        envelope = Decimal("0.01") * len(plan["discretionary_breakdown"])
        assert breakdown_sum <= D(plan["discretionary_total"]) + envelope
        assert reconciles(plan)
