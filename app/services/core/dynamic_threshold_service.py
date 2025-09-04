"""
Dynamic Financial Threshold Service for MITA Finance

This service provides economically-sound, contextual financial thresholds that replace
all hardcoded values throughout the MITA application. It uses economic principles,
regional data, and user context to generate personalized financial parameters.

Economic Foundation:
- Income elasticity of demand theory
- Regional cost-of-living adjustments
- Life-cycle hypothesis application
- Behavioral economics insights
- Current economic indicators integration

Author: Claude Code (AI Financial Economist)
"""

from typing import Dict, Tuple, Optional, List
from enum import Enum
from dataclasses import dataclass
from datetime import datetime
import logging
import math

from app.services.core.income_classification_service import (
    IncomeClassificationService, IncomeTier
)
from app.config.country_profiles_loader import get_profile

logger = logging.getLogger(__name__)


@dataclass
class UserContext:
    """User context for threshold calculations"""
    monthly_income: float
    age: int
    region: str = "US"
    family_size: int = 1
    debt_to_income_ratio: float = 0.0
    months_of_data: int = 1
    current_savings_rate: float = 0.0
    housing_status: str = "rent"  # rent, own, family
    life_stage: str = "single"  # single, couple, family, retirement


@dataclass  
class EconomicContext:
    """Current economic environment context"""
    inflation_rate: float = 0.032  # Current US inflation ~3.2%
    unemployment_rate: float = 0.037  # Current US unemployment ~3.7%
    interest_rate: float = 0.055  # Current fed rate ~5.5%
    recession_risk: float = 0.15  # Low-moderate recession risk
    regional_col_index: float = 1.0  # Cost of living index (1.0 = national average)


class ThresholdType(Enum):
    """Types of financial thresholds"""
    BUDGET_ALLOCATION = "budget_allocation"
    SPENDING_PATTERN = "spending_pattern"
    HEALTH_SCORING = "health_scoring"
    SAVINGS_TARGET = "savings_target"
    GOAL_CONSTRAINT = "goal_constraint"
    BEHAVIORAL_TRIGGER = "behavioral_trigger"
    TIME_BIAS = "time_bias"
    COOLDOWN_PERIOD = "cooldown_period"
    CATEGORY_PRIORITY = "category_priority"


class DynamicThresholdService:
    """
    Centralized service for calculating dynamic, contextual financial thresholds.
    
    Replaces all hardcoded values with economically-justified calculations based on:
    1. User income tier and actual income level
    2. Regional cost-of-living differences  
    3. Current economic conditions
    4. Life stage and family situation
    5. Individual financial capacity
    """
    
    def __init__(self):
        self.income_service = IncomeClassificationService()
        self._load_economic_indicators()
    
    def _load_economic_indicators(self) -> None:
        """Load current economic indicators (in production, from external APIs)"""
        # In production, these would come from Fed APIs, BLS data, etc.
        self.economic_context = EconomicContext()
        
    def get_budget_allocation_thresholds(
        self, 
        user_context: UserContext
    ) -> Dict[str, float]:
        """
        Calculate dynamic budget allocation percentages based on user context.
        
        Economic Principle: Income elasticity - spending patterns change with income levels.
        Higher income allows lower % for necessities, higher % for discretionary.
        
        Args:
            user_context: User's financial and demographic context
            
        Returns:
            Dict with category allocation percentages (0.0-1.0)
        """
        tier = self.income_service.classify_income(
            user_context.monthly_income, user_context.region
        )
        
        # Get base allocations from income classification service
        base_allocations = self.income_service.get_budget_weights(tier, user_context.region)
        
        # Apply contextual adjustments
        adjusted_allocations = self._adjust_for_context(
            base_allocations, user_context, tier
        )
        
        # Apply economic environment adjustments
        final_allocations = self._adjust_for_economic_environment(
            adjusted_allocations, user_context
        )
        
        logger.info(f"Generated budget allocations for {tier.value} tier: {final_allocations}")
        return final_allocations
    
    def get_spending_pattern_thresholds(
        self, 
        user_context: UserContext
    ) -> Dict[str, float]:
        """
        Calculate spending pattern detection thresholds based on income and context.
        
        Economic Principle: Absolute dollar thresholds should scale with income.
        What's a "small purchase" varies dramatically by income level.
        
        Returns:
            Dict with thresholds for pattern detection
        """
        tier = self.income_service.classify_income(
            user_context.monthly_income, user_context.region
        )
        
        # Base small purchase threshold: 0.5% of monthly income, min $5, max $100
        small_purchase_base = user_context.monthly_income * 0.005
        small_purchase_threshold = max(5.0, min(100.0, small_purchase_base))
        
        # Medium purchase: 2% of monthly income
        medium_purchase_threshold = user_context.monthly_income * 0.02
        
        # Large purchase: 10% of monthly income
        large_purchase_threshold = user_context.monthly_income * 0.10
        
        # Category concentration thresholds adjust with income sophistication
        concentration_thresholds = self._get_concentration_thresholds(tier)
        
        # Variance thresholds based on income stability expectations
        variance_thresholds = self._get_variance_thresholds(tier, user_context)
        
        return {
            "small_purchase_threshold": small_purchase_threshold,
            "medium_purchase_threshold": medium_purchase_threshold, 
            "large_purchase_threshold": large_purchase_threshold,
            "impulse_buying_threshold": self._get_impulse_threshold(tier),
            **concentration_thresholds,
            **variance_thresholds
        }
    
    def get_financial_health_thresholds(
        self,
        user_context: UserContext
    ) -> Dict[str, Dict[str, float]]:
        """
        Calculate financial health scoring thresholds appropriate for user context.
        
        Economic Principle: Financial health benchmarks should be relative to 
        income tier capabilities and regional economic conditions.
        """
        tier = self.income_service.classify_income(
            user_context.monthly_income, user_context.region
        )
        
        # Get behavioral patterns for this tier
        behavioral_pattern = self.income_service.get_behavioral_pattern(tier)
        
        # Grade boundaries adjust based on tier expectations
        grade_boundaries = self._get_tier_appropriate_grades(tier)
        
        # Component score expectations
        component_expectations = {
            "budgeting_excellence": self._get_budgeting_threshold(tier, behavioral_pattern),
            "spending_efficiency": self._get_efficiency_threshold(tier, behavioral_pattern),
            "savings_achievement": self._get_savings_threshold(tier, behavioral_pattern),
            "consistency_target": self._get_consistency_threshold(tier, behavioral_pattern)
        }
        
        return {
            "grade_boundaries": grade_boundaries,
            "component_expectations": component_expectations,
            "improvement_benchmarks": self._get_improvement_benchmarks(tier)
        }
    
    def get_savings_rate_targets(
        self,
        user_context: UserContext
    ) -> Dict[str, float]:
        """
        Calculate contextual savings rate targets.
        
        Economic Principle: Optimal savings rates depend on:
        1. Life cycle stage (young = growth, older = preservation)
        2. Regional cost pressures
        3. Current economic environment (inflation, rates)
        4. Individual debt obligations
        """
        tier = self.income_service.classify_income(
            user_context.monthly_income, user_context.region
        )
        
        behavioral_pattern = self.income_service.get_behavioral_pattern(tier)
        base_savings_rate = behavioral_pattern["savings_rate_target"]
        
        # Adjust for life stage using life-cycle hypothesis
        life_stage_multiplier = self._get_life_stage_savings_multiplier(
            user_context.age, user_context.life_stage
        )
        
        # Adjust for debt burden
        debt_adjustment = self._get_debt_adjustment_factor(
            user_context.debt_to_income_ratio
        )
        
        # Adjust for economic environment
        economic_adjustment = self._get_economic_environment_adjustment()
        
        # Calculate final targets
        target_rate = (base_savings_rate * life_stage_multiplier * 
                      debt_adjustment * economic_adjustment)
        
        # Minimum and maximum bounds
        minimum_rate = max(0.02, target_rate * 0.5)  # Never below 2%
        maximum_rate = min(0.5, target_rate * 1.5)   # Never above 50%
        
        return {
            "target_savings_rate": min(maximum_rate, max(minimum_rate, target_rate)),
            "minimum_savings_rate": minimum_rate,
            "stretch_savings_rate": maximum_rate,
            "emergency_fund_months": self._get_emergency_fund_target(tier, user_context)
        }
    
    def get_goal_setting_constraints(
        self,
        user_context: UserContext
    ) -> Dict[str, any]:
        """
        Calculate goal setting constraints based on financial capacity.
        
        Economic Principle: Goal constraints should reflect actual financial
        capacity, not arbitrary limits.
        """
        tier = self.income_service.classify_income(
            user_context.monthly_income, user_context.region
        )
        
        savings_targets = self.get_savings_rate_targets(user_context)
        available_monthly = (user_context.monthly_income * 
                           savings_targets["target_savings_rate"])
        
        return {
            "maximum_goal_timeline_years": self._get_max_timeline(tier),
            "minimum_monthly_contribution": available_monthly * 0.1,
            "maximum_monthly_contribution": available_monthly,
            "goal_priority_matrix": self._get_goal_priorities(tier, user_context),
            "achievability_factors": self._get_achievability_factors(tier, user_context)
        }
    
    def get_behavioral_trigger_thresholds(
        self,
        user_context: UserContext
    ) -> Dict[str, float]:
        """
        Calculate behavioral trigger thresholds for spending alerts and nudges.
        
        Economic Principle: Trigger points should be income-relative and
        culturally appropriate for the user's context.
        """
        tier = self.income_service.classify_income(
            user_context.monthly_income, user_context.region
        )
        
        budget_allocations = self.get_budget_allocation_thresholds(user_context)
        
        # Calculate category-specific overspending thresholds
        overspending_thresholds = {}
        for category, allocation in budget_allocations.items():
            if category in ["entertainment", "dining", "shopping"]:
                # More sensitive triggers for discretionary spending
                threshold_multiplier = 1.15  # 15% over budget triggers alert
            else:
                # Less sensitive for necessities
                threshold_multiplier = 1.25  # 25% over budget triggers alert
                
            overspending_thresholds[f"{category}_overspending"] = threshold_multiplier
        
        return {
            **overspending_thresholds,
            "total_budget_variance_threshold": 1.1 + (0.05 * tier.value.count('_')),
            "impulse_purchase_threshold": user_context.monthly_income * 0.02,
            "subscription_accumulation_limit": 5 + tier.value.count('_'),  # More for higher tiers
            "weekend_overspending_multiplier": 1.3  # Weekend can be 30% higher than weekday
        }
    
    def get_housing_affordability_threshold(
        self,
        user_context: UserContext
    ) -> Dict[str, float]:
        """
        Calculate housing affordability thresholds with regional adjustments.
        
        Economic Principle: Housing costs vary dramatically by region and should
        reflect local market conditions, not national averages.
        """
        tier = self.income_service.classify_income(
            user_context.monthly_income, user_context.region
        )
        
        # Get base housing ratio from tier
        behavioral_pattern = self.income_service.get_behavioral_pattern(tier)
        base_housing_ratio = behavioral_pattern["housing_ratio_target"]
        
        # Get regional adjustment from country profile
        profile = get_profile(user_context.region)
        regional_housing_multiplier = profile.get("housing_cost_multiplier", 1.0)
        
        # Adjust for current market conditions
        market_adjustment = self._get_housing_market_adjustment(user_context.region)
        
        # Final housing ratio with bounds
        adjusted_ratio = base_housing_ratio * regional_housing_multiplier * market_adjustment
        final_ratio = max(0.20, min(0.50, adjusted_ratio))  # Between 20-50%
        
        return {
            "recommended_housing_ratio": final_ratio,
            "maximum_housing_ratio": min(0.50, final_ratio * 1.25),
            "comfortable_housing_ratio": final_ratio * 0.85,
            "regional_adjustment_factor": regional_housing_multiplier
        }
    
    def get_time_bias_thresholds(
        self,
        user_context: UserContext
    ) -> Dict[str, List[float]]:
        """
        Calculate dynamic time bias for spending categories based on economic behavioral patterns.
        
        Economic Principle: Spending patterns vary by day of week based on:
        1. Work schedules and income timing
        2. Social/cultural patterns 
        3. Behavioral economics (weekend effect, payday effect)
        4. Regional cultural differences
        """
        tier = self.income_service.classify_income(
            user_context.monthly_income, user_context.region
        )
        
        # Base patterns adjusted for income tier and cultural context
        base_patterns = self._get_base_time_patterns()
        
        # Adjust patterns based on income tier behavioral capacity
        adjusted_patterns = {}
        for category, pattern in base_patterns.items():
            adjusted_patterns[category] = self._adjust_time_pattern_for_tier(
                pattern, tier, category, user_context
            )
        
        return adjusted_patterns
    
    def get_cooldown_thresholds(
        self,
        user_context: UserContext
    ) -> Dict[str, int]:
        """
        Calculate dynamic cooldown periods for spending categories.
        
        Economic Principle: Optimal purchase frequency varies by:
        1. Income level (higher income = shorter cooldowns for discretionary)
        2. Category necessity level
        3. Behavioral control capacity
        4. Economic environment
        """
        tier = self.income_service.classify_income(
            user_context.monthly_income, user_context.region
        )
        
        # Base cooldown periods in days
        base_cooldowns = {
            "entertainment": 3,      # Base entertainment cooldown
            "dining_out": 2,         # Base dining cooldown
            "clothing": 7,           # Base clothing cooldown  
            "shopping": 5,           # Base shopping cooldown
            "groceries": 1,          # Basic necessity, short cooldown
            "transport": 0,          # No cooldown for necessary transport
            "healthcare": 0,         # No cooldown for healthcare
            "utilities": 0           # No cooldown for utilities
        }
        
        # Adjust based on income tier capacity
        tier_multipliers = {
            IncomeTier.LOW: 1.5,           # Longer cooldowns - need more discipline
            IncomeTier.LOWER_MIDDLE: 1.2,  
            IncomeTier.MIDDLE: 1.0,        # Base cooldowns
            IncomeTier.UPPER_MIDDLE: 0.8,  # Shorter cooldowns - more flexibility
            IncomeTier.HIGH: 0.6           # Shortest cooldowns - high discretionary income
        }
        
        multiplier = tier_multipliers[tier]
        
        adjusted_cooldowns = {}
        for category, base_days in base_cooldowns.items():
            adjusted_days = int(base_days * multiplier)
            
            # Apply economic environment adjustments
            if self.economic_context.recession_risk > 0.3:
                # Increase cooldowns during high recession risk
                if category in ["entertainment", "dining_out", "clothing", "shopping"]:
                    adjusted_days = int(adjusted_days * 1.3)
            
            adjusted_cooldowns[category] = max(0, adjusted_days)
        
        return adjusted_cooldowns
    
    def get_category_priority_thresholds(
        self,
        user_context: UserContext
    ) -> Dict[str, int]:
        """
        Calculate dynamic category priorities based on economic hierarchy of needs.
        
        Economic Principle: Category priorities shift based on:
        1. Maslow's hierarchy applied to financial needs
        2. Income tier capacity
        3. Regional economic pressures
        4. Life stage requirements
        """
        tier = self.income_service.classify_income(
            user_context.monthly_income, user_context.region
        )
        
        # Base hierarchy - lower numbers = higher priority
        base_priorities = {
            "housing": 1,        # Always highest priority
            "utilities": 2,      # Basic infrastructure
            "healthcare": 3,     # Health maintenance
            "groceries": 4,      # Food security
            "transport": 5,      # Economic mobility
            "debt_payment": 6,   # Financial obligations
            "insurance": 7,      # Risk management
            "savings": 8,        # Future security
            "education": 9,      # Human capital
            "dining_out": 10,    # Convenience
            "entertainment": 11, # Recreation
            "shopping": 12,      # Discretionary goods
            "travel": 13,        # Luxury experiences
            "other": 14          # Miscellaneous
        }
        
        # Adjust priorities based on income tier capacity
        adjusted_priorities = base_priorities.copy()
        
        # Higher income tiers can prioritize investment and long-term goals
        if tier in [IncomeTier.UPPER_MIDDLE, IncomeTier.HIGH]:
            adjusted_priorities["investments"] = 7  # Higher priority for wealth building
            adjusted_priorities["savings"] = 6     # Earlier in priority chain
            adjusted_priorities["education"] = 5   # Invest in human capital
        
        # Lower income tiers focus on basic security
        if tier in [IncomeTier.LOW, IncomeTier.LOWER_MIDDLE]:
            adjusted_priorities["savings"] = 12    # Lower priority when struggling with basics
            adjusted_priorities["entertainment"] = 15  # Very low priority
            adjusted_priorities["shopping"] = 16   # Lowest priority
        
        # Adjust for family context
        if user_context.family_size > 1:
            adjusted_priorities["healthcare"] = 2  # Higher priority for families
            adjusted_priorities["education"] = 6   # Important for children
            adjusted_priorities["insurance"] = 5   # Critical for family protection
        
        # Adjust for age/life stage
        if user_context.age > 50:
            adjusted_priorities["healthcare"] = 2   # Higher priority as we age
            adjusted_priorities["retirement"] = 7   # New high priority category
        
        return adjusted_priorities
    
    def get_dynamic_budget_method_recommendation(
        self,
        user_context: UserContext
    ) -> Dict[str, any]:
        """
        Calculate personalized budget method recommendation instead of hardcoded 50/30/20.
        
        Economic Principle: Optimal budgeting method depends on:
        1. Income predictability and level
        2. Financial sophistication capacity
        3. Time availability for financial management
        4. Regional economic complexity
        """
        tier = self.income_service.classify_income(
            user_context.monthly_income, user_context.region
        )
        
        # Get dynamic allocations instead of fixed 50/30/20
        allocations = self.get_budget_allocation_thresholds(user_context)
        
        # Calculate personalized percentages
        needs_pct = sum(allocations.get(cat, 0) for cat in ['housing', 'utilities', 'groceries', 'transport', 'healthcare']) * 100
        wants_pct = sum(allocations.get(cat, 0) for cat in ['entertainment', 'dining', 'shopping', 'miscellaneous']) * 100
        savings_pct = allocations.get('savings', 0.1) * 100
        
        # Recommend appropriate budgeting method based on tier and context
        if tier in [IncomeTier.LOW, IncomeTier.LOWER_MIDDLE]:
            method = "needs_first"
            description = f"Focus on essentials ({needs_pct:.0f}%) then limited discretionary ({wants_pct:.0f}%) and achievable savings ({savings_pct:.0f}%)"
        elif tier == IncomeTier.MIDDLE:
            method = "balanced_percentage"
            description = f"Balanced approach: {needs_pct:.0f}% needs, {wants_pct:.0f}% wants, {savings_pct:.0f}% savings"
        else:  # UPPER_MIDDLE, HIGH
            investment_pct = allocations.get('investments', 0.05) * 100
            method = "wealth_building"
            description = f"Optimized for wealth: {needs_pct:.0f}% needs, {wants_pct:.0f}% wants, {savings_pct:.0f}% savings, {investment_pct:.0f}% investments"
        
        return {
            "method": method,
            "description": description,
            "needs_percentage": needs_pct,
            "wants_percentage": wants_pct, 
            "savings_percentage": savings_pct,
            "investments_percentage": allocations.get('investments', 0.0) * 100,
            "allocations": allocations
        }
    
    # Helper methods for calculations
    
    def _adjust_for_context(
        self, 
        base_allocations: Dict[str, float],
        user_context: UserContext,
        tier: IncomeTier
    ) -> Dict[str, float]:
        """Adjust allocations for user-specific context"""
        adjusted = base_allocations.copy()
        
        # Family size adjustments
        if user_context.family_size > 1:
            # Families need more for food, healthcare, less for discretionary
            adjusted["food"] = adjusted.get("food", 0.12) * (1 + user_context.family_size * 0.1)
            adjusted["healthcare"] = adjusted.get("healthcare", 0.06) * (1 + user_context.family_size * 0.08)
            adjusted["entertainment"] = adjusted.get("entertainment", 0.08) * 0.8
        
        # Age-based adjustments
        if user_context.age > 50:
            # Older individuals typically spend more on healthcare, less on entertainment
            adjusted["healthcare"] = adjusted.get("healthcare", 0.06) * 1.3
            adjusted["entertainment"] = adjusted.get("entertainment", 0.08) * 0.9
        
        # Debt adjustment
        if user_context.debt_to_income_ratio > 0.2:
            # High debt requires allocation adjustment
            debt_factor = min(0.4, user_context.debt_to_income_ratio)
            adjusted["debt_payment"] = debt_factor
            # Reduce discretionary to accommodate debt payments
            for category in ["entertainment", "shopping", "miscellaneous"]:
                if category in adjusted:
                    adjusted[category] *= 0.7
        
        # Normalize to sum to 1.0
        total = sum(adjusted.values())
        if total > 0:
            adjusted = {k: v/total for k, v in adjusted.items()}
        
        return adjusted
    
    def _adjust_for_economic_environment(
        self,
        allocations: Dict[str, float],
        user_context: UserContext
    ) -> Dict[str, float]:
        """Adjust allocations for current economic conditions"""
        adjusted = allocations.copy()
        
        # High inflation: increase necessities allocation
        if self.economic_context.inflation_rate > 0.04:
            inflation_adjustment = 1 + (self.economic_context.inflation_rate - 0.04) * 2
            adjusted["food"] = adjusted.get("food", 0.12) * inflation_adjustment
            adjusted["utilities"] = adjusted.get("utilities", 0.06) * inflation_adjustment
        
        # High interest rates: increase savings allocation
        if self.economic_context.interest_rate > 0.05:
            rate_bonus = (self.economic_context.interest_rate - 0.05) * 10
            adjusted["savings"] = adjusted.get("savings", 0.1) * (1 + rate_bonus)
        
        # Recession risk: increase emergency fund priority
        if self.economic_context.recession_risk > 0.2:
            emergency_boost = self.economic_context.recession_risk * 0.5
            adjusted["savings"] = adjusted.get("savings", 0.1) * (1 + emergency_boost)
        
        # Normalize
        total = sum(adjusted.values())
        if total > 0:
            adjusted = {k: v/total for k, v in adjusted.items()}
        
        return adjusted
    
    def _get_concentration_thresholds(self, tier: IncomeTier) -> Dict[str, float]:
        """Get category concentration thresholds based on income tier sophistication"""
        # Higher income tiers should have more diversified spending
        base_concentration = {
            IncomeTier.LOW: 0.7,           # Can concentrate spending more
            IncomeTier.LOWER_MIDDLE: 0.6,  # Moderate concentration okay
            IncomeTier.MIDDLE: 0.5,        # Should diversify more
            IncomeTier.UPPER_MIDDLE: 0.4,  # High diversification expected
            IncomeTier.HIGH: 0.35          # Very diversified spending
        }
        
        return {
            "category_concentration_threshold": base_concentration[tier],
            "category_concentration_warning": base_concentration[tier] + 0.1,
            "category_concentration_critical": base_concentration[tier] + 0.2
        }
    
    def _get_variance_thresholds(
        self, 
        tier: IncomeTier, 
        user_context: UserContext
    ) -> Dict[str, float]:
        """Get spending variance thresholds based on income stability expectations"""
        # Higher income tiers should have more consistent spending
        base_variance = {
            IncomeTier.LOW: 0.4,           # High variance acceptable
            IncomeTier.LOWER_MIDDLE: 0.35, # Moderate variance
            IncomeTier.MIDDLE: 0.3,        # Lower variance expected
            IncomeTier.UPPER_MIDDLE: 0.25, # Consistent spending
            IncomeTier.HIGH: 0.2           # Very consistent spending
        }
        
        # Adjust for life stage - younger people have more variable spending
        age_adjustment = 1.0
        if user_context.age < 30:
            age_adjustment = 1.2
        elif user_context.age > 50:
            age_adjustment = 0.9
        
        threshold = base_variance[tier] * age_adjustment
        
        return {
            "monthly_variance_threshold": threshold,
            "monthly_variance_warning": threshold * 0.8,
            "monthly_variance_excellent": threshold * 0.5
        }
    
    def _get_impulse_threshold(self, tier: IncomeTier) -> float:
        """Get impulse buying threshold based on income tier"""
        # Higher income can handle more impulse buying
        thresholds = {
            IncomeTier.LOW: 0.5,           # Very sensitive to impulse buying
            IncomeTier.LOWER_MIDDLE: 0.55,
            IncomeTier.MIDDLE: 0.6,
            IncomeTier.UPPER_MIDDLE: 0.65,
            IncomeTier.HIGH: 0.7           # Can afford some impulse purchases
        }
        return thresholds[tier]
    
    def _get_tier_appropriate_grades(self, tier: IncomeTier) -> Dict[str, float]:
        """Get grade boundaries appropriate for income tier capabilities"""
        # Lower tiers get more lenient grading due to constraint challenges
        adjustments = {
            IncomeTier.LOW: 0.85,          # 15% easier grading
            IncomeTier.LOWER_MIDDLE: 0.92,
            IncomeTier.MIDDLE: 1.0,        # Standard grading
            IncomeTier.UPPER_MIDDLE: 1.05,
            IncomeTier.HIGH: 1.1           # 10% harder grading
        }
        
        adjustment = adjustments[tier]
        
        return {
            "A_plus": 90 * adjustment,
            "A": 85 * adjustment,
            "B_plus": 80 * adjustment,
            "B": 75 * adjustment,
            "C_plus": 70 * adjustment,
            "C": 65 * adjustment,
            "D_plus": 60 * adjustment,
            "D": 55 * adjustment
        }
    
    def _get_budgeting_threshold(self, tier: IncomeTier, behavioral_pattern: Dict) -> float:
        """Get budgeting excellence threshold for tier"""
        base_score = 70  # Base expectation
        
        # Higher tiers expected to have better budgeting
        tier_bonuses = {
            IncomeTier.LOW: -5,
            IncomeTier.LOWER_MIDDLE: -2,
            IncomeTier.MIDDLE: 0,
            IncomeTier.UPPER_MIDDLE: 3,
            IncomeTier.HIGH: 5
        }
        
        return base_score + tier_bonuses[tier]
    
    def _get_efficiency_threshold(self, tier: IncomeTier, behavioral_pattern: Dict) -> float:
        """Get spending efficiency threshold for tier"""
        base_score = 65
        
        # Efficiency expectations increase with income
        tier_bonuses = {
            IncomeTier.LOW: -8,     # Lower expectations due to constraints
            IncomeTier.LOWER_MIDDLE: -4,
            IncomeTier.MIDDLE: 0,
            IncomeTier.UPPER_MIDDLE: 5,
            IncomeTier.HIGH: 10     # High expectations for efficiency
        }
        
        return base_score + tier_bonuses[tier]
    
    def _get_savings_threshold(self, tier: IncomeTier, behavioral_pattern: Dict) -> float:
        """Get savings achievement threshold for tier"""
        target_rate = behavioral_pattern["savings_rate_target"]
        
        # Achievement threshold is 80% of target rate
        return target_rate * 0.8 * 100  # Convert to percentage score
    
    def _get_consistency_threshold(self, tier: IncomeTier, behavioral_pattern: Dict) -> float:
        """Get spending consistency threshold for tier"""
        base_score = 75
        
        # Higher tiers expected to be more consistent
        tier_adjustments = {
            IncomeTier.LOW: -10,    # More volatile due to constraints
            IncomeTier.LOWER_MIDDLE: -5,
            IncomeTier.MIDDLE: 0,
            IncomeTier.UPPER_MIDDLE: 5,
            IncomeTier.HIGH: 10     # Very consistent expected
        }
        
        return base_score + tier_adjustments[tier]
    
    def _get_improvement_benchmarks(self, tier: IncomeTier) -> Dict[str, float]:
        """Get improvement benchmarks for tier"""
        return {
            "month_over_month_target": 2.0,  # 2% improvement
            "quarterly_improvement_target": 5.0,  # 5% improvement
            "annual_improvement_target": 15.0,   # 15% improvement
            "consistency_improvement_target": 3.0  # 3% more consistent
        }
    
    def _get_life_stage_savings_multiplier(self, age: int, life_stage: str) -> float:
        """Calculate life stage multiplier for savings rate"""
        # Life-cycle hypothesis: save more in middle years
        if age < 25:
            return 0.8  # Lower savings when starting career
        elif age < 35:
            return 1.0  # Standard savings rate
        elif age < 50:
            return 1.2  # Peak earning/saving years
        elif age < 65:
            return 1.1  # Pre-retirement boost
        else:
            return 0.6  # Retirement - lower savings need
    
    def _get_debt_adjustment_factor(self, debt_to_income: float) -> float:
        """Calculate adjustment factor for debt burden"""
        if debt_to_income <= 0.1:
            return 1.0  # No adjustment for low debt
        elif debt_to_income <= 0.2:
            return 0.9  # Slight reduction
        elif debt_to_income <= 0.4:
            return 0.7  # Significant reduction
        else:
            return 0.5  # Major reduction for high debt
    
    def _get_economic_environment_adjustment(self) -> float:
        """Calculate adjustment for current economic environment"""
        adjustment = 1.0
        
        # High inflation reduces savings capacity
        if self.economic_context.inflation_rate > 0.04:
            adjustment *= (1 - (self.economic_context.inflation_rate - 0.04) * 2)
        
        # High interest rates encourage savings
        if self.economic_context.interest_rate > 0.05:
            adjustment *= (1 + (self.economic_context.interest_rate - 0.05) * 3)
        
        return max(0.5, min(1.5, adjustment))
    
    def _get_emergency_fund_target(
        self, 
        tier: IncomeTier, 
        user_context: UserContext
    ) -> float:
        """Calculate emergency fund target in months"""
        base_months = {
            IncomeTier.LOW: 2,             # Harder to save, but need emergency fund
            IncomeTier.LOWER_MIDDLE: 3,
            IncomeTier.MIDDLE: 4,
            IncomeTier.UPPER_MIDDLE: 5,
            IncomeTier.HIGH: 6
        }
        
        months = base_months[tier]
        
        # Adjust for job security (family size as proxy)
        if user_context.family_size > 1:
            months += 1  # Families need more
        
        # Adjust for economic uncertainty
        if self.economic_context.recession_risk > 0.2:
            months += 1
            
        return months
    
    def _get_max_timeline(self, tier: IncomeTier) -> float:
        """Get maximum goal timeline based on income tier planning horizon"""
        horizons = {
            IncomeTier.LOW: 3,             # Shorter planning horizon
            IncomeTier.LOWER_MIDDLE: 4,
            IncomeTier.MIDDLE: 5,
            IncomeTier.UPPER_MIDDLE: 7,
            IncomeTier.HIGH: 10            # Longer planning horizon
        }
        return horizons[tier]
    
    def _get_goal_priorities(
        self, 
        tier: IncomeTier, 
        user_context: UserContext
    ) -> List[str]:
        """Get goal priorities for tier and context"""
        base_priorities = {
            IncomeTier.LOW: ["emergency", "debt", "essentials"],
            IncomeTier.LOWER_MIDDLE: ["emergency", "debt", "savings", "education"],
            IncomeTier.MIDDLE: ["emergency", "investment", "savings", "property", "education"],
            IncomeTier.UPPER_MIDDLE: ["investment", "property", "tax", "education", "business"],
            IncomeTier.HIGH: ["investment", "tax", "estate", "business", "charity"]
        }
        
        priorities = base_priorities[tier].copy()
        
        # Adjust for age
        if user_context.age > 50:
            priorities = ["retirement", "healthcare"] + priorities
        
        # Adjust for family
        if user_context.family_size > 1:
            if "education" not in priorities:
                priorities.append("education")
            if "family_protection" not in priorities:
                priorities.append("family_protection")
        
        return priorities
    
    def _get_achievability_factors(
        self,
        tier: IncomeTier,
        user_context: UserContext
    ) -> Dict[str, float]:
        """Get goal achievability factors"""
        return {
            "income_stability_factor": 0.9 if user_context.debt_to_income_ratio > 0.3 else 1.0,
            "time_horizon_factor": 1.2 if user_context.age < 30 else 1.0,
            "economic_environment_factor": 0.8 if self.economic_context.recession_risk > 0.3 else 1.0,
            "regional_cost_factor": self.economic_context.regional_col_index
        }
    
    def _get_housing_market_adjustment(self, region: str) -> float:
        """Get housing market adjustment for region"""
        # In production, this would use real-time housing market data
        regional_adjustments = {
            "US-CA": 1.4,    # California - expensive market
            "US-NY": 1.3,    # New York - expensive market  
            "US-TX": 0.9,    # Texas - moderate market
            "US-FL": 1.0,    # Florida - average market
            "US": 1.0        # Default US average
        }
        
        return regional_adjustments.get(region, 1.0)
    
    def _get_base_time_patterns(self) -> Dict[str, List[float]]:
        """Get base time patterns for spending categories (Mon-Sun)"""
        return {
            "entertainment": [0.1, 0.1, 0.1, 0.2, 0.6, 0.9, 1.0],  # Weekend heavy
            "dining_out": [0.1, 0.1, 0.2, 0.4, 0.8, 1.0, 0.9],     # Friday-Saturday peak
            "clothing": [0.1, 0.1, 0.1, 0.2, 0.6, 0.9, 0.9],       # Weekend shopping
            "groceries": [0.8, 0.8, 0.8, 0.7, 0.6, 0.3, 0.3],      # Weekday preference
            "transport": [0.7, 0.7, 0.7, 0.7, 0.7, 0.2, 0.2],      # Weekday commuting
            "shopping": [0.2, 0.2, 0.2, 0.3, 0.6, 0.9, 0.8],       # Weekend preference
            "healthcare": [0.8, 0.9, 0.8, 0.7, 0.6, 0.4, 0.1],     # Weekday medical hours
            "utilities": [1.0] * 7,                                  # No time bias
            "housing": [1.0] * 7                                     # No time bias
        }
    
    def _adjust_time_pattern_for_tier(
        self,
        base_pattern: List[float],
        tier: IncomeTier,
        category: str,
        user_context: UserContext
    ) -> List[float]:
        """Adjust time patterns based on income tier behavioral patterns"""
        adjusted = base_pattern.copy()
        
        # Higher income tiers have more flexible schedules
        if tier in [IncomeTier.UPPER_MIDDLE, IncomeTier.HIGH]:
            # Smooth out patterns - more flexibility throughout week
            for i in range(len(adjusted)):
                if category in ["entertainment", "dining_out", "shopping"]:
                    # Higher earners can afford weekday entertainment
                    adjusted[i] = min(1.0, adjusted[i] + 0.1)
        
        # Lower income tiers have more constrained patterns
        elif tier in [IncomeTier.LOW, IncomeTier.LOWER_MIDDLE]:
            # More concentrated spending on fewer days
            for i in range(len(adjusted)):
                if category in ["entertainment", "dining_out", "shopping"]:
                    # More budget-conscious timing
                    if adjusted[i] < 0.5:
                        adjusted[i] *= 0.8  # Reduce low days further
                    else:
                        adjusted[i] = min(1.0, adjusted[i] * 1.2)  # Concentrate on high days
        
        # Adjust for family context
        if user_context.family_size > 1:
            # Family spending more spread out, less weekend concentration
            for i in range(len(adjusted)):
                if i < 5:  # Weekdays
                    adjusted[i] = min(1.0, adjusted[i] * 1.1)
                else:  # Weekends
                    adjusted[i] *= 0.9
        
        # Normalize pattern to maintain relative relationships
        max_val = max(adjusted)
        if max_val > 0:
            adjusted = [val / max_val for val in adjusted]
        
        return adjusted


# Singleton instance for application use
_dynamic_threshold_service = DynamicThresholdService()


# Public API functions
def get_dynamic_thresholds(
    threshold_type: ThresholdType,
    user_context: UserContext
) -> Dict[str, any]:
    """
    Main entry point for getting dynamic financial thresholds.
    
    Args:
        threshold_type: Type of threshold needed
        user_context: User's financial and demographic context
        
    Returns:
        Dict with appropriate thresholds for the user
    """
    service = _dynamic_threshold_service
    
    if threshold_type == ThresholdType.BUDGET_ALLOCATION:
        return service.get_budget_allocation_thresholds(user_context)
    elif threshold_type == ThresholdType.SPENDING_PATTERN:
        return service.get_spending_pattern_thresholds(user_context)
    elif threshold_type == ThresholdType.HEALTH_SCORING:
        return service.get_financial_health_thresholds(user_context)
    elif threshold_type == ThresholdType.SAVINGS_TARGET:
        return service.get_savings_rate_targets(user_context)
    elif threshold_type == ThresholdType.GOAL_CONSTRAINT:
        return service.get_goal_setting_constraints(user_context)
    elif threshold_type == ThresholdType.BEHAVIORAL_TRIGGER:
        return service.get_behavioral_trigger_thresholds(user_context)
    elif threshold_type == ThresholdType.TIME_BIAS:
        return service.get_time_bias_thresholds(user_context)
    elif threshold_type == ThresholdType.COOLDOWN_PERIOD:
        return service.get_cooldown_thresholds(user_context)
    elif threshold_type == ThresholdType.CATEGORY_PRIORITY:
        return service.get_category_priority_thresholds(user_context)
    else:
        raise ValueError(f"Unknown threshold type: {threshold_type}")


def get_housing_affordability_thresholds(user_context: UserContext) -> Dict[str, float]:
    """Get housing affordability thresholds for user context"""
    return _dynamic_threshold_service.get_housing_affordability_threshold(user_context)


def get_dynamic_budget_method(user_context: UserContext) -> Dict[str, any]:
    """Get personalized budget method recommendation instead of hardcoded 50/30/20"""
    return _dynamic_threshold_service.get_dynamic_budget_method_recommendation(user_context)


def validate_threshold_consistency(
    thresholds: Dict[str, any],
    user_context: UserContext
) -> bool:
    """
    Validate that calculated thresholds are internally consistent.
    
    Args:
        thresholds: Calculated thresholds
        user_context: User context
        
    Returns:
        bool: True if thresholds are consistent
    """
    try:
        # Basic validation - ensure all percentages sum appropriately
        if "budget_allocation" in str(thresholds):
            total = sum(v for v in thresholds.values() if isinstance(v, (int, float)))
            if total > 1.2 or total < 0.8:  # Allow some flexibility
                return False
                
        # Ensure savings targets are achievable
        if "savings_rate" in str(thresholds):
            savings_rate = thresholds.get("target_savings_rate", 0)
            if savings_rate > 0.5 or savings_rate < 0:
                return False
        
        return True
        
    except Exception as e:
        logger.error(f"Threshold validation failed: {e}")
        return False