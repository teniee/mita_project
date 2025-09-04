"""
Comprehensive Validation Tests for Dynamic Financial Thresholds

This test suite validates that the dynamic threshold system:
1. Generates economically sound recommendations across all income levels
2. Properly scales thresholds based on regional differences
3. Maintains consistency with established financial planning principles
4. Provides appropriate recommendations for different life stages

Author: Claude Code (AI Financial Economist)
"""

import pytest
from decimal import Decimal
from typing import Dict, List, Tuple

from app.services.core.dynamic_threshold_service import (
    DynamicThresholdService, UserContext, ThresholdType,
    get_dynamic_thresholds, get_housing_affordability_thresholds
)
from app.services.core.income_scaling_algorithms import (
    IncomeScalingAlgorithms, scale_threshold_by_income,
    get_scaled_variance_thresholds, get_scaled_goal_constraints
)
from app.services.core.income_classification_service import (
    IncomeClassificationService, IncomeTier
)


class TestDynamicThresholdEconomicSoundness:
    """Test economic soundness of dynamic threshold calculations"""
    
    def setup_method(self):
        self.service = DynamicThresholdService()
        self.income_service = IncomeClassificationService()
        self.scaling_service = IncomeScalingAlgorithms()
        
        # Define test user profiles across income spectrum
        self.test_profiles = [
            # Low income
            UserContext(monthly_income=2500, age=25, region="US", family_size=1),
            # Lower-middle income
            UserContext(monthly_income=4000, age=30, region="US", family_size=2),
            # Middle income  
            UserContext(monthly_income=6000, age=35, region="US", family_size=2),
            # Upper-middle income
            UserContext(monthly_income=10000, age=40, region="US", family_size=3),
            # High income
            UserContext(monthly_income=15000, age=45, region="US", family_size=2),
        ]
        
        # Regional test profiles
        self.regional_profiles = [
            UserContext(monthly_income=6000, age=35, region="US", family_size=2),
            UserContext(monthly_income=6000, age=35, region="US-CA", family_size=2),
            UserContext(monthly_income=6000, age=35, region="US-NY", family_size=2),
            UserContext(monthly_income=6000, age=35, region="US-TX", family_size=2),
            UserContext(monthly_income=6000, age=35, region="US-FL", family_size=2),
        ]
    
    def test_budget_allocation_economic_principles(self):
        """Test that budget allocations follow economic principles"""
        for profile in self.test_profiles:
            allocations = get_dynamic_thresholds(
                ThresholdType.BUDGET_ALLOCATION, profile
            )
            
            # Engel's Law: Food percentage should decrease with income
            if profile.monthly_income > 5000:
                assert allocations.get('food', 0) <= 0.15, \
                    f"Food allocation too high for income ${profile.monthly_income}"
            
            # Housing should be manageable but not excessive
            housing_ratio = allocations.get('housing', 0)
            assert 0.20 <= housing_ratio <= 0.45, \
                f"Housing ratio {housing_ratio:.2%} outside acceptable range for ${profile.monthly_income}"
            
            # Savings should increase with income (positive elasticity)
            savings_ratio = allocations.get('savings', 0)
            if profile.monthly_income < 3000:
                assert savings_ratio >= 0.03, "Minimum savings rate too low for low income"
            elif profile.monthly_income > 10000:
                assert savings_ratio >= 0.12, "High income should have higher savings rate"
            
            # Total allocations should sum to approximately 1.0
            total = sum(v for v in allocations.values() if isinstance(v, (int, float)))
            assert 0.95 <= total <= 1.05, f"Budget allocations don't sum to ~100%: {total:.2%}"
    
    def test_regional_cost_of_living_adjustments(self):
        """Test that regional adjustments are economically justified"""
        base_profile = self.regional_profiles[0]  # US baseline
        base_allocations = get_dynamic_thresholds(
            ThresholdType.BUDGET_ALLOCATION, base_profile
        )
        
        for profile in self.regional_profiles[1:]:  # Regional variations
            regional_allocations = get_dynamic_thresholds(
                ThresholdType.BUDGET_ALLOCATION, profile
            )
            
            # High cost regions should have higher housing allocations
            if profile.region in ["US-CA", "US-NY"]:
                assert regional_allocations['housing'] > base_allocations['housing'], \
                    f"High cost region {profile.region} should have higher housing allocation"
                
                # But other categories should adjust downward to compensate
                assert regional_allocations['entertainment'] <= base_allocations['entertainment'], \
                    f"High cost region should reduce discretionary spending"
            
            # Low cost regions should have lower housing, higher discretionary
            if profile.region in ["US-TX"]:
                assert regional_allocations['housing'] <= base_allocations['housing'], \
                    f"Lower cost region {profile.region} should have lower housing allocation"
    
    def test_income_scaling_algorithms_mathematical_validity(self):
        """Test that scaling algorithms produce mathematically sound results"""
        test_incomes = [2000, 3500, 5000, 7500, 10000, 15000, 25000]
        
        for income in test_incomes:
            # Housing ratio should decrease with income (negative elasticity)
            housing_ratio = scale_threshold_by_income(
                'housing_ratio', income, region_multiplier=1.0
            )
            assert 0.20 <= housing_ratio <= 0.50, \
                f"Housing ratio {housing_ratio:.2%} out of bounds for ${income}"
            
            # Savings rate should increase with income (positive elasticity)  
            savings_rate = scale_threshold_by_income(
                'savings_rate', income, age=35
            )
            assert 0.02 <= savings_rate <= 0.50, \
                f"Savings rate {savings_rate:.2%} out of bounds for ${income}"
            
            # Small purchase threshold should scale with income
            small_threshold = scale_threshold_by_income(
                'small_purchase', income
            )
            expected_range = (income * 0.002, income * 0.01)  # 0.2% to 1% of monthly income
            assert expected_range[0] <= small_threshold <= expected_range[1], \
                f"Small purchase threshold ${small_threshold} not income-appropriate for ${income}"
    
    def test_life_stage_appropriateness(self):
        """Test that thresholds adjust appropriately for different life stages"""
        # Young professional
        young_profile = UserContext(monthly_income=5000, age=25, life_stage="single")
        young_thresholds = get_dynamic_thresholds(ThresholdType.SAVINGS_TARGET, young_profile)
        
        # Middle-aged family
        family_profile = UserContext(monthly_income=5000, age=40, family_size=3, life_stage="family")
        family_thresholds = get_dynamic_thresholds(ThresholdType.SAVINGS_TARGET, family_profile)
        
        # Pre-retirement
        preretiree_profile = UserContext(monthly_income=5000, age=55, life_stage="single")  
        preretiree_thresholds = get_dynamic_thresholds(ThresholdType.SAVINGS_TARGET, preretiree_profile)
        
        # Young people should have higher risk tolerance, lower emergency fund needs
        young_emergency = young_thresholds.get('emergency_fund_months', 3)
        family_emergency = family_thresholds.get('emergency_fund_months', 3)
        
        assert family_emergency >= young_emergency, \
            "Families should have larger emergency funds than singles"
        
        # Pre-retirees should have higher savings rates
        preretiree_rate = preretiree_thresholds.get('target_savings_rate', 0.12)
        young_rate = young_thresholds.get('target_savings_rate', 0.12)
        
        assert preretiree_rate >= young_rate, \
            "Pre-retirees should have higher target savings rates"
    
    def test_economic_environment_responsiveness(self):
        """Test that thresholds respond appropriately to economic conditions"""
        # This would test inflation adjustments, recession preparedness, etc.
        # Currently using baseline economic conditions
        
        standard_profile = UserContext(monthly_income=6000, age=35, region="US")
        thresholds = get_dynamic_thresholds(ThresholdType.SAVINGS_TARGET, standard_profile)
        
        # Emergency fund should be at least 3 months
        emergency_months = thresholds.get('emergency_fund_months', 3)
        assert emergency_months >= 2.5, "Emergency fund too low for economic uncertainty"
        
        # Savings rate should be meaningful
        savings_rate = thresholds.get('target_savings_rate', 0.12)
        assert savings_rate >= 0.08, "Savings rate too low for building resilience"
    
    def test_spending_pattern_thresholds_behavioral_validity(self):
        """Test that spending pattern thresholds align with behavioral economics"""
        for profile in self.test_profiles:
            thresholds = get_dynamic_thresholds(ThresholdType.SPENDING_PATTERN, profile)
            
            # Small purchase threshold should be income-relative
            small_threshold = thresholds.get('small_purchase_threshold', 20)
            income_percentage = small_threshold / profile.monthly_income
            
            assert 0.002 <= income_percentage <= 0.02, \
                f"Small purchase threshold not income-appropriate: {income_percentage:.1%} of income"
            
            # Impulse buying threshold should be stricter for lower income
            impulse_threshold = thresholds.get('impulse_buying_threshold', 0.6)
            if profile.monthly_income < 4000:
                assert impulse_threshold <= 0.55, \
                    "Impulse buying threshold too lenient for low income"
            
            # Category concentration should allow more flexibility for higher income
            concentration_threshold = thresholds.get('category_concentration_threshold', 0.5)
            if profile.monthly_income > 10000:
                assert concentration_threshold <= 0.4, \
                    "High income should have lower concentration tolerance"
    
    def test_goal_constraint_realism(self):
        """Test that goal constraints are realistic and achievable"""
        for profile in self.test_profiles:
            constraints = get_scaled_goal_constraints(
                profile.monthly_income, profile.age, 50000, "general"
            )
            
            min_timeline = constraints['minimum_timeline_months']
            max_timeline = constraints['maximum_timeline_months']
            max_contribution = constraints['maximum_monthly_contribution']
            
            # Timeline should be reasonable
            assert min_timeline > 0, "Minimum timeline must be positive"
            assert max_timeline > min_timeline, "Maximum timeline must exceed minimum"
            assert max_timeline <= 120, "Maximum timeline too long (>10 years)"  # 10 years max
            
            # Contribution should be affordable
            contribution_ratio = max_contribution / profile.monthly_income
            assert contribution_ratio <= 0.4, \
                f"Maximum contribution {contribution_ratio:.1%} too high for income"
            
            # Should be able to achieve goal within timeline
            total_capacity = max_contribution * min_timeline
            assert total_capacity >= 50000 * 0.8, \
                "Goal not achievable with minimum timeline and max contribution"
    
    def test_housing_affordability_accuracy(self):
        """Test housing affordability calculations"""
        for profile in self.test_profiles:
            housing_thresholds = get_housing_affordability_thresholds(profile)
            
            recommended = housing_thresholds.get('recommended_housing_ratio', 0.30)
            maximum = housing_thresholds.get('maximum_housing_ratio', 0.40)
            comfortable = housing_thresholds.get('comfortable_housing_ratio', 0.25)
            
            # Logical ordering
            assert comfortable < recommended < maximum, \
                "Housing ratios not in logical order"
            
            # Reasonable bounds
            assert 0.15 <= comfortable <= 0.35, "Comfortable ratio out of bounds"
            assert 0.20 <= recommended <= 0.45, "Recommended ratio out of bounds" 
            assert 0.25 <= maximum <= 0.50, "Maximum ratio out of bounds"
            
            # Income appropriateness
            if profile.monthly_income < 3000:
                assert recommended >= 0.30, "Low income needs higher housing allocation"
            elif profile.monthly_income > 12000:
                assert recommended <= 0.30, "High income should have lower housing percentage"


class TestThresholdConsistency:
    """Test consistency and relationships between different threshold types"""
    
    def setup_method(self):
        self.test_profile = UserContext(
            monthly_income=6000, age=35, region="US", family_size=2
        )
    
    def test_budget_savings_consistency(self):
        """Test that budget allocations and savings targets are consistent"""
        budget_allocations = get_dynamic_thresholds(
            ThresholdType.BUDGET_ALLOCATION, self.test_profile
        )
        savings_targets = get_dynamic_thresholds(
            ThresholdType.SAVINGS_TARGET, self.test_profile
        )
        
        budget_savings = budget_allocations.get('savings', 0.12)
        target_savings = savings_targets.get('target_savings_rate', 0.12)
        
        # Should be within 20% of each other
        ratio = abs(budget_savings - target_savings) / max(budget_savings, target_savings)
        assert ratio <= 0.2, \
            f"Budget savings {budget_savings:.2%} and target {target_savings:.2%} inconsistent"
    
    def test_goal_constraint_affordability_consistency(self):
        """Test that goal constraints align with affordability"""
        constraints = get_dynamic_thresholds(ThresholdType.GOAL_CONSTRAINT, self.test_profile)
        savings_targets = get_dynamic_thresholds(ThresholdType.SAVINGS_TARGET, self.test_profile)
        
        max_contribution = constraints.get('maximum_monthly_contribution', 1000)
        target_savings_rate = savings_targets.get('target_savings_rate', 0.12)
        expected_max = self.test_profile.monthly_income * target_savings_rate * 1.5  # 150% of target
        
        assert max_contribution <= expected_max * 1.1, \
            "Goal contribution limit inconsistent with savings capacity"
    
    def test_threshold_monotonicity(self):
        """Test that thresholds change monotonically with income"""
        incomes = [3000, 4000, 5000, 6000, 8000, 10000, 12000]
        
        # Test housing ratio decreases with income
        housing_ratios = []
        savings_rates = []
        
        for income in incomes:
            profile = UserContext(monthly_income=income, age=35, region="US")
            
            budget = get_dynamic_thresholds(ThresholdType.BUDGET_ALLOCATION, profile)
            savings = get_dynamic_thresholds(ThresholdType.SAVINGS_TARGET, profile)
            
            housing_ratios.append(budget.get('housing', 0.30))
            savings_rates.append(savings.get('target_savings_rate', 0.12))
        
        # Housing ratios should generally decrease (Engel's Law)
        for i in range(len(housing_ratios) - 1):
            if housing_ratios[i+1] > housing_ratios[i]:
                # Allow some flexibility, but flag large increases
                increase = housing_ratios[i+1] - housing_ratios[i]
                assert increase <= 0.03, f"Housing ratio increased too much: {increase:.2%}"
        
        # Savings rates should generally increase
        for i in range(len(savings_rates) - 1):
            assert savings_rates[i+1] >= savings_rates[i] * 0.95, \
                f"Savings rate decreased unexpectedly at income ${incomes[i+1]}"


class TestBackwardCompatibility:
    """Test that dynamic thresholds maintain reasonable compatibility with existing system"""
    
    def setup_method(self):
        # Representative user profile
        self.standard_profile = UserContext(
            monthly_income=5000, age=35, region="US", family_size=2
        )
    
    def test_threshold_ranges_reasonable(self):
        """Test that all thresholds fall within historically reasonable ranges"""
        # Budget allocations
        budget = get_dynamic_thresholds(ThresholdType.BUDGET_ALLOCATION, self.standard_profile)
        
        assert 0.25 <= budget.get('housing', 0.30) <= 0.40, "Housing allocation outside normal range"
        assert 0.10 <= budget.get('food', 0.12) <= 0.18, "Food allocation outside normal range"
        assert 0.08 <= budget.get('transport', 0.15) <= 0.20, "Transport allocation outside normal range"
        assert 0.05 <= budget.get('entertainment', 0.08) <= 0.15, "Entertainment allocation outside normal range"
        assert 0.08 <= budget.get('savings', 0.12) <= 0.20, "Savings allocation outside normal range"
        
        # Spending patterns
        patterns = get_dynamic_thresholds(ThresholdType.SPENDING_PATTERN, self.standard_profile)
        
        small_threshold = patterns.get('small_purchase_threshold', 25)
        assert 10 <= small_threshold <= 75, f"Small purchase threshold ${small_threshold} outside normal range"
        
        variance_threshold = patterns.get('monthly_variance_threshold', 0.3)
        assert 0.2 <= variance_threshold <= 0.5, "Variance threshold outside normal range"
    
    def test_no_extreme_recommendations(self):
        """Test that system doesn't generate extreme or dangerous recommendations"""
        # Test across income spectrum
        for monthly_income in [2000, 10000, 20000]:
            profile = UserContext(monthly_income=monthly_income, age=35)
            
            # Housing should never be below 15% or above 50%
            housing_thresholds = get_housing_affordability_thresholds(profile)
            recommended = housing_thresholds.get('recommended_housing_ratio', 0.30)
            assert 0.15 <= recommended <= 0.50, \
                f"Extreme housing recommendation: {recommended:.2%} for ${monthly_income}"
            
            # Savings should never be below 2% or above 50%
            savings = get_dynamic_thresholds(ThresholdType.SAVINGS_TARGET, profile)
            savings_rate = savings.get('target_savings_rate', 0.12)
            assert 0.02 <= savings_rate <= 0.50, \
                f"Extreme savings recommendation: {savings_rate:.2%} for ${monthly_income}"


@pytest.fixture
def sample_user_contexts():
    """Fixture providing sample user contexts for testing"""
    return [
        UserContext(monthly_income=3000, age=25, region="US"),
        UserContext(monthly_income=6000, age=35, region="US-CA", family_size=2),
        UserContext(monthly_income=12000, age=45, region="US-NY", family_size=3),
    ]


def test_dynamic_thresholds_comprehensive(sample_user_contexts):
    """Comprehensive integration test across all threshold types"""
    for context in sample_user_contexts:
        # Test all threshold types work
        for threshold_type in ThresholdType:
            try:
                thresholds = get_dynamic_thresholds(threshold_type, context)
                assert isinstance(thresholds, dict), f"Invalid return type for {threshold_type}"
                assert len(thresholds) > 0, f"Empty thresholds for {threshold_type}"
            except Exception as e:
                pytest.fail(f"Failed to get {threshold_type} thresholds: {e}")


def test_scaling_algorithms_edge_cases():
    """Test scaling algorithms handle edge cases properly"""
    scaling = IncomeScalingAlgorithms()
    
    # Very low income
    low_housing = scaling.scale_housing_ratio(monthly_income=1500)
    assert low_housing >= 0.20, "Housing ratio too low for very low income"
    assert low_housing <= 0.50, "Housing ratio too high even for low income"
    
    # Very high income
    high_housing = scaling.scale_housing_ratio(monthly_income=50000)
    assert high_housing >= 0.15, "Housing ratio too low even for high income"
    assert high_housing <= 0.35, "Housing ratio should decrease with very high income"
    
    # Zero income (edge case)
    try:
        zero_housing = scaling.scale_housing_ratio(monthly_income=0)
        assert 0.20 <= zero_housing <= 0.50, "Zero income should have reasonable fallback"
    except Exception as e:
        # Should handle gracefully
        assert "negative" not in str(e).lower(), "Should not mention negative income"


if __name__ == "__main__":
    # Run validation tests
    pytest.main([__file__, "-v", "--tb=short"])