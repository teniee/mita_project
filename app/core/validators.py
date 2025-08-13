"""
Comprehensive Input Validation System for MITA Financial Application
Provides robust validation for all API inputs to prevent errors and security issues.
Focuses on financial data integrity, security, and compliance requirements.
"""

import re
import logging
from typing import Any, Dict, List, Optional, Union, Callable, Set
from datetime import datetime, date, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from email_validator import validate_email, EmailNotValidError
from fastapi import HTTPException, status
from pydantic import BaseModel, validator, Field, field_validator, ValidationError as PydanticValidationError
from pydantic import condecimal
import bleach
import pycountry
import phonenumbers
from phonenumbers.phonenumberutil import NumberParseException

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Custom validation error"""
    def __init__(self, message: str, field: str = None):
        self.message = message
        self.field = field
        super().__init__(self.message)


# Financial application constants
class FinancialConstants:
    """Constants for financial validation in MITA application"""
    
    # Currency configurations
    SUPPORTED_CURRENCIES = {"USD"}  # Currently US-only, expandable for international
    DEFAULT_CURRENCY = "USD"
    
    # Financial limits (in USD)
    MIN_TRANSACTION_AMOUNT = Decimal("0.01")
    MAX_TRANSACTION_AMOUNT = Decimal("999999.99")
    MIN_ANNUAL_INCOME = Decimal("0.00")
    MAX_ANNUAL_INCOME = Decimal("99999999.99")
    MIN_BUDGET_AMOUNT = Decimal("0.01")
    MAX_BUDGET_AMOUNT = Decimal("9999999.99")
    MIN_GOAL_AMOUNT = Decimal("1.00")
    MAX_GOAL_AMOUNT = Decimal("99999999.99")
    
    # Geographic constraints (US-only for now)
    SUPPORTED_COUNTRIES = {"US"}
    US_STATES = {
        "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
        "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
        "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
        "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
        "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY", "DC"
    }
    
    # Transaction categories for strict validation
    VALID_TRANSACTION_CATEGORIES = {
        'food', 'dining', 'groceries', 'transportation', 'gas', 'public_transport',
        'entertainment', 'shopping', 'clothing', 'healthcare', 'insurance',
        'utilities', 'rent', 'mortgage', 'education', 'childcare', 'pets',
        'travel', 'subscriptions', 'gifts', 'charity', 'income', 'other'
    }
    
    # Goal categories
    VALID_GOAL_CATEGORIES = {
        'savings', 'debt_payoff', 'investment', 'purchase', 'travel',
        'education', 'emergency_fund', 'retirement', 'healthcare', 'other'
    }


class InputSanitizer:
    """Enhanced input sanitization utilities for financial application security"""
    
    # Allowed HTML tags for rich text fields (very restrictive for financial app)
    ALLOWED_TAGS = ['p', 'br', 'strong', 'em', 'u']
    ALLOWED_ATTRIBUTES = {}
    
    # Enhanced SQL injection patterns for financial applications
    SQL_INJECTION_PATTERNS = [
        r'(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|EXECUTE|UNION|SCRIPT)\b)',
        r'(--|;|/\*|\*/|xp_|sp_)',
        r'(\b(OR|AND)\s+\d+\s*=\s*\d+)',
        r'(\bUNION\s+(ALL\s+)?SELECT)',
        r'(\bDROP\s+TABLE)',
        r'(\bTRUNCATE\s+TABLE)',
        r'(\bDELETE\s+FROM)',
        r'(\bSHUTDOWN\b)',
    ]
    
    # Enhanced XSS patterns for financial applications
    XSS_PATTERNS = [
        r'<script[^>]*>.*?</script>',
        r'javascript:',
        r'on\w+\s*=',
        r'<iframe[^>]*>.*?</iframe>',
        r'<object[^>]*>.*?</object>',
        r'<embed[^>]*>.*?</embed>',
        r'<link[^>]*>.*?</link>',
        r'<meta[^>]*>.*?</meta>',
        r'data:text/html',
        r'vbscript:',
    ]
    
    # Financial data patterns that should be blocked
    FINANCIAL_INJECTION_PATTERNS = [
        r'(\$\{[^}]*\})',  # Template injection
        r'(#{[^}]*})',      # Expression injection
        r'(\{\{[^}]*\}\})', # Template syntax
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
        
        # Check for financial injection patterns
        for pattern in cls.FINANCIAL_INJECTION_PATTERNS:
            if re.search(pattern, value, re.IGNORECASE):
                logger.warning(f"Potential template injection blocked: {pattern}")
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
    def sanitize_amount(cls, amount: Union[str, int, float, Decimal], 
                       min_value: Optional[Decimal] = None, 
                       max_value: Optional[Decimal] = None,
                       field_name: str = "amount") -> Decimal:
        """
        Validate and sanitize monetary amounts with precise decimal handling.
        Ensures financial precision and prevents floating-point errors.
        """
        try:
            if amount is None:
                raise ValidationError(f"{field_name} is required")
            
            # Handle string input with currency symbols
            if isinstance(amount, str):
                # Remove common currency symbols and whitespace
                cleaned_amount = re.sub(r'[\$£€¥₹,\s]', '', amount)
                # Ensure only valid decimal characters remain
                if not re.match(r'^-?\d*\.?\d+$', cleaned_amount):
                    raise ValidationError(f"Invalid {field_name} format")
                amount = cleaned_amount
            
            # Convert to Decimal for precise financial calculations
            decimal_amount = Decimal(str(amount))
            
            # Set default limits if not provided
            if min_value is None:
                min_value = FinancialConstants.MIN_TRANSACTION_AMOUNT
            if max_value is None:
                max_value = FinancialConstants.MAX_TRANSACTION_AMOUNT
            
            # Validate against limits
            if decimal_amount < min_value:
                raise ValidationError(f"{field_name} must be at least ${min_value}")
            
            if decimal_amount > max_value:
                raise ValidationError(f"{field_name} cannot exceed ${max_value}")
            
            # Round to 2 decimal places using banker's rounding for financial accuracy
            quantized_amount = decimal_amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            
            # Additional validation for suspicious patterns
            if decimal_amount != quantized_amount and abs(decimal_amount - quantized_amount) > Decimal('0.001'):
                logger.warning(f"Suspicious precision in {field_name}: {decimal_amount}")
            
            return quantized_amount
            
        except (InvalidOperation, ValueError) as e:
            raise ValidationError(f"Invalid {field_name} format: {str(e)}")
    
    @classmethod
    def sanitize_currency_code(cls, currency: str) -> str:
        """Validate currency code against supported currencies"""
        if not currency:
            return FinancialConstants.DEFAULT_CURRENCY
        
        currency = currency.upper().strip()
        
        if currency not in FinancialConstants.SUPPORTED_CURRENCIES:
            raise ValidationError(
                f"Unsupported currency: {currency}. "
                f"Supported currencies: {', '.join(FinancialConstants.SUPPORTED_CURRENCIES)}"
            )
        
        return currency
    
    @classmethod
    def sanitize_country_code(cls, country: str) -> str:
        """Validate country code for US-only operations"""
        if not country:
            raise ValidationError("Country code is required")
        
        country = country.upper().strip()
        
        # Validate format
        if len(country) != 2:
            raise ValidationError("Country code must be 2 characters")
        
        # Currently only support US
        if country not in FinancialConstants.SUPPORTED_COUNTRIES:
            raise ValidationError(
                f"Service not available in {country}. "
                f"Currently available in: {', '.join(FinancialConstants.SUPPORTED_COUNTRIES)}"
            )
        
        return country
    
    @classmethod
    def sanitize_state_code(cls, state: str, country: str = "US") -> str:
        """Validate US state code"""
        if not state:
            raise ValidationError("State code is required")
        
        state = state.upper().strip()
        
        if country == "US":
            if state not in FinancialConstants.US_STATES:
                raise ValidationError(f"Invalid US state code: {state}")
        
        return state
    
    @classmethod
    def sanitize_zip_code(cls, zip_code: str, country: str = "US") -> str:
        """Validate ZIP code format"""
        if not zip_code:
            raise ValidationError("ZIP code is required")
        
        zip_code = zip_code.strip()
        
        if country == "US":
            # US ZIP code formats: 12345 or 12345-6789
            if not re.match(r'^\d{5}(-\d{4})?$', zip_code):
                raise ValidationError("Invalid US ZIP code format (use 12345 or 12345-6789)")
        
        return zip_code
    
    @classmethod
    def sanitize_phone_number(cls, phone: str, country: str = "US") -> str:
        """Validate and format phone number"""
        if not phone:
            raise ValidationError("Phone number is required")
        
        try:
            # Parse phone number with country context
            country_code = "US" if country == "US" else None
            parsed_number = phonenumbers.parse(phone, country_code)
            
            # Validate the number
            if not phonenumbers.is_valid_number(parsed_number):
                raise ValidationError("Invalid phone number")
            
            # Format as E164 for storage
            formatted_number = phonenumbers.format_number(
                parsed_number, phonenumbers.PhoneNumberFormat.E164
            )
            
            return formatted_number
            
        except NumberParseException as e:
            raise ValidationError(f"Invalid phone number format: {str(e)}")
    
    @classmethod
    def sanitize_transaction_category(cls, category: str) -> str:
        """Validate transaction category against allowed values"""
        if not category:
            raise ValidationError("Transaction category is required")
        
        category = category.lower().strip()
        
        if category not in FinancialConstants.VALID_TRANSACTION_CATEGORIES:
            raise ValidationError(
                f"Invalid transaction category: {category}. "
                f"Valid categories: {', '.join(sorted(FinancialConstants.VALID_TRANSACTION_CATEGORIES))}"
            )
        
        return category
    
    @classmethod
    def sanitize_goal_category(cls, category: str) -> str:
        """Validate goal category against allowed values"""
        if not category:
            raise ValidationError("Goal category is required")
        
        category = category.lower().strip()
        
        if category not in FinancialConstants.VALID_GOAL_CATEGORIES:
            raise ValidationError(
                f"Invalid goal category: {category}. "
                f"Valid categories: {', '.join(sorted(FinancialConstants.VALID_GOAL_CATEGORIES))}"
            )
        
        return category
    
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


# Enhanced Pydantic Validators for MITA Financial Application

class EnhancedUserValidator(BaseValidator):
    """Enhanced user input validation with financial application security"""
    
    email: str = Field(..., min_length=5, max_length=255, description="User email address")
    password: Optional[str] = Field(None, min_length=8, max_length=128, description="User password")
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="User full name")
    country: Optional[str] = Field(None, min_length=2, max_length=2, description="Country code (US only)")
    state: Optional[str] = Field(None, min_length=2, max_length=2, description="State code")
    zip_code: Optional[str] = Field(None, min_length=5, max_length=10, description="ZIP code")
    phone: Optional[str] = Field(None, min_length=10, max_length=20, description="Phone number")
    annual_income: Optional[condecimal(max_digits=10, decimal_places=2, ge=0)] = Field(
        None, description="Annual income in USD"
    )
    timezone: Optional[str] = Field(None, min_length=3, max_length=50, description="User timezone")
    
    @field_validator('email')
    @classmethod
    def validate_email(cls, v):
        if not v:
            raise ValueError("Email is required")
        return InputSanitizer.sanitize_email(v)
    
    @field_validator('password')
    @classmethod
    def validate_password(cls, v):
        if v is None:
            return v
        
        # Enhanced password validation for financial applications
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        
        if len(v) > 128:
            raise ValueError("Password cannot exceed 128 characters")
        
        # Check for common weak passwords
        common_passwords = {
            'password', '12345678', 'qwerty', 'password123', 'admin', 
            'letmein', 'welcome', 'monkey', 'dragon', 'password1'
        }
        if v.lower() in common_passwords:
            raise ValueError("Password is too common, please choose a stronger password")
        
        # Security requirements for financial app
        has_lower = any(c.islower() for c in v)
        has_upper = any(c.isupper() for c in v)
        has_digit = any(c.isdigit() for c in v)
        has_special = any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?' for c in v)
        
        if not (has_lower and has_upper and has_digit):
            raise ValueError(
                "Password must contain at least one uppercase letter, "
                "one lowercase letter, and one number"
            )
        
        # Check for repeated characters (potential security risk)
        if re.search(r'(.)\1{3,}', v):
            raise ValueError("Password cannot contain more than 3 consecutive identical characters")
        
        # Check for common patterns
        if re.search(r'(123|abc|qwe)', v.lower()):
            raise ValueError("Password cannot contain common patterns")
        
        return v
    
    @field_validator('name')
    @classmethod
    def validate_name(cls, v):
        if v is None:
            return v
        
        # Enhanced name validation for financial compliance
        sanitized_name = InputSanitizer.sanitize_string(v, max_length=100)
        
        # Check for valid name format
        if not re.match(r'^[A-Za-z\s\-\.\']+$', sanitized_name):
            raise ValueError("Name can only contain letters, spaces, hyphens, periods, and apostrophes")
        
        # Check for minimum length
        if len(sanitized_name.strip()) < 2:
            raise ValueError("Name must be at least 2 characters long")
        
        # Check for suspicious patterns
        if re.search(r'\d', sanitized_name):
            raise ValueError("Name cannot contain numbers")
        
        # Check for excessive punctuation
        punct_count = sum(1 for c in sanitized_name if c in '-.\' ')
        if punct_count / len(sanitized_name) > 0.3:
            raise ValueError("Name contains excessive punctuation")
        
        return sanitized_name.title()  # Proper case formatting
    
    @field_validator('country')
    @classmethod
    def validate_country(cls, v):
        if v is None:
            return "US"  # Default to US
        
        return InputSanitizer.sanitize_country_code(v)
    
    @field_validator('state')
    @classmethod
    def validate_state(cls, v, info):
        if v is None:
            return v
        
        # Get country from context if available
        country = info.data.get('country', 'US') if info.data else 'US'
        return InputSanitizer.sanitize_state_code(v, country)
    
    @field_validator('zip_code')
    @classmethod
    def validate_zip_code(cls, v, info):
        if v is None:
            return v
        
        # Get country from context if available
        country = info.data.get('country', 'US') if info.data else 'US'
        return InputSanitizer.sanitize_zip_code(v, country)
    
    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v, info):
        if v is None:
            return v
        
        # Get country from context if available
        country = info.data.get('country', 'US') if info.data else 'US'
        return InputSanitizer.sanitize_phone_number(v, country)
    
    @field_validator('annual_income')
    @classmethod
    def validate_annual_income(cls, v):
        if v is None:
            return v
        
        return InputSanitizer.sanitize_amount(
            v, 
            min_value=FinancialConstants.MIN_ANNUAL_INCOME,
            max_value=FinancialConstants.MAX_ANNUAL_INCOME,
            field_name="annual income"
        )
    
    @field_validator('timezone')
    @classmethod
    def validate_timezone(cls, v):
        if v is None:
            return "UTC"
        
        # Basic timezone validation
        v = InputSanitizer.sanitize_string(v, max_length=50)
        
        # Common timezone formats
        valid_timezone_pattern = r'^[A-Za-z_/\-+0-9]+$'
        if not re.match(valid_timezone_pattern, v):
            raise ValueError("Invalid timezone format")
        
        return v


class EnhancedTransactionValidator(BaseValidator):
    """Enhanced transaction input validation for financial precision"""
    
    amount: condecimal(max_digits=12, decimal_places=2, gt=0) = Field(
        ..., description="Transaction amount with precise decimal handling"
    )
    category: str = Field(..., min_length=1, max_length=50, description="Transaction category")
    description: Optional[str] = Field(None, max_length=500, description="Transaction description")
    currency: Optional[str] = Field(None, min_length=3, max_length=3, description="Currency code")
    merchant: Optional[str] = Field(None, max_length=200, description="Merchant name")
    location: Optional[str] = Field(None, max_length=200, description="Transaction location")
    tags: Optional[List[str]] = Field(None, max_items=10, description="Transaction tags")
    spent_at: Optional[datetime] = Field(None, description="Transaction date and time")
    is_recurring: Optional[bool] = Field(False, description="Is this a recurring transaction")
    confidence_score: Optional[float] = Field(None, ge=0.0, le=1.0, description="OCR confidence score")
    
    @field_validator('amount')
    @classmethod
    def validate_amount(cls, v):
        return InputSanitizer.sanitize_amount(
            v, 
            min_value=FinancialConstants.MIN_TRANSACTION_AMOUNT,
            max_value=FinancialConstants.MAX_TRANSACTION_AMOUNT,
            field_name="transaction amount"
        )
    
    @field_validator('category')
    @classmethod
    def validate_category(cls, v):
        return InputSanitizer.sanitize_transaction_category(v)
    
    @field_validator('description')
    @classmethod
    def validate_description(cls, v):
        if v is None:
            return v
        
        # Enhanced description validation for financial transactions
        sanitized = InputSanitizer.sanitize_string(v, max_length=500)
        
        # Check for suspicious patterns in descriptions
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
        now = datetime.utcnow()
        
        # Check if date is not too far in the future (allow 1 day for timezone differences)
        if v > now + timedelta(days=1):
            raise ValueError("Transaction date cannot be more than 1 day in the future")
        
        # Check if date is not too far in the past (financial records retention)
        if v < now - timedelta(days=365 * 7):  # 7 years for financial records
            raise ValueError("Transaction date cannot be more than 7 years in the past")
        
        # Check for suspicious future dates
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


class EnhancedBudgetValidator(BaseValidator):
    """Enhanced budget input validation for financial planning"""
    
    period: str = Field(..., pattern=r'^(monthly|weekly|yearly)$', description="Budget period")
    category: str = Field(..., min_length=1, max_length=50, description="Budget category")
    amount: condecimal(max_digits=12, decimal_places=2, gt=0) = Field(
        ..., description="Budget amount with precise decimal handling"
    )
    currency: Optional[str] = Field(None, min_length=3, max_length=3, description="Currency code")
    description: Optional[str] = Field(None, max_length=500, description="Budget description")
    start_date: Optional[date] = Field(None, description="Budget start date")
    end_date: Optional[date] = Field(None, description="Budget end date")
    is_flexible: Optional[bool] = Field(True, description="Can budget be adjusted automatically")
    priority: Optional[int] = Field(1, ge=1, le=5, description="Budget priority (1-5)")
    
    @field_validator('amount')
    @classmethod
    def validate_amount(cls, v):
        return InputSanitizer.sanitize_amount(
            v,
            min_value=FinancialConstants.MIN_BUDGET_AMOUNT,
            max_value=FinancialConstants.MAX_BUDGET_AMOUNT,
            field_name="budget amount"
        )
    
    @field_validator('category')
    @classmethod
    def validate_category(cls, v):
        return InputSanitizer.sanitize_transaction_category(v)
    
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
    
    @field_validator('start_date')
    @classmethod
    def validate_start_date(cls, v):
        if v is None:
            return date.today()
        
        start_date = InputSanitizer.sanitize_date(v)
        
        # Budget start date validation
        if start_date < date.today() - timedelta(days=30):
            raise ValueError("Budget start date cannot be more than 30 days in the past")
        
        if start_date > date.today() + timedelta(days=365):
            raise ValueError("Budget start date cannot be more than 1 year in the future")
        
        return start_date
    
    @field_validator('end_date')
    @classmethod
    def validate_end_date(cls, v, info):
        if v is None:
            return v
        
        end_date = InputSanitizer.sanitize_date(v)
        start_date = info.data.get('start_date', date.today()) if info.data else date.today()
        
        # End date must be after start date
        if end_date <= start_date:
            raise ValueError("Budget end date must be after start date")
        
        # Reasonable limit for budget duration
        if end_date > start_date + timedelta(days=365 * 5):
            raise ValueError("Budget duration cannot exceed 5 years")
        
        return end_date


class EnhancedGoalValidator(BaseValidator):
    """Enhanced goal input validation for financial planning"""
    
    title: str = Field(..., min_length=1, max_length=200, description="Goal title")
    description: Optional[str] = Field(None, max_length=1000, description="Goal description")
    category: str = Field(..., min_length=1, max_length=50, description="Goal category")
    target_amount: condecimal(max_digits=12, decimal_places=2, gt=0) = Field(
        ..., description="Target amount with precise decimal handling"
    )
    current_amount: Optional[condecimal(max_digits=12, decimal_places=2, ge=0)] = Field(
        None, description="Current progress amount"
    )
    currency: Optional[str] = Field(None, min_length=3, max_length=3, description="Currency code")
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


class EnhancedValidationMiddleware:
    """Enhanced middleware for comprehensive request validation with security monitoring"""
    
    def __init__(self):
        self.validators = {
            'user': EnhancedUserValidator,
            'transaction': EnhancedTransactionValidator,
            'goal': EnhancedGoalValidator,
            'budget': EnhancedBudgetValidator,
            # Legacy support
            'user_legacy': UserValidator,
            'transaction_legacy': TransactionValidator,
            'goal_legacy': GoalValidator,
        }
        self.security_events = []
    
    def validate_request(self, request_type: str, data: Dict[str, Any], 
                        user_id: str = None, ip_address: str = None) -> Dict[str, Any]:
        """
        Validate request data with comprehensive security monitoring.
        
        Args:
            request_type: Type of validation to perform
            data: Request data to validate
            user_id: ID of the user making the request
            ip_address: IP address of the request
            
        Returns:
            Validated and sanitized data
            
        Raises:
            ValidationError: If validation fails
        """
        if request_type not in self.validators:
            self._log_security_event(
                event_type="invalid_validation_type",
                details={"request_type": request_type},
                user_id=user_id,
                ip_address=ip_address
            )
            raise ValidationError(f"Unknown request type: {request_type}")
        
        validator_class = self.validators[request_type]
        
        try:
            # Pre-validation security checks
            self._pre_validation_security_check(data, user_id, ip_address)
            
            # Perform validation
            validated_data = validator_class(**data)
            validated_dict = validated_data.model_dump(exclude_unset=True)
            
            # Post-validation security checks
            self._post_validation_security_check(validated_dict, user_id, ip_address)
            
            # Log successful validation for audit
            logger.info(
                f"Successful validation for {request_type}",
                extra={
                    "user_id": user_id,
                    "request_type": request_type,
                    "data_keys": list(data.keys()) if data else [],
                    "ip_address": ip_address
                }
            )
            
            return validated_dict
            
        except PydanticValidationError as e:
            # Log detailed validation errors for security monitoring
            error_details = {
                "validation_errors": [
                    {"field": error["loc"], "message": error["msg"]}
                    for error in e.errors()
                ],
                "request_type": request_type,
                "data_preview": {k: str(v)[:50] for k, v in (data or {}).items()}
            }
            
            self._log_security_event(
                event_type="validation_failure",
                details=error_details,
                user_id=user_id,
                ip_address=ip_address
            )
            
            # Return user-friendly error message
            user_errors = []
            for error in e.errors():
                field = '.'.join(str(loc) for loc in error['loc'])
                message = error['msg']
                user_errors.append(f"{field}: {message}")
            
            raise ValidationError(f"Validation failed: {'; '.join(user_errors)}")
            
        except ValueError as e:
            self._log_security_event(
                event_type="value_error",
                details={"error": str(e), "request_type": request_type},
                user_id=user_id,
                ip_address=ip_address
            )
            raise ValidationError(f"Validation error: {str(e)}")
            
        except Exception as e:
            # Log unexpected errors for investigation
            logger.error(
                f"Unexpected validation error for {request_type}: {str(e)}",
                extra={
                    "user_id": user_id,
                    "request_type": request_type,
                    "ip_address": ip_address,
                    "error_type": type(e).__name__
                }
            )
            self._log_security_event(
                event_type="unexpected_error",
                details={"error": str(e), "error_type": type(e).__name__},
                user_id=user_id,
                ip_address=ip_address
            )
            raise ValidationError("Invalid request data")
    
    def _pre_validation_security_check(self, data: Dict[str, Any], 
                                     user_id: str = None, ip_address: str = None):
        """Perform security checks before validation"""
        if not data:
            return
        
        # Check for suspicious data patterns
        data_str = str(data).lower()
        
        # Check for potential injection attempts
        injection_patterns = [
            r'<script', r'javascript:', r'on\w+\s*=', r'eval\s*\(',
            r'exec\s*\(', r'system\s*\(', r'union\s+select',
            r'drop\s+table', r'insert\s+into', r'delete\s+from'
        ]
        
        for pattern in injection_patterns:
            if re.search(pattern, data_str):
                self._log_security_event(
                    event_type="potential_injection",
                    details={
                        "pattern": pattern,
                        "data_preview": data_str[:200]
                    },
                    user_id=user_id,
                    ip_address=ip_address,
                    severity="high"
                )
                break
        
        # Check for excessive data size
        if len(str(data)) > 50000:  # 50KB limit
            self._log_security_event(
                event_type="large_request",
                details={"data_size": len(str(data))},
                user_id=user_id,
                ip_address=ip_address
            )
    
    def _post_validation_security_check(self, validated_data: Dict[str, Any], 
                                      user_id: str = None, ip_address: str = None):
        """Perform security checks after validation"""
        # Check for unusual financial amounts
        for key, value in validated_data.items():
            if key.endswith('_amount') or key.endswith('amount'):
                if isinstance(value, (int, float, Decimal)):
                    amount = Decimal(str(value))
                    
                    # Flag unusually large amounts
                    if amount > Decimal('100000'):  # $100,000
                        self._log_security_event(
                            event_type="large_amount",
                            details={
                                "field": key,
                                "amount": str(amount)
                            },
                            user_id=user_id,
                            ip_address=ip_address
                        )
                    
                    # Flag unusual precision (more than 2 decimal places)
                    if '.' in str(amount) and len(str(amount).split('.')[1]) > 2:
                        self._log_security_event(
                            event_type="unusual_precision",
                            details={
                                "field": key,
                                "amount": str(amount)
                            },
                            user_id=user_id,
                            ip_address=ip_address
                        )
    
    def _log_security_event(self, event_type: str, details: Dict[str, Any],
                          user_id: str = None, ip_address: str = None,
                          severity: str = "medium"):
        """Log security events for monitoring and analysis"""
        security_event = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type,
            "severity": severity,
            "user_id": user_id,
            "ip_address": ip_address,
            "details": details
        }
        
        self.security_events.append(security_event)
        
        # Log to application logger
        logger.warning(
            f"Security event: {event_type}",
            extra=security_event
        )
        
        # In production, this could also send to SIEM or security monitoring system
    
    def get_security_events(self, since: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """Get security events for analysis"""
        if since is None:
            return self.security_events.copy()
        
        return [
            event for event in self.security_events
            if datetime.fromisoformat(event["timestamp"]) >= since
        ]
    
    def clear_security_events(self):
        """Clear security events (for testing or maintenance)"""
        self.security_events.clear()


# Global enhanced validator instance
enhanced_validator = EnhancedValidationMiddleware()

# Legacy support
validator = ValidationMiddleware()


def validate_request_data(request_type: str, enhanced: bool = True):
    """Decorator for enhanced automatic request validation with security monitoring"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Extract request data, user, and IP from various sources
            data = kwargs.get('data')
            user_id = None
            ip_address = None
            
            # Try to extract user ID from different possible sources
            if 'user' in kwargs:
                user_id = getattr(kwargs['user'], 'id', str(kwargs['user']))
            elif 'current_user' in kwargs:
                user_id = getattr(kwargs['current_user'], 'id', str(kwargs['current_user']))
            
            # Try to extract IP address from request
            if 'request' in kwargs:
                ip_address = kwargs['request'].client.host
            
            # Validate the request data
            if data:
                try:
                    validation_middleware = enhanced_validator if enhanced else validator
                    
                    if enhanced:
                        validated_data = validation_middleware.validate_request(
                            request_type, data, user_id=user_id, ip_address=ip_address
                        )
                    else:
                        validated_data = validation_middleware.validate_request(request_type, data)
                    
                    kwargs['data'] = validated_data
                    
                except ValidationError as e:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Validation error: {e.message}"
                    )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator


# Convenience functions for common validation patterns
def validate_financial_amount(amount: Union[str, int, float, Decimal], 
                            field_name: str = "amount",
                            min_value: Optional[Decimal] = None,
                            max_value: Optional[Decimal] = None) -> Decimal:
    """Validate financial amount with proper error handling"""
    return InputSanitizer.sanitize_amount(amount, min_value, max_value, field_name)


def validate_user_input(data: Dict[str, Any], 
                       user_id: str = None, 
                       ip_address: str = None) -> Dict[str, Any]:
    """Validate user registration/update input"""
    return enhanced_validator.validate_request('user', data, user_id, ip_address)


def validate_transaction_input(data: Dict[str, Any], 
                             user_id: str = None, 
                             ip_address: str = None) -> Dict[str, Any]:
    """Validate transaction input"""
    return enhanced_validator.validate_request('transaction', data, user_id, ip_address)


def validate_goal_input(data: Dict[str, Any], 
                       user_id: str = None, 
                       ip_address: str = None) -> Dict[str, Any]:
    """Validate goal input"""
    return enhanced_validator.validate_request('goal', data, user_id, ip_address)


def validate_budget_input(data: Dict[str, Any], 
                         user_id: str = None, 
                         ip_address: str = None) -> Dict[str, Any]:
    """Validate budget input"""
    return enhanced_validator.validate_request('budget', data, user_id, ip_address)


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