from decimal import Decimal
from typing import Optional, List
from datetime import date

from pydantic import BaseModel, Field, field_validator, condecimal
from app.core.validators import InputSanitizer, FinancialConstants


class InstallmentEvalRequest(BaseModel):
    """Enhanced installment evaluation request with comprehensive validation"""
    
    price: condecimal(max_digits=12, decimal_places=2, gt=0) = Field(
        ..., description="Purchase price with precise decimal handling"
    )
    months: int = Field(..., ge=1, le=360, description="Number of months for installment (max 30 years)")
    down_payment: Optional[condecimal(max_digits=12, decimal_places=2, ge=0)] = Field(
        None, description="Down payment amount"
    )
    interest_rate: Optional[condecimal(max_digits=5, decimal_places=4, ge=0, le=1)] = Field(
        None, description="Annual interest rate (as decimal, e.g., 0.05 for 5%)"
    )
    current_monthly_income: Optional[condecimal(max_digits=12, decimal_places=2, ge=0)] = Field(
        None, description="Current monthly income for affordability calculation"
    )
    existing_monthly_debt: Optional[condecimal(max_digits=12, decimal_places=2, ge=0)] = Field(
        None, description="Existing monthly debt payments"
    )
    
    @field_validator('price')
    @classmethod
    def validate_price(cls, v):
        return InputSanitizer.sanitize_amount(
            v,
            min_value=Decimal('1.00'),
            max_value=FinancialConstants.MAX_GOAL_AMOUNT,
            field_name="purchase price"
        )
    
    @field_validator('months')
    @classmethod
    def validate_months(cls, v):
        if v < 1:
            raise ValueError("Installment period must be at least 1 month")
        if v > 360:  # 30 years maximum
            raise ValueError("Installment period cannot exceed 30 years (360 months)")
        return v
    
    @field_validator('down_payment')
    @classmethod
    def validate_down_payment(cls, v, info):
        if v is None:
            return Decimal('0.00')
        
        down_payment = InputSanitizer.sanitize_amount(
            v,
            min_value=Decimal('0.00'),
            max_value=FinancialConstants.MAX_GOAL_AMOUNT,
            field_name="down payment"
        )
        
        # Down payment cannot exceed purchase price
        price = info.data.get('price') if info.data else None
        if price and down_payment > price:
            raise ValueError("Down payment cannot exceed purchase price")
        
        return down_payment
    
    @field_validator('interest_rate')
    @classmethod
    def validate_interest_rate(cls, v):
        if v is None:
            return Decimal('0.00')
        
        if v < 0:
            raise ValueError("Interest rate cannot be negative")
        if v > 1:
            raise ValueError("Interest rate must be expressed as decimal (e.g., 0.05 for 5%)")
        
        return v
    
    @field_validator('current_monthly_income')
    @classmethod
    def validate_monthly_income(cls, v):
        if v is None:
            return v
        
        return InputSanitizer.sanitize_amount(
            v,
            min_value=Decimal('0.00'),
            max_value=FinancialConstants.MAX_ANNUAL_INCOME / 12,
            field_name="monthly income"
        )
    
    @field_validator('existing_monthly_debt')
    @classmethod
    def validate_monthly_debt(cls, v):
        if v is None:
            return Decimal('0.00')
        
        return InputSanitizer.sanitize_amount(
            v,
            min_value=Decimal('0.00'),
            max_value=FinancialConstants.MAX_ANNUAL_INCOME / 12,
            field_name="monthly debt"
        )


class InstallmentEvalResult(BaseModel):
    """Enhanced installment evaluation result"""
    
    can_afford: bool
    monthly_payment: Decimal
    total_cost: Decimal
    total_interest: Decimal
    debt_to_income_ratio: Optional[float] = None
    reason: str
    recommendations: List[str] = []
    alternative_terms: Optional[List[dict]] = None
    
    class Config:
        json_encoders = {
            Decimal: lambda v: str(v)
        }


class GoalIn(BaseModel):
    """Enhanced goal creation schema with comprehensive validation"""
    
    title: str = Field(..., min_length=1, max_length=200, description="Goal title")
    description: Optional[str] = Field(None, max_length=1000, description="Goal description")
    category: str = Field(..., min_length=1, max_length=50, description="Goal category")
    target_amount: condecimal(max_digits=12, decimal_places=2, gt=0) = Field(
        ..., description="Target amount with precise decimal handling"
    )
    current_amount: Optional[condecimal(max_digits=12, decimal_places=2, ge=0)] = Field(
        None, description="Current progress amount"
    )
    currency: Optional[str] = Field("USD", min_length=3, max_length=3, description="Currency code")
    target_date: Optional[date] = Field(None, description="Target completion date")
    priority: Optional[int] = Field(1, ge=1, le=5, description="Goal priority (1-5)")
    is_active: Optional[bool] = Field(True, description="Is goal currently active")
    monthly_contribution: Optional[condecimal(max_digits=10, decimal_places=2, ge=0)] = Field(
        None, description="Planned monthly contribution"
    )
    
    @field_validator('title')
    @classmethod
    def validate_title(cls, v):
        sanitized = InputSanitizer.sanitize_string(v, max_length=200)
        
        # Goal title should be meaningful
        if len(sanitized.strip()) < 3:
            raise ValueError("Goal title must be at least 3 characters long")
        
        # Check for common placeholder text
        placeholders = ['untitled', 'new goal', 'goal', 'test', 'sample']
        if sanitized.lower().strip() in placeholders:
            raise ValueError("Please provide a meaningful goal title")
        
        return sanitized.title()
    
    @field_validator('description')
    @classmethod
    def validate_description(cls, v):
        if v is None:
            return v
        
        # Allow basic HTML formatting for goals
        return InputSanitizer.sanitize_string(v, max_length=1000, allow_html=True)
    
    @field_validator('category')
    @classmethod
    def validate_category(cls, v):
        return InputSanitizer.sanitize_goal_category(v)
    
    @field_validator('target_amount')
    @classmethod
    def validate_target_amount(cls, v):
        return InputSanitizer.sanitize_amount(
            v,
            min_value=FinancialConstants.MIN_GOAL_AMOUNT,
            max_value=FinancialConstants.MAX_GOAL_AMOUNT,
            field_name="goal target amount"
        )
    
    @field_validator('current_amount')
    @classmethod
    def validate_current_amount(cls, v, info):
        if v is None:
            return Decimal('0.00')
        
        current_amount = InputSanitizer.sanitize_amount(
            v,
            min_value=Decimal('0.00'),
            max_value=FinancialConstants.MAX_GOAL_AMOUNT,
            field_name="goal current amount"
        )
        
        # Current amount should not exceed target amount
        target_amount = info.data.get('target_amount') if info.data else None
        if target_amount and current_amount > target_amount:
            raise ValueError("Current amount cannot exceed target amount")
        
        return current_amount
    
    @field_validator('currency')
    @classmethod
    def validate_currency(cls, v):
        if v is None:
            return FinancialConstants.DEFAULT_CURRENCY
        return InputSanitizer.sanitize_currency_code(v)
    
    @field_validator('target_date')
    @classmethod
    def validate_target_date(cls, v):
        if v is None:
            return v
        
        target_date = InputSanitizer.sanitize_date(v)
        
        # Target date should be in the future
        if target_date <= date.today():
            raise ValueError("Goal target date must be in the future")
        
        # Minimum goal duration (1 month)
        from datetime import timedelta
        if target_date < date.today() + timedelta(days=30):
            raise ValueError("Goal target date must be at least 30 days in the future")
        
        # Reasonable limit - 20 years for retirement goals
        if target_date > date.today() + timedelta(days=365 * 20):
            raise ValueError("Goal target date cannot be more than 20 years in the future")
        
        return target_date
    
    @field_validator('monthly_contribution')
    @classmethod
    def validate_monthly_contribution(cls, v, info):
        if v is None:
            return v
        
        contribution = InputSanitizer.sanitize_amount(
            v,
            min_value=Decimal('1.00'),
            max_value=FinancialConstants.MAX_BUDGET_AMOUNT,
            field_name="monthly contribution"
        )
        
        # Validate contribution makes sense for the goal
        target_amount = info.data.get('target_amount') if info.data else None
        target_date = info.data.get('target_date') if info.data else None
        
        if target_amount and target_date:
            # Calculate months until target date
            import logging
            logger = logging.getLogger(__name__)
            
            today = date.today()
            months_remaining = (target_date.year - today.year) * 12 + target_date.month - today.month
            
            if months_remaining > 0:
                required_monthly = target_amount / months_remaining
                
                # Warning if contribution is significantly higher than needed
                if contribution > required_monthly * 2:
                    logger.warning(
                        f"High monthly contribution: ${contribution} vs required ${required_monthly}"
                    )
        
        return contribution


class GoalOut(BaseModel):
    """Enhanced goal output schema"""
    
    id: str
    title: str
    description: Optional[str] = None
    category: str
    target_amount: Decimal
    current_amount: Decimal
    currency: str = "USD"
    target_date: Optional[date] = None
    priority: int = 1
    is_active: bool = True
    monthly_contribution: Optional[Decimal] = None
    progress_percentage: float = 0.0
    months_remaining: Optional[int] = None
    projected_completion: Optional[date] = None
    created_at: date
    updated_at: Optional[date] = None
    
    class Config:
        from_attributes = True
        json_encoders = {
            Decimal: lambda v: str(v)
        }
