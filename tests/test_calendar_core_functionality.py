"""
Pytest Test Suite for MITA Calendar Core Functionality
Tests all components after fixes applied
"""

import pytest
from decimal import Decimal
from datetime import datetime
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestIncomeClassification:
    """Test suite for income classification service"""
    
    def test_income_tier_low(self):
        from app.services.core.income_classification_service import classify_income
        tier = classify_income(2500, "US")
        assert tier.name == "LOW"
    
    def test_income_tier_lower_middle(self):
        from app.services.core.income_classification_service import classify_income
        tier = classify_income(4500, "US")
        assert tier.name == "LOWER_MIDDLE"
    
    def test_income_tier_middle(self):
        from app.services.core.income_classification_service import classify_income
        tier = classify_income(6500, "US")
        assert tier.name == "MIDDLE"
    
    def test_income_tier_upper_middle(self):
        from app.services.core.income_classification_service import classify_income
        tier = classify_income(10000, "US")
        assert tier.name == "UPPER_MIDDLE"
    
    def test_income_tier_high(self):
        from app.services.core.income_classification_service import classify_income
        tier = classify_income(15000, "US")
        assert tier.name == "HIGH"


class TestBudgetGeneration:
    """Test suite for budget generation logic"""
    
    @pytest.fixture
    def sample_user_data(self):
        return {
            "income": {"monthly_income": 5000, "additional_income": 500},
            "fixed_expenses": {"rent": 1200, "utilities": 150, "insurance": 100},
            "spending_habits": {
                "dining_out_per_month": 8,
                "entertainment_per_month": 4,
                "clothing_per_month": 3,
                "coffee_per_week": 5,
                "transport_per_month": 20
            },
            "goals": {"savings_goal_amount_per_month": 500},
            "region": "US-CA"
        }
    
    def test_budget_generation_returns_dict(self, sample_user_data):
        from app.services.core.engine.budget_logic import generate_budget_from_answers
        budget_plan = generate_budget_from_answers(sample_user_data)
        assert isinstance(budget_plan, dict)
    
    def test_budget_has_required_fields(self, sample_user_data):
        from app.services.core.engine.budget_logic import generate_budget_from_answers
        budget_plan = generate_budget_from_answers(sample_user_data)
        
        required_fields = [
            "total_income", "fixed_expenses_total", "discretionary_total",
            "savings_goal", "user_class", "discretionary_breakdown"
        ]
        for field in required_fields:
            assert field in budget_plan
    
    def test_budget_balances(self, sample_user_data):
        from app.services.core.engine.budget_logic import generate_budget_from_answers
        budget_plan = generate_budget_from_answers(sample_user_data)
        
        total_income = budget_plan["total_income"]
        budget_sum = (
            budget_plan["fixed_expenses_total"] +
            budget_plan["savings_goal"] +
            budget_plan["discretionary_total"]
        )
        
        assert abs(budget_sum - total_income) < 1
    
    def test_budget_user_class(self, sample_user_data):
        from app.services.core.engine.budget_logic import generate_budget_from_answers
        budget_plan = generate_budget_from_answers(sample_user_data)
        
        assert budget_plan["user_class"] in [
            "low", "lower_middle", "middle", "upper_middle", "high"
        ]


class TestCalendarGeneration:
    """Test suite for calendar generation (post-fix)"""
    
    @pytest.fixture
    def sample_user_data_with_breakdown(self):
        return {
            "income": {"monthly_income": 5000, "additional_income": 500},
            "fixed_expenses": {"rent": 1200, "utilities": 150, "insurance": 100},
            "spending_habits": {
                "dining_out_per_month": 8,
                "entertainment_per_month": 4,
                "clothing_per_month": 3,
                "coffee_per_week": 5,
                "transport_per_month": 20
            },
            "goals": {"savings_goal_amount_per_month": 500},
            "region": "US-CA",
            "monthly_income": 5500,
            "discretionary_breakdown": {
                "dining out": 516.36,
                "entertainment events": 258.18,
                "clothing": 193.64,
                "coffee": 1290.91,
                "transport": 1290.91
            }
        }
    
    def test_calendar_returns_list(self, sample_user_data_with_breakdown):
        from app.services.core.engine.monthly_budget_engine import build_monthly_budget
        
        year = datetime.now().year
        month = datetime.now().month
        calendar_data = build_monthly_budget(sample_user_data_with_breakdown, year, month)
        
        assert isinstance(calendar_data, list)
    
    def test_calendar_has_correct_number_of_days(self, sample_user_data_with_breakdown):
        from app.services.core.engine.monthly_budget_engine import build_monthly_budget
        import calendar
        
        year = datetime.now().year
        month = datetime.now().month
        num_days = calendar.monthrange(year, month)[1]
        
        calendar_data = build_monthly_budget(sample_user_data_with_breakdown, year, month)
        
        assert len(calendar_data) == num_days
    
    def test_calendar_days_are_dicts(self, sample_user_data_with_breakdown):
        from app.services.core.engine.monthly_budget_engine import build_monthly_budget
        
        year = datetime.now().year
        month = datetime.now().month
        calendar_data = build_monthly_budget(sample_user_data_with_breakdown, year, month)
        
        assert all(isinstance(day, dict) for day in calendar_data)
    
    def test_calendar_days_have_required_keys(self, sample_user_data_with_breakdown):
        from app.services.core.engine.monthly_budget_engine import build_monthly_budget
        
        year = datetime.now().year
        month = datetime.now().month
        calendar_data = build_monthly_budget(sample_user_data_with_breakdown, year, month)
        
        required_keys = ["date", "planned_budget", "total", "day_type", "status"]
        for day in calendar_data:
            for key in required_keys:
                assert key in day
    
    def test_calendar_fixed_pattern_rent_day_1(self, sample_user_data_with_breakdown):
        from app.services.core.engine.monthly_budget_engine import build_monthly_budget
        
        year = datetime.now().year
        month = datetime.now().month
        calendar_data = build_monthly_budget(sample_user_data_with_breakdown, year, month)
        
        # Rent should be allocated to day 1
        assert "rent" in calendar_data[0]["planned_budget"]
    
    def test_calendar_spread_pattern(self, sample_user_data_with_breakdown):
        from app.services.core.engine.monthly_budget_engine import build_monthly_budget
        
        year = datetime.now().year
        month = datetime.now().month
        calendar_data = build_monthly_budget(sample_user_data_with_breakdown, year, month)
        
        # Coffee should be spread across multiple days
        coffee_days = [d for d in calendar_data if "coffee" in d.get("planned_budget", {})]
        assert len(coffee_days) > 1
    
    def test_calendar_clustered_pattern(self, sample_user_data_with_breakdown):
        from app.services.core.engine.monthly_budget_engine import build_monthly_budget
        
        year = datetime.now().year
        month = datetime.now().month
        calendar_data = build_monthly_budget(sample_user_data_with_breakdown, year, month)
        
        # Dining out should be clustered on specific days
        dining_days = [d for d in calendar_data if "dining out" in d.get("planned_budget", {})]
        assert len(dining_days) >= 1


class TestBudgetRedistribution:
    """Test suite for budget redistribution algorithm"""
    
    def test_redistributor_creation(self):
        from app.engine.budget_redistributor import BudgetRedistributor
        
        test_calendar = {
            "2025-01-01": {"total": Decimal("150"), "limit": Decimal("100")},
            "2025-01-02": {"total": Decimal("70"), "limit": Decimal("100")},
        }
        
        redistributor = BudgetRedistributor(test_calendar)
        assert redistributor is not None
    
    def test_redistribution_executes(self):
        from app.engine.budget_redistributor import BudgetRedistributor
        
        test_calendar = {
            "2025-01-01": {"total": Decimal("150"), "limit": Decimal("100")},
            "2025-01-02": {"total": Decimal("70"), "limit": Decimal("100")},
            "2025-01-03": {"total": Decimal("80"), "limit": Decimal("100")},
        }
        
        redistributor = BudgetRedistributor(test_calendar)
        updated_calendar, transfers = redistributor.redistribute_budget()
        
        assert len(transfers) > 0
    
    def test_redistribution_preserves_total(self):
        from app.engine.budget_redistributor import BudgetRedistributor
        
        test_calendar = {
            "2025-01-01": {"total": Decimal("150"), "limit": Decimal("100")},
            "2025-01-02": {"total": Decimal("70"), "limit": Decimal("100")},
            "2025-01-03": {"total": Decimal("80"), "limit": Decimal("100")},
        }
        
        before_total = sum(d["total"] for d in test_calendar.values())
        
        redistributor = BudgetRedistributor(test_calendar)
        updated_calendar, transfers = redistributor.redistribute_budget()
        
        after_total = sum(d["total"] for d in updated_calendar.values())
        
        assert before_total == after_total
    
    def test_redistribution_reduces_overspending(self):
        from app.engine.budget_redistributor import BudgetRedistributor
        
        test_calendar = {
            "2025-01-01": {"total": Decimal("150"), "limit": Decimal("100")},
            "2025-01-02": {"total": Decimal("70"), "limit": Decimal("100")},
            "2025-01-03": {"total": Decimal("80"), "limit": Decimal("100")},
        }
        
        before_over = sum(max(Decimal(0), d['total'] - d['limit']) for d in test_calendar.values())
        
        redistributor = BudgetRedistributor(test_calendar)
        updated_calendar, transfers = redistributor.redistribute_budget()
        
        after_over = sum(max(Decimal(0), d['total'] - d['limit']) for d in updated_calendar.values())
        
        assert after_over <= before_over


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
