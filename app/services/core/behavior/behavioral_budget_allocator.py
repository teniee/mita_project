import logging
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from app.services.core.dynamic_threshold_service import (
    DynamicThresholdService, get_dynamic_thresholds, ThresholdType, UserContext
)

logger = logging.getLogger(__name__)


def get_behavioral_allocation(
    start_date: str, 
    num_days: int, 
    budget_plan: Dict[str, float],
    user_context: Optional[UserContext] = None
) -> List[Dict[str, float]]:
    """Distribute behavioral budget across days using dynamic weekday bias and cooldown.

    :param start_date: Start date in ``YYYY-MM-DD`` format
    :param num_days: Number of days in the period
    :param budget_plan: Category budget, e.g. ``{"groceries": 100.0, "transport": 50.0}``
    :param user_context: User context for dynamic threshold calculation
    :return: List of dictionaries where each element is a day's budget
    """
    # Create default user context if none provided
    if user_context is None:
        user_context = UserContext(
            monthly_income=5000,  # Default middle-income
            age=35,
            region="US",
            family_size=1
        )
    
    # Get dynamic thresholds based on user context
    time_bias_thresholds = get_dynamic_thresholds(ThresholdType.TIME_BIAS, user_context)
    cooldown_thresholds = get_dynamic_thresholds(ThresholdType.COOLDOWN_PERIOD, user_context)
    
    base_date = datetime.strptime(start_date, "%Y-%m-%d")
    calendar = [base_date + timedelta(days=i) for i in range(num_days)]

    memory = defaultdict(list)
    result: List[Dict[str, float]] = [defaultdict(float) for _ in range(num_days)]

    for category, total in budget_plan.items():
        # Use dynamic cooldown based on user context
        cooldown = cooldown_thresholds.get(category, cooldown_thresholds.get(category.replace(" ", "_"), 0))
        
        # Use dynamic time bias based on user context
        bias = time_bias_thresholds.get(category, time_bias_thresholds.get(category.replace(" ", "_"), [1.0] * 7))
        slots = []

        for i, date in enumerate(calendar):
            weekday = date.weekday()
            score = bias[weekday] if weekday < len(bias) else 1.0
            recent_days = memory[category]

            if recent_days and (i - recent_days[-1]) <= cooldown:
                score = 0

            if score > 0:
                slots.append((i, score))

        slots.sort(key=lambda x: -x[1])
        
        # Dynamic slot limitation based on category and user behavior
        if category in ["entertainment", "entertainment events", "clothing", "dining out", "dining_out"]:
            max_slots = 4  # Discretionary spending spread across fewer days
        else:
            max_slots = len(slots)  # Essential spending can be any day
            
        selected = sorted([i for i, _ in slots[:max_slots]])

        if selected:
            amount = round(total / len(selected), 2)
            for i in selected:
                result[i][category] += amount
                memory[category].append(i)

    return [dict(day) for day in result]


def allocate_behavioral_budget(user_id: int, total_budget: float, db: Session) -> dict:
    """
    Allocate budget across categories based on behavioral analysis.

    This function takes a total budget and distributes it across spending categories
    using behavioral patterns and user context.

    Args:
        user_id: User ID for context
        total_budget: Total budget to allocate
        db: Database session

    Returns:
        Dictionary with category allocations and metadata.
        Key fields:
          - user_context_applied: True only when DynamicThresholdService returned
            personalised weights. False means hardcoded defaults were used.
          - allocation_method: "dynamic" | "hardcoded_fallback"
          - income_tier: classified tier string (e.g. "middle"), "unknown" on error
          - confidence: 0.85 for dynamic, 0.50 for hardcoded fallback
    """
    from app.db.models.user import User
    from app.services.core.income_classification_service import IncomeClassificationService

    # ------------------------------------------------------------------ #
    # 1. Build user context from DB record                                 #
    # ------------------------------------------------------------------ #
    user = db.query(User).filter(User.id == user_id).first()

    monthly_income = user.monthly_income if user else total_budget
    region = user.country if user and hasattr(user, "country") else "US"
    age = user.age if user and hasattr(user, "age") else 35

    user_context = UserContext(
        monthly_income=monthly_income,
        age=age,
        region=region,
        family_size=1,
    )

    # Classify income tier upfront — pure computation, used in both paths.
    try:
        income_tier: str = IncomeClassificationService().classify_income(
            monthly_income, region
        ).value
    except Exception:
        income_tier = "unknown"

    # ------------------------------------------------------------------ #
    # 2. Hardcoded fallback distribution                                   #
    # ------------------------------------------------------------------ #
    default_distribution = {
        "food": 0.30,
        "transportation": 0.15,
        "utilities": 0.10,
        "entertainment": 0.10,
        "shopping": 0.10,
        "healthcare": 0.05,
        "savings": 0.20,
    }

    # ------------------------------------------------------------------ #
    # 3. Try personalised weights from DynamicThresholdService             #
    # ------------------------------------------------------------------ #
    user_context_applied = False
    try:
        svc = DynamicThresholdService()
        thresholds = svc.get_budget_allocation_thresholds(user_context)
        if thresholds and isinstance(thresholds, dict) and len(thresholds) > 0:
            categories = {
                cat: round(float(total_budget) * float(weight), 2)
                for cat, weight in thresholds.items()
            }
            user_context_applied = True
            logger.info(
                "behavioral_allocation.dynamic_context_applied",
                extra={
                    "user_id": user_id,
                    "income_tier": income_tier,
                    "monthly_income": monthly_income,
                    "region": region,
                    "categories_count": len(categories),
                    "allocation_method": "dynamic",
                },
            )
        else:
            raise ValueError("DynamicThresholdService returned empty thresholds")
    except Exception as exc:
        categories = {
            cat: round(total_budget * pct, 2)
            for cat, pct in default_distribution.items()
        }
        user_context_applied = False
        logger.warning(
            "behavioral_allocation.fallback_to_hardcoded",
            extra={
                "user_id": user_id,
                "income_tier": income_tier,
                "monthly_income": monthly_income,
                "fallback_reason": type(exc).__name__,
                "allocation_method": "hardcoded_fallback",
            },
            exc_info=True,
        )

    return {
        "categories": categories,
        "total_allocated": sum(categories.values()),
        "method": "behavioral_allocation",
        "allocation_method": "dynamic" if user_context_applied else "hardcoded_fallback",
        "income_tier": income_tier,
        "confidence": 0.85 if user_context_applied else 0.50,
        "user_context_applied": user_context_applied,
    }
