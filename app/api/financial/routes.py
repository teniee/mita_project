from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.api.financial.schemas import InstallmentEvalRequest  # noqa: E501
from app.api.financial.schemas import InstallmentEvalResult
from app.api.financial.services import evaluate_installment
from app.core.session import get_db

# Import standardized error handling system
from app.core.standardized_error_handler import (
    ValidationError,
    BusinessLogicError,
    ErrorCode,
    validate_amount,
    validate_required_fields
)
from app.core.error_decorators import handle_financial_errors, ErrorHandlingMixin
from app.utils.response_wrapper import StandardizedResponse, FinancialResponseHelper

from app.services.core.dynamic_threshold_service import (
    get_dynamic_budget_method, get_dynamic_thresholds, 
    ThresholdType, UserContext
)

router = APIRouter(prefix="/financial", tags=["financial"])

# Error handling mixin for financial routes
class FinancialErrorHandler(ErrorHandlingMixin):
    pass

financial_error_handler = FinancialErrorHandler()


@router.post("/installment-evaluate", response_model=InstallmentEvalResult, 
             summary="Evaluate installment plan affordability")
@handle_financial_errors
async def installment_check_standardized(
    request: Request,
    payload: InstallmentEvalRequest,
    user=Depends(get_current_user),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
):
    """
    Evaluate whether a user can afford an installment plan based on their budget and financial profile.
    
    This endpoint uses standardized error handling to provide:
    - Consistent validation error messages
    - Proper business logic error handling
    - Financial constraint validation
    - Comprehensive audit logging
    """
    
    # Validate required fields
    payload_dict = payload.dict()
    validate_required_fields(payload_dict, ["price", "months"])
    
    # Validate amount (price)
    validated_price = validate_amount(
        payload.price, 
        min_amount=1.0, 
        max_amount=1000000.0
    )
    
    # Validate months
    if not isinstance(payload.months, int) or payload.months < 1 or payload.months > 60:
        raise ValidationError(
            "Installment period must be between 1 and 60 months",
            ErrorCode.VALIDATION_OUT_OF_RANGE,
            details={"min_months": 1, "max_months": 60, "provided_months": payload.months}
        )
    
    try:
        # Evaluate installment using the existing service
        result = evaluate_installment(user.id, validated_price, payload.months, db)
        
        if not result:
            raise BusinessLogicError(
                "Unable to evaluate installment at this time",
                ErrorCode.BUSINESS_INVALID_OPERATION
            )
        
        # Calculate additional financial insights
        monthly_payment = validated_price / payload.months
        total_budget_impact = monthly_payment * payload.months
        
        # Add metadata for better user experience
        analysis_meta = {
            "monthly_payment": round(monthly_payment, 2),
            "total_amount": validated_price,
            "installment_period": payload.months,
            "budget_impact_assessment": "within_limits" if result.get("affordable", False) else "exceeds_limits"
        }
        
        return FinancialResponseHelper.analysis_result(
            analysis_data=result,
            analysis_type="installment_evaluation",
            confidence_score=result.get("confidence_score", 0.85)
        )
        
    except Exception as e:
        if isinstance(e, (ValidationError, BusinessLogicError)):
            raise
        else:
            raise BusinessLogicError(
                f"Installment evaluation failed: {str(e)}",
                ErrorCode.BUSINESS_INVALID_OPERATION
            )


@router.get("/dynamic-budget-method")
async def get_personalized_budget_method(
    user=Depends(get_current_user),  # noqa: B008
):
    """Get personalized budget method recommendation instead of hardcoded 50/30/20"""
    
    # Create user context from user data
    user_context = UserContext(
        monthly_income=getattr(user, 'monthly_income', 5000),
        age=getattr(user, 'age', 35),
        region=getattr(user, 'region', 'US'),
        family_size=getattr(user, 'family_size', 1),
        debt_to_income_ratio=getattr(user, 'debt_to_income_ratio', 0.0),
        housing_status=getattr(user, 'housing_status', 'rent'),
        life_stage=getattr(user, 'life_stage', 'single')
    )
    
    # Get personalized budget method
    budget_method = get_dynamic_budget_method(user_context)
    
    return success_response({
        "personalized_method": budget_method,
        "user_tier": "calculated_dynamically",
        "economic_justification": (
            "Budget allocation calculated using income elasticity theory, "
            "regional cost adjustments, and behavioral economics principles"
        )
    })


@router.get("/dynamic-thresholds/{threshold_type}")
async def get_personalized_thresholds(
    threshold_type: str,
    user=Depends(get_current_user),  # noqa: B008
):
    """Get dynamic financial thresholds for user context"""
    
    # Create user context from user data
    user_context = UserContext(
        monthly_income=getattr(user, 'monthly_income', 5000),
        age=getattr(user, 'age', 35),
        region=getattr(user, 'region', 'US'),
        family_size=getattr(user, 'family_size', 1),
        debt_to_income_ratio=getattr(user, 'debt_to_income_ratio', 0.0),
        housing_status=getattr(user, 'housing_status', 'rent'),
        life_stage=getattr(user, 'life_stage', 'single')
    )
    
    # Map string to ThresholdType enum
    threshold_type_mapping = {
        "budget_allocation": ThresholdType.BUDGET_ALLOCATION,
        "spending_pattern": ThresholdType.SPENDING_PATTERN,
        "health_scoring": ThresholdType.HEALTH_SCORING,
        "savings_target": ThresholdType.SAVINGS_TARGET,
        "goal_constraint": ThresholdType.GOAL_CONSTRAINT,
        "behavioral_trigger": ThresholdType.BEHAVIORAL_TRIGGER,
        "time_bias": ThresholdType.TIME_BIAS,
        "cooldown_period": ThresholdType.COOLDOWN_PERIOD,
        "category_priority": ThresholdType.CATEGORY_PRIORITY
    }
    
    if threshold_type not in threshold_type_mapping:
        return success_response({
            "error": f"Invalid threshold type: {threshold_type}",
            "available_types": list(threshold_type_mapping.keys())
        })
    
    # Get dynamic thresholds
    thresholds = get_dynamic_thresholds(
        threshold_type_mapping[threshold_type], 
        user_context
    )
    
    return success_response({
        "threshold_type": threshold_type,
        "thresholds": thresholds,
        "user_context_applied": True,
        "economic_basis": (
            f"Thresholds calculated using economic principles specific to "
            f"{user_context.region} region and user's financial profile"
        )
    })
