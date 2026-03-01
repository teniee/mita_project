"""
Comprehensive error handling system for MITA backend
Provides consistent error responses, logging, and user-friendly messages
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from pydantic import ValidationError
import sentry_sdk

logger = logging.getLogger(__name__)


class MITAException(Exception):
    """Base exception class for MITA application"""
    
    def __init__(self, message: str, error_code: str = "MITA_ERROR", status_code: int = 500, details: Optional[Dict] = None):
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)


class ValidationException(MITAException):
    """Exception for validation errors"""
    
    def __init__(self, message: str, field: str = None, details: Optional[Dict] = None):
        super().__init__(
            message=message,
            error_code="VALIDATION_ERROR",
            status_code=400,
            details={**(details or {}), "field": field}
        )


class AuthenticationException(MITAException):
    """Exception for authentication errors"""
    
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(
            message=message,
            error_code="AUTH_ERROR",
            status_code=401
        )


class AuthorizationException(MITAException):
    """Exception for authorization errors"""
    
    def __init__(self, message: str = "Access denied"):
        super().__init__(
            message=message,
            error_code="AUTHORIZATION_ERROR",
            status_code=403
        )


class ResourceNotFoundException(MITAException):
    """Exception for resource not found errors"""
    
    def __init__(self, resource: str, identifier: str = ""):
        message = f"{resource} not found"
        if identifier:
            message += f": {identifier}"
        
        super().__init__(
            message=message,
            error_code="RESOURCE_NOT_FOUND",
            status_code=404,
            details={"resource": resource, "identifier": identifier}
        )


class BusinessLogicException(MITAException):
    """Exception for business logic violations"""
    
    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(
            message=message,
            error_code="BUSINESS_LOGIC_ERROR",
            status_code=422,
            details=details
        )


class ExternalServiceException(MITAException):
    """Exception for external service errors"""
    
    def __init__(self, service: str, message: str = "External service error"):
        super().__init__(
            message=f"{service}: {message}",
            error_code="EXTERNAL_SERVICE_ERROR",
            status_code=503,
            details={"service": service}
        )


class DatabaseException(MITAException):
    """Exception for database errors"""
    
    def __init__(self, message: str = "Database operation failed", details: Optional[Dict] = None):
        super().__init__(
            message=message,
            error_code="DATABASE_ERROR",
            status_code=500,
            details=details
        )


class RateLimitException(MITAException):
    """Exception for rate limiting"""
    
    def __init__(self, message: str = "Rate limit exceeded", retry_after: Optional[int] = None):
        super().__init__(
            message=message,
            error_code="RATE_LIMIT_ERROR",
            status_code=429,
            details={"retry_after": retry_after} if retry_after else {}
        )
        self.retry_after = retry_after


class ErrorHandler:
    """Centralized error handling and logging"""
    
    @staticmethod
    def log_error(error: Exception, request: Optional[Request] = None, user_id: Optional[int] = None) -> str:
        """Log error with context and return error ID"""
        error_id = f"error_{datetime.utcnow().strftime('%Y%m%d_%H%M%S_%f')}"
        
        context = {
            "error_id": error_id,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "user_id": user_id,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        if request:
            try:
                context.update({
                    "method": request.method,
                    "url": str(request.url),
                    "headers": dict(request.headers),
                    "client_ip": request.client.host if request.client else None
                })
            except Exception as e:
                # If there's an issue with request context, log it safely
                context["request_error"] = f"Failed to serialize request context: {str(e)}"
        
        # Log with appropriate level
        if isinstance(error, (ValidationException, AuthenticationException, AuthorizationException)):
            logger.warning(f"Client error {error_id}: {error}", extra=context)
        elif isinstance(error, ResourceNotFoundException):
            logger.info(f"Resource not found {error_id}: {error}", extra=context)
        else:
            logger.error(f"Server error {error_id}: {error}", extra=context, exc_info=True)
            
            # Send to Sentry for server errors
            with sentry_sdk.push_scope() as scope:
                scope.set_context("error_context", context)
                scope.set_tag("error_id", error_id)
                sentry_sdk.capture_exception(error)
        
        return error_id
    
    @staticmethod
    def create_error_response(error: Exception, request: Optional[Request] = None, user_id: Optional[int] = None, headers: Optional[Dict[str, str]] = None) -> JSONResponse:
        """Create standardized error response"""
        error_id = ErrorHandler.log_error(error, request, user_id)
        
        if isinstance(error, MITAException):
            response_data = {
                "success": False,
                "error": {
                    "code": error.error_code,
                    "message": error.message,
                    "error_id": error_id,
                    "details": error.details
                }
            }
            return JSONResponse(
                status_code=error.status_code,
                content=response_data,
                headers=headers
            )
        
        elif isinstance(error, ValidationError):
            response_data = {
                "success": False,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Invalid input data",
                    "error_id": error_id,
                    "details": {
                        "validation_errors": [
                            {
                                "field": ".".join(str(loc) for loc in err["loc"]),
                                "message": err["msg"],
                                "type": err["type"]
                            }
                            for err in error.errors()
                        ]
                    }
                }
            }
            return JSONResponse(status_code=422, content=response_data)
        
        elif isinstance(error, SQLAlchemyError):
            if isinstance(error, IntegrityError):
                message = "Data integrity violation"
                if "duplicate key" in str(error).lower():
                    message = "Resource already exists"
                elif "foreign key" in str(error).lower():
                    message = "Invalid reference to related resource"
            else:
                message = "Database operation failed"
            
            response_data = {
                "success": False,
                "error": {
                    "code": "DATABASE_ERROR",
                    "message": message,
                    "error_id": error_id
                }
            }
            return JSONResponse(status_code=500, content=response_data)
        
        elif isinstance(error, HTTPException):
            response_data = {
                "success": False,
                "error": {
                    "code": "HTTP_ERROR",
                    "message": error.detail,
                    "error_id": error_id
                }
            }
            return JSONResponse(status_code=error.status_code, content=response_data)
        
        else:
            # Generic server error
            response_data = {
                "success": False,
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": "An unexpected error occurred",
                    "error_id": error_id
                }
            }
            return JSONResponse(status_code=500, content=response_data)


def handle_database_errors(func):
    """Decorator to handle common database errors"""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except IntegrityError as e:
            if "duplicate key" in str(e).lower():
                raise BusinessLogicException("Resource already exists")
            elif "foreign key" in str(e).lower():
                raise BusinessLogicException("Invalid reference to related resource")
            else:
                raise DatabaseException("Data integrity violation")
        except SQLAlchemyError as e:
            raise DatabaseException(f"Database operation failed: {str(e)}")
    
    return wrapper


def validate_positive_number(value: float, field_name: str) -> float:
    """Validate that a number is positive"""
    if value <= 0:
        raise ValidationException(f"{field_name} must be positive", field=field_name)
    return value


def validate_date_range(start_date: datetime, end_date: datetime) -> None:
    """Validate date range"""
    if start_date > end_date:
        raise ValidationException("Start date must be before end date")
    
    if (end_date - start_date).days > 365:
        raise ValidationException("Date range cannot exceed 1 year")


def validate_user_access(user_id: int, resource_user_id: int) -> None:
    """Validate user has access to resource"""
    if user_id != resource_user_id:
        raise AuthorizationException("Access denied to resource")


def sanitize_string_input(value: str, max_length: int = 1000) -> str:
    """Sanitize string input"""
    if not isinstance(value, str):
        raise ValidationException("Value must be a string")
    
    # Remove potentially dangerous characters
    sanitized = value.strip()
    
    if len(sanitized) > max_length:
        raise ValidationException(f"Value exceeds maximum length of {max_length}")
    
    # Basic XSS prevention
    dangerous_patterns = ['<script', 'javascript:', 'onclick', 'onerror']
    for pattern in dangerous_patterns:
        if pattern.lower() in sanitized.lower():
            raise ValidationException("Value contains potentially dangerous content")
    
    return sanitized


def validate_amount(amount: float, min_amount: float = 0.01, max_amount: float = 1000000) -> float:
    """Validate monetary amount"""
    if not isinstance(amount, (int, float)):
        raise ValidationException("Amount must be a number")
    
    if amount < min_amount:
        raise ValidationException(f"Amount must be at least ${min_amount}")
    
    if amount > max_amount:
        raise ValidationException(f"Amount cannot exceed ${max_amount}")
    
    # Round to 2 decimal places
    return round(float(amount), 2)


def validate_category(category: str) -> str:
    """Validate expense category"""
    valid_categories = [
        'food', 'dining', 'groceries', 'transportation', 'gas', 'public_transport',
        'entertainment', 'shopping', 'clothing', 'healthcare', 'insurance',
        'utilities', 'rent', 'mortgage', 'education', 'childcare', 'pets',
        'travel', 'subscriptions', 'gifts', 'charity', 'other'
    ]
    
    category = category.lower().strip()
    
    if category not in valid_categories:
        raise ValidationException(f"Invalid category. Must be one of: {', '.join(valid_categories)}")
    
    return category


def validate_email(email: str) -> str:
    """Validate email format"""
    import re
    
    email = email.strip().lower()
    
    # Basic email regex
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    
    if not re.match(pattern, email):
        raise ValidationException("Invalid email format")
    
    if len(email) > 254:  # RFC 5321 limit
        raise ValidationException("Email address too long")
    
    return email


class InputValidator:
    """Comprehensive input validation class"""
    
    @staticmethod
    def validate_expense_data(data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate expense creation data"""
        validated = {}
        
        # Required fields
        if 'amount' not in data:
            raise ValidationException("Amount is required")
        validated['amount'] = validate_amount(data['amount'])
        
        if 'category' not in data:
            raise ValidationException("Category is required")
        validated['category'] = validate_category(data['category'])
        
        # Optional fields
        if 'description' in data:
            validated['description'] = sanitize_string_input(data['description'], 500)
        
        if 'date' in data:
            try:
                if isinstance(data['date'], str):
                    validated['date'] = datetime.fromisoformat(data['date'].replace('Z', '+00:00'))
                else:
                    validated['date'] = data['date']
            except ValueError:
                raise ValidationException("Invalid date format")
        
        return validated
    
    @staticmethod
    def validate_budget_data(data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate budget creation data"""
        validated = {}
        
        if 'monthly_income' in data:
            validated['monthly_income'] = validate_amount(data['monthly_income'], min_amount=0, max_amount=10000000)
        
        if 'savings_target' in data:
            validated['savings_target'] = validate_amount(data['savings_target'], min_amount=0)
        
        if 'categories' in data and isinstance(data['categories'], dict):
            validated_categories = {}
            for category, amount in data['categories'].items():
                validated_categories[validate_category(category)] = validate_amount(amount, min_amount=0)
            validated['categories'] = validated_categories
        
        return validated
    
    @staticmethod
    def validate_user_data(data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate user registration/update data"""
        validated = {}
        
        if 'email' in data:
            validated['email'] = validate_email(data['email'])
        
        if 'name' in data:
            validated['name'] = sanitize_string_input(data['name'], 100)
        
        if 'password' in data:
            password = data['password']
            if len(password) < 8:
                raise ValidationException("Password must be at least 8 characters long")
            if len(password) > 128:
                raise ValidationException("Password too long")
            validated['password'] = password
        
        return validated


# Exception handlers for FastAPI
async def mita_exception_handler(request: Request, exc: MITAException) -> JSONResponse:
    """Handle MITA custom exceptions"""
    return ErrorHandler.create_error_response(exc, request)


async def rate_limit_exception_handler(request: Request, exc: RateLimitException) -> JSONResponse:
    """Handle rate limit exceptions with proper headers"""
    headers = {}
    if exc.retry_after:
        headers["Retry-After"] = str(exc.retry_after)
    return ErrorHandler.create_error_response(exc, request, headers=headers)


async def validation_exception_handler(request: Request, exc: ValidationError) -> JSONResponse:
    """Handle Pydantic validation exceptions"""
    return ErrorHandler.create_error_response(exc, request)


async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    """Handle SQLAlchemy exceptions"""
    return ErrorHandler.create_error_response(exc, request)


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle all other exceptions"""
    return ErrorHandler.create_error_response(exc, request)