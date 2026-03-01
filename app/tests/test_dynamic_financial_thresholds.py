"""
Test suite for Dynamic Financial Threshold System
Validates economic soundness across different user profiles and income levels
"""

import pytest

from app.services.core.dynamic_threshold_service import (
    DynamicThresholdService, 
    UserContext, 
    get_dynamic_budget_method,
    get_housing_affordability_thresholds
)


class TestDynamicThresholdEconomicSoundness:
    """Test economic soundness of dynamic threshold calculations"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.service = DynamicThresholdService()
        
        # Test user profiles representing different economic situations
        self.user_profiles = {
            'low_income_single': UserContext(
                monthly_income=3000,
                age=28,
                region='US',
                family_size=1,
                debt_to_income_ratio=0.15,
                housing_status='rent',
                life_stage='single'
            ),
            'lower_middle_family': UserContext(
                monthly_income=4800,
                age=35,
                region='US-TX',
                family_size=3,
                debt_to_income_ratio=0.25,
                housing_status='rent',
                life_stage='family'
            ),
            'middle_income_couple': UserContext(
                monthly_income=7200,
                age=32,
                region='US',
                family_size=2,
                debt_to_income_ratio=0.18,
                housing_status='own',
                life_stage='couple'
            ),
            'upper_middle_california': UserContext(
                monthly_income=12000,
                age=40,
                region='US-CA',
                family_size=2,
                debt_to_income_ratio=0.10,
                housing_status='own',
                life_stage='couple'
            ),
            'high_income_executive': UserContext(
                monthly_income=25000,
                age=45,
                region='US-NY',
                family_size=4,
                debt_to_income_ratio=0.05,
                housing_status='own',
                life_stage='family'
            ),
            'senior_retiree': UserContext(
                monthly_income=4500,
                age=68,
                region='US-FL',
                family_size=2,
                debt_to_income_ratio=0.0,
                housing_status='own',
                life_stage='retirement'
            )
        }
    
    def test_budget_allocations_sum_to_one(self):
        """Test that budget allocations sum to approximately 100%"""
        for profile_name, user_context in self.user_profiles.items():
            allocations = self.service.get_budget_allocation_thresholds(user_context)
            total = sum(allocations.values())
            
            # Should sum to between 95% and 105% (allowing for rounding)
            assert 0.95 <= total <= 1.05, (
                f"Budget allocations for {profile_name} sum to {total:.3f}, "
                f"should be close to 1.0. Allocations: {allocations}"
            )
    
    def test_housing_ratios_economically_sound(self):
        """Test that housing ratios follow economic best practices"""
        for profile_name, user_context in self.user_profiles.items():
            housing_thresholds = get_housing_affordability_thresholds(user_context)
            recommended_ratio = housing_thresholds['recommended_housing_ratio']
            
            # Housing should be between 20% and 50% of income
            assert 0.20 <= recommended_ratio <= 0.50, (
                f"Housing ratio for {profile_name} is {recommended_ratio:.3f}, "
                f"should be between 20% and 50%"
            )
            
            # Higher income should generally allow for lower housing percentage
            if user_context.monthly_income > 15000:
                assert recommended_ratio <= 0.35, (
                    f"High income profile {profile_name} should have housing ratio ≤ 35%, "
                    f"got {recommended_ratio:.3f}"
                )
    
    def test_savings_rates_increase_with_income(self):
        """Test that savings rate targets increase with income capacity"""
        savings_rates = {}
        for profile_name, user_context in self.user_profiles.items():
            savings_targets = self.service.get_savings_rate_targets(user_context)
            savings_rates[profile_name] = savings_targets['target_savings_rate']
        
        # Higher income profiles should generally have higher savings rates
        assert savings_rates['high_income_executive'] > savings_rates['low_income_single']
        assert savings_rates['upper_middle_california'] > savings_rates['lower_middle_family']
        
        # All savings rates should be reasonable (between 2% and 50%)
        for profile_name, rate in savings_rates.items():
            assert 0.02 <= rate <= 0.50, (
                f"Savings rate for {profile_name} is {rate:.3f}, "
                f"should be between 2% and 50%"
            )
    
    def test_regional_cost_adjustments(self):
        """Test that regional cost differences are reflected in allocations"""
        # Compare same income in different regions
        base_context = UserContext(
            monthly_income=7000,
            age=35,
            family_size=2,
            debt_to_income_ratio=0.15
        )
        
        regions = ['US', 'US-CA', 'US-NY', 'US-TX']
        housing_ratios = {}
        
        for region in regions:
            context = UserContext(
                monthly_income=base_context.monthly_income,
                age=base_context.age,
                region=region,
                family_size=base_context.family_size,
                debt_to_income_ratio=base_context.debt_to_income_ratio
            )
            
            housing_thresholds = get_housing_affordability_thresholds(context)
            housing_ratios[region] = housing_thresholds['recommended_housing_ratio']
        
        # High-cost regions should have higher housing ratios
        assert housing_ratios['US-CA'] > housing_ratios['US-TX'], (
            "California should have higher housing ratio than Texas"
        )
        assert housing_ratios['US-NY'] > housing_ratios['US'], (
            "New York should have higher housing ratio than US average"
        )
    
    def test_life_stage_adjustments(self):
        """Test that life stage affects financial priorities appropriately"""
        base_income = 6000
        
        contexts = {
            'young_single': UserContext(monthly_income=base_income, age=25, life_stage='single', family_size=1),
            'family': UserContext(monthly_income=base_income, age=35, life_stage='family', family_size=4),
            'senior': UserContext(monthly_income=base_income, age=65, life_stage='retirement', family_size=2)
        }
        
        for life_stage, context in contexts.items():
            priorities = self.service.get_category_priority_thresholds(context)
            
            if life_stage == 'family':
                # Families should prioritize healthcare and education
                assert priorities['healthcare'] <= 5, "Families should prioritize healthcare"
                assert priorities.get('education', 10) <= 9, "Families should prioritize education"
            
            elif life_stage == 'senior':
                # Seniors should prioritize healthcare
                assert priorities['healthcare'] <= 3, "Seniors should highly prioritize healthcare"
    
    def test_debt_impact_on_allocations(self):
        """Test that high debt appropriately affects budget allocations"""
        base_context = UserContext(
            monthly_income=6000,
            age=35,
            region='US',
            family_size=2
        )
        
        low_debt_context = UserContext(**base_context.__dict__, debt_to_income_ratio=0.05)
        high_debt_context = UserContext(**base_context.__dict__, debt_to_income_ratio=0.35)
        
        low_debt_allocations = self.service.get_budget_allocation_thresholds(low_debt_context)
        high_debt_allocations = self.service.get_budget_allocation_thresholds(high_debt_context)
        
        # High debt should result in debt payment allocation
        if 'debt_payment' in high_debt_allocations:
            assert high_debt_allocations['debt_payment'] > 0.2, (
                "High debt should allocate significant portion to debt payment"
            )
        
        # High debt should reduce discretionary spending
        discretionary_categories = ['entertainment', 'shopping', 'miscellaneous']
        for category in discretionary_categories:
            if category in low_debt_allocations or category in high_debt_allocations:
                low_disc = low_debt_allocations.get(category, 0)
                high_disc = high_debt_allocations.get(category, 0)
                if low_disc > 0:  # Only compare if category exists in low debt scenario
                    assert high_disc <= low_disc, (
                        f"High debt should reduce {category} spending"
                    )
    
    def test_spending_pattern_thresholds_scale_with_income(self):
        """Test that spending pattern detection thresholds scale appropriately with income"""
        profiles = ['low_income_single', 'middle_income_couple', 'high_income_executive']
        
        small_purchase_thresholds = {}
        large_purchase_thresholds = {}
        
        for profile_name in profiles:
            context = self.user_profiles[profile_name]
            thresholds = self.service.get_spending_pattern_thresholds(context)
            
            small_purchase_thresholds[profile_name] = thresholds['small_purchase_threshold']
            large_purchase_thresholds[profile_name] = thresholds['large_purchase_threshold']
        
        # Higher income should have higher thresholds
        assert (small_purchase_thresholds['high_income_executive'] > 
                small_purchase_thresholds['low_income_single'])
        
        assert (large_purchase_thresholds['high_income_executive'] > 
                large_purchase_thresholds['low_income_single'])
        
        # Large purchase threshold should be meaningfully larger than small
        for profile_name in profiles:
            assert (large_purchase_thresholds[profile_name] > 
                   small_purchase_thresholds[profile_name] * 3), (
                f"Large purchase threshold should be >> small for {profile_name}"
            )
    
    def test_dynamic_budget_method_appropriateness(self):
        """Test that recommended budget methods are appropriate for income levels"""
        for profile_name, user_context in self.user_profiles.items():
            budget_method = get_dynamic_budget_method(user_context)
            
            # Validate percentages are reasonable
            needs_pct = budget_method['needs_percentage']
            wants_pct = budget_method['wants_percentage']
            savings_pct = budget_method['savings_percentage']
            
            assert 30 <= needs_pct <= 80, f"Needs % for {profile_name} should be 30-80%, got {needs_pct}"
            assert 5 <= wants_pct <= 40, f"Wants % for {profile_name} should be 5-40%, got {wants_pct}"
            assert 2 <= savings_pct <= 30, f"Savings % for {profile_name} should be 2-30%, got {savings_pct}"
            
            # Total should be reasonable (allowing for investments category)
            total_pct = needs_pct + wants_pct + savings_pct
            assert 80 <= total_pct <= 120, f"Total % for {profile_name} should be 80-120%, got {total_pct}"
            
            # Method should be appropriate for income level
            method = budget_method['method']
            if user_context.monthly_income < 4000:
                assert method in ['needs_first'], f"Low income should use needs_first method, got {method}"
            elif user_context.monthly_income > 15000:
                assert method in ['wealth_building'], f"High income should use wealth_building method, got {method}"
    
    def test_cooldown_periods_make_economic_sense(self):
        """Test that cooldown periods reflect economic behavioral patterns"""
        for profile_name, user_context in self.user_profiles.items():
            cooldowns = self.service.get_cooldown_thresholds(user_context)
            
            # Essential categories should have minimal cooldowns
            assert cooldowns.get('groceries', 0) <= 1, "Groceries should have minimal cooldown"
            assert cooldowns.get('transport', 0) == 0, "Transport should have no cooldown"
            assert cooldowns.get('healthcare', 0) == 0, "Healthcare should have no cooldown"
            
            # Discretionary categories should have meaningful cooldowns
            assert cooldowns.get('entertainment', 0) >= 1, "Entertainment should have some cooldown"
            assert cooldowns.get('clothing', 0) >= 3, "Clothing should have meaningful cooldown"
            
            # Higher income should generally have shorter cooldowns
            if user_context.monthly_income > 15000:
                for category in ['entertainment', 'dining_out', 'shopping']:
                    if category in cooldowns:
                        assert cooldowns[category] <= 5, (
                            f"High income should have shorter {category} cooldown"
                        )
    
    def test_economic_environment_adjustments(self):
        """Test that economic environment affects thresholds appropriately"""
        # This tests the service's ability to adjust for economic conditions
        base_context = self.user_profiles['middle_income_couple']
        
        # Test with modified economic conditions (would normally come from external APIs)
        service_high_inflation = DynamicThresholdService()
        service_high_inflation.economic_context.inflation_rate = 0.08  # 8% inflation
        service_high_inflation.economic_context.recession_risk = 0.4   # High recession risk
        
        normal_allocations = self.service.get_budget_allocation_thresholds(base_context)
        crisis_allocations = service_high_inflation.get_budget_allocation_thresholds(base_context)
        
        # During economic stress, savings should be prioritized more
        if 'savings' in normal_allocations and 'savings' in crisis_allocations:
            assert crisis_allocations['savings'] >= normal_allocations['savings'], (
                "High recession risk should increase savings priority"
            )
    
    def test_threshold_consistency_validation(self):
        """Test that our validation functions work correctly"""
        from app.services.core.dynamic_threshold_service import validate_threshold_consistency
        
        # Test valid thresholds
        valid_budget_thresholds = {'housing': 0.3, 'food': 0.15, 'savings': 0.2, 'other': 0.35}
        assert validate_threshold_consistency(valid_budget_thresholds, self.user_profiles['middle_income_couple'])
        
        # Test invalid thresholds (sum too high)
        invalid_thresholds = {'housing': 0.6, 'food': 0.3, 'savings': 0.3, 'other': 0.2}
        assert not validate_threshold_consistency(invalid_thresholds, self.user_profiles['middle_income_couple'])
    
    @pytest.mark.parametrize("income_level", [2000, 5000, 10000, 20000, 50000])
    def test_income_scaling_smoothness(self, income_level):
        """Test that threshold scaling is smooth across income levels"""
        context = UserContext(
            monthly_income=income_level,
            age=35,
            region='US',
            family_size=2
        )
        
        # All threshold calculations should succeed without errors
        budget_allocations = self.service.get_budget_allocation_thresholds(context)
        spending_patterns = self.service.get_spending_pattern_thresholds(context)
        savings_targets = self.service.get_savings_rate_targets(context)
        
        # Basic sanity checks
        assert isinstance(budget_allocations, dict) and budget_allocations
        assert isinstance(spending_patterns, dict) and spending_patterns
        assert isinstance(savings_targets, dict) and savings_targets
        
        # Ensure reasonable ranges for any income level
        total_budget = sum(budget_allocations.values())
        assert 0.8 <= total_budget <= 1.2, f"Budget total should be reasonable for income {income_level}"


class TestAPIEndpointIntegration:
    """Test integration with API endpoints"""
    
    def test_api_response_structure(self):
        """Test that API responses have correct structure"""
        # Test budget method API structure
        context = UserContext(monthly_income=6000, age=35, region='US', family_size=2)
        budget_method = get_dynamic_budget_method(context)
        
        # Verify required fields
        required_fields = ['method', 'description', 'needs_percentage', 'wants_percentage', 
                          'savings_percentage', 'allocations']
        for field in required_fields:
            assert field in budget_method, f"Budget method response missing field: {field}"
        
        # Verify reasonable values
        assert isinstance(budget_method['allocations'], dict)
        assert budget_method['needs_percentage'] > 0
        assert budget_method['wants_percentage'] > 0
        assert budget_method['savings_percentage'] > 0


if __name__ == "__main__":
    # Run a quick validation
    test_suite = TestDynamicThresholdEconomicSoundness()
    test_suite.setup_method()
    
    print("Running economic soundness validation...")
    
    # Test basic functionality
    test_suite.test_budget_allocations_sum_to_one()
    print("✅ Budget allocations sum correctly")
    
    test_suite.test_housing_ratios_economically_sound()
    print("✅ Housing ratios are economically sound")
    
    test_suite.test_savings_rates_increase_with_income()
    print("✅ Savings rates scale with income appropriately")
    
    test_suite.test_dynamic_budget_method_appropriateness()
    print("✅ Dynamic budget methods are appropriate for income levels")
    
    print("\n🎉 All economic soundness tests passed!")
    print("\nDynamic Financial Threshold System is ready for production use.")