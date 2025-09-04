"""
Centralized Income Classification Service for MITA Finance

This service provides the single source of truth for all income classification logic
across the MITA backend. It ensures economic accuracy, regional considerations,
and consistent 5-tier classification.

Economic Justification:
- Based on US Census Bureau median household income data (2024)
- Incorporates regional cost-of-living adjustments
- Aligns with behavioral economics research on financial decision-making
- Uses thresholds that reflect actual purchasing power and financial capability
"""

from typing import Dict, Tuple, Optional
from enum import Enum
import logging
from app.config.country_profiles_loader import get_profile

logger = logging.getLogger(__name__)


class IncomeTier(Enum):
    """5-tier income classification system"""
    LOW = "low"
    LOWER_MIDDLE = "lower_middle"
    MIDDLE = "middle"
    UPPER_MIDDLE = "upper_middle"
    HIGH = "high"


class IncomeClassificationService:
    """
    Centralized service for income classification with economic accuracy.
    
    All income classification in MITA backend MUST use this service to ensure:
    1. Consistent 5-tier system across all modules
    2. Regional cost-of-living adjustments
    3. Economic accuracy based on current data
    4. Behavioral economics alignment
    """

    def __init__(self):
        """Initialize the service with validation"""
        self._validate_profiles()

    def _validate_profiles(self) -> None:
        """Validate that country profiles have required thresholds"""
        try:
            # Test core profiles exist and have thresholds
            us_profile = get_profile("US")
            ca_profile = get_profile("US-CA")
            
            for profile, name in [(us_profile, "US"), (ca_profile, "US-CA")]:
                thresholds = profile.get("class_thresholds", {})
                required_keys = ["low", "lower_middle", "middle", "upper_middle"]
                
                for key in required_keys:
                    if key not in thresholds:
                        logger.error(f"Missing threshold '{key}' in {name} profile")
                        raise ValueError(f"Invalid income classification config for {name}")
                        
        except Exception as e:
            logger.error(f"Income classification service validation failed: {e}")
            raise

    def classify_income(self, monthly_income: float, region: str = "US") -> IncomeTier:
        """
        Classify monthly income into 5-tier system with regional adjustment.
        
        Args:
            monthly_income: User's monthly income in USD
            region: Region code (e.g., "US", "US-CA", "US-TX")
            
        Returns:
            IncomeTier: The appropriate income tier
            
        Raises:
            ValueError: If income is negative or region is invalid
        """
        if monthly_income < 0:
            raise ValueError("Income cannot be negative")
        
        # Get region-specific thresholds
        profile = get_profile(region)
        thresholds = profile.get("class_thresholds", {})
        
        # Convert monthly to annual income for comparison
        annual_income = monthly_income * 12
        
        # Apply 5-tier classification with regional thresholds
        if annual_income <= thresholds.get("low", 36000):
            return IncomeTier.LOW
        elif annual_income <= thresholds.get("lower_middle", 57600):
            return IncomeTier.LOWER_MIDDLE
        elif annual_income <= thresholds.get("middle", 86400):
            return IncomeTier.MIDDLE
        elif annual_income <= thresholds.get("upper_middle", 144000):
            return IncomeTier.UPPER_MIDDLE
        else:
            return IncomeTier.HIGH

    def get_tier_thresholds(self, region: str = "US") -> Dict[str, float]:
        """
        Get the income thresholds for a region.
        
        Args:
            region: Region code
            
        Returns:
            Dict with threshold values in annual USD
        """
        profile = get_profile(region)
        return profile.get("class_thresholds", {
            "low": 36000,
            "lower_middle": 57600,
            "middle": 86400,
            "upper_middle": 144000
        })

    def get_tier_display_info(self, tier: IncomeTier, region: str = "US") -> Dict[str, str]:
        """
        Get display information for an income tier.
        
        Args:
            tier: Income tier
            region: Region code for localized ranges
            
        Returns:
            Dict with display name, description, and range
        """
        thresholds = self.get_tier_thresholds(region)
        
        tier_info = {
            IncomeTier.LOW: {
                "name": "Foundation Builder",
                "description": "Building financial foundation through essential spending optimization",
                "range": f"Up to ${thresholds['low']:,.0f}/year"
            },
            IncomeTier.LOWER_MIDDLE: {
                "name": "Momentum Builder", 
                "description": "Creating financial momentum through systematic saving and growth",
                "range": f"${thresholds['low']:,.0f} - ${thresholds['lower_middle']:,.0f}/year"
            },
            IncomeTier.MIDDLE: {
                "name": "Strategic Achiever",
                "description": "Achieving strategic financial goals through balanced optimization",
                "range": f"${thresholds['lower_middle']:,.0f} - ${thresholds['middle']:,.0f}/year"
            },
            IncomeTier.UPPER_MIDDLE: {
                "name": "Wealth Accelerator",
                "description": "Accelerating wealth building through sophisticated strategies",
                "range": f"${thresholds['middle']:,.0f} - ${thresholds['upper_middle']:,.0f}/year"
            },
            IncomeTier.HIGH: {
                "name": "Legacy Builder",
                "description": "Building lasting legacy through advanced wealth strategies",
                "range": f"Above ${thresholds['upper_middle']:,.0f}/year"
            }
        }
        
        return tier_info[tier]

    def get_behavioral_pattern(self, tier: IncomeTier) -> Dict[str, any]:
        """
        Get behavioral economics pattern for income tier.
        
        Based on research on financial decision-making by income level.
        """
        patterns = {
            IncomeTier.LOW: {
                "decision_time": "immediate",
                "planning_horizon": "weekly",
                "risk_tolerance": "very_low",
                "primary_motivators": ["security", "progress"],
                "mental_accounting_buckets": 2,
                "savings_rate_target": 0.05,
                "housing_ratio_target": 0.40
            },
            IncomeTier.LOWER_MIDDLE: {
                "decision_time": "hours_to_days",
                "planning_horizon": "monthly",
                "risk_tolerance": "low",
                "primary_motivators": ["progress", "peer_comparison"],
                "mental_accounting_buckets": 4,
                "savings_rate_target": 0.08,
                "housing_ratio_target": 0.35
            },
            IncomeTier.MIDDLE: {
                "decision_time": "days_to_weeks",
                "planning_horizon": "quarterly",
                "risk_tolerance": "moderate",
                "primary_motivators": ["optimization", "status"],
                "mental_accounting_buckets": 6,
                "savings_rate_target": 0.12,
                "housing_ratio_target": 0.30
            },
            IncomeTier.UPPER_MIDDLE: {
                "decision_time": "weeks_to_months",
                "planning_horizon": "yearly",
                "risk_tolerance": "moderate_high",
                "primary_motivators": ["efficiency", "legacy"],
                "mental_accounting_buckets": 8,
                "savings_rate_target": 0.18,
                "housing_ratio_target": 0.28
            },
            IncomeTier.HIGH: {
                "decision_time": "months_to_years",
                "planning_horizon": "multi_year",
                "risk_tolerance": "high",
                "primary_motivators": ["impact", "complexity_management"],
                "mental_accounting_buckets": 10,
                "savings_rate_target": 0.25,
                "housing_ratio_target": 0.25
            }
        }
        
        return patterns[tier]

    def get_budget_weights(self, tier: IncomeTier, region: str = "US") -> Dict[str, float]:
        """
        Get economically optimized budget allocation weights for income tier.
        
        Args:
            tier: Income tier
            region: Region for cost-of-living adjustment
            
        Returns:
            Dict with category allocation percentages
        """
        profile = get_profile(region)
        tier_classes = profile.get("classes", {})
        
        # Use tier-specific allocations from country profile
        tier_key = tier.value
        if tier_key in tier_classes:
            return tier_classes[tier_key]
        
        # Fallback to economically sound defaults
        defaults = {
            IncomeTier.LOW: {
                "housing": 0.40, "food": 0.15, "transport": 0.15,
                "utilities": 0.10, "healthcare": 0.08, "savings": 0.05,
                "entertainment": 0.04, "miscellaneous": 0.03
            },
            IncomeTier.LOWER_MIDDLE: {
                "housing": 0.35, "food": 0.13, "transport": 0.15,
                "utilities": 0.08, "healthcare": 0.07, "savings": 0.08,
                "entertainment": 0.06, "miscellaneous": 0.08
            },
            IncomeTier.MIDDLE: {
                "housing": 0.30, "food": 0.12, "transport": 0.15,
                "utilities": 0.07, "healthcare": 0.06, "savings": 0.12,
                "entertainment": 0.08, "miscellaneous": 0.10
            },
            IncomeTier.UPPER_MIDDLE: {
                "housing": 0.28, "food": 0.10, "transport": 0.13,
                "utilities": 0.05, "healthcare": 0.05, "savings": 0.15,
                "entertainment": 0.09, "investments": 0.10, "miscellaneous": 0.05
            },
            IncomeTier.HIGH: {
                "housing": 0.25, "food": 0.08, "transport": 0.10,
                "utilities": 0.04, "healthcare": 0.04, "savings": 0.12,
                "entertainment": 0.10, "investments": 0.20, "luxury": 0.07
            }
        }
        
        return defaults[tier]

    def is_near_tier_boundary(self, monthly_income: float, region: str = "US") -> Tuple[bool, Optional[IncomeTier]]:
        """
        Check if user is near a tier boundary (within 5%) for upgrade motivation.
        
        Args:
            monthly_income: Monthly income
            region: Region code
            
        Returns:
            Tuple of (is_near_boundary, next_tier_if_applicable)
        """
        current_tier = self.classify_income(monthly_income, region)
        annual_income = monthly_income * 12
        thresholds = self.get_tier_thresholds(region)
        
        # Check if within 5% of next tier boundary
        if current_tier == IncomeTier.LOW:
            current_max = thresholds["low"]
            next_tier = IncomeTier.LOWER_MIDDLE
        elif current_tier == IncomeTier.LOWER_MIDDLE:
            current_max = thresholds["lower_middle"]
            next_tier = IncomeTier.MIDDLE
        elif current_tier == IncomeTier.MIDDLE:
            current_max = thresholds["middle"]
            next_tier = IncomeTier.UPPER_MIDDLE
        elif current_tier == IncomeTier.UPPER_MIDDLE:
            current_max = thresholds["upper_middle"]
            next_tier = IncomeTier.HIGH
        else:  # HIGH tier
            return False, None
            
        # Calculate if within 5% of the current tier's upper boundary
        distance_to_boundary = current_max - annual_income
        boundary_threshold = current_max * 0.05  # 5% of the boundary value
        
        is_near = distance_to_boundary <= boundary_threshold
        return is_near, next_tier if is_near else None

    def validate_classification_consistency(self, profile: Dict) -> bool:
        """
        Validate that a user profile would be classified consistently.
        Used for testing and QA.
        
        Args:
            profile: User profile dict with income and region
            
        Returns:
            bool: True if classification is consistent
        """
        try:
            # Check required fields exist
            if "income" not in profile or "region" not in profile:
                return False
                
            income = profile.get("income", 0)
            region = profile.get("region", "US")
            
            # Validate income is non-negative
            if income < 0:
                return False
            
            # Test classification
            tier = self.classify_income(income, region)
            
            # Test that tier boundaries make sense
            thresholds = self.get_tier_thresholds(region)
            annual_income = income * 12
            
            # Validate tier assignment is correct
            if tier == IncomeTier.LOW and annual_income > thresholds["low"]:
                return False
            if tier == IncomeTier.LOWER_MIDDLE and (
                annual_income <= thresholds["low"] or 
                annual_income > thresholds["lower_middle"]
            ):
                return False
            if tier == IncomeTier.MIDDLE and (
                annual_income <= thresholds["lower_middle"] or 
                annual_income > thresholds["middle"]
            ):
                return False
            if tier == IncomeTier.UPPER_MIDDLE and (
                annual_income <= thresholds["middle"] or 
                annual_income > thresholds["upper_middle"]
            ):
                return False
            if tier == IncomeTier.HIGH and annual_income <= thresholds["upper_middle"]:
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Classification validation failed: {e}")
            return False


# Singleton instance for application use
_income_service = IncomeClassificationService()


# Public API functions for backward compatibility
def classify_income(monthly_income: float, region: str = "US") -> IncomeTier:
    """Classify monthly income into tier - main entry point"""
    return _income_service.classify_income(monthly_income, region)


def get_tier_string(tier: IncomeTier) -> str:
    """Get string representation of tier for API compatibility"""
    return tier.value


def get_tier_display_info(tier: IncomeTier, region: str = "US") -> Dict[str, str]:
    """Get display information for tier"""
    return _income_service.get_tier_display_info(tier, region)


def get_budget_weights(tier: IncomeTier, region: str = "US") -> Dict[str, float]:
    """Get budget allocation weights for tier"""
    return _income_service.get_budget_weights(tier, region)


def validate_income_profile(profile: Dict) -> bool:
    """Validate income profile for consistency"""
    return _income_service.validate_classification_consistency(profile)