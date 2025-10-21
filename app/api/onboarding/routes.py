import json
from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.session import get_db
from app.engine.calendar_engine_behavioral import build_calendar
from app.services.budget_planner import generate_budget_from_answers
from app.services.calendar_service_real import save_calendar_for_user
from app.utils.response_wrapper import success_response

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


@router.get("/questions", response_model=dict)
async def get_questions():
    """Return onboarding questions from the config directory."""
    base_dir = Path(__file__).resolve().parent.parent
    path = base_dir / "config" / "onboarding_questions.json"
    if not path.exists():
        return success_response({"questions": []})
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return success_response(data)


@router.post("/submit")
async def submit_onboarding(
    answers: dict,
    db: Session = Depends(get_db),  # noqa: B008
    current_user=Depends(get_current_user),  # noqa: B008
):
    """
    Submit onboarding data and generate user's budget plan and calendar.

    Expected data format:
    {
        "income": {"monthly_income": float, "additional_income": float},
        "fixed_expenses": {"category": float, ...},
        "spending_habits": {"dining_out_per_month": int, ...},
        "goals": {"savings_goal_amount_per_month": float, ...},
        "region": str (optional)
    }
    """
    try:
        # Validate required data structure
        income_data = answers.get('income')
        if not income_data or not isinstance(income_data, dict):
            return {
                "success": False,
                "error": "Invalid income data format. Expected object with monthly_income.",
                "code": "INVALID_INCOME_FORMAT"
            }

        monthly_income = income_data.get('monthly_income', 0)
        if monthly_income <= 0:
            return {
                "success": False,
                "error": "Monthly income must be greater than 0",
                "code": "INVALID_INCOME_VALUE"
            }

        # Validate fixed expenses
        fixed_expenses = answers.get('fixed_expenses', {})
        if not isinstance(fixed_expenses, dict):
            return {
                "success": False,
                "error": "Invalid fixed_expenses format. Expected object.",
                "code": "INVALID_EXPENSES_FORMAT"
            }

        # Save income to user profile
        current_user.monthly_income = monthly_income
        db.add(current_user)
        db.flush()

        # Generate budget plan with error handling
        try:
            budget_plan = generate_budget_from_answers(answers)
        except ValueError as e:
            db.rollback()
            return {
                "success": False,
                "error": str(e),
                "code": "BUDGET_GENERATION_FAILED"
            }
        except Exception as e:
            db.rollback()
            return {
                "success": False,
                "error": f"Failed to generate budget: {str(e)}",
                "code": "BUDGET_GENERATION_ERROR"
            }

        # Build calendar with error handling
        try:
            # Prepare calendar config by merging answers and budget_plan
            # Add top-level monthly_income for calendar engine compatibility
            calendar_config = {
                **answers,
                **budget_plan,
                "monthly_income": monthly_income,  # Add top-level for calendar engine
                "user_id": str(current_user.id),  # Required by calendar engine
            }
            calendar_data = build_calendar(calendar_config)
            save_calendar_for_user(db, current_user.id, calendar_data)
        except Exception as e:
            db.rollback()
            return {
                "success": False,
                "error": f"Failed to build calendar: {str(e)}",
                "code": "CALENDAR_BUILD_ERROR"
            }

        # Mark user as having completed onboarding
        current_user.has_onboarded = True
        db.add(current_user)

        # Commit all changes including income, calendar, and onboarding flag
        db.commit()

        return success_response({
            "status": "success",
            "calendar_days": len(calendar_data),
            "budget_plan": budget_plan,
            "message": "Onboarding completed successfully"
        })

    except Exception as e:
        db.rollback()
        return {
            "success": False,
            "error": f"Unexpected error during onboarding: {str(e)}",
            "code": "ONBOARDING_ERROR"
        }
