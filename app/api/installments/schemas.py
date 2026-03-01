"""
Installment Payment Module - Pydantic Schemas
Professional financial validation for US economy

Based on BNPL research findings:
- Safe payment threshold: <5% of monthly income
- Minimum safe balance: $2,500
- Safe DTI (Debt-to-Income): <35%
- Critical DTI: <43%
"""

from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, condecimal

from app.core.validators import InputSanitizer
from app.schemas.base import UserOwnedDecimalResponseSchema
from app.db.models.installment import (
    InstallmentCategory,
    AgeGroup,
    RiskLevel,
    InstallmentStatus
)


# ===== FINANCIAL PROFILE SCHEMAS =====

class UserFinancialProfileCreate(BaseModel):
    """Create or update user's financial profile"""
    monthly_income: condecimal(max_digits=12, decimal_places=2, gt=0) = Field(
        ...,
        description="Monthly income after taxes in USD"
    )
    current_balance: condecimal(max_digits=12, decimal_places=2, ge=0) = Field(
        ...,
        description="Current available balance in USD"
    )
    age_group: AgeGroup = Field(..., description="User's age group for risk assessment")

    # Existing obligations
    credit_card_debt: bool = Field(False, description="Has outstanding credit card debt?")
    credit_card_payment: condecimal(max_digits=12, decimal_places=2, ge=0) = Field(
        0,
        description="Monthly credit card payment in USD"
    )
    other_loans_payment: condecimal(max_digits=12, decimal_places=2, ge=0) = Field(
        0,
        description="Other loans monthly payment in USD"
    )
    rent_payment: condecimal(max_digits=12, decimal_places=2, ge=0) = Field(
        0,
        description="Monthly rent payment in USD"
    )
    subscriptions_payment: condecimal(max_digits=12, decimal_places=2, ge=0) = Field(
        0,
        description="Monthly subscriptions in USD"
    )

    # Future plans
    planning_mortgage: bool = Field(False, description="Planning to apply for mortgage in 6 months?")

    @field_validator('monthly_income')
    @classmethod
    def validate_monthly_income(cls, v):
        # US minimum wage ~$1,256/month (federal), typical range $1,500-$20,000/month
        if v < 500:
            raise ValueError("Monthly income seems too low. Please enter income after taxes in USD.")
        if v > 100000:
            raise ValueError("Monthly income seems unusually high. Please verify the amount.")
        return v

    @field_validator('current_balance')
    @classmethod
    def validate_current_balance(cls, v):
        if v > 10000000:  # $10M seems like a reasonable upper limit
            raise ValueError("Balance seems unusually high. Please verify the amount.")
        return v


class UserFinancialProfileOut(BaseModel):
    """Output schema for financial profile"""
    id: UUID
    user_id: UUID
    monthly_income: Decimal
    current_balance: Decimal
    age_group: AgeGroup
    credit_card_debt: bool
    credit_card_payment: Decimal
    other_loans_payment: Decimal
    rent_payment: Decimal
    subscriptions_payment: Decimal
    planning_mortgage: bool
    updated_at: datetime

    class Config:
        from_attributes = True
        json_encoders = {
            Decimal: lambda v: str(v)
        }


# ===== INSTALLMENT CALCULATOR SCHEMAS =====

class InstallmentCalculatorInput(BaseModel):
    """
    Input for installment calculator
    Based on US financial best practices and BNPL research
    """
    # Purchase details
    purchase_amount: condecimal(max_digits=12, decimal_places=2, gt=0) = Field(
        ...,
        description="Purchase amount in USD"
    )
    category: InstallmentCategory = Field(..., description="Purchase category")

    # Payment structure
    num_payments: int = Field(..., ge=2, le=48, description="Number of payments (2-48)")
    interest_rate: condecimal(max_digits=5, decimal_places=2, ge=0, le=50) = Field(
        0,
        description="Annual interest rate percentage (0-50%)"
    )

    # Financial profile (if not already saved)
    monthly_income: Optional[condecimal(max_digits=12, decimal_places=2, gt=0)] = Field(
        None,
        description="Monthly income if not in profile"
    )
    current_balance: Optional[condecimal(max_digits=12, decimal_places=2, ge=0)] = Field(
        None,
        description="Current balance if not in profile"
    )
    age_group: Optional[AgeGroup] = Field(None, description="Age group if not in profile")

    # Existing obligations
    active_installments_count: int = Field(0, ge=0, le=20, description="Number of active installments")
    active_installments_monthly: condecimal(max_digits=12, decimal_places=2, ge=0) = Field(
        0,
        description="Total monthly payment for active installments"
    )
    credit_card_debt: bool = Field(False, description="Has credit card debt?")
    other_monthly_obligations: condecimal(max_digits=12, decimal_places=2, ge=0) = Field(
        0,
        description="Other monthly financial obligations (loans, rent, etc.)"
    )
    planning_mortgage: bool = Field(False, description="Planning mortgage in 6 months?")

    @field_validator('purchase_amount')
    @classmethod
    def validate_purchase_amount(cls, v):
        # Typical BNPL range: $50 - $10,000, but allow up to $50,000 for major purchases
        if v < 10:
            raise ValueError("Purchase amount must be at least $10")
        if v > 50000:
            raise ValueError("Purchase amount exceeds $50,000. Consider traditional financing.")
        return v

    @field_validator('num_payments')
    @classmethod
    def validate_num_payments(cls, v):
        # Common BNPL terms: 4, 6, 12, 24 payments
        common_terms = [2, 3, 4, 6, 9, 12, 18, 24, 36, 48]
        if v not in common_terms:
            # Allow it but could warn
            pass
        return v


class RiskFactor(BaseModel):
    """Individual risk factor that triggered during assessment"""
    factor: str = Field(..., description="Risk factor identifier")
    severity: str = Field(..., description="high, medium, low")
    message: str = Field(..., description="User-friendly explanation")
    stat: Optional[str] = Field(None, description="Relevant statistic if applicable")


class AlternativeRecommendation(BaseModel):
    """Alternative approach recommendation"""
    recommendation_type: str = Field(..., description="save, wait, reduce_term, etc.")
    title: str = Field(..., description="Recommendation title")
    description: str = Field(..., description="Detailed recommendation")
    savings_amount: Optional[Decimal] = Field(None, description="How much to save if applicable")
    time_needed_days: Optional[int] = Field(None, description="Days needed if applicable")


class InstallmentCalculatorOutput(BaseModel):
    """
    Output from installment calculator with comprehensive risk assessment
    Based on professional financial analysis
    """
    # Risk assessment
    risk_level: RiskLevel = Field(..., description="Overall risk level")
    risk_score: int = Field(..., ge=0, le=100, description="Numerical risk score (0-100)")
    verdict: str = Field(..., description="Short verdict message")

    # Payment calculations
    monthly_payment: Decimal = Field(..., description="Monthly payment amount in USD")
    total_interest: Decimal = Field(..., description="Total interest paid over term")
    total_cost: Decimal = Field(..., description="Total cost including interest")
    first_payment_amount: Decimal = Field(..., description="First payment amount")

    # Payment schedule
    payment_schedule: List[Dict] = Field(..., description="Detailed payment schedule")

    # Financial impact
    dti_ratio: Decimal = Field(..., description="Debt-to-Income ratio after this installment (%)")
    payment_to_income_ratio: Decimal = Field(..., description="This payment as % of income")
    remaining_monthly_funds: Decimal = Field(..., description="Money left after all obligations")
    balance_after_first_payment: Decimal = Field(..., description="Balance after first payment")

    # Risk analysis
    risk_factors: List[RiskFactor] = Field(..., description="List of triggered risk factors")
    personalized_message: str = Field(..., description="Personalized explanation based on user's situation")

    # Recommendations
    alternative_recommendation: Optional[AlternativeRecommendation] = Field(
        None,
        description="Alternative approach recommendation"
    )

    # Educational content
    warnings: List[str] = Field(default_factory=list, description="Important warnings")
    tips: List[str] = Field(default_factory=list, description="Helpful tips")
    statistics: List[str] = Field(default_factory=list, description="Relevant statistics")

    # Hidden costs
    potential_late_fee: Optional[Decimal] = Field(None, description="Potential late fee")
    potential_overdraft: Optional[Decimal] = Field(None, description="Potential overdraft fee")
    hidden_cost_message: Optional[str] = Field(None, description="Hidden costs explanation")

    class Config:
        json_encoders = {
            Decimal: lambda v: str(v)
        }


# ===== INSTALLMENT MANAGEMENT SCHEMAS =====

class InstallmentCreate(BaseModel):
    """Create a new installment for tracking"""
    item_name: str = Field(..., min_length=1, max_length=200, description="Name of item/service")
    category: InstallmentCategory = Field(..., description="Purchase category")

    total_amount: condecimal(max_digits=12, decimal_places=2, gt=0) = Field(
        ...,
        description="Total amount in USD"
    )
    payment_amount: condecimal(max_digits=12, decimal_places=2, gt=0) = Field(
        ...,
        description="Payment amount per period in USD"
    )
    interest_rate: condecimal(max_digits=5, decimal_places=2, ge=0) = Field(
        0,
        description="Interest rate %"
    )

    total_payments: int = Field(..., ge=2, le=48, description="Total number of payments")
    payments_made: int = Field(0, ge=0, description="Payments already made")
    payment_frequency: str = Field("monthly", description="monthly or biweekly")

    first_payment_date: datetime = Field(..., description="Date of first payment")
    next_payment_date: datetime = Field(..., description="Date of next payment")

    notes: Optional[str] = Field(None, max_length=1000, description="Additional notes")

    @field_validator('item_name')
    @classmethod
    def validate_item_name(cls, v):
        return InputSanitizer.sanitize_string(v, max_length=200)

    @field_validator('notes')
    @classmethod
    def validate_notes(cls, v):
        if v is None:
            return v
        return InputSanitizer.sanitize_string(v, max_length=1000)


class InstallmentUpdate(BaseModel):
    """Update an existing installment"""
    payments_made: Optional[int] = Field(None, ge=0, description="Update payments made count")
    next_payment_date: Optional[datetime] = Field(None, description="Update next payment date")
    status: Optional[InstallmentStatus] = Field(None, description="Update status")
    notes: Optional[str] = Field(None, max_length=1000, description="Update notes")

    @field_validator('notes')
    @classmethod
    def validate_notes(cls, v):
        if v is None:
            return v
        return InputSanitizer.sanitize_string(v, max_length=1000)


class InstallmentOut(UserOwnedDecimalResponseSchema):
    """Output schema for installment"""
    item_name: str
    category: InstallmentCategory
    total_amount: Decimal
    payment_amount: Decimal
    interest_rate: Decimal
    total_payments: int
    payments_made: int
    payment_frequency: str
    first_payment_date: datetime
    next_payment_date: datetime
    final_payment_date: datetime
    status: InstallmentStatus
    notes: Optional[str]

    # Calculated fields
    progress_percentage: Optional[float] = None
    remaining_payments: Optional[int] = None
    total_paid: Optional[Decimal] = None
    remaining_balance: Optional[Decimal] = None


class InstallmentsSummary(BaseModel):
    """Summary of all user's installments"""
    total_active: int = Field(..., description="Number of active installments")
    total_completed: int = Field(..., description="Number of completed installments")
    total_monthly_payment: Decimal = Field(..., description="Total monthly payment across all installments")
    next_payment_date: Optional[datetime] = Field(None, description="Next upcoming payment date")
    next_payment_amount: Optional[Decimal] = Field(None, description="Next payment amount")
    installments: List[InstallmentOut] = Field(..., description="List of all installments")

    # Risk assessment for current load
    current_installment_load: str = Field(..., description="safe, moderate, high, critical")
    load_message: str = Field(..., description="Message about current installment load")

    class Config:
        json_encoders = {
            Decimal: lambda v: str(v)
        }


# ===== ACHIEVEMENT SCHEMAS =====

class InstallmentAchievementOut(BaseModel):
    """User's installment achievements"""
    id: UUID
    user_id: UUID
    installments_completed: int
    calculations_performed: int
    calculations_declined: int
    days_without_new_installment: int
    max_days_streak: int
    interest_saved: Decimal
    achievement_level: str
    last_calculation_date: Optional[datetime]
    updated_at: datetime

    class Config:
        from_attributes = True
        json_encoders = {
            Decimal: lambda v: str(v)
        }


# ===== CALENDAR INTEGRATION SCHEMAS =====

class InstallmentCalendarEvent(BaseModel):
    """Installment payment event for calendar integration"""
    installment_id: UUID
    item_name: str
    payment_amount: Decimal
    payment_date: datetime
    is_upcoming: bool
    days_until_payment: int
    status: str  # "upcoming", "today", "overdue"

    class Config:
        json_encoders = {
            Decimal: lambda v: str(v)
        }


class MonthlyInstallmentsCalendar(BaseModel):
    """Monthly view of installment payments"""
    year: int
    month: int
    total_payments_this_month: Decimal
    payment_dates: List[InstallmentCalendarEvent]
    available_after_installments: Decimal

    class Config:
        json_encoders = {
            Decimal: lambda v: str(v)
        }
