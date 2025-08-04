from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class TxnIn(BaseModel):
    category: str
    amount: Decimal = Field(..., ge=0, decimal_places=2, description="Transaction amount with 2 decimal places")
    spent_at: datetime = datetime.utcnow()
    description: Optional[str] = Field(None, max_length=500)
    
    @field_validator('amount')
    @classmethod
    def validate_amount(cls, v):
        """Ensure amount is properly formatted for financial calculations"""
        if isinstance(v, (int, float)):
            v = Decimal(str(v))
        
        # Round to 2 decimal places for financial accuracy
        return round(v, 2)
    
    @field_validator('category')
    @classmethod
    def validate_category(cls, v):
        """Validate transaction category"""
        valid_categories = [
            'food', 'dining', 'groceries', 'transportation', 'gas', 'public_transport',
            'entertainment', 'shopping', 'clothing', 'healthcare', 'insurance',
            'utilities', 'rent', 'mortgage', 'education', 'childcare', 'pets',
            'travel', 'subscriptions', 'gifts', 'charity', 'income', 'other'
        ]
        
        if v.lower() not in valid_categories:
            raise ValueError(f'Invalid category. Must be one of: {", ".join(valid_categories)}')
        
        return v.lower()


class TxnOut(BaseModel):
    id: str
    category: str
    amount: Decimal
    currency: str = "USD"
    spent_at: datetime
    description: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True
        json_encoders = {
            Decimal: lambda v: float(v)  # Convert Decimal to float for JSON serialization
        }
