"""
Comprehensive Input Validation for MITA Finance Application
Provides secure input validation and sanitization for emergency endpoints
"""

import re
import logging
from typing import Optional, Dict, Any, Tuple

# Try to import email-validator, fall back to basic validation if not available
try:
    from email_validator import validate_email, EmailNotValidError
    EMAIL_VALIDATOR_AVAILABLE = True
except ImportError:
    EMAIL_VALIDATOR_AVAILABLE = False

logger = logging.getLogger(__name__)

# ============================================================================
# SECURITY VALIDATION FUNCTIONS
# ============================================================================

def validate_email_secure(email: str) -> Tuple[bool, Optional[str]]:
    """
    Comprehensive email validation following security best practices
    Returns (is_valid, error_message)
    """
    if not email:
        return False, "Email is required"
    
    # Length validation
    if len(email) > 254:  # RFC 5321 limit
        return False, "Email address too long"
    
    if len(email) < 5:  # Minimum realistic email
        return False, "Email address too short"
    
    # Basic format validation first
    if '@' not in email or email.count('@') != 1:
        return False, "Invalid email format"
    
    # More comprehensive validation
    if EMAIL_VALIDATOR_AVAILABLE:
        try:
            # Use email-validator library for RFC-compliant validation
            validate_email(email)
            return True, None
        except EmailNotValidError:
            return False, "Invalid email format"
        except Exception as e:
            logger.warning(f"Email validation error: {e}")
            return False, "Invalid email format"
    else:
        # Fallback to regex-based validation
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if re.match(email_pattern, email):
            return True, None
        else:
            return False, "Invalid email format"

def validate_password_secure(password: str) -> Tuple[bool, Optional[str]]:
    """
    Comprehensive password validation for security
    Returns (is_valid, error_message)
    """
    if not password:
        return False, "Password is required"
    
    # Length validation
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    
    if len(password) > 128:  # Prevent DoS attacks
        return False, "Password cannot exceed 128 characters"
    
    # Character validation - ensure printable characters
    if not all(ord(c) >= 32 and ord(c) <= 126 for c in password):
        return False, "Password contains invalid characters"
    
    # Strength validation (basic)
    has_lower = any(c.islower() for c in password)
    has_upper = any(c.isupper() for c in password)
    has_digit = any(c.isdigit() for c in password)
    
    strength_score = sum([has_lower, has_upper, has_digit])
    
    if len(password) < 12 and strength_score < 2:
        return False, "Password too weak. Use a mix of letters, numbers, and symbols"
    
    return True, None

def validate_country_code(country: str) -> Tuple[bool, Optional[str]]:
    """
    Validate country code input
    Returns (is_valid, error_message)
    """
    if not country:
        return False, "Country is required"
    
    # Length validation
    if len(country) > 3:
        return False, "Invalid country code format"
    
    # Allow common formats: US, USA, GB, GBR, etc.
    if not re.match(r'^[A-Z]{2,3}$', country.upper()):
        return False, "Country code must be 2-3 uppercase letters"
    
    return True, None

def validate_annual_income(annual_income: Any) -> Tuple[bool, Optional[str], int]:
    """
    Validate annual income input
    Returns (is_valid, error_message, sanitized_value)
    """
    if annual_income is None:
        return True, None, 0  # Default value
    
    try:
        income = int(annual_income)
        
        # Range validation
        if income < 0:
            return False, "Annual income cannot be negative", 0
        
        if income > 10_000_000:  # $10M limit to prevent abuse
            return False, "Annual income value too high", 0
        
        return True, None, income
        
    except (ValueError, TypeError):
        return False, "Annual income must be a valid number", 0

def validate_timezone(timezone: str) -> Tuple[bool, Optional[str]]:
    """
    Validate timezone input
    Returns (is_valid, error_message)
    """
    if not timezone:
        return False, "Timezone is required"
    
    # Length validation
    if len(timezone) > 50:
        return False, "Timezone identifier too long"
    
    # Basic format validation for common timezones
    # Allow UTC, America/New_York, Europe/London, etc.
    if not re.match(r'^[A-Za-z]+(/[A-Za-z_]+)*$', timezone):
        return False, "Invalid timezone format"
    
    # Whitelist common timezones to prevent injection
    common_timezones = [
        'UTC', 'GMT',
        'America/New_York', 'America/Chicago', 'America/Denver', 'America/Los_Angeles',
        'Europe/London', 'Europe/Paris', 'Europe/Berlin', 'Europe/Rome',
        'Asia/Tokyo', 'Asia/Shanghai', 'Asia/Mumbai', 'Asia/Dubai',
        'Australia/Sydney', 'Australia/Melbourne',
        'Pacific/Auckland'
    ]
    
    if timezone not in common_timezones:
        logger.warning(f"Uncommon timezone used: {timezone}")
        # Still allow it but log for monitoring
    
    return True, None

def validate_registration_input(email: str, password: str, country: str = None, 
                              annual_income: Any = None, timezone: str = None) -> Dict[str, Any]:
    """
    Comprehensive validation for registration inputs
    Returns validation result with sanitized values
    """
    result = {
        "valid": True,
        "errors": [],
        "sanitized": {
            "email": "",
            "country": "US",  # Default
            "annual_income": 0,  # Default
            "timezone": "UTC"  # Default
        }
    }
    
    # Email validation
    email_valid, email_error = validate_email_secure(email)
    if not email_valid:
        result["valid"] = False
        result["errors"].append(email_error)
    else:
        result["sanitized"]["email"] = email.lower().strip()
    
    # Password validation
    password_valid, password_error = validate_password_secure(password)
    if not password_valid:
        result["valid"] = False
        result["errors"].append(password_error)
    
    # Country validation
    if country:
        country_valid, country_error = validate_country_code(country)
        if not country_valid:
            result["valid"] = False
            result["errors"].append(country_error)
        else:
            result["sanitized"]["country"] = country.upper().strip()
    
    # Annual income validation
    income_valid, income_error, income_value = validate_annual_income(annual_income)
    if not income_valid:
        result["valid"] = False
        result["errors"].append(income_error)
    else:
        result["sanitized"]["annual_income"] = income_value
    
    # Timezone validation
    if timezone:
        tz_valid, tz_error = validate_timezone(timezone)
        if not tz_valid:
            result["valid"] = False
            result["errors"].append(tz_error)
        else:
            result["sanitized"]["timezone"] = timezone.strip()
    
    return result

def sanitize_user_input(input_string: str, max_length: int = 255) -> str:
    """
    General input sanitization function
    """
    if not input_string:
        return ""
    
    # Limit length to prevent DoS
    sanitized = str(input_string)[:max_length]
    
    # Remove control characters but keep printable ones
    sanitized = ''.join(char for char in sanitized if ord(char) >= 32 or char in ['\t', '\n', '\r'])
    
    # Strip whitespace
    sanitized = sanitized.strip()
    
    return sanitized

# ============================================================================
# SECURITY RATE LIMITING HELPERS
# ============================================================================

def is_suspicious_request_pattern(email: str, user_agent: str = None, ip: str = None) -> bool:
    """
    Detect suspicious request patterns that might indicate attacks
    """
    suspicious_patterns = [
        # Email patterns
        len(email) > 100,  # Unusually long email
        email.count('.') > 5,  # Too many dots
        email.count('-') > 10,  # Too many dashes
        
        # SQL injection patterns in email
        any(pattern in email.lower() for pattern in ['union', 'select', 'drop', 'insert', '--', ';']),
        
        # XSS patterns
        any(pattern in email.lower() for pattern in ['<script', 'javascript:', 'onload=', 'onerror=']),
    ]
    
    if user_agent:
        # Suspicious user agents
        suspicious_ua = [
            'curl', 'wget', 'python-requests', 'bot', 'crawler', 'scanner'
        ]
        if any(ua in user_agent.lower() for ua in suspicious_ua):
            suspicious_patterns.append(True)
    
    return any(suspicious_patterns)