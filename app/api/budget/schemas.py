from typing import Any, Dict, Optional, List
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator, condecimal
from app.core.validators import InputSanitizer, FinancialConstants


class BudgetRequest(BaseModel):
    """Enhanced budget request schema with comprehensive validation"""
    
    user_answers: Dict[str, Any] = Field(..., description="User questionnaire responses")
    year: int = Field(..., ge=2020, le=2030, description="Budget year")
    month: int = Field(..., ge=1, le=12, description="Budget month")
    
    @field_validator('user_answers')
    @classmethod
    def validate_user_answers(cls, v):
        if not isinstance(v, dict):
            raise ValueError("User answers must be a dictionary")
        
        # Validate that answers contain reasonable data
        if not v:
            raise ValueError("User answers cannot be empty")
        
        # Sanitize string values in answers
        sanitized_answers = {}
        for key, value in v.items():
            if isinstance(value, str):
                sanitized_answers[key] = InputSanitizer.sanitize_string(value, max_length=1000)
            elif isinstance(value, (int, float)) and 'income' in key.lower():
                # Validate income-related fields
                sanitized_answers[key] = float(InputSanitizer.sanitize_amount(
                    value,
                    min_value=FinancialConstants.MIN_ANNUAL_INCOME,
                    max_value=FinancialConstants.MAX_ANNUAL_INCOME,
                    field_name=key
                ))
            else:
                sanitized_answers[key] = value
        
        return sanitized_answers
    
    @field_validator('year')
    @classmethod
    def validate_year(cls, v):
        current_year = date.today().year
        if v < current_year - 1:
            raise ValueError(f"Budget year cannot be more than 1 year in the past")
        if v > current_year + 5:
            raise ValueError(f"Budget year cannot be more than 5 years in the future")
        return v


class BudgetCategoryIn(BaseModel):
    """Schema for budget category creation/update"""
    
    category: str = Field(..., min_length=1, max_length=50, description="Budget category")
    amount: condecimal(max_digits=12, decimal_places=2, gt=0) = Field(
        ..., description="Budget amount with precise decimal handling"
    )
    period: str = Field("monthly", regex=r'^(weekly|monthly|yearly)$', description="Budget period")
    currency: Optional[str] = Field("USD", min_length=3, max_length=3, description="Currency code")
    description: Optional[str] = Field(None, max_length=500, description="Budget description")
    is_flexible: Optional[bool] = Field(True, description="Can budget be adjusted automatically")
    priority: Optional[int] = Field(1, ge=1, le=5, description="Budget priority (1-5)")
    
    @field_validator('category')
    @classmethod
    def validate_category(cls, v):
        return InputSanitizer.sanitize_transaction_category(v)
    
    @field_validator('amount')
    @classmethod
    def validate_amount(cls, v):
        return InputSanitizer.sanitize_amount(
            v,
            min_value=FinancialConstants.MIN_BUDGET_AMOUNT,
            max_value=FinancialConstants.MAX_BUDGET_AMOUNT,
            field_name="budget amount"
        )
    
    @field_validator('currency')
    @classmethod
    def validate_currency(cls, v):
        if v is None:
            return FinancialConstants.DEFAULT_CURRENCY
        return InputSanitizer.sanitize_currency_code(v)
    
    @field_validator('description')
    @classmethod
    def validate_description(cls, v):
        if v is None:
            return v
        return InputSanitizer.sanitize_string(v, max_length=500)


class BudgetOut(BaseModel):
    """Enhanced budget output schema"""
    
    id: str
    category: str
    amount: Decimal
    period: str
    currency: str = "USD"
    description: Optional[str] = None
    is_flexible: bool = True
    priority: int = 1
    spent_amount: Optional[Decimal] = None
    remaining_amount: Optional[Decimal] = None
    utilization_percentage: Optional[float] = None
    created_at: date
    updated_at: Optional[date] = None
    
    class Config:
        from_attributes = True
        json_encoders = {
            Decimal: lambda v: str(v)  # Keep precision by converting to string
        }


class BudgetAnalysisOut(BaseModel):
    """Budget analysis and recommendations schema"""
    
    total_budget: Decimal
    total_spent: Decimal
    total_remaining: Decimal
    utilization_percentage: float
    categories: List[BudgetOut]
    recommendations: List[str]
    overspent_categories: List[str]
    underutilized_categories: List[str]
    
    class Config:
        json_encoders = {
            Decimal: lambda v: str(v)
        }


class BudgetAdjustmentIn(BaseModel):
    """Schema for budget adjustments and redistribution"""
    
    adjustments: Dict[str, condecimal(max_digits=12, decimal_places=2, gt=0)] = Field(
        ..., description="Category adjustments (category -> new amount)"
    )
    reason: Optional[str] = Field(None, max_length=500, description="Reason for adjustment")
    effective_date: Optional[date] = Field(None, description="When adjustment takes effect")
    
    @field_validator('adjustments')
    @classmethod
    def validate_adjustments(cls, v):
        if not v:
            raise ValueError("At least one adjustment is required")
        
        validated_adjustments = {}
        for category, amount in v.items():
            # Validate category
            validated_category = InputSanitizer.sanitize_transaction_category(category)
            
            # Validate amount
            validated_amount = InputSanitizer.sanitize_amount(
                amount,
                min_value=FinancialConstants.MIN_BUDGET_AMOUNT,
                max_value=FinancialConstants.MAX_BUDGET_AMOUNT,
                field_name=f"budget adjustment for {category}"
            )
            
            validated_adjustments[validated_category] = validated_amount
        
        return validated_adjustments
    
    @field_validator('reason')
    @classmethod
    def validate_reason(cls, v):
        if v is None:
            return v
        return InputSanitizer.sanitize_string(v, max_length=500)
    
    @field_validator('effective_date')
    @classmethod
    def validate_effective_date(cls, v):
        if v is None:
            return date.today()
        
        effective_date = InputSanitizer.sanitize_date(v)
        
        # Effective date validation
        from datetime import timedelta
        if effective_date < date.today() - timedelta(days=7):
            raise ValueError("Effective date cannot be more than 7 days in the past")
        
        if effective_date > date.today() + timedelta(days=365):
            raise ValueError("Effective date cannot be more than 1 year in the future")
        
        return effective_date
