"""
Income-Based Scaling Algorithms for MITA Finance

This module provides sophisticated algorithms for scaling financial thresholds
based on income levels, economic theory, and behavioral economics principles.

Economic Foundation:
- Engel's Law: As income increases, percentage spent on necessities decreases
- Income elasticity of demand theory
- Marginal utility theory
- Behavioral economics insights on spending patterns

Author: Claude Code (AI Financial Economist)
"""

from typing import Dict
from dataclasses import dataclass
import math
import logging

from app.services.core.income_classification_service import IncomeTier, classify_income

logger = logging.getLogger(__name__)


@dataclass
class ScalingParameters:
    """Parameters for income-based scaling calculations"""
    base_income: float          # Reference income level
    elasticity_coefficient: float  # Income elasticity (-1 to 2)
    minimum_threshold: float    # Absolute minimum value
    maximum_threshold: float    # Absolute maximum value
    diminishing_returns_point: float  # Income level where returns diminish


class IncomeScalingAlgorithms:
    """
    Advanced algorithms for scaling financial thresholds based on income.
    
    Uses established economic principles to ensure thresholds are:
    1. Income-appropriate
    2. Economically sound
    3. Behaviorally aligned
    4. Regionally adjusted
    """
    
    def __init__(self):
        self._load_scaling_parameters()
    
    def _load_scaling_parameters(self) -> None:
        """Load scaling parameters for different threshold types"""
        self.scaling_params = {
            "housing_ratio": ScalingParameters(
                base_income=70000,      # US median income baseline
                elasticity_coefficient=-0.3,  # Housing % decreases with income
                minimum_threshold=0.20,
                maximum_threshold=0.50,
                diminishing_returns_point=150000
            ),
            "food_ratio": ScalingParameters(
                base_income=70000,
                elasticity_coefficient=-0.5,  # Food % decreases significantly (Engel's Law)
                minimum_threshold=0.08,
                maximum_threshold=0.20,
                diminishing_returns_point=120000
            ),
            "savings_rate": ScalingParameters(
                base_income=70000,
                elasticity_coefficient=0.4,   # Savings % increases with income
                minimum_threshold=0.02,
                maximum_threshold=0.50,
                diminishing_returns_point=200000
            ),
            "small_purchase": ScalingParameters(
                base_income=70000,
                elasticity_coefficient=0.6,   # Small purchases scale with income
                minimum_threshold=5.0,
                maximum_threshold=100.0,
                diminishing_returns_point=150000
            ),
            "emergency_fund": ScalingParameters(
                base_income=70000,
                elasticity_coefficient=0.2,   # Emergency fund months increase slowly
                minimum_threshold=2.0,
                maximum_threshold=12.0,
                diminishing_returns_point=180000
            ),
            "investment_capacity": ScalingParameters(
                base_income=70000,
                elasticity_coefficient=0.8,   # Investment capacity increases strongly
                minimum_threshold=0.05,
                maximum_threshold=0.60,
                diminishing_returns_point=250000
            )
        }
    
    def scale_housing_ratio(
        self,
        monthly_income: float,
        region_multiplier: float = 1.0,
        family_size: int = 1
    ) -> float:
        """
        Scale housing ratio based on income using Engel's Law principles.
        
        Economic Theory: As income increases, the proportion spent on housing
        typically decreases (though absolute amounts increase).
        
        Args:
            monthly_income: User's monthly income
            region_multiplier: Regional cost adjustment
            family_size: Household size adjustment
            
        Returns:
            float: Recommended housing ratio (0.0-1.0)
        """
        annual_income = monthly_income * 12
        params = self.scaling_params["housing_ratio"]
        
        # Base calculation using income elasticity
        base_ratio = 0.30  # 30% baseline for median income
        
        # Apply income elasticity scaling
        income_ratio = annual_income / params.base_income
        elasticity_adjustment = (income_ratio ** params.elasticity_coefficient)
        scaled_ratio = base_ratio * elasticity_adjustment
        
        # Apply diminishing returns for very high incomes
        if annual_income > params.diminishing_returns_point:
            excess_income = annual_income - params.diminishing_returns_point
            diminishing_factor = 1 - (excess_income / 500000) * 0.1  # 10% reduction per 500k
            scaled_ratio *= max(0.8, diminishing_factor)
        
        # Apply regional adjustment
        regional_adjusted = scaled_ratio * region_multiplier
        
        # Apply family size adjustment (more people need more space)
        if family_size > 1:
            family_adjustment = 1 + (family_size - 1) * 0.05  # 5% per additional person
            regional_adjusted *= family_adjustment
        
        # Apply bounds
        final_ratio = max(params.minimum_threshold, 
                         min(params.maximum_threshold, regional_adjusted))
        
        logger.debug(f"Housing ratio calculation: {monthly_income:.0f}/mo -> {final_ratio:.2%}")
        return final_ratio
    
    def scale_food_ratio(
        self,
        monthly_income: float,
        family_size: int = 1,
        regional_food_cost_multiplier: float = 1.0
    ) -> float:
        """
        Scale food spending ratio using Engel's Law.
        
        Economic Theory: Food spending as % of income decreases as income increases.
        This is one of the most well-established relationships in economics.
        """
        annual_income = monthly_income * 12
        params = self.scaling_params["food_ratio"]
        
        # Base food ratio for median income
        base_ratio = 0.12  # 12% baseline
        
        # Apply Engel's Law scaling (strong negative elasticity)
        income_ratio = annual_income / params.base_income
        elasticity_adjustment = (income_ratio ** params.elasticity_coefficient)
        scaled_ratio = base_ratio * elasticity_adjustment
        
        # Family size has significant impact on food spending
        if family_size > 1:
            # Food costs don't scale linearly with family size due to economies of scale
            family_multiplier = 1 + (family_size - 1) * 0.3  # 30% per additional person
            scaled_ratio *= family_multiplier
        
        # Regional food cost adjustment
        regional_adjusted = scaled_ratio * regional_food_cost_multiplier
        
        # Apply bounds
        final_ratio = max(params.minimum_threshold,
                         min(params.maximum_threshold, regional_adjusted))
        
        logger.debug(f"Food ratio calculation: {monthly_income:.0f}/mo -> {final_ratio:.2%}")
        return final_ratio
    
    def scale_savings_rate_target(
        self,
        monthly_income: float,
        age: int,
        debt_to_income_ratio: float = 0.0,
        economic_uncertainty: float = 0.0
    ) -> float:
        """
        Scale target savings rate based on income and life circumstances.
        
        Economic Theory: Higher income allows higher savings rates (positive elasticity).
        Life-cycle hypothesis: Savings patterns vary by age.
        """
        annual_income = monthly_income * 12
        params = self.scaling_params["savings_rate"]
        
        # Base savings rate for median income
        base_rate = 0.12  # 12% baseline
        
        # Income elasticity scaling (positive for savings)
        income_ratio = annual_income / params.base_income
        elasticity_adjustment = (income_ratio ** params.elasticity_coefficient)
        scaled_rate = base_rate * elasticity_adjustment
        
        # Life-cycle adjustment
        age_multiplier = self._get_age_savings_multiplier(age)
        scaled_rate *= age_multiplier
        
        # Debt burden adjustment (high debt reduces savings capacity)
        if debt_to_income_ratio > 0.1:
            debt_penalty = max(0.5, 1 - debt_to_income_ratio * 1.5)
            scaled_rate *= debt_penalty
        
        # Economic uncertainty adjustment (recession risk increases target)
        uncertainty_bonus = 1 + economic_uncertainty * 0.3
        scaled_rate *= uncertainty_bonus
        
        # Apply diminishing returns for very high incomes
        if annual_income > params.diminishing_returns_point:
            diminishing_factor = 1 - math.log(annual_income / params.diminishing_returns_point) * 0.05
            scaled_rate *= max(0.8, diminishing_factor)
        
        # Apply bounds
        final_rate = max(params.minimum_threshold,
                        min(params.maximum_threshold, scaled_rate))
        
        logger.debug(f"Savings rate calculation: {monthly_income:.0f}/mo, age {age} -> {final_rate:.2%}")
        return final_rate
    
    def scale_small_purchase_threshold(
        self,
        monthly_income: float,
        spending_tier: IncomeTier,
        regional_cost_index: float = 1.0
    ) -> float:
        """
        Scale "small purchase" threshold based on income.
        
        Economic Theory: What constitutes a "small" purchase is income-relative.
        A $50 purchase is significant for low income, trivial for high income.
        """
        annual_income = monthly_income * 12
        params = self.scaling_params["small_purchase"]
        
        # Base threshold (0.5% of monthly income)
        base_threshold = monthly_income * 0.005
        
        # Income elasticity scaling
        income_ratio = annual_income / params.base_income
        elasticity_adjustment = (income_ratio ** params.elasticity_coefficient)
        scaled_threshold = base_threshold * elasticity_adjustment
        
        # Tier-specific adjustments (behavioral differences)
        tier_multipliers = {
            IncomeTier.LOW: 0.8,           # More sensitive to small purchases
            IncomeTier.LOWER_MIDDLE: 0.9,
            IncomeTier.MIDDLE: 1.0,
            IncomeTier.UPPER_MIDDLE: 1.1,
            IncomeTier.HIGH: 1.2           # Less sensitive to small purchases
        }
        scaled_threshold *= tier_multipliers.get(spending_tier, 1.0)
        
        # Regional cost adjustment
        regional_adjusted = scaled_threshold * regional_cost_index
        
        # Apply bounds
        final_threshold = max(params.minimum_threshold,
                             min(params.maximum_threshold, regional_adjusted))
        
        logger.debug(f"Small purchase threshold: {monthly_income:.0f}/mo -> ${final_threshold:.2f}")
        return final_threshold
    
    def scale_emergency_fund_months(
        self,
        monthly_income: float,
        job_security: float = 0.5,  # 0 = very insecure, 1 = very secure
        family_size: int = 1,
        regional_volatility: float = 0.0  # Regional economic volatility
    ) -> float:
        """
        Scale emergency fund target based on income and risk factors.
        
        Economic Theory: Higher income allows larger emergency funds,
        but also correlates with more stable employment.
        """
        annual_income = monthly_income * 12
        params = self.scaling_params["emergency_fund"]
        
        # Base emergency fund (3 months for median income)
        base_months = 3.0
        
        # Income elasticity scaling (slight positive elasticity)
        income_ratio = annual_income / params.base_income
        elasticity_adjustment = (income_ratio ** params.elasticity_coefficient)
        scaled_months = base_months * elasticity_adjustment
        
        # Job security adjustment (less secure = more months needed)
        security_adjustment = 1 + (1 - job_security) * 0.5  # Up to 50% more
        scaled_months *= security_adjustment
        
        # Family size adjustment (more dependents = larger fund needed)
        if family_size > 1:
            family_adjustment = 1 + (family_size - 1) * 0.3  # 30% per additional person
            scaled_months *= family_adjustment
        
        # Regional economic volatility adjustment
        volatility_adjustment = 1 + regional_volatility * 0.4  # Up to 40% more
        scaled_months *= volatility_adjustment
        
        # Apply bounds
        final_months = max(params.minimum_threshold,
                          min(params.maximum_threshold, scaled_months))
        
        logger.debug(f"Emergency fund target: {monthly_income:.0f}/mo -> {final_months:.1f} months")
        return final_months
    
    def scale_investment_capacity(
        self,
        monthly_income: float,
        existing_savings_rate: float,
        risk_tolerance: float = 0.5,  # 0 = very conservative, 1 = very aggressive
        age: int = 35
    ) -> float:
        """
        Scale investment capacity based on income and risk profile.
        
        Economic Theory: Investment capacity increases strongly with income
        (high positive elasticity) and varies by risk tolerance and age.
        """
        annual_income = monthly_income * 12
        params = self.scaling_params["investment_capacity"]
        
        # Base investment capacity (10% for median income)
        base_capacity = 0.10
        
        # Strong positive elasticity for investment capacity
        income_ratio = annual_income / params.base_income
        elasticity_adjustment = (income_ratio ** params.elasticity_coefficient)
        scaled_capacity = base_capacity * elasticity_adjustment
        
        # Risk tolerance adjustment
        risk_multiplier = 0.5 + risk_tolerance * 1.5  # 0.5x to 2.0x multiplier
        scaled_capacity *= risk_multiplier
        
        # Age-based adjustment (time horizon)
        age_multiplier = self._get_age_investment_multiplier(age)
        scaled_capacity *= age_multiplier
        
        # Can't exceed available income after existing savings
        available_capacity = max(0, 1.0 - existing_savings_rate - 0.6)  # Leave 60% for living expenses
        scaled_capacity = min(scaled_capacity, available_capacity)
        
        # Apply bounds
        final_capacity = max(params.minimum_threshold,
                            min(params.maximum_threshold, scaled_capacity))
        
        logger.debug(f"Investment capacity: {monthly_income:.0f}/mo -> {final_capacity:.2%}")
        return final_capacity
    
    def scale_category_variance_thresholds(
        self,
        monthly_income: float,
        spending_tier: IncomeTier,
        months_of_data: int = 6
    ) -> Dict[str, float]:
        """
        Scale spending variance thresholds based on income tier.
        
        Economic Theory: Higher income typically correlates with more predictable
        spending patterns due to better financial planning and stability.
        """
        # Base variance thresholds by category
        base_thresholds = {
            "housing": 0.05,      # Housing should be very stable
            "utilities": 0.15,    # Some seasonal variation
            "food": 0.20,         # Moderate variation acceptable
            "transport": 0.25,    # Can vary with usage
            "entertainment": 0.40, # High variation acceptable
            "shopping": 0.50,     # Very high variation acceptable
            "miscellaneous": 0.60  # Highest variation expected
        }
        
        # Tier-based adjustments (higher tiers should have lower variance)
        tier_multipliers = {
            IncomeTier.LOW: 1.3,           # Allow higher variance due to constraints
            IncomeTier.LOWER_MIDDLE: 1.1,
            IncomeTier.MIDDLE: 1.0,        # Baseline
            IncomeTier.UPPER_MIDDLE: 0.8,  # Lower variance expected
            IncomeTier.HIGH: 0.6           # Much lower variance expected
        }
        
        tier_multiplier = tier_multipliers.get(spending_tier, 1.0)
        
        # Data maturity adjustment (less data = higher tolerance)
        data_multiplier = max(0.8, 1.5 - months_of_data * 0.1)
        
        # Apply adjustments
        scaled_thresholds = {}
        for category, threshold in base_thresholds.items():
            scaled_thresholds[category] = threshold * tier_multiplier * data_multiplier
        
        logger.debug(f"Variance thresholds for {spending_tier}: {scaled_thresholds}")
        return scaled_thresholds
    
    def scale_goal_timeline_constraints(
        self,
        monthly_income: float,
        age: int,
        goal_amount: float,
        goal_category: str = "general"
    ) -> Dict[str, float]:
        """
        Scale goal timeline constraints based on income and goal characteristics.
        
        Economic Theory: Higher income allows more aggressive goal timelines.
        Age affects time horizon preferences.
        """
        monthly_income * 12
        
        # Calculate maximum reasonable contribution (% of income)
        income_tier = classify_income(monthly_income)
        
        # Maximum goal contribution rates by tier
        max_contribution_rates = {
            IncomeTier.LOW: 0.08,          # 8% max for goals
            IncomeTier.LOWER_MIDDLE: 0.12, # 12% max
            IncomeTier.MIDDLE: 0.18,       # 18% max
            IncomeTier.UPPER_MIDDLE: 0.25, # 25% max
            IncomeTier.HIGH: 0.35          # 35% max
        }
        
        max_monthly_contribution = monthly_income * max_contribution_rates[income_tier]
        
        # Calculate timeline constraints
        minimum_timeline_months = max(1, goal_amount / max_monthly_contribution)
        
        # Age-based maximum timeline
        age_based_max_years = {
            (18, 30): 10,   # Young - long horizons
            (30, 45): 8,    # Middle age - moderate horizons
            (45, 60): 6,    # Pre-retirement - shorter horizons
            (60, 100): 4    # Retirement age - short horizons
        }
        
        max_timeline_years = 10  # Default
        for age_range, years in age_based_max_years.items():
            if age_range[0] <= age < age_range[1]:
                max_timeline_years = years
                break
        
        maximum_timeline_months = max_timeline_years * 12
        
        # Goal category adjustments
        category_multipliers = {
            "emergency": 0.5,      # Emergency goals should be faster
            "debt": 0.7,           # Debt payoff should be aggressive
            "education": 1.2,      # Education can take longer
            "retirement": 2.0,     # Retirement planning is long-term
            "house": 1.5,          # Home buying moderate-term
            "vacation": 0.8,       # Vacation goals shorter-term
            "general": 1.0         # Baseline
        }
        
        category_multiplier = category_multipliers.get(goal_category.lower(), 1.0)
        maximum_timeline_months *= category_multiplier
        
        return {
            "minimum_timeline_months": minimum_timeline_months,
            "maximum_timeline_months": maximum_timeline_months,
            "optimal_timeline_months": minimum_timeline_months * 1.5,  # 50% buffer
            "maximum_monthly_contribution": max_monthly_contribution,
            "recommended_monthly_contribution": max_monthly_contribution * 0.7
        }
    
    # Helper methods for scaling calculations
    
    def _get_age_savings_multiplier(self, age: int) -> float:
        """Get age-based savings rate multiplier using life-cycle theory"""
        if age < 25:
            return 0.8      # Lower savings when starting career
        elif age < 35:
            return 1.0      # Standard savings rate
        elif age < 50:
            return 1.2      # Peak earning/saving years
        elif age < 65:
            return 1.1      # Pre-retirement boost
        else:
            return 0.6      # Retirement - lower savings need
    
    def _get_age_investment_multiplier(self, age: int) -> float:
        """Get age-based investment multiplier based on time horizon"""
        if age < 30:
            return 1.3      # Long time horizon allows aggressive investing
        elif age < 40:
            return 1.2      # Good time horizon
        elif age < 50:
            return 1.0      # Moderate time horizon
        elif age < 60:
            return 0.8      # Shorter time horizon
        else:
            return 0.5      # Conservative approach near/in retirement
    
    def calculate_income_elasticity(
        self,
        threshold_type: str,
        base_value: float,
        base_income: float,
        target_income: float
    ) -> float:
        """
        Calculate income elasticity adjustment for any threshold.
        
        General formula for applying income elasticity to financial thresholds.
        """
        if threshold_type not in self.scaling_params:
            logger.warning(f"Unknown threshold type: {threshold_type}")
            return base_value
        
        params = self.scaling_params[threshold_type]
        
        # Calculate income ratio
        income_ratio = target_income / base_income
        
        # Apply elasticity coefficient
        elasticity_adjustment = income_ratio ** params.elasticity_coefficient
        
        # Calculate scaled value
        scaled_value = base_value * elasticity_adjustment
        
        # Apply bounds if specified
        if params.minimum_threshold is not None and params.maximum_threshold is not None:
            scaled_value = max(params.minimum_threshold, 
                             min(params.maximum_threshold, scaled_value))
        
        logger.debug(f"Elasticity scaling for {threshold_type}: {base_value:.3f} -> {scaled_value:.3f}")
        return scaled_value


# Singleton instance for application use  
_income_scaling_service = IncomeScalingAlgorithms()


# Public API functions
def scale_threshold_by_income(
    threshold_type: str,
    monthly_income: float,
    **kwargs
) -> float:
    """
    Scale any financial threshold based on income.
    
    Args:
        threshold_type: Type of threshold to scale
        monthly_income: User's monthly income
        **kwargs: Additional parameters specific to threshold type
        
    Returns:
        float: Income-scaled threshold value
    """
    service = _income_scaling_service
    
    if threshold_type == "housing_ratio":
        return service.scale_housing_ratio(monthly_income, **kwargs)
    elif threshold_type == "food_ratio":
        return service.scale_food_ratio(monthly_income, **kwargs)
    elif threshold_type == "savings_rate":
        return service.scale_savings_rate_target(monthly_income, **kwargs)
    elif threshold_type == "small_purchase":
        return service.scale_small_purchase_threshold(monthly_income, **kwargs)
    elif threshold_type == "emergency_fund":
        return service.scale_emergency_fund_months(monthly_income, **kwargs)
    elif threshold_type == "investment_capacity":
        return service.scale_investment_capacity(monthly_income, **kwargs)
    else:
        raise ValueError(f"Unknown threshold type: {threshold_type}")


def get_scaled_variance_thresholds(
    monthly_income: float,
    months_of_data: int = 6
) -> Dict[str, float]:
    """Get income-appropriate spending variance thresholds"""
    spending_tier = classify_income(monthly_income)
    return _income_scaling_service.scale_category_variance_thresholds(
        monthly_income, spending_tier, months_of_data
    )


def get_scaled_goal_constraints(
    monthly_income: float,
    age: int,
    goal_amount: float,
    goal_category: str = "general"
) -> Dict[str, float]:
    """Get income-appropriate goal timeline constraints"""
    return _income_scaling_service.scale_goal_timeline_constraints(
        monthly_income, age, goal_amount, goal_category
    )