from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, field_validator, condecimal


class FastRegisterIn(BaseModel):
    """Lightweight registration schema optimized for performance"""
    
    email: str = Field(..., min_length=5, max_length=255, description="User email address")
    password: str = Field(..., min_length=8, max_length=128, description="User password")
    country: str = Field("US", min_length=2, max_length=3, description="Country code")
    annual_income: Optional[float] = Field(0.0, ge=0, le=10000000, description="Annual income")
    timezone: str = Field("UTC", min_length=1, max_length=50, description="User timezone")
    
    @field_validator('email')
    @classmethod
    def validate_email(cls, v):
        # Fast email validation - no heavy sanitization
        if '@' not in v or '.' not in v.split('@')[1]:
            raise ValueError("Invalid email format")
        return v.lower().strip()
    
    @field_validator('password')
    @classmethod
    def validate_password(cls, v):
        # Minimal password validation for speed
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class RegisterIn(BaseModel):
    """Enhanced user registration schema with comprehensive validation"""
    
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=8, max_length=128, description="User password")
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="User full name")
    country: str = Field("US", min_length=2, max_length=2, description="Country code (US only)")
    state: Optional[str] = Field(None, min_length=2, max_length=2, description="State code")
    zip_code: Optional[str] = Field(None, min_length=5, max_length=10, description="ZIP code")
    phone: Optional[str] = Field(None, min_length=10, max_length=20, description="Phone number")
    annual_income: condecimal(max_digits=10, decimal_places=2, ge=0) = Field(
        Decimal('0.00'), description="Annual income in USD"
    )
    timezone: str = Field("UTC", min_length=3, max_length=50, description="User timezone")
    
    @field_validator('email')
    @classmethod
    def validate_email(cls, v):
        if not v:
            raise ValueError("Email is required")
        # RESTORED: Optimized input validation
        # return InputSanitizer.sanitize_email(v)
        # Fast basic email validation without external dependencies
        if '@' not in v or '.' not in v.split('@')[1]:
            raise ValueError("Invalid email format")
        return v.lower().strip()
    
    @field_validator('password')
    @classmethod
    def validate_password(cls, v):
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
        
        if not (has_lower and has_upper and has_digit):
            raise ValueError(
                "Password must contain at least one uppercase letter, "
                "one lowercase letter, and one number"
            )
        
        # Check for repeated characters (potential security risk)
        import re
        if re.search(r'(.)\1{3,}', v):
            raise ValueError("Password cannot contain more than 3 consecutive identical characters")
        
        # Check for very weak patterns only (production-friendly)
        if re.search(r'(12345|abcde|qwerty)', v.lower()):
            raise ValueError("Password is too weak, please choose a stronger password")
        
        return v
    
    @field_validator('name')
    @classmethod
    def validate_name(cls, v):
        if v is None:
            return v
        
        # RESTORED: Optimized input validation
        # sanitized_name = InputSanitizer.sanitize_string(v, max_length=100)
        # Basic name validation without external dependencies
        v = v.strip()
        if len(v) > 100:
            raise ValueError("Name too long")
        
        # Check for valid name format
        import re
        if not re.match(r'^[A-Za-z\s\-\.\']+$', v):
            raise ValueError("Name can only contain letters, spaces, hyphens, periods, and apostrophes")
        
        # Check for minimum length
        if len(v) < 2:
            raise ValueError("Name must be at least 2 characters long")
        
        return v.title()
    
    @field_validator('country')
    @classmethod
    def validate_country(cls, v):
        # International support - allow any valid country code
        if not v:
            return "US"
        v = v.upper().strip()
        if len(v) != 2:
            raise ValueError("Country code must be 2 characters (ISO 3166-1 alpha-2)")
        # Allow all country codes for international support
        return v
    
    @field_validator('state')
    @classmethod
    def validate_state(cls, v, info):
        if v is None:
            return v

        # International support - allow state names and codes
        v = v.strip()
        if len(v) == 0:
            return v
        # Allow up to 50 characters for international state/province names
        if len(v) > 50:
            raise ValueError("State/province name too long")
        return v
    
    @field_validator('zip_code')
    @classmethod
    def validate_zip_code(cls, v, info):
        if v is None:
            return v

        # International support - allow various postal code formats
        v = v.strip()
        if len(v) == 0:
            return v
        # Allow alphanumeric postal codes (UK: SW1A 1AA, Canada: K1A 0B1, etc.)
        # Minimum 3 characters (some countries have short codes)
        if len(v) < 3 or len(v) > 12:
            raise ValueError('Postal code must be between 3 and 12 characters')
        return v
    
    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v, info):
        if v is None:
            return v

        # International support - allow various phone formats with country codes
        # Remove common formatting characters
        v = v.strip().replace('(', '').replace(')', '').replace('-', '').replace(' ', '').replace('+', '')

        # After cleanup, should be digits only, minimum 7 (some countries), maximum 15 (E.164 standard)
        if not v.isdigit():
            raise ValueError('Phone number must contain only digits (after removing formatting)')

        if len(v) < 7 or len(v) > 15:
            raise ValueError('Phone number must be between 7 and 15 digits')

        return v
    
    @field_validator('annual_income')
    @classmethod
    def validate_annual_income(cls, v):
        # RESTORED: Optimized input validation
        # return InputSanitizer.sanitize_amount(
        #     v, 
        #     min_value=FinancialConstants.MIN_ANNUAL_INCOME,
        #     max_value=FinancialConstants.MAX_ANNUAL_INCOME,
        #     field_name="annual income"
        # )
        # Basic income validation without external dependencies
        if v < 0 or v > 99999999:
            raise ValueError('Invalid annual income amount')
        return v
    
    @field_validator('timezone')
    @classmethod
    def validate_timezone(cls, v):
        if not v:
            return "UTC"
        
        # EMERGENCY FIX: Basic timezone validation without InputSanitizer
        v = v.strip()[:50]  # Basic string sanitization
        
        # Common timezone formats
        import re
        valid_timezone_pattern = r'^[A-Za-z_/\-+0-9]+$'
        if not re.match(valid_timezone_pattern, v):
            raise ValueError("Invalid timezone format")
        
        return v


class LoginIn(BaseModel):
    """Enhanced login schema with security validation"""
    
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=1, max_length=128, description="User password")
    
    @field_validator('email')
    @classmethod
    def validate_email(cls, v):
        # RESTORED: Optimized input validation
        # return InputSanitizer.sanitize_email(v)
        # Fast basic email validation without external dependencies
        if '@' not in v or '.' not in v.split('@')[1]:
            raise ValueError("Invalid email format")
        return v.lower().strip()
    
    @field_validator('password')
    @classmethod
    def validate_password(cls, v):
        # Basic validation for login (don't expose security requirements)
        if not v or len(v) == 0:
            raise ValueError("Password is required")
        
        if len(v) > 128:
            raise ValueError("Invalid password format")
        
        return v


class GoogleAuthIn(BaseModel):
    """Google authentication schema with validation"""
    
    id_token: str = Field(..., min_length=10, max_length=2048, description="Google ID token")
    
    @field_validator('id_token')
    @classmethod
    def validate_id_token(cls, v):
        if not v:
            raise ValueError("ID token is required")
        
        # Basic JWT token format validation
        import re
        if not re.match(r'^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$', v):
            raise ValueError("Invalid ID token format")
        
        return v


class TokenOut(BaseModel):
    """Token response schema"""
    
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: Optional[int] = None
    
    class Config:
        json_encoders = {
            # Ensure tokens are properly serialized
        }
