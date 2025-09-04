"""
Behavioral Configuration - Dynamic Version

This configuration now uses the dynamic threshold service to generate contextual
values instead of hardcoded ones. The functions below provide defaults when 
user context is not available, but the preferred approach is to use the
DynamicThresholdService with actual user context.
"""

from typing import Dict, List, Optional
from app.services.core.dynamic_threshold_service import (
    get_dynamic_thresholds, ThresholdType, UserContext
)


def get_category_time_bias(user_context: Optional[UserContext] = None) -> Dict[str, Dict[str, float]]:
    """Get time bias for categories, optionally using user context for personalization"""
    if user_context:
        # Use dynamic thresholds for full day patterns 
        time_patterns = get_dynamic_thresholds(ThresholdType.TIME_BIAS, user_context)
        return _convert_daily_to_time_of_day(time_patterns)
    
    # Fallback static values when user context unavailable
    return {
        "coffee": {"morning": 0.7, "afternoon": 0.2, "evening": 0.1},
        "groceries": {"afternoon": 0.5, "evening": 0.5},
        "transport": {"morning": 0.4, "evening": 0.6},
    }


def get_category_cooldown(user_context: Optional[UserContext] = None) -> Dict[str, int]:
    """Get category cooldown periods, optionally using user context for personalization"""
    if user_context:
        return get_dynamic_thresholds(ThresholdType.COOLDOWN_PERIOD, user_context)
    
    # Fallback static values when user context unavailable
    return {"shopping": 3, "restaurants": 2, "entertainment": 4}


def get_category_priorities(user_context: Optional[UserContext] = None) -> Dict[str, int]:
    """Get category priorities, optionally using user context for personalization"""
    if user_context:
        return get_dynamic_thresholds(ThresholdType.CATEGORY_PRIORITY, user_context)
    
    # Fallback static values when user context unavailable
    return {
        "housing": 1,
        "groceries": 2,
        "transport": 3,
        "utilities": 4,
        "healthcare": 5,
        "restaurants": 6,
        "entertainment": 7,
        "shopping": 8,
        "coffee": 9,
        "other": 10
    }


def _convert_daily_to_time_of_day(daily_patterns: Dict[str, List[float]]) -> Dict[str, Dict[str, float]]:
    """Convert daily patterns to time-of-day patterns for specific categories"""
    time_of_day_patterns = {}
    
    for category, daily_pattern in daily_patterns.items():
        if category in ["coffee"]:
            # Coffee typically consumed in morning
            time_of_day_patterns[category] = {
                "morning": 0.7, "afternoon": 0.2, "evening": 0.1
            }
        elif category in ["groceries"]:
            # Groceries typically bought afternoon/evening
            time_of_day_patterns[category] = {
                "afternoon": 0.5, "evening": 0.5
            }
        elif category in ["transport"]:
            # Transport patterns based on commuting
            time_of_day_patterns[category] = {
                "morning": 0.4, "evening": 0.6
            }
    
    return time_of_day_patterns


# Legacy constants for backwards compatibility - deprecated
CATEGORY_TIME_BIAS = get_category_time_bias()
CATEGORY_COOLDOWN = get_category_cooldown()  
CATEGORY_PRIORITIES = get_category_priorities()
