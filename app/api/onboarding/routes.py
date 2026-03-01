import json
import logging
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.api.onboarding.schemas import OnboardingSubmitRequest
from app.core.session import get_db
from app.db.models import User
from app.engine.calendar_engine_behavioral import build_calendar
from app.services.core.engine.budget_logic import generate_budget_from_answers
from app.services.calendar_service_real import save_calendar_for_user
from app.utils.response_wrapper import success_response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


@router.get("/questions", response_model=dict)
def get_questions():
    """Return onboarding questions from the config directory."""
    base_dir = Path(__file__).resolve().parent.parent
    path = base_dir / "config" / "onboarding_questions.json"
    if not path.exists():
        return success_response({"questions": []})
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return success_response(data)


@router.post("/submit")
def submit_onboarding(
    request: OnboardingSubmitRequest,
    db: Session = Depends(get_db),  # noqa: B008
    current_user=Depends(get_current_user),  # noqa: B008
):
    """
    Submit onboarding data and generate user's budget plan and calendar.

    Request body (OnboardingSubmitRequest):
    {
        "income": {"monthly_income": float, "additional_income": float},
        "fixed_expenses": {"category": float, ...},
        "spending_habits": {"dining_out_per_month": int, ...},
        "goals": {"savings_goal_amount_per_month": float, ...},
        "region": str (optional)
    }

    Raises:
        HTTPException 400: Invalid request data
        HTTPException 401: Unauthorized (from get_current_user dependency)
        HTTPException 422: Validation error
        HTTPException 500: Internal server error
    """
    # NOTE: get_current_user dependency handles auth and will raise 401 if unauthorized
    # FastAPI automatically validates request using Pydantic and raises 422 if invalid
    logger.info(f"📝 ONBOARDING SUBMISSION RECEIVED for user {current_user.id}")
    logger.info(f"User email: {current_user.email}")
    logger.info(f"User has_onboarded: {current_user.has_onboarded}")
    logger.info(f"Request income: {request.income.monthly_income}")

    # Extract validated data (FastAPI has already validated via Pydantic)
    monthly_income = request.income.monthly_income

    # Convert request to dict for backward compatibility with existing services
    answers = request.model_dump()

    logger.debug(f"Validated data for user {current_user.id}: monthly_income={monthly_income}")

    # Save income to user profile
    # BUGFIX: Query user fresh in sync session to avoid async/sync session conflict
    # current_user is attached to async session from get_current_user dependency
    try:
        user = db.query(User).filter(User.id == current_user.id).first()
        if not user:
            logger.error(f"User {current_user.id} not found in sync session")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "User not found", "code": "USER_NOT_FOUND"}
            )

        user.monthly_income = monthly_income
        db.flush()
        logger.debug(f"Updated monthly_income for user {user.id}")
    except HTTPException:
        # Re-raise HTTP exceptions (auth errors, etc.) without modification
        raise
    except Exception as e:
        logger.error(f"Database error updating user income for {current_user.id}: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Failed to update user profile",
                "code": "DATABASE_ERROR"
            }
        )

    # Generate budget plan with error handling
    try:
        budget_plan = generate_budget_from_answers(answers)
        logger.debug(f"Generated budget plan for user {current_user.id}")
    except HTTPException:
        # Re-raise HTTP exceptions (auth errors, etc.) without modification
        raise
    except ValueError as e:
        logger.warning(f"Budget generation validation error for user {current_user.id}: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": str(e),
                "code": "BUDGET_GENERATION_FAILED"
            }
        )
    except Exception as e:
        logger.error(f"Budget generation error for user {current_user.id}: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": f"Failed to generate budget: {str(e)}",
                "code": "BUDGET_GENERATION_ERROR"
            }
        )

    # Build calendar with error handling
    try:
        # Get current year and month for calendar generation
        now = datetime.utcnow()
        current_year = now.year
        current_month = now.month

        # Prepare calendar config by merging answers and budget_plan
        # Add top-level monthly_income for calendar engine compatibility
        calendar_config = {
            **answers,
            **budget_plan,
            "monthly_income": monthly_income,  # Add top-level for calendar engine
            "user_id": str(current_user.id),  # Required by calendar engine
            "year": current_year,  # BUGFIX: Add current year to prevent defaulting to 2025
            "month": current_month,  # BUGFIX: Add current month
        }
        calendar_data = build_calendar(calendar_config)
        save_calendar_for_user(db, current_user.id, calendar_data)
        logger.debug(f"Built and saved calendar for user {current_user.id}: {len(calendar_data)} days")
    except HTTPException:
        # Re-raise HTTP exceptions (auth errors, etc.) without modification
        raise
    except ValueError as e:
        logger.warning(f"Calendar build validation error for user {current_user.id}: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": f"Failed to build calendar: {str(e)}",
                "code": "CALENDAR_BUILD_FAILED"
            }
        )
    except Exception as e:
        logger.error(f"Calendar build error for user {current_user.id}: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": f"Failed to build calendar: {str(e)}",
                "code": "CALENDAR_BUILD_ERROR"
            }
        )

    # Mark user as having completed onboarding
    try:
        # BUGFIX: Use user object from sync session (not current_user from async session)
        user.has_onboarded = True
        # No need to db.add() - user is already in the session from the query above

        # Commit all changes including income, calendar, and onboarding flag
        db.commit()
        logger.info(f"Onboarding completed successfully for user {user.id}")
    except HTTPException:
        # Re-raise HTTP exceptions (auth errors, etc.) without modification
        raise
    except Exception as e:
        logger.error(f"Database commit error for user {current_user.id}: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Failed to save onboarding data",
                "code": "COMMIT_ERROR"
            }
        )

    return success_response({
        "status": "success",
        "calendar_days": len(calendar_data),
        "budget_plan": budget_plan,
        "message": "Onboarding completed successfully"
    })
