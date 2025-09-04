"""
Error Handling Decorators for MITA Finance API Routes

Provides decorators that wrap route handlers with consistent error handling,
logging, and response formatting. These decorators automatically catch
exceptions and convert them to standardized API responses.
"""

import asyncio
import functools
import inspect
from typing import Any, Callable, Dict, List, Optional, Type, Union

from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.core.standardized_error_handler import (
    StandardizedAPIException,
    StandardizedErrorHandler,
    AuthenticationError,
    AuthorizationError,
    ValidationError,
    ResourceNotFoundError,
    BusinessLogicError,
    DatabaseError,
    ExternalServiceError,
    RateLimitError,
    ErrorCode,
    map_database_error
)


def handle_errors(
    catch_exceptions: Optional[List[Type[Exception]]] = None,
    transform_exceptions: Optional[Dict[Type[Exception], Type[StandardizedAPIException]]] = None,
    log_level: str = "auto",
    include_stack_trace: bool = False
):
    """
    Decorator that provides comprehensive error handling for route handlers.
    
    Args:
        catch_exceptions: Specific exception types to catch (None = catch all)
        transform_exceptions: Mapping of exception types to standardized exceptions
        log_level: Logging level ('auto', 'debug', 'info', 'warning', 'error')
        include_stack_trace: Whether to include stack trace in error response (debug only)
    """
    
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                # Extract request and user info if available
                request = None
                user_id = None
                
                # Look for request object in args/kwargs
                for arg in args:
                    if isinstance(arg, Request):
                        request = arg
                        break
                
                for value in kwargs.values():
                    if isinstance(value, Request):
                        request = value
                        break
                    # Look for user object with id attribute
                    elif hasattr(value, 'id') and hasattr(value, 'email'):
                        user_id = str(value.id)
                
                # Call the original function
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)
                
                return result
                
            except Exception as e:
                # Check if we should catch this specific exception
                if catch_exceptions and type(e) not in catch_exceptions:
                    raise
                
                # Transform exception if mapping provided
                if transform_exceptions and type(e) in transform_exceptions:
                    target_exception_class = transform_exceptions[type(e)]
                    transformed_error = target_exception_class(str(e))
                    return StandardizedErrorHandler.create_response(
                        transformed_error, request, user_id
                    )
                
                # Handle SQLAlchemy errors
                if isinstance(e, SQLAlchemyError):
                    mapped_error = map_database_error(e)
                    return StandardizedErrorHandler.create_response(
                        mapped_error, request, user_id
                    )
                
                # Handle already standardized errors
                if isinstance(e, StandardizedAPIException):
                    return StandardizedErrorHandler.create_response(e, request, user_id)
                
                # Handle FastAPI HTTPExceptions
                if isinstance(e, HTTPException):
                    return StandardizedErrorHandler.create_response(e, request, user_id)
                
                # Handle all other exceptions as internal server errors
                internal_error = StandardizedAPIException(
                    message="An unexpected error occurred",
                    error_code=ErrorCode.SYSTEM_INTERNAL_ERROR,
                    status_code=500,
                    context={"original_error": type(e).__name__}
                )
                
                return StandardizedErrorHandler.create_response(
                    internal_error, request, user_id, {"original_error": str(e)}
                )
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            try:
                # Extract request and user info if available
                request = None
                user_id = None
                
                # Look for request object in args/kwargs
                for arg in args:
                    if isinstance(arg, Request):
                        request = arg
                        break
                
                for value in kwargs.values():
                    if isinstance(value, Request):
                        request = value
                        break
                    # Look for user object with id attribute
                    elif hasattr(value, 'id') and hasattr(value, 'email'):
                        user_id = str(value.id)
                
                # Call the original function
                result = func(*args, **kwargs)
                return result
                
            except Exception as e:
                # Check if we should catch this specific exception
                if catch_exceptions and type(e) not in catch_exceptions:
                    raise
                
                # Transform exception if mapping provided
                if transform_exceptions and type(e) in transform_exceptions:
                    target_exception_class = transform_exceptions[type(e)]
                    transformed_error = target_exception_class(str(e))
                    return StandardizedErrorHandler.create_response(
                        transformed_error, request, user_id
                    )
                
                # Handle SQLAlchemy errors
                if isinstance(e, SQLAlchemyError):
                    mapped_error = map_database_error(e)
                    return StandardizedErrorHandler.create_response(
                        mapped_error, request, user_id
                    )
                
                # Handle already standardized errors
                if isinstance(e, StandardizedAPIException):
                    return StandardizedErrorHandler.create_response(e, request, user_id)
                
                # Handle FastAPI HTTPExceptions
                if isinstance(e, HTTPException):
                    return StandardizedErrorHandler.create_response(e, request, user_id)
                
                # Handle all other exceptions as internal server errors
                internal_error = StandardizedAPIException(
                    message="An unexpected error occurred",
                    error_code=ErrorCode.SYSTEM_INTERNAL_ERROR,
                    status_code=500,
                    context={"original_error": type(e).__name__}
                )
                
                return StandardizedErrorHandler.create_response(
                    internal_error, request, user_id, {"original_error": str(e)}
                )
        
        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


def handle_auth_errors(func: Callable) -> Callable:
    """
    Decorator specifically for authentication-related endpoints.
    Provides consistent error handling for login, registration, and token operations.
    """
    
    exception_mapping = {
        ValueError: AuthenticationError,
        KeyError: AuthenticationError,
        AttributeError: AuthenticationError,
    }
    
    return handle_errors(
        transform_exceptions=exception_mapping,
        log_level="warning"
    )(func)


def handle_financial_errors(func: Callable) -> Callable:
    """
    Decorator for financial transaction endpoints.
    Handles business logic errors related to budgets, transactions, and financial operations.
    """
    
    exception_mapping = {
        ValueError: BusinessLogicError,
        ArithmeticError: BusinessLogicError,
    }
    
    return handle_errors(
        transform_exceptions=exception_mapping,
        log_level="warning"
    )(func)


def handle_validation_errors(func: Callable) -> Callable:
    """
    Decorator for endpoints that handle user input validation.
    Converts validation-related exceptions to proper validation errors.
    """
    
    exception_mapping = {
        ValueError: ValidationError,
        TypeError: ValidationError,
    }
    
    return handle_errors(
        transform_exceptions=exception_mapping,
        log_level="info"
    )(func)


def handle_resource_errors(func: Callable) -> Callable:
    """
    Decorator for endpoints that handle resource operations (CRUD).
    Handles not found, conflict, and access control errors.
    """
    
    exception_mapping = {
        KeyError: ResourceNotFoundError,
        AttributeError: ResourceNotFoundError,
        PermissionError: AuthorizationError,
    }
    
    return handle_errors(
        transform_exceptions=exception_mapping,
        log_level="info"
    )(func)


class ErrorHandlingMixin:
    """
    Mixin class that provides error handling methods for route classes.
    Can be used with FastAPI router classes or service classes.
    """
    
    def handle_database_error(self, error: SQLAlchemyError, context: Optional[Dict[str, Any]] = None):
        """Handle database errors with proper context"""
        mapped_error = map_database_error(error)
        if context:
            mapped_error.context.update(context)
        raise mapped_error
    
    def handle_validation_error(self, message: str, field: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        """Create and raise validation error"""
        error_details = details or {}
        if field:
            error_details["field"] = field
        
        raise ValidationError(message, ErrorCode.VALIDATION_INVALID_FORMAT, details=error_details)
    
    def handle_not_found_error(self, resource: str, identifier: Optional[str] = None):
        """Create and raise resource not found error"""
        raise ResourceNotFoundError(resource, identifier or "")
    
    def handle_auth_error(self, message: str = "Authentication failed"):
        """Create and raise authentication error"""
        raise AuthenticationError(message)
    
    def handle_permission_error(self, message: str = "Access denied"):
        """Create and raise authorization error"""
        raise AuthorizationError(message)
    
    def handle_business_logic_error(self, message: str, error_code: str = ErrorCode.BUSINESS_INVALID_OPERATION):
        """Create and raise business logic error"""
        raise BusinessLogicError(message, error_code)


def validate_and_handle(validation_func: Callable):
    """
    Decorator that runs a validation function before executing the main function.
    If validation fails, automatically converts to appropriate error response.
    
    Args:
        validation_func: Function that performs validation and raises exceptions on failure
    """
    
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                # Run validation
                if asyncio.iscoroutinefunction(validation_func):
                    await validation_func(*args, **kwargs)
                else:
                    validation_func(*args, **kwargs)
                
                # Execute main function
                if asyncio.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                else:
                    return func(*args, **kwargs)
                    
            except Exception as e:
                if isinstance(e, StandardizedAPIException):
                    raise
                else:
                    # Convert to validation error
                    raise ValidationError(str(e))
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            try:
                # Run validation
                validation_func(*args, **kwargs)
                
                # Execute main function
                return func(*args, **kwargs)
                    
            except Exception as e:
                if isinstance(e, StandardizedAPIException):
                    raise
                else:
                    # Convert to validation error
                    raise ValidationError(str(e))
        
        # Return appropriate wrapper
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


def require_permissions(*required_permissions: str):
    """
    Decorator that checks if the current user has the required permissions.
    Automatically raises AuthorizationError if permissions are insufficient.
    """
    
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Look for user object in kwargs
            user = None
            for value in kwargs.values():
                if hasattr(value, 'id') and hasattr(value, 'email'):
                    user = value
                    break
            
            if not user:
                raise AuthenticationError("User authentication required")
            
            # Check permissions (simplified - adjust based on your permission system)
            user_permissions = getattr(user, 'permissions', [])
            if not all(perm in user_permissions for perm in required_permissions):
                missing_perms = [perm for perm in required_permissions if perm not in user_permissions]
                raise AuthorizationError(
                    f"Missing required permissions: {', '.join(missing_perms)}",
                    details={"required_permissions": list(required_permissions), "missing_permissions": missing_perms}
                )
            
            # Execute main function
            if asyncio.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            else:
                return func(*args, **kwargs)
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            # Look for user object in kwargs
            user = None
            for value in kwargs.values():
                if hasattr(value, 'id') and hasattr(value, 'email'):
                    user = value
                    break
            
            if not user:
                raise AuthenticationError("User authentication required")
            
            # Check permissions
            user_permissions = getattr(user, 'permissions', [])
            if not all(perm in user_permissions for perm in required_permissions):
                missing_perms = [perm for perm in required_permissions if perm not in user_permissions]
                raise AuthorizationError(
                    f"Missing required permissions: {', '.join(missing_perms)}",
                    details={"required_permissions": list(required_permissions), "missing_permissions": missing_perms}
                )
            
            # Execute main function
            return func(*args, **kwargs)
        
        # Return appropriate wrapper
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


def log_performance(threshold_ms: int = 1000):
    """
    Decorator that logs performance warnings for slow operations.
    Integrates with the error handling system for performance monitoring.
    """
    
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            import time
            start_time = time.time()
            
            try:
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)
                
                duration_ms = (time.time() - start_time) * 1000
                
                if duration_ms > threshold_ms:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(
                        f"Slow operation detected: {func.__name__} took {duration_ms:.2f}ms",
                        extra={"function": func.__name__, "duration_ms": duration_ms, "threshold_ms": threshold_ms}
                    )
                
                return result
                
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                # Add performance context to error
                if hasattr(e, 'context') and isinstance(e.context, dict):
                    e.context["performance"] = {"duration_ms": duration_ms, "threshold_ms": threshold_ms}
                raise
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            import time
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                
                duration_ms = (time.time() - start_time) * 1000
                
                if duration_ms > threshold_ms:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(
                        f"Slow operation detected: {func.__name__} took {duration_ms:.2f}ms",
                        extra={"function": func.__name__, "duration_ms": duration_ms, "threshold_ms": threshold_ms}
                    )
                
                return result
                
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                # Add performance context to error
                if hasattr(e, 'context') and isinstance(e.context, dict):
                    e.context["performance"] = {"duration_ms": duration_ms, "threshold_ms": threshold_ms}
                raise
        
        # Return appropriate wrapper
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator