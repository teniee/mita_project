"""
Standardized Error Handling System for MITA Finance FastAPI Application

This module provides a comprehensive, consistent error handling system that ensures:
1. Standardized error response formats across all endpoints
2. Consistent HTTP status codes for similar error types
3. Proper error logging with context and traceability
4. User-friendly error messages with appropriate detail levels
5. Integration with Sentry for production monitoring
"""

import logging
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Union

from fastapi import HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy.exc import (
    IntegrityError,
    SQLAlchemyError,
    NoResultFound,
    MultipleResultsFound,
    DatabaseError,
    DisconnectionError,
    TimeoutError as SQLTimeoutError
)
import sentry_sdk

logger = logging.getLogger(__name__)


class ErrorCode:
    """Standardized error codes for the MITA Finance API"""
    
    # Authentication & Authorization (1000-1999)
    AUTH_INVALID_CREDENTIALS = "AUTH_1001"
    AUTH_TOKEN_EXPIRED = "AUTH_1002"
    AUTH_TOKEN_INVALID = "AUTH_1003"
    AUTH_TOKEN_MISSING = "AUTH_1004"
    AUTH_TOKEN_BLACKLISTED = "AUTH_1005"
    AUTH_REFRESH_TOKEN_INVALID = "AUTH_1006"
    AUTH_INSUFFICIENT_PERMISSIONS = "AUTH_1007"
    AUTH_ACCOUNT_LOCKED = "AUTH_1008"
    AUTH_PASSWORD_RESET_REQUIRED = "AUTH_1009"
    AUTH_TWO_FACTOR_REQUIRED = "AUTH_1010"
    
    # Validation Errors (2000-2999)
    VALIDATION_REQUIRED_FIELD = "VALIDATION_2001"
    VALIDATION_INVALID_FORMAT = "VALIDATION_2002"
    VALIDATION_OUT_OF_RANGE = "VALIDATION_2003"
    VALIDATION_INVALID_EMAIL = "VALIDATION_2004"
    VALIDATION_PASSWORD_WEAK = "VALIDATION_2005"
    VALIDATION_AMOUNT_INVALID = "VALIDATION_2006"
    VALIDATION_DATE_INVALID = "VALIDATION_2007"
    VALIDATION_CURRENCY_INVALID = "VALIDATION_2008"
    VALIDATION_CATEGORY_INVALID = "VALIDATION_2009"
    VALIDATION_JSON_MALFORMED = "VALIDATION_2010"
    
    # Resource Errors (3000-3999)
    RESOURCE_NOT_FOUND = "RESOURCE_3001"
    RESOURCE_ALREADY_EXISTS = "RESOURCE_3002"
    RESOURCE_CONFLICT = "RESOURCE_3003"
    RESOURCE_GONE = "RESOURCE_3004"
    RESOURCE_ACCESS_DENIED = "RESOURCE_3005"
    
    # Business Logic Errors (4000-4999)
    BUSINESS_INSUFFICIENT_FUNDS = "BUSINESS_4001"
    BUSINESS_BUDGET_EXCEEDED = "BUSINESS_4002"
    BUSINESS_TRANSACTION_LIMIT = "BUSINESS_4003"
    BUSINESS_INVALID_OPERATION = "BUSINESS_4004"
    BUSINESS_ACCOUNT_SUSPENDED = "BUSINESS_4005"
    BUSINESS_FEATURE_DISABLED = "BUSINESS_4006"
    BUSINESS_QUOTA_EXCEEDED = "BUSINESS_4007"
    
    # Database Errors (5000-5999)
    DATABASE_CONNECTION_ERROR = "DATABASE_5001"
    DATABASE_TIMEOUT = "DATABASE_5002"
    DATABASE_CONSTRAINT_VIOLATION = "DATABASE_5003"
    DATABASE_INTEGRITY_ERROR = "DATABASE_5004"
    DATABASE_QUERY_ERROR = "DATABASE_5005"
    
    # External Service Errors (6000-6999)
    EXTERNAL_SERVICE_UNAVAILABLE = "EXTERNAL_6001"
    EXTERNAL_SERVICE_TIMEOUT = "EXTERNAL_6002"
    EXTERNAL_API_ERROR = "EXTERNAL_6003"
    EXTERNAL_PAYMENT_ERROR = "EXTERNAL_6004"
    
    # Rate Limiting (7000-7999)
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_7001"
    RATE_LIMIT_QUOTA_EXCEEDED = "RATE_LIMIT_7002"
    
    # System Errors (8000-8999)
    SYSTEM_INTERNAL_ERROR = "SYSTEM_8001"
    SYSTEM_MAINTENANCE = "SYSTEM_8002"
    SYSTEM_CONFIGURATION_ERROR = "SYSTEM_8003"
    SYSTEM_RESOURCE_EXHAUSTED = "SYSTEM_8004"


class StandardizedAPIException(Exception):
    """Base exception class for all API errors with standardized structure"""
    
    def __init__(
        self,
        message: str,
        error_code: str,
        status_code: int,
        details: Optional[Dict[str, Any]] = None,
        user_message: Optional[str] = None,
        retry_after: Optional[int] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.details = details or {}
        self.user_message = user_message or message
        self.retry_after = retry_after
        self.context = context or {}
        self.error_id = f"mita_{uuid.uuid4().hex[:12]}"
        self.timestamp = datetime.utcnow()
        
        super().__init__(self.message)


class AuthenticationError(StandardizedAPIException):
    """Authentication-related errors"""
    
    def __init__(self, message: str = "Authentication failed", error_code: str = ErrorCode.AUTH_INVALID_CREDENTIALS, **kwargs):
        super().__init__(message, error_code, status.HTTP_401_UNAUTHORIZED, **kwargs)


class AuthorizationError(StandardizedAPIException):
    """Authorization-related errors"""
    
    def __init__(self, message: str = "Access denied", error_code: str = ErrorCode.AUTH_INSUFFICIENT_PERMISSIONS, **kwargs):
        super().__init__(message, error_code, status.HTTP_403_FORBIDDEN, **kwargs)


class ValidationError(StandardizedAPIException):
    """Validation-related errors"""
    
    def __init__(self, message: str = "Invalid input data", error_code: str = ErrorCode.VALIDATION_INVALID_FORMAT, **kwargs):
        super().__init__(message, error_code, status.HTTP_422_UNPROCESSABLE_ENTITY, **kwargs)


class ResourceNotFoundError(StandardizedAPIException):
    """Resource not found errors"""
    
    def __init__(self, resource: str, identifier: str = "", **kwargs):
        message = f"{resource} not found"
        if identifier:
            message += f" with identifier: {identifier}"
        
        details = {"resource_type": resource}
        if identifier:
            details["identifier"] = identifier
            
        super().__init__(
            message, 
            ErrorCode.RESOURCE_NOT_FOUND, 
            status.HTTP_404_NOT_FOUND,
            details=details,
            **kwargs
        )


class BusinessLogicError(StandardizedAPIException):
    """Business logic violation errors"""
    
    def __init__(self, message: str, error_code: str = ErrorCode.BUSINESS_INVALID_OPERATION, **kwargs):
        super().__init__(message, error_code, status.HTTP_422_UNPROCESSABLE_ENTITY, **kwargs)


class DatabaseError(StandardizedAPIException):
    """Database-related errors"""
    
    def __init__(self, message: str = "Database operation failed", error_code: str = ErrorCode.DATABASE_QUERY_ERROR, **kwargs):
        super().__init__(message, error_code, status.HTTP_500_INTERNAL_SERVER_ERROR, **kwargs)


class ExternalServiceError(StandardizedAPIException):
    """External service errors"""
    
    def __init__(self, service: str, message: str = "External service error", **kwargs):
        full_message = f"{service}: {message}"
        super().__init__(
            full_message, 
            ErrorCode.EXTERNAL_SERVICE_UNAVAILABLE, 
            status.HTTP_503_SERVICE_UNAVAILABLE,
            details={"service": service},
            **kwargs
        )


class RateLimitError(StandardizedAPIException):
    """Rate limiting errors"""

    def __init__(self, message: str = "Rate limit exceeded", retry_after: int = 60, **kwargs):
        super().__init__(
            message,
            ErrorCode.RATE_LIMIT_EXCEEDED,
            status.HTTP_429_TOO_MANY_REQUESTS,
            retry_after=retry_after,
            **kwargs
        )


class InternalServerError(StandardizedAPIException):
    """Internal server errors"""

    def __init__(self, message: str = "Internal server error", **kwargs):
        super().__init__(
            message,
            ErrorCode.SYSTEM_INTERNAL_ERROR,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            **kwargs
        )


class ErrorResponse:
    """Standardized error response structure"""
    
    @staticmethod
    def create(
        error: Union[Exception, StandardizedAPIException],
        request: Optional[Request] = None,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create standardized error response dictionary"""
        
        # Generate error ID for tracking
        error_id = getattr(error, 'error_id', f"mita_{uuid.uuid4().hex[:12]}")
        timestamp = getattr(error, 'timestamp', datetime.utcnow())
        
        if isinstance(error, StandardizedAPIException):
            response = {
                "success": False,
                "error": {
                    "code": error.error_code,
                    "message": error.user_message,
                    "error_id": error_id,
                    "timestamp": timestamp.isoformat() + "Z",
                    "details": error.details
                }
            }
            
            # Add retry information for rate limiting
            if error.retry_after:
                response["error"]["retry_after"] = error.retry_after
                
        elif isinstance(error, (ValidationError, RequestValidationError)):
            # Handle Pydantic validation errors and FastAPI request validation errors
            validation_errors = []
            if hasattr(error, 'errors') and callable(error.errors):
                for err in error.errors():
                    validation_errors.append({
                        "field": ".".join(str(loc) for loc in err.get("loc", [])),
                        "message": err.get("msg", "Invalid value"),
                        "type": err.get("type", "value_error"),
                        "input": err.get("input")
                    })

            response = {
                "success": False,
                "error": {
                    "code": ErrorCode.VALIDATION_INVALID_FORMAT,
                    "message": "Request validation failed",
                    "error_id": error_id,
                    "timestamp": timestamp.isoformat() + "Z",
                    "details": {
                        "validation_errors": validation_errors
                    }
                }
            }
            
        elif isinstance(error, HTTPException):
            # Map FastAPI HTTPExceptions to standardized format
            error_code_mapping = {
                401: ErrorCode.AUTH_INVALID_CREDENTIALS,
                403: ErrorCode.AUTH_INSUFFICIENT_PERMISSIONS,
                404: ErrorCode.RESOURCE_NOT_FOUND,
                422: ErrorCode.VALIDATION_INVALID_FORMAT,
                429: ErrorCode.RATE_LIMIT_EXCEEDED,
                500: ErrorCode.SYSTEM_INTERNAL_ERROR,
                503: ErrorCode.EXTERNAL_SERVICE_UNAVAILABLE
            }
            
            response = {
                "success": False,
                "error": {
                    "code": error_code_mapping.get(error.status_code, ErrorCode.SYSTEM_INTERNAL_ERROR),
                    "message": error.detail if isinstance(error.detail, str) else "An error occurred",
                    "error_id": error_id,
                    "timestamp": timestamp.isoformat() + "Z",
                    "details": {}
                }
            }
            
        else:
            # Generic exception handling
            response = {
                "success": False,
                "error": {
                    "code": ErrorCode.SYSTEM_INTERNAL_ERROR,
                    "message": "An unexpected error occurred",
                    "error_id": error_id,
                    "timestamp": timestamp.isoformat() + "Z",
                    "details": {}
                }
            }
        
        # Add request context for debugging (non-production)
        if request and logger.level <= logging.DEBUG:
            response["error"]["debug_info"] = {
                "method": request.method,
                "path": request.url.path,
                "query_params": dict(request.query_params)
            }
        
        return response


class StandardizedErrorHandler:
    """Centralized error handling with logging and monitoring"""
    
    @staticmethod
    def log_error(
        error: Exception,
        request: Optional[Request] = None,
        user_id: Optional[str] = None,
        extra_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Log error with comprehensive context"""
        
        error_id = getattr(error, 'error_id', f"mita_{uuid.uuid4().hex[:12]}")
        
        # Build logging context
        log_context = {
            "error_id": error_id,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "user_id": user_id,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Add request context if available
        if request:
            try:
                log_context.update({
                    "method": request.method,
                    "url": str(request.url),
                    "client_ip": getattr(request.client, 'host', None),
                    "user_agent": request.headers.get("user-agent", ""),
                    "headers": dict(request.headers) if logger.level <= logging.DEBUG else {}
                })
            except Exception as ctx_error:
                log_context["context_error"] = f"Failed to capture request context: {str(ctx_error)}"
        
        # Add extra context
        if extra_context:
            log_context.update(extra_context)
        
        # Determine logging level and log
        if isinstance(error, (AuthenticationError, AuthorizationError, ValidationError)):
            logger.warning(f"Client error [{error_id}]: {error}", extra=log_context)
        elif isinstance(error, ResourceNotFoundError):
            logger.info(f"Resource not found [{error_id}]: {error}", extra=log_context)
        elif isinstance(error, BusinessLogicError):
            logger.warning(f"Business logic error [{error_id}]: {error}", extra=log_context)
        elif isinstance(error, RateLimitError):
            logger.warning(f"Rate limit exceeded [{error_id}]: {error}", extra=log_context)
        else:
            # Server errors - log with full stack trace
            logger.error(
                f"Server error [{error_id}]: {error}",
                extra=log_context,
                exc_info=True
            )
            
            # Send critical errors to Sentry
            with sentry_sdk.push_scope() as scope:
                scope.set_context("error_context", log_context)
                scope.set_tag("error_id", error_id)
                scope.set_user({"id": user_id} if user_id else None)
                sentry_sdk.capture_exception(error)
        
        return error_id
    
    @staticmethod
    def create_response(
        error: Exception,
        request: Optional[Request] = None,
        user_id: Optional[str] = None,
        extra_context: Optional[Dict[str, Any]] = None
    ) -> JSONResponse:
        """Create standardized JSON error response"""
        
        # Log the error
        StandardizedErrorHandler.log_error(error, request, user_id, extra_context)
        
        # Create response data
        response_data = ErrorResponse.create(error, request, user_id)
        
        # Determine status code
        if isinstance(error, StandardizedAPIException):
            status_code = error.status_code
        elif isinstance(error, HTTPException):
            status_code = error.status_code
        elif isinstance(error, (ValidationError, RequestValidationError)):
            status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
        else:
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        
        # Create headers
        headers = {}
        if isinstance(error, (StandardizedAPIException, RateLimitError)) and hasattr(error, 'retry_after'):
            if error.retry_after:
                headers["Retry-After"] = str(error.retry_after)
        
        return JSONResponse(
            status_code=status_code,
            content=response_data,
            headers=headers
        )


# Database error mapping
def map_database_error(error: SQLAlchemyError) -> StandardizedAPIException:
    """Map SQLAlchemy errors to standardized exceptions"""
    
    if isinstance(error, IntegrityError):
        error_msg = str(error.orig) if hasattr(error, 'orig') else str(error)
        
        if "duplicate key" in error_msg.lower() or "unique constraint" in error_msg.lower():
            return BusinessLogicError(
                "Resource already exists",
                ErrorCode.RESOURCE_ALREADY_EXISTS
            )
        elif "foreign key" in error_msg.lower():
            return ValidationError(
                "Invalid reference to related resource",
                ErrorCode.DATABASE_CONSTRAINT_VIOLATION
            )
        else:
            return DatabaseError(
                "Data integrity constraint violation",
                ErrorCode.DATABASE_INTEGRITY_ERROR
            )
    
    elif isinstance(error, NoResultFound):
        return ResourceNotFoundError(
            "Resource", 
            "The requested resource was not found"
        )
    
    elif isinstance(error, MultipleResultsFound):
        return DatabaseError(
            "Multiple results found where one expected",
            ErrorCode.DATABASE_QUERY_ERROR
        )
    
    elif isinstance(error, (DisconnectionError, SQLTimeoutError)):
        return DatabaseError(
            "Database connection issue",
            ErrorCode.DATABASE_CONNECTION_ERROR
        )
    
    else:
        return DatabaseError(
            f"Database operation failed: {type(error).__name__}",
            ErrorCode.DATABASE_QUERY_ERROR
        )


# Validation helpers
def validate_required_fields(data: Dict[str, Any], required_fields: List[str]) -> None:
    """Validate that all required fields are present and not empty"""
    missing_fields = []
    empty_fields = []
    
    for field in required_fields:
        if field not in data:
            missing_fields.append(field)
        elif data[field] is None or (isinstance(data[field], str) and not data[field].strip()):
            empty_fields.append(field)
    
    if missing_fields:
        raise ValidationError(
            f"Missing required fields: {', '.join(missing_fields)}",
            ErrorCode.VALIDATION_REQUIRED_FIELD,
            details={"missing_fields": missing_fields}
        )
    
    if empty_fields:
        raise ValidationError(
            f"Empty required fields: {', '.join(empty_fields)}",
            ErrorCode.VALIDATION_REQUIRED_FIELD,
            details={"empty_fields": empty_fields}
        )


def validate_amount(amount: Union[int, float, Decimal], min_amount: float = 0.01, max_amount: float = 1000000.0) -> float:
    """Validate monetary amount with proper error handling - accepts int, float, or Decimal"""
    if not isinstance(amount, (int, float, Decimal)):
        raise ValidationError(
            "Amount must be a number",
            ErrorCode.VALIDATION_AMOUNT_INVALID,
            details={"provided_type": type(amount).__name__}
        )

    # Convert to float for comparison (Decimal objects support comparison but we standardize on float)
    amount_float = float(amount)

    if amount_float < min_amount:
        raise ValidationError(
            f"Amount must be at least ${min_amount:.2f}",
            ErrorCode.VALIDATION_OUT_OF_RANGE,
            details={"min_amount": min_amount, "provided_amount": amount_float}
        )

    if amount_float > max_amount:
        raise ValidationError(
            f"Amount cannot exceed ${max_amount:,.2f}",
            ErrorCode.VALIDATION_OUT_OF_RANGE,
            details={"max_amount": max_amount, "provided_amount": amount_float}
        )

    return round(amount_float, 2)


def validate_email(email: str) -> str:
    """Validate email format with comprehensive error handling"""
    import re
    
    if not isinstance(email, str):
        raise ValidationError(
            "Email must be a string",
            ErrorCode.VALIDATION_INVALID_FORMAT
        )
    
    email = email.strip().lower()
    
    if not email:
        raise ValidationError(
            "Email address is required",
            ErrorCode.VALIDATION_REQUIRED_FIELD
        )
    
    # RFC 5322 compliant email regex (simplified)
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    
    if not re.match(email_pattern, email):
        raise ValidationError(
            "Invalid email format",
            ErrorCode.VALIDATION_INVALID_EMAIL,
            details={"provided_email": email[:50]}  # Truncate for security
        )
    
    if len(email) > 254:  # RFC 5321 limit
        raise ValidationError(
            "Email address is too long",
            ErrorCode.VALIDATION_OUT_OF_RANGE,
            details={"max_length": 254, "provided_length": len(email)}
        )
    
    return email


def validate_password(password: str) -> None:
    """Validate password strength with detailed feedback"""
    if not isinstance(password, str):
        raise ValidationError(
            "Password must be a string",
            ErrorCode.VALIDATION_INVALID_FORMAT
        )
    
    issues = []
    
    if len(password) < 8:
        issues.append("at least 8 characters")
    
    if len(password) > 128:
        issues.append("no more than 128 characters")
    
    if not any(c.islower() for c in password):
        issues.append("at least one lowercase letter")
    
    if not any(c.isupper() for c in password):
        issues.append("at least one uppercase letter")
    
    if not any(c.isdigit() for c in password):
        issues.append("at least one number")
    
    if issues:
        raise ValidationError(
            f"Password must contain: {', '.join(issues)}",
            ErrorCode.VALIDATION_PASSWORD_WEAK,
            details={"requirements": issues}
        )
