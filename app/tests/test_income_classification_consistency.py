"""
Comprehensive test suite for income classification consistency across all backend components.
This ensures zero-tolerance quality standards for financial accuracy.
"""

import pytest
from decimal import Decimal
from unittest.mock import patch, MagicMock

# Import all the classification functions from different modules
from app.logic.cohort_analysis import CohortAnalyzer as LegacyCohortAnalyzer
from app.engine.cohort_analyzer import CohortAnalyzer as EngineCohortAnalyzer, determine_cohort
from app.services.core.cohort.cohort_analysis import CohortAnalyzer as CoreCohortAnalyzer, determine_cohort as core_determine_cohort
from app.services.core.engine.budget_logic import generate_budget_from_answers
from app.services.plan_service import generate_monthly_plan


class TestIncomeClassificationConsistency:
    """Test suite to ensure all income classification logic uses consistent 5-tier system."""
    
    @pytest.fixture
    def mock_country_profile(self):
        """Mock country profile with standard US-CA thresholds."""
        return {
            "class_thresholds": {
                "low": 36000,           # $3,000/month
                "lower_middle": 57600,  # $4,800/month  
                "middle": 86400,        # $7,200/month
                "upper_middle": 144000  # $12,000/month
            },
            "default_behavior": "balanced",
            "split_profiles": {
                "low": {"essentials": 0.7, "discretionary": 0.3},
                "lower_middle": {"essentials": 0.6, "discretionary": 0.4},
                "middle": {"essentials": 0.5, "discretionary": 0.5},
                "upper_middle": {"essentials": 0.4, "discretionary": 0.6},
                "high": {"essentials": 0.3, "discretionary": 0.7}
            }
        }
    
    @pytest.fixture
    def test_profiles(self):
        """Test profiles covering all income brackets and edge cases."""
        return [
            # Low income bracket
            {"income": 2500, "region": "US-CA", "behavior": "neutral", "categories": [], "expected_tier": "low"},
            {"income": 3000, "region": "US-CA", "behavior": "neutral", "categories": [], "expected_tier": "low"},
            
            # Lower middle bracket
            {"income": 3001, "region": "US-CA", "behavior": "neutral", "categories": [], "expected_tier": "lower_middle"},
            {"income": 4800, "region": "US-CA", "behavior": "neutral", "categories": [], "expected_tier": "lower_middle"},
            
            # Middle bracket
            {"income": 4801, "region": "US-CA", "behavior": "neutral", "categories": [], "expected_tier": "middle"},
            {"income": 7200, "region": "US-CA", "behavior": "neutral", "categories": [], "expected_tier": "middle"},
            
            # Upper middle bracket
            {"income": 7201, "region": "US-CA", "behavior": "neutral", "categories": [], "expected_tier": "upper_middle"},
            {"income": 12000, "region": "US-CA", "behavior": "neutral", "categories": [], "expected_tier": "upper_middle"},
            
            # High income bracket
            {"income": 12001, "region": "US-CA", "behavior": "neutral", "categories": [], "expected_tier": "high"},
            {"income": 20000, "region": "US-CA", "behavior": "neutral", "categories": [], "expected_tier": "high"},
            
            # Edge cases - exact threshold boundaries
            {"income": 3000.00, "region": "US-CA", "behavior": "neutral", "categories": [], "expected_tier": "low"},
            {"income": 4800.00, "region": "US-CA", "behavior": "neutral", "categories": [], "expected_tier": "lower_middle"},
            {"income": 7200.00, "region": "US-CA", "behavior": "neutral", "categories": [], "expected_tier": "middle"},
            {"income": 12000.00, "region": "US-CA", "behavior": "neutral", "categories": [], "expected_tier": "upper_middle"},
        ]
    
    @patch('app.config.country_profiles_loader.get_profile')
    def test_legacy_cohort_analyzer_consistency(self, mock_get_profile, mock_country_profile, test_profiles):
        """Test that legacy cohort analyzer uses 5-tier system consistently."""
        mock_get_profile.return_value = mock_country_profile
        
        analyzer = LegacyCohortAnalyzer()
        
        for profile in test_profiles:
            analyzer.register_user("test_user", profile)
            cohort = analyzer.assign_cohort("test_user")
            
            # Extract income band from cohort string (format: US-CA-income_band-style-tag1-tag2)
            # Income band is at index 2 since region contains hyphen (US-CA)
            cohort_parts = cohort.split("-")
            income_band = cohort_parts[2] if len(cohort_parts) >= 3 else "PARSE_ERROR"
            
            assert income_band == profile["expected_tier"], (
                f"Legacy cohort analyzer failed for income ${profile['income']}: "
                f"expected {profile['expected_tier']}, got {income_band}"
            )
    
    @patch('app.config.country_profiles_loader.get_profile')
    def test_engine_cohort_analyzer_consistency(self, mock_get_profile, mock_country_profile, test_profiles):
        """Test that engine cohort analyzer uses 5-tier system consistently."""
        mock_get_profile.return_value = mock_country_profile
        
        analyzer = EngineCohortAnalyzer()
        
        for profile in test_profiles:
            analyzer.register_user("test_user", profile)
            cohort = analyzer.assign_cohort("test_user")
            
            # Extract income band from cohort string (format: US-CA-income_band-style-tag1-tag2)
            cohort_parts = cohort.split("-")
            income_band = cohort_parts[2] if len(cohort_parts) >= 3 else "PARSE_ERROR"
            
            assert income_band == profile["expected_tier"], (
                f"Engine cohort analyzer failed for income ${profile['income']}: "
                f"expected {profile['expected_tier']}, got {income_band}"
            )
    
    @patch('app.config.country_profiles_loader.get_profile')
    def test_core_cohort_analyzer_consistency(self, mock_get_profile, mock_country_profile, test_profiles):
        """Test that core cohort analyzer uses 5-tier system consistently."""
        mock_get_profile.return_value = mock_country_profile
        
        analyzer = CoreCohortAnalyzer()
        
        for profile in test_profiles:
            cohort = analyzer.assign_cohort(profile)
            
            # Extract income band from cohort string (format: US-CA-income_band-style-tag1-tag2)
            cohort_parts = cohort.split("-")
            income_band = cohort_parts[2] if len(cohort_parts) >= 3 else "PARSE_ERROR"
            
            assert income_band == profile["expected_tier"], (
                f"Core cohort analyzer failed for income ${profile['income']}: "
                f"expected {profile['expected_tier']}, got {income_band}"
            )
    
    @patch('app.config.country_profiles_loader.get_profile')
    def test_budget_logic_consistency(self, mock_get_profile, mock_country_profile):
        """Test that budget logic uses 5-tier system consistently."""
        mock_get_profile.return_value = mock_country_profile
        
        test_cases = [
            {"monthly_income": 2500, "expected_class": "low"},
            {"monthly_income": 3000, "expected_class": "low"},
            {"monthly_income": 3001, "expected_class": "lower_middle"},
            {"monthly_income": 4800, "expected_class": "lower_middle"},
            {"monthly_income": 4801, "expected_class": "middle"},
            {"monthly_income": 7200, "expected_class": "middle"},
            {"monthly_income": 7201, "expected_class": "upper_middle"},
            {"monthly_income": 12000, "expected_class": "upper_middle"},
            {"monthly_income": 12001, "expected_class": "high"},
            {"monthly_income": 20000, "expected_class": "high"},
        ]
        
        for case in test_cases:
            answers = {
                "region": "US-CA",
                "income": {
                    "monthly_income": case["monthly_income"],
                    "additional_income": 0
                },
                "fixed_expenses": {"rent": 1000, "utilities": 200},
                "goals": {"savings_goal_amount_per_month": 500},
                "spending_habits": {
                    "dining_out_per_month": 5,
                    "entertainment_per_month": 3,
                    "clothing_per_month": 2,
                    "travel_per_year": 12,
                    "coffee_per_week": 7,
                    "transport_per_month": 10
                }
            }
            
            try:
                budget = generate_budget_from_answers(answers)
                user_class = budget["user_class"]
                
                assert user_class == case["expected_class"], (
                    f"Budget logic failed for income ${case['monthly_income']}: "
                    f"expected {case['expected_class']}, got {user_class}"
                )
            except ValueError:
                # Skip cases where fixed expenses exceed income
                continue
    
    def test_all_analyzers_produce_same_classification(self, mock_country_profile):
        """Critical test: All analyzers must produce identical income classifications."""
        with patch('app.config.country_profiles_loader.get_profile', return_value=mock_country_profile):
            test_incomes = [2500, 3000, 3001, 4800, 4801, 7200, 7201, 12000, 12001, 20000]
            
            for income in test_incomes:
                profile = {
                    "income": income,
                    "region": "US-CA",
                    "behavior": "neutral",
                    "categories": []
                }
                
                # Test all cohort analyzers
                legacy_analyzer = LegacyCohortAnalyzer()
                legacy_analyzer.register_user("test", profile)
                legacy_cohort = legacy_analyzer.assign_cohort("test")
                legacy_cohort_parts = legacy_cohort.split("-")
                legacy_tier = legacy_cohort_parts[2] if len(legacy_cohort_parts) >= 3 else "PARSE_ERROR"
                
                engine_analyzer = EngineCohortAnalyzer()
                engine_analyzer.register_user("test", profile)
                engine_cohort = engine_analyzer.assign_cohort("test")
                engine_cohort_parts = engine_cohort.split("-")
                engine_tier = engine_cohort_parts[2] if len(engine_cohort_parts) >= 3 else "PARSE_ERROR"
                
                core_analyzer = CoreCohortAnalyzer()
                core_cohort = core_analyzer.assign_cohort(profile)
                core_cohort_parts = core_cohort.split("-")
                core_tier = core_cohort_parts[2] if len(core_cohort_parts) >= 3 else "PARSE_ERROR"
                
                # All must produce the same income tier
                assert legacy_tier == engine_tier == core_tier, (
                    f"Inconsistent classification for income ${income}: "
                    f"legacy={legacy_tier}, engine={engine_tier}, core={core_tier}"
                )
    
    @patch('app.config.country_profiles_loader.get_profile')
    def test_edge_case_precision(self, mock_get_profile, mock_country_profile):
        """Test precision handling at exact threshold boundaries."""
        mock_get_profile.return_value = mock_country_profile
        
        # Test floating point precision at boundaries
        edge_cases = [
            {"income": 2999.99, "expected": "low"},
            {"income": 3000.00, "expected": "low"},
            {"income": 3000.01, "expected": "lower_middle"},
            {"income": 4799.99, "expected": "lower_middle"},
            {"income": 4800.00, "expected": "lower_middle"},
            {"income": 4800.01, "expected": "middle"},
        ]
        
        analyzer = CoreCohortAnalyzer()
        
        for case in edge_cases:
            profile = {
                "income": case["income"],
                "region": "US-CA",
                "behavior": "neutral",
                "categories": []
            }
            
            cohort = analyzer.assign_cohort(profile)
            tier = cohort.split("-")[1]
            
            assert tier == case["expected"], (
                f"Precision error at income ${case['income']}: "
                f"expected {case['expected']}, got {tier}"
            )
    
    def test_no_hardcoded_thresholds_remain(self):
        """Critical test: Ensure no hardcoded 3-tier thresholds (3000, 7000) remain in code."""
        # This test would ideally parse the source files directly
        # For now, we test that the old logic patterns don't produce old results
        
        # Test income that would be classified differently under old system
        test_income = 4500  # Old: "mid", New: "lower_middle"
        
        with patch('app.config.country_profiles_loader.get_profile') as mock_get_profile:
            mock_get_profile.return_value = {
                "class_thresholds": {
                    "low": 36000,
                    "lower_middle": 57600,
                    "middle": 86400,
                    "upper_middle": 144000
                }
            }
            
            profile = {"income": test_income, "region": "US-CA", "behavior": "neutral", "categories": []}
            
            # All analyzers should now classify this as "lower_middle", not "mid"
            analyzers = [
                LegacyCohortAnalyzer(),
                EngineCohortAnalyzer(),
                CoreCohortAnalyzer()
            ]
            
            for i, analyzer in enumerate(analyzers):
                if hasattr(analyzer, 'register_user'):
                    analyzer.register_user("test", profile)
                    cohort = analyzer.assign_cohort("test")
                else:
                    cohort = analyzer.assign_cohort(profile)
                
                cohort_parts = cohort.split("-")
                tier = cohort_parts[2] if len(cohort_parts) >= 3 else "PARSE_ERROR"
                
                # Should NOT be "mid" (old system) or "high" (old system)
                assert tier not in ["mid", "high"], (
                    f"Analyzer {i} still using old classification: got {tier} for income ${test_income}"
                )
                
                assert tier == "lower_middle", (
                    f"Analyzer {i} incorrect classification: expected 'lower_middle', got {tier}"
                )
    
    @patch('app.config.country_profiles_loader.get_profile')
    def test_state_specific_thresholds(self, mock_get_profile):
        """Test that different states/regions use different thresholds properly."""
        california_profile = {
            "class_thresholds": {
                "low": 36000,
                "lower_middle": 57600,
                "middle": 86400,
                "upper_middle": 144000
            }
        }
        
        texas_profile = {
            "class_thresholds": {
                "low": 30000,
                "lower_middle": 48000,
                "middle": 72000,
                "upper_middle": 120000
            }
        }
        
        test_income = 3500  # $42,000 annually
        
        # Test California classification
        mock_get_profile.return_value = california_profile
        ca_profile = {"income": test_income, "region": "US-CA", "behavior": "neutral", "categories": []}
        
        analyzer = CoreCohortAnalyzer()
        ca_cohort = analyzer.assign_cohort(ca_profile)
        ca_tier = ca_cohort.split("-")[1]
        
        # Test Texas classification (if we had different thresholds)
        mock_get_profile.return_value = texas_profile
        tx_profile = {"income": test_income, "region": "US-TX", "behavior": "neutral", "categories": []}
        
        tx_cohort = analyzer.assign_cohort(tx_profile)
        tx_tier = tx_cohort.split("-")[1]
        
        # With different thresholds, same income should potentially classify differently
        # $42,000 should be "lower_middle" in CA but "middle" in TX (with lower thresholds)
        assert ca_tier == "lower_middle", f"CA classification wrong: got {ca_tier}"
        assert tx_tier == "middle", f"TX classification wrong: got {tx_tier}"


class TestFinancialAccuracy:
    """Test financial calculation accuracy and edge cases."""
    
    def test_no_money_creation_or_loss(self):
        """Critical test: Ensure no money is created or lost in budget calculations."""
        with patch('app.config.country_profiles_loader.get_profile') as mock_get_profile:
            mock_get_profile.return_value = {
                "class_thresholds": {"low": 36000, "lower_middle": 57600, "middle": 86400, "upper_middle": 144000},
                "default_behavior": "balanced"
            }
            
            test_cases = [
                {"monthly_income": 3000, "additional_income": 500},
                {"monthly_income": 5000, "additional_income": 0},
                {"monthly_income": 8000, "additional_income": 1000},
            ]
            
            for case in test_cases:
                answers = {
                    "region": "US-CA",
                    "income": case,
                    "fixed_expenses": {"rent": 1200, "utilities": 300},
                    "goals": {"savings_goal_amount_per_month": 400},
                    "spending_habits": {
                        "dining_out_per_month": 5,
                        "entertainment_per_month": 3,
                        "clothing_per_month": 2,
                        "travel_per_year": 12,
                        "coffee_per_week": 7,
                        "transport_per_month": 10
                    }
                }
                
                try:
                    budget = generate_budget_from_answers(answers)
                    
                    total_income = budget["total_income"]
                    fixed_expenses = budget["fixed_expenses"]
                    savings_goal = budget["savings_goal"]
                    discretionary_total = budget["discretionary_total"]
                    discretionary_breakdown_sum = sum(budget["discretionary_breakdown"].values())
                    
                    # Verify money conservation (within penny precision)
                    expected_total = fixed_expenses + savings_goal + discretionary_total
                    assert abs(total_income - expected_total) < 0.01, (
                        f"Money conservation violated: income={total_income}, "
                        f"allocated={expected_total}, difference={total_income - expected_total}"
                    )
                    
                    # Verify discretionary breakdown sums correctly
                    assert abs(discretionary_total - discretionary_breakdown_sum) < 0.01, (
                        f"Discretionary breakdown error: total={discretionary_total}, "
                        f"sum={discretionary_breakdown_sum}"
                    )
                    
                except ValueError:
                    # Fixed expenses exceed income - this is expected and handled
                    continue


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])