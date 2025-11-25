"""
Pydantic schemas for onboarding API endpoints.

Provides comprehensive request/response validation with proper field constraints.
"""

from typing import Dict, Optional
from pydantic import BaseModel, Field, field_validator


class IncomeData(BaseModel):
    """Income information schema"""
    monthly_income: float = Field(..., gt=0, description="Monthly income must be greater than 0")
    additional_income: Optional[float] = Field(0, ge=0, description="Additional income (optional)")


class SpendingHabits(BaseModel):
    """Spending habits schema"""
    dining_out_per_month: Optional[int] = Field(0, ge=0, description="Dining out frequency per month")
    entertainment_budget: Optional[float] = Field(0, ge=0, description="Entertainment budget")
    shopping_frequency: Optional[int] = Field(0, ge=0, description="Shopping frequency per month")


class GoalsData(BaseModel):
    """Financial goals schema"""
    savings_goal_amount_per_month: Optional[float] = Field(0, ge=0, description="Monthly savings goal")
    emergency_fund_target: Optional[float] = Field(0, ge=0, description="Emergency fund target")
    debt_payoff_goal: Optional[float] = Field(0, ge=0, description="Debt payoff goal")


class OnboardingSubmitRequest(BaseModel):
    """Request schema for onboarding submission"""
    income: IncomeData = Field(..., description="Income information")
    fixed_expenses: Dict[str, float] = Field(..., description="Fixed expenses by category")
    spending_habits: Optional[SpendingHabits] = Field(None, description="Spending habits (optional)")
    goals: Optional[GoalsData] = Field(None, description="Financial goals (optional)")
    region: Optional[str] = Field(None, max_length=100, description="User's region (optional)")

    @field_validator('fixed_expenses')
    @classmethod
    def validate_fixed_expenses(cls, v: Dict[str, float]) -> Dict[str, float]:
        """Validate that fixed expenses are non-negative and reasonable"""
        if not isinstance(v, dict):
            raise ValueError("fixed_expenses must be an object")

        if not v:
            # Allow empty dict - user might not have fixed expenses
            return v

        for category, amount in v.items():
            # Validate category name
            if not category or not category.strip():
                raise ValueError("Expense category cannot be empty")

            if len(category) > 100:
                raise ValueError(f"Category name '{category}' too long (max 100 characters)")

            # Validate amount
            if not isinstance(amount, (int, float)):
                raise ValueError(f"Expense amount for '{category}' must be a number")

            if amount < 0:
                raise ValueError(f"Expense amount for '{category}' cannot be negative")

            # Reasonable upper limit to prevent abuse
            if amount > 1_000_000:
                raise ValueError(f"Expense amount for '{category}' exceeds reasonable limit")

        return v

    @field_validator('region')
    @classmethod
    def validate_region(cls, v: Optional[str]) -> Optional[str]:
        """Validate and sanitize region field"""
        if v is not None:
            v = v.strip()
            if not v:
                return None
        return v


class BudgetPlanResponse(BaseModel):
    """Budget plan response schema"""
    # This will be populated by generate_budget_from_answers
    # Schema depends on budget planner implementation
    pass


class OnboardingSubmitResponse(BaseModel):
    """Response schema for successful onboarding submission"""
    status: str = Field(..., description="Operation status")
    calendar_days: int = Field(..., description="Number of calendar days generated")
    budget_plan: Dict = Field(..., description="Generated budget plan")
    message: str = Field(..., description="Success message")