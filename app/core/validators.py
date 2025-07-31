"""
Comprehensive Input Validation System
Provides robust validation for all API inputs to prevent errors and security issues
"""

import re
import logging
from typing import Any, Dict, List, Optional, Union, Callable
from datetime import datetime, date, timedelta
from decimal import Decimal, InvalidOperation
from email_validator import validate_email, EmailNotValidError
from fastapi import HTTPException, status
from pydantic import BaseModel, validator, Field
import bleach

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Custom validation error"""
    def __init__(self, message: str, field: str = None):
        self.message = message
        self.field = field
        super().__init__(self.message)


class InputSanitizer:
    """Input sanitization utilities"""
    
    # Allowed HTML tags for rich text fields (very restrictive)
    ALLOWED_TAGS = ['p', 'br', 'strong', 'em', 'u']
    ALLOWED_ATTRIBUTES = {}
    
    # SQL injection patterns
    SQL_INJECTION_PATTERNS = [
        r'(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|EXECUTE|UNION|SCRIPT)\b)',
        r'(--|;|/\*|\*/|xp_|sp_)',
        r'(\b(OR|AND)\s+\d+\s*=\s*\d+)',
        r'(\bUNION\s+(ALL\s+)?SELECT)',
    ]
    
    # XSS patterns
    XSS_PATTERNS = [
        r'<script[^>]*>.*?</script>',
        r'javascript:',
        r'on\w+\s*=',
        r'<iframe[^>]*>.*?</iframe>',
    ]
    
    @classmethod
    def sanitize_string(cls, value: str, max_length: int = None, allow_html: bool = False) -> str:
        """Sanitize string input"""
        if not isinstance(value, str):
            raise ValidationError(f"Expected string, got {type(value).__name__}")
        
        # Basic sanitization
        value = value.strip()
        
        if not value:
            return value
        
        # Length check
        if max_length and len(value) > max_length:
            raise ValidationError(f"String too long. Maximum length: {max_length}")
        
        # HTML sanitization
        if allow_html:
            value = bleach.clean(
                value, 
                tags=cls.ALLOWED_TAGS, 
                attributes=cls.ALLOWED_ATTRIBUTES,
                strip=True
            )
        else:
            # Remove all HTML tags
            value = bleach.clean(value, tags=[], attributes={}, strip=True)
        
        # Check for SQL injection patterns
        for pattern in cls.SQL_INJECTION_PATTERNS:
            if re.search(pattern, value, re.IGNORECASE):
                logger.warning(f"Potential SQL injection attempt blocked: {pattern}")
                raise ValidationError("Invalid characters detected in input")
        
        # Check for XSS patterns
        for pattern in cls.XSS_PATTERNS:
            if re.search(pattern, value, re.IGNORECASE):
                logger.warning(f"Potential XSS attempt blocked: {pattern}")
                raise ValidationError("Invalid characters detected in input")
        
        return value
    
    @classmethod
    def sanitize_email(cls, email: str) -> str:
        """Validate and sanitize email"""
        try:
            # Validate email format
            validated_email = validate_email(email)
            return validated_email.email.lower()
        except EmailNotValidError as e:
            raise ValidationError(f"Invalid email format: {str(e)}")
    
    @classmethod
    def sanitize_amount(cls, amount: Union[str, int, float, Decimal], min_value: float = 0) -> Decimal:
        """Validate and sanitize monetary amounts"""
        try:
            if isinstance(amount, str):
                # Remove currency symbols and spaces
                amount = re.sub(r'[^\d.-]', '', amount)
            
            decimal_amount = Decimal(str(amount))
            
            # Check for reasonable limits
            if decimal_amount < Decimal(str(min_value)):
                raise ValidationError(f"Amount must be at least {min_value}")
            
            if decimal_amount > Decimal('999999999.99'):
                raise ValidationError("Amount is too large")
            
            # Round to 2 decimal places
            return decimal_amount.quantize(Decimal('0.01'))
            
        except (InvalidOperation, ValueError) as e:
            raise ValidationError(f"Invalid amount format: {str(e)}")
    
    @classmethod
    def sanitize_date(cls, date_input: Union[str, date, datetime]) -> date:
        """Validate and sanitize date input"""
        if isinstance(date_input, date):
            return date_input
        
        if isinstance(date_input, datetime):
            return date_input.date()
        
        if isinstance(date_input, str):
            # Try multiple date formats
            date_formats = [
                '%Y-%m-%d',
                '%m/%d/%Y',
                '%d/%m/%Y',
                '%Y-%m-%d %H:%M:%S',
            ]
            
            for date_format in date_formats:
                try:
                    parsed_date = datetime.strptime(date_input, date_format).date()
                    
                    # Reasonable date range check
                    if parsed_date.year < 1900 or parsed_date.year > 2100:
                        raise ValidationError("Date is outside acceptable range")
                    
                    return parsed_date
                except ValueError:
                    continue
            
            raise ValidationError(f"Invalid date format: {date_input}")
        
        raise ValidationError(f"Invalid date type: {type(date_input)}")


class BaseValidator(BaseModel):
    """Base validator with common validation methods"""
    
    class Config:
        # Validate assignment to catch errors early
        validate_assignment = True
        # Allow extra fields but ignore them
        extra = "ignore"
        # Use enum values
        use_enum_values = True


class UserValidator(BaseValidator):
    """User input validation"""
    
    email: str = Field(..., min_length=5, max_length=255)
    password: Optional[str] = Field(None, min_length=8, max_length=128)
    name: Optional[str] = Field(None, max_length=100)
    country: Optional[str] = Field(None, min_length=2, max_length=2)
    annual_income: Optional[Decimal] = Field(None, ge=0, le=99999999.99)
    
    @validator('email')
    def validate_email(cls, v):
        return InputSanitizer.sanitize_email(v)
    
    @validator('password')
    def validate_password(cls, v):
        if v is None:
            return v
        
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        
        # Check for common patterns
        if v.lower() in ['password', '12345678', 'qwerty']:
            raise ValueError("Password is too common")
        
        # Require at least one number and one letter
        if not re.search(r'[A-Za-z]', v) or not re.search(r'\d', v):
            raise ValueError("Password must contain both letters and numbers")
        
        return v
    
    @validator('name')
    def validate_name(cls, v):
        if v is None:
            return v
        return InputSanitizer.sanitize_string(v, max_length=100)
    
    @validator('country')
    def validate_country(cls, v):
        if v is None:
            return v
        
        v = v.upper()
        # Basic country code validation (ISO 3166-1 alpha-2)
        if not re.match(r'^[A-Z]{2}$', v):
            raise ValueError("Country must be a 2-letter ISO code")
        
        return v


class TransactionValidator(BaseValidator):
    """Transaction input validation"""
    
    amount: Decimal = Field(..., gt=0, le=999999.99)
    category: str = Field(..., min_length=1, max_length=50)
    description: Optional[str] = Field(None, max_length=500)
    transaction_type: str = Field(..., regex=r'^(income|expense)$')
    spent_at: Optional[datetime] = None
    
    @validator('amount')
    def validate_amount(cls, v):
        return InputSanitizer.sanitize_amount(v, min_value=0.01)
    
    @validator('category')
    def validate_category(cls, v):
        # Allowed categories (can be moved to config)
        allowed_categories = {
            'food', 'transport', 'entertainment', 'shopping', 'utilities',
            'healthcare', 'education', 'travel', 'fitness', 'other'
        }
        
        sanitized = InputSanitizer.sanitize_string(v, max_length=50).lower()
        
        if sanitized not in allowed_categories:
            raise ValueError(f"Invalid category. Allowed: {', '.join(allowed_categories)}")
        
        return sanitized
    
    @validator('description')
    def validate_description(cls, v):
        if v is None:
            return v
        return InputSanitizer.sanitize_string(v, max_length=500)
    
    @validator('spent_at')
    def validate_spent_at(cls, v):
        if v is None:
            return datetime.now()
        
        # Check if date is not too far in the future
        if v > datetime.now() + timedelta(days=1):
            raise ValueError("Transaction date cannot be more than 1 day in the future")
        
        # Check if date is not too far in the past
        if v < datetime.now() - timedelta(days=365 * 5):
            raise ValueError("Transaction date cannot be more than 5 years in the past")
        
        return v


class GoalValidator(BaseValidator):
    """Goal input validation"""
    
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    category: str = Field(..., min_length=1, max_length=50)
    target_amount: Optional[Decimal] = Field(None, gt=0, le=999999999.99)
    target_date: Optional[date] = None
    
    @validator('title')
    def validate_title(cls, v):
        return InputSanitizer.sanitize_string(v, max_length=200)
    
    @validator('description')
    def validate_description(cls, v):
        if v is None:
            return v
        return InputSanitizer.sanitize_string(v, max_length=1000, allow_html=True)
    
    @validator('category')
    def validate_category(cls, v):
        allowed_categories = {
            'savings', 'debt_payoff', 'investment', 'purchase', 'travel', 
            'education', 'emergency_fund', 'retirement', 'other'
        }
        
        sanitized = InputSanitizer.sanitize_string(v, max_length=50).lower()
        
        if sanitized not in allowed_categories:
            raise ValueError(f"Invalid goal category. Allowed: {', '.join(allowed_categories)}")
        
        return sanitized
    
    @validator('target_date')
    def validate_target_date(cls, v):
        if v is None:
            return v
        
        target_date = InputSanitizer.sanitize_date(v)
        
        # Target date should be in the future
        if target_date <= date.today():
            raise ValueError("Target date must be in the future")
        
        # Reasonable limit - 10 years in the future
        if target_date > date.today() + timedelta(days=365 * 10):
            raise ValueError("Target date cannot be more than 10 years in the future")
        
        return target_date


class ValidationMiddleware:
    """Middleware for automatic request validation"""
    
    def __init__(self):
        self.validators = {
            'user': UserValidator,
            'transaction': TransactionValidator,
            'goal': GoalValidator,
        }
    
    def validate_request(self, request_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate request data based on type"""
        if request_type not in self.validators:
            raise ValidationError(f"Unknown request type: {request_type}")
        
        validator_class = self.validators[request_type]
        
        try:
            validated_data = validator_class(**data)
            return validated_data.dict(exclude_unset=True)
        except ValueError as e:
            raise ValidationError(f"Validation error: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected validation error for {request_type}: {str(e)}")
            raise ValidationError("Invalid request data")


# Global validator instance
validator = ValidationMiddleware()


def validate_request_data(request_type: str):
    """Decorator for automatic request validation"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Extract request data from kwargs
            if 'data' in kwargs:
                try:
                    validated_data = validator.validate_request(request_type, kwargs['data'])
                    kwargs['data'] = validated_data
                except ValidationError as e:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Validation error: {e.message}"
                    )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator


def sanitize_search_query(query: str, max_length: int = 100) -> str:
    """Sanitize search queries to prevent injection attacks"""
    if not query:
        return ""
    
    # Remove potentially dangerous characters
    sanitized = re.sub(r'[<>"\';\\%_]', '', query)
    
    # Limit length
    sanitized = sanitized[:max_length]
    
    # Remove extra whitespace
    sanitized = ' '.join(sanitized.split())
    
    return InputSanitizer.sanitize_string(sanitized, max_length=max_length)


def validate_pagination_params(page: int = 1, per_page: int = 20) -> tuple[int, int]:
    """Validate pagination parameters"""
    if page < 1:
        page = 1
    
    if per_page < 1:
        per_page = 20
    elif per_page > 100:  # Limit to prevent large result sets
        per_page = 100
    
    return page, per_page