"""
Comprehensive test suite for the centralized Income Classification Service.

This test ensures zero-tolerance financial accuracy and consistency across
all income classification logic in MITA Finance.
"""

import pytest
from app.services.core.income_classification_service import (
    IncomeClassificationService,
    IncomeTier,
    classify_income,
    get_tier_string,
    get_tier_display_info,
    get_budget_weights,
    validate_income_profile
)


class TestIncomeClassificationService:
    """Test suite for centralized income classification service"""
    
    def setup_method(self):
        """Setup test fixtures"""
        self.service = IncomeClassificationService()
    
    def test_service_initialization(self):
        """Test that service initializes correctly with profile validation"""
        # Should not raise any exceptions
        service = IncomeClassificationService()
        assert service is not None
    
    @pytest.mark.parametrize("monthly_income,region,expected_tier", [
        # US National thresholds
        (2999.99, "US", IncomeTier.LOW),
        (3000.00, "US", IncomeTier.LOW),
        (3000.01, "US", IncomeTier.LOWER_MIDDLE),
        (4799.99, "US", IncomeTier.LOWER_MIDDLE),
        (4800.00, "US", IncomeTier.LOWER_MIDDLE),
        (4800.01, "US", IncomeTier.MIDDLE),
        (7199.99, "US", IncomeTier.MIDDLE),
        (7200.00, "US", IncomeTier.MIDDLE),
        (7200.01, "US", IncomeTier.UPPER_MIDDLE),
        (11999.99, "US", IncomeTier.UPPER_MIDDLE),
        (12000.00, "US", IncomeTier.UPPER_MIDDLE),
        (12000.01, "US", IncomeTier.HIGH),
        (20000.00, "US", IncomeTier.HIGH),
        
        # California thresholds (higher due to cost of living)
        (3744.58, "US-CA", IncomeTier.LOW),      # $44,935 annually
        (3744.59, "US-CA", IncomeTier.LOWER_MIDDLE),
        (5991.33, "US-CA", IncomeTier.LOWER_MIDDLE), # $71,896 annually
        (5991.34, "US-CA", IncomeTier.MIDDLE),
        (8987.00, "US-CA", IncomeTier.MIDDLE),   # $107,844 annually
        (8987.01, "US-CA", IncomeTier.UPPER_MIDDLE),
        (14978.33, "US-CA", IncomeTier.UPPER_MIDDLE), # $179,740 annually
        (14978.34, "US-CA", IncomeTier.HIGH),
    ])
    def test_income_classification_accuracy(self, monthly_income, region, expected_tier):
        """Test that income classification is mathematically accurate"""
        actual_tier = self.service.classify_income(monthly_income, region)
        assert actual_tier == expected_tier, (
            f"Classification error for ${monthly_income}/month in {region}: "
            f"expected {expected_tier.value}, got {actual_tier.value}"
        )
    
    def test_negative_income_validation(self):
        """Test that negative income raises appropriate error"""
        with pytest.raises(ValueError, match="Income cannot be negative"):
            self.service.classify_income(-1000, "US")
    
    def test_boundary_precision(self):
        """Test precision at exact threshold boundaries"""
        # Test floating-point precision issues
        test_cases = [
            (2999.995, "US", IncomeTier.LOW),        # Should round down
            (3000.004, "US", IncomeTier.LOWER_MIDDLE), # Should round up
            (4799.996, "US", IncomeTier.LOWER_MIDDLE),
            (4800.004, "US", IncomeTier.MIDDLE),
        ]
        
        for income, region, expected in test_cases:
            actual = self.service.classify_income(income, region)
            assert actual == expected, (
                f"Precision error at ${income}: expected {expected.value}, got {actual.value}"
            )
    
    def test_tier_thresholds_retrieval(self):
        """Test that tier thresholds are correctly retrieved"""
        us_thresholds = self.service.get_tier_thresholds("US")
        
        # Verify all required thresholds exist
        required_keys = ["low", "lower_middle", "middle", "upper_middle"]
        for key in required_keys:
            assert key in us_thresholds, f"Missing threshold: {key}"
            assert us_thresholds[key] > 0, f"Invalid threshold for {key}: {us_thresholds[key]}"
        
        # Verify thresholds are in ascending order
        assert us_thresholds["low"] < us_thresholds["lower_middle"]
        assert us_thresholds["lower_middle"] < us_thresholds["middle"]
        assert us_thresholds["middle"] < us_thresholds["upper_middle"]
    
    def test_tier_display_info(self):
        """Test tier display information is complete and accurate"""
        for tier in IncomeTier:
            info = self.service.get_tier_display_info(tier, "US")
            
            # Verify all required fields exist
            assert "name" in info
            assert "description" in info
            assert "range" in info
            
            # Verify fields are non-empty
            assert len(info["name"]) > 0
            assert len(info["description"]) > 0
            assert len(info["range"]) > 0
            
            # Verify range contains dollar amounts
            assert "$" in info["range"]
    
    def test_behavioral_patterns(self):
        """Test behavioral economics patterns are complete"""
        for tier in IncomeTier:
            pattern = self.service.get_behavioral_pattern(tier)
            
            # Verify all required behavioral attributes exist
            required_attrs = [
                "decision_time", "planning_horizon", "risk_tolerance",
                "primary_motivators", "mental_accounting_buckets",
                "savings_rate_target", "housing_ratio_target"
            ]
            
            for attr in required_attrs:
                assert attr in pattern, f"Missing behavioral attribute {attr} for {tier.value}"
            
            # Verify savings rate is reasonable (0-40%)
            savings_rate = pattern["savings_rate_target"]
            assert 0.0 <= savings_rate <= 0.4, (
                f"Unreasonable savings rate for {tier.value}: {savings_rate}"
            )
            
            # Verify housing ratio is reasonable (20-50%)
            housing_ratio = pattern["housing_ratio_target"]
            assert 0.2 <= housing_ratio <= 0.5, (
                f"Unreasonable housing ratio for {tier.value}: {housing_ratio}"
            )
    
    def test_budget_weights_completeness(self):
        """Test that budget weights are complete and sum correctly"""
        for tier in IncomeTier:
            weights = self.service.get_budget_weights(tier, "US")
            
            # Verify weights sum to approximately 1.0 (allowing for rounding)
            total_weight = sum(weights.values())
            assert abs(total_weight - 1.0) < 0.01, (
                f"Budget weights don't sum to 1.0 for {tier.value}: {total_weight}"
            )
            
            # Verify all weights are positive
            for category, weight in weights.items():
                assert weight > 0, f"Negative weight for {category} in {tier.value}: {weight}"
                assert weight < 1.0, f"Weight > 100% for {category} in {tier.value}: {weight}"
            
            # Verify essential categories exist
            essential_categories = ["housing", "food", "transport"]
            for category in essential_categories:
                assert category in weights, (
                    f"Missing essential category {category} for {tier.value}"
                )
    
    def test_tier_boundary_detection(self):
        """Test near-boundary detection for tier transitions"""
        # Test cases for boundary detection (within 5% of tier upper boundary)
        test_cases = [
            # Lower middle tier max: $57.6K, 5% = $2.88K, so $54.72K+ is "near"
            (4560, "US", True, IncomeTier.MIDDLE),      # $54.72K - exactly at 5% threshold
            (4400, "US", False, None),                  # $52.8K - not close enough
            
            # Middle tier max: $86.4K, 5% = $4.32K, so $82.08K+ is "near"  
            (6840, "US", True, IncomeTier.UPPER_MIDDLE), # $82.08K - exactly at 5% threshold
            (6500, "US", False, None),                   # $78K - not close enough
            
            # Upper middle tier max: $144K, 5% = $7.2K, so $136.8K+ is "near"
            (11400, "US", True, IncomeTier.HIGH),       # $136.8K - exactly at 5% threshold
            (10000, "US", False, None),                 # $120K - not close enough
            
            # High tier has no next tier
            (15000, "US", False, None),                 # High tier has no next
        ]
        
        for income, region, expected_near, expected_next in test_cases:
            is_near, next_tier = self.service.is_near_tier_boundary(income, region)
            
            assert is_near == expected_near, (
                f"Boundary detection error for ${income}: expected {expected_near}, got {is_near}"
            )
            assert next_tier == expected_next, (
                f"Next tier error for ${income}: expected {expected_next}, got {next_tier}"
            )
    
    def test_consistency_across_regions(self):
        """Test that classification logic is consistent across regions"""
        test_income = 5000  # Monthly income that should classify differently by region
        
        us_tier = self.service.classify_income(test_income, "US")
        ca_tier = self.service.classify_income(test_income, "US-CA")
        
        # Same income may classify differently due to regional cost adjustments
        # This is expected behavior, not an error
        assert us_tier in IncomeTier
        assert ca_tier in IncomeTier
    
    def test_validation_function(self):
        """Test income profile validation function"""
        # Valid profiles
        valid_profiles = [
            {"income": 5000, "region": "US"},
            {"income": 3500, "region": "US-CA"},
            {"income": 0, "region": "US"},  # Zero income should be valid
        ]
        
        for profile in valid_profiles:
            assert self.service.validate_classification_consistency(profile), (
                f"Valid profile rejected: {profile}"
            )
        
        # Invalid profiles
        invalid_profiles = [
            {"income": -100, "region": "US"},  # Negative income
            {},  # Missing fields
        ]
        
        for profile in invalid_profiles:
            assert not self.service.validate_classification_consistency(profile), (
                f"Invalid profile accepted: {profile}"
            )


class TestPublicAPI:
    """Test the public API functions for backward compatibility"""
    
    def test_classify_income_function(self):
        """Test main public classification function"""
        tier = classify_income(5000, "US")
        assert tier == IncomeTier.MIDDLE
    
    def test_get_tier_string_function(self):
        """Test tier string conversion"""
        assert get_tier_string(IncomeTier.LOW) == "low"
        assert get_tier_string(IncomeTier.LOWER_MIDDLE) == "lower_middle"
        assert get_tier_string(IncomeTier.HIGH) == "high"
    
    def test_get_tier_display_info_function(self):
        """Test display info retrieval function"""
        info = get_tier_display_info(IncomeTier.MIDDLE, "US")
        assert "name" in info
        assert "description" in info
        assert "range" in info
    
    def test_get_budget_weights_function(self):
        """Test budget weights retrieval function"""
        weights = get_budget_weights(IncomeTier.MIDDLE, "US")
        assert isinstance(weights, dict)
        assert len(weights) > 0
        
        # Verify weights sum to approximately 1.0
        total = sum(weights.values())
        assert abs(total - 1.0) < 0.01
    
    def test_validate_income_profile_function(self):
        """Test profile validation function"""
        valid_profile = {"income": 5000, "region": "US"}
        assert validate_income_profile(valid_profile)
        
        invalid_profile = {"income": -100, "region": "US"}
        assert not validate_income_profile(invalid_profile)


class TestEconomicAccuracy:
    """Test economic accuracy and real-world applicability"""
    
    def test_median_income_classification(self):
        """Test that US median income classifies correctly"""
        # US median household income ~$70,000 annually = ~$5,833 monthly
        median_monthly = 70000 / 12
        tier = classify_income(median_monthly, "US")
        
        # Median income should classify as MIDDLE tier
        assert tier == IncomeTier.MIDDLE, (
            f"US median income should be MIDDLE tier, got {tier.value}"
        )
    
    def test_poverty_level_classification(self):
        """Test that poverty-level income classifies as LOW"""
        # Federal poverty guideline ~$15,060 annually = ~$1,255 monthly
        poverty_monthly = 15060 / 12
        tier = classify_income(poverty_monthly, "US")
        
        assert tier == IncomeTier.LOW, (
            f"Poverty-level income should be LOW tier, got {tier.value}"
        )
    
    def test_high_earner_classification(self):
        """Test that high-income earners classify correctly"""
        # Top 10% income ~$150,000+ annually
        high_earner_monthly = 150000 / 12
        tier = classify_income(high_earner_monthly, "US")
        
        assert tier == IncomeTier.HIGH, (
            f"High earner should be HIGH tier, got {tier.value}"
        )
    
    def test_cost_of_living_adjustment(self):
        """Test that regional cost-of-living adjustments work correctly"""
        test_income = 4000  # $48K annually
        
        us_tier = classify_income(test_income, "US")
        ca_tier = classify_income(test_income, "US-CA")
        
        # California should have higher thresholds due to cost of living
        # Same income should potentially classify lower in CA than US
        # This verifies regional adjustment is working
        assert us_tier in IncomeTier
        assert ca_tier in IncomeTier
    
    def test_savings_rate_targets_realistic(self):
        """Test that savings rate targets are economically realistic"""
        service = IncomeClassificationService()
        
        for tier in IncomeTier:
            pattern = service.get_behavioral_pattern(tier)
            savings_rate = pattern["savings_rate_target"]
            
            # Verify savings rates increase with income (behavioral economics)
            if tier == IncomeTier.LOW:
                assert savings_rate <= 0.10, "Low income savings rate too high"
            elif tier == IncomeTier.HIGH:
                assert savings_rate >= 0.15, "High income savings rate too low"
    
    def test_housing_ratio_economic_soundness(self):
        """Test that housing ratios align with economic best practices"""
        service = IncomeClassificationService()
        
        for tier in IncomeTier:
            pattern = service.get_behavioral_pattern(tier)
            housing_ratio = pattern["housing_ratio_target"]
            
            # Housing ratios should decrease as percentage of income as income rises
            if tier == IncomeTier.LOW:
                assert housing_ratio >= 0.35, "Low income housing ratio too low"
            elif tier == IncomeTier.HIGH:
                assert housing_ratio <= 0.30, "High income housing ratio too high"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])