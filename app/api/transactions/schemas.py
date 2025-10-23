from datetime import datetime
from decimal import Decimal
from typing import Optional, List

from pydantic import BaseModel, Field, field_validator, condecimal
from app.core.validators import InputSanitizer, FinancialConstants


class TxnIn(BaseModel):
    """Enhanced transaction input schema with comprehensive financial validation"""

    amount: condecimal(max_digits=12, decimal_places=2, gt=0) = Field(
        ..., description="Transaction amount with precise decimal handling"
    )
    category: str = Field(..., min_length=1, max_length=50, description="Transaction category")
    description: Optional[str] = Field(None, max_length=500, description="Transaction description")
    currency: Optional[str] = Field("USD", min_length=3, max_length=3, description="Currency code")
    merchant: Optional[str] = Field(None, max_length=200, description="Merchant name")
    location: Optional[str] = Field(None, max_length=200, description="Transaction location")
    tags: Optional[List[str]] = Field(None, max_items=10, description="Transaction tags")
    spent_at: Optional[datetime] = Field(None, description="Transaction date and time")
    is_recurring: Optional[bool] = Field(False, description="Is this a recurring transaction")
    confidence_score: Optional[float] = Field(None, ge=0.0, le=1.0, description="OCR confidence score")
    receipt_url: Optional[str] = Field(None, max_length=500, description="Receipt image URL")

    # MODULE 5: Goal Integration
    goal_id: Optional[str] = Field(None, description="Link transaction to a savings goal (UUID)")
    
    @field_validator('amount')
    @classmethod
    def validate_amount(cls, v):
        """Validate transaction amount with financial precision"""
        return InputSanitizer.sanitize_amount(
            v, 
            min_value=FinancialConstants.MIN_TRANSACTION_AMOUNT,
            max_value=FinancialConstants.MAX_TRANSACTION_AMOUNT,
            field_name="transaction amount"
        )
    
    @field_validator('category')
    @classmethod
    def validate_category(cls, v):
        """Validate transaction category against allowed values"""
        return InputSanitizer.sanitize_transaction_category(v)
    
    @field_validator('description')
    @classmethod
    def validate_description(cls, v):
        if v is None:
            return v
        
        # Enhanced description validation for financial transactions
        sanitized = InputSanitizer.sanitize_string(v, max_length=500)
        
        # Check for suspicious patterns in descriptions
        import re
        import logging
        logger = logging.getLogger(__name__)
        
        suspicious_patterns = [
            r'\b(test|fake|dummy|sample)\b',  # Test data indicators
            r'\b(hack|exploit|inject)\b',    # Security-related terms
            r'[<>{}]',                       # Potential injection characters
        ]
        
        for pattern in suspicious_patterns:
            if re.search(pattern, sanitized.lower()):
                logger.warning(f"Suspicious transaction description: {sanitized[:50]}...")
        
        return sanitized
    
    @field_validator('currency')
    @classmethod
    def validate_currency(cls, v):
        if v is None:
            return FinancialConstants.DEFAULT_CURRENCY
        
        return InputSanitizer.sanitize_currency_code(v)
    
    @field_validator('merchant')
    @classmethod
    def validate_merchant(cls, v):
        if v is None:
            return v
        
        # Enhanced merchant validation
        sanitized = InputSanitizer.sanitize_string(v, max_length=200)
        
        # Check for valid merchant name format
        if len(sanitized.strip()) < 2:
            raise ValueError("Merchant name must be at least 2 characters")
        
        # Remove excessive whitespace
        sanitized = ' '.join(sanitized.split())
        
        return sanitized.title()  # Proper case formatting
    
    @field_validator('location')
    @classmethod
    def validate_location(cls, v):
        if v is None:
            return v
        
        sanitized = InputSanitizer.sanitize_string(v, max_length=200)
        
        # Basic location format validation
        if len(sanitized.strip()) < 2:
            raise ValueError("Location must be at least 2 characters")
        
        return sanitized.title()
    
    @field_validator('tags')
    @classmethod
    def validate_tags(cls, v):
        if v is None:
            return v
        
        if not isinstance(v, list):
            raise ValueError("Tags must be a list")
        
        validated_tags = []
        for tag in v:
            if not isinstance(tag, str):
                raise ValueError("Each tag must be a string")
            
            # Sanitize each tag
            sanitized_tag = InputSanitizer.sanitize_string(tag, max_length=50)
            
            # Tag format validation
            import re
            if not re.match(r'^[a-zA-Z0-9_\-\s]+$', sanitized_tag):
                raise ValueError(f"Invalid tag format: {sanitized_tag}")
            
            # Convert to lowercase and remove extra spaces
            clean_tag = '_'.join(sanitized_tag.lower().split())
            
            if len(clean_tag) >= 2 and clean_tag not in validated_tags:
                validated_tags.append(clean_tag)
        
        return validated_tags[:10]  # Limit to 10 tags
    
    @field_validator('spent_at')
    @classmethod
    def validate_spent_at(cls, v):
        if v is None:
            return datetime.utcnow()
        
        # Enhanced date validation for financial transactions
        from datetime import timedelta
        now = datetime.utcnow()
        
        # Check if date is not too far in the future (allow 1 day for timezone differences)
        if v > now + timedelta(days=1):
            raise ValueError("Transaction date cannot be more than 1 day in the future")
        
        # Check if date is not too far in the past (financial records retention)
        if v < now - timedelta(days=365 * 7):  # 7 years for financial records
            raise ValueError("Transaction date cannot be more than 7 years in the past")
        
        # Check for suspicious future dates
        import logging
        logger = logging.getLogger(__name__)
        if v > now + timedelta(hours=12):
            logger.warning(f"Transaction with future date: {v}")
        
        return v
    
    @field_validator('confidence_score')
    @classmethod
    def validate_confidence_score(cls, v):
        if v is None:
            return v
        
        # Confidence score for OCR-processed transactions
        if not isinstance(v, (int, float)):
            raise ValueError("Confidence score must be a number")
        
        if v < 0.0 or v > 1.0:
            raise ValueError("Confidence score must be between 0.0 and 1.0")
        
        return round(float(v), 3)  # Round to 3 decimal places
    
    @field_validator('receipt_url')
    @classmethod
    def validate_receipt_url(cls, v):
        if v is None:
            return v
        
        # Basic URL validation for receipt images
        import re
        if not re.match(r'^https?://[^\s]+\.(jpg|jpeg|png|pdf)$', v.lower()):
            raise ValueError("Invalid receipt URL format (must be HTTPS with image/PDF extension)")
        
        return v


class TxnOut(BaseModel):
    """Enhanced transaction output schema"""

    id: str
    category: str
    amount: Decimal
    currency: str = "USD"
    description: Optional[str] = None
    merchant: Optional[str] = None
    location: Optional[str] = None
    tags: Optional[List[str]] = None
    spent_at: datetime
    is_recurring: bool = False
    confidence_score: Optional[float] = None
    receipt_url: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    # MODULE 5: Goal Integration
    goal_id: Optional[str] = None
    
    class Config:
        from_attributes = True
        json_encoders = {
            Decimal: lambda v: str(v)  # Keep precision by converting to string
        }


class TxnUpdate(BaseModel):
    """Schema for updating transactions"""
    
    amount: Optional[condecimal(max_digits=12, decimal_places=2, gt=0)] = None
    category: Optional[str] = Field(None, min_length=1, max_length=50)
    description: Optional[str] = Field(None, max_length=500)
    merchant: Optional[str] = Field(None, max_length=200)
    location: Optional[str] = Field(None, max_length=200)
    tags: Optional[List[str]] = Field(None, max_items=10)
    spent_at: Optional[datetime] = None
    is_recurring: Optional[bool] = None
    
    # Use the same validators as TxnIn for consistency
    validate_amount = field_validator('amount', mode='before')(TxnIn.validate_amount)
    validate_category = field_validator('category')(TxnIn.validate_category)
    validate_description = field_validator('description')(TxnIn.validate_description)
    validate_merchant = field_validator('merchant')(TxnIn.validate_merchant)
    validate_location = field_validator('location')(TxnIn.validate_location)
    validate_tags = field_validator('tags')(TxnIn.validate_tags)
    validate_spent_at = field_validator('spent_at')(TxnIn.validate_spent_at)


class BulkTxnIn(BaseModel):
    """Schema for bulk transaction import"""
    
    transactions: List[TxnIn] = Field(..., min_items=1, max_items=100)
    source: Optional[str] = Field(None, max_length=50, description="Import source (csv, ocr, etc.)")
    
    @field_validator('transactions')
    @classmethod
    def validate_transactions(cls, v):
        if len(v) > 100:
            raise ValueError("Cannot import more than 100 transactions at once")
        
        # Check for duplicate transactions within the batch
        seen = set()
        for txn in v:
            # Create a simple hash based on amount, category, and spent_at
            txn_hash = (txn.amount, txn.category, txn.spent_at.date() if txn.spent_at else None)
            if txn_hash in seen:
                raise ValueError("Duplicate transactions detected in batch")
            seen.add(txn_hash)
        
        return v
