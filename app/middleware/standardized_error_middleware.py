"""
Standardized Error Handling Middleware for MITA Finance API

This middleware provides a final layer of error handling to catch any errors
that weren't handled by the route decorators or exception handlers. It ensures
that ALL responses follow the standardized error format.
"""

import json
import logging
import time
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.standardized_error_handler import (
    StandardizedErrorHandler,
    StandardizedAPIException,
    ErrorCode
)


logger = logging.getLogger(__name__)


class StandardizedErrorMiddleware(BaseHTTPMiddleware):
    """
    Middleware that ensures all error responses are standardized.
    
    This middleware:
    1. Catches any unhandled exceptions
    2. Ensures response format consistency
    3. Adds performance monitoring
    4. Provides request context for debugging
    """
    
    def __init__(
        self, 
        app, 
        include_request_details: bool = False,
        max_response_time_warning_ms: int = 2000
    ):
        super().__init__(app)
        self.include_request_details = include_request_details
        self.max_response_time_warning_ms = max_response_time_warning_ms
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()
        
        try:
            # Process the request
            response = await call_next(request)
            
            # Calculate response time
            response_time_ms = (time.time() - start_time) * 1000
            
            # Log slow requests
            if response_time_ms > self.max_response_time_warning_ms:
                logger.warning(
                    f"Slow request detected: {request.method} {request.url.path} "
                    f"took {response_time_ms:.2f}ms",
                    extra={
                        "method": request.method,
                        "path": request.url.path,
                        "response_time_ms": response_time_ms,
                        "status_code": response.status_code
                    }
                )
            
            # Check if response is an error response that needs standardization
            if response.status_code >= 400:
                # Check if response body follows our standard format
                try:
                    if hasattr(response, 'body'):
                        body = response.body
                        if isinstance(body, bytes):
                            body_content = json.loads(body.decode())
                            
                            # Check if response follows our standard format
                            if not self._is_standardized_response(body_content):
                                # Convert to standardized format
                                standardized_error = StandardizedAPIException(
                                    message=body_content.get("detail", "An error occurred"),
                                    error_code=self._map_status_to_error_code(response.status_code),
                                    status_code=response.status_code
                                )
                                
                                return StandardizedErrorHandler.create_response(
                                    standardized_error, request
                                )
                except (json.JSONDecodeError, AttributeError):
                    # If we can't parse the response, leave it as is
                    pass
            
            # Add security headers to all responses
            response.headers["X-Request-ID"] = getattr(request.state, 'request_id', 'unknown')
            response.headers["X-Response-Time-MS"] = f"{response_time_ms:.2f}"
            
            return response
            
        except Exception as e:
            # This is the final safety net for any unhandled exceptions
            response_time_ms = (time.time() - start_time) * 1000
            
            logger.error(
                f"Unhandled exception in middleware: {type(e).__name__}: {str(e)}",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "response_time_ms": response_time_ms,
                    "exception_type": type(e).__name__
                },
                exc_info=True
            )
            
            # Create a standardized error response
            if isinstance(e, StandardizedAPIException):
                return StandardizedErrorHandler.create_response(e, request)
            else:
                # Convert any other exception to a standardized internal server error
                internal_error = StandardizedAPIException(
                    message="An unexpected error occurred",
                    error_code=ErrorCode.SYSTEM_INTERNAL_ERROR,
                    status_code=500,
                    context={
                        "original_error_type": type(e).__name__,
                        "response_time_ms": response_time_ms
                    }
                )
                
                return StandardizedErrorHandler.create_response(
                    internal_error, 
                    request,
                    extra_context={
                        "middleware_catch": True,
                        "original_error": str(e)[:500]  # Truncate for security
                    }
                )
    
    def _is_standardized_response(self, response_content: dict) -> bool:
        """
        Check if a response follows our standardized format.
        
        A standardized error response should have:
        - success: false
        - error: {code, message, error_id, timestamp, details}
        """
        if not isinstance(response_content, dict):
            return False
        
        # Check for standardized success response
        if response_content.get("success") is True:
            return "data" in response_content and "timestamp" in response_content
        
        # Check for standardized error response
        if response_content.get("success") is False:
            error = response_content.get("error", {})
            required_fields = ["code", "message", "error_id", "timestamp"]
            return all(field in error for field in required_fields)
        
        return False
    
    def _map_status_to_error_code(self, status_code: int) -> str:
        """Map HTTP status codes to standardized error codes"""
        status_to_error_code = {
            400: ErrorCode.VALIDATION_INVALID_FORMAT,
            401: ErrorCode.AUTH_INVALID_CREDENTIALS,
            403: ErrorCode.AUTH_INSUFFICIENT_PERMISSIONS,
            404: ErrorCode.RESOURCE_NOT_FOUND,
            409: ErrorCode.RESOURCE_CONFLICT,
            422: ErrorCode.VALIDATION_INVALID_FORMAT,
            429: ErrorCode.RATE_LIMIT_EXCEEDED,
            500: ErrorCode.SYSTEM_INTERNAL_ERROR,
            502: ErrorCode.EXTERNAL_SERVICE_UNAVAILABLE,
            503: ErrorCode.SYSTEM_MAINTENANCE,
            504: ErrorCode.EXTERNAL_SERVICE_TIMEOUT
        }
        
        return status_to_error_code.get(status_code, ErrorCode.SYSTEM_INTERNAL_ERROR)


class ResponseValidationMiddleware(BaseHTTPMiddleware):
    """
    Middleware that validates all API responses to ensure they follow
    the standardized format and contain required fields.
    """
    
    def __init__(self, app, validate_success_responses: bool = True):
        super().__init__(app)
        self.validate_success_responses = validate_success_responses
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        
        # Only validate JSON responses
        content_type = response.headers.get("content-type", "")
        if not content_type.startswith("application/json"):
            return response
        
        # Skip validation for specific paths
        skip_paths = ["/docs", "/redoc", "/openapi.json", "/health", "/"]
        if request.url.path in skip_paths:
            return response
        
        try:
            # Read response body
            if hasattr(response, 'body') and response.body:
                body_content = json.loads(response.body.decode())
                
                # Validate response structure
                validation_issues = self._validate_response_structure(
                    body_content, 
                    response.status_code
                )
                
                if validation_issues:
                    logger.warning(
                        f"Response validation issues for {request.method} {request.url.path}: "
                        f"{'; '.join(validation_issues)}",
                        extra={
                            "method": request.method,
                            "path": request.url.path,
                            "status_code": response.status_code,
                            "validation_issues": validation_issues
                        }
                    )
                
        except (json.JSONDecodeError, AttributeError, UnicodeDecodeError):
            # If we can't validate, log and continue
            logger.debug(
                f"Could not validate response format for {request.method} {request.url.path}"
            )
        
        return response
    
    def _validate_response_structure(
        self, 
        response_content: dict, 
        status_code: int
    ) -> list[str]:
        """
        Validate that the response follows the expected structure.
        Returns a list of validation issues found.
        """
        issues = []
        
        if not isinstance(response_content, dict):
            issues.append("Response content must be a JSON object")
            return issues
        
        # Check for required 'success' field
        if "success" not in response_content:
            issues.append("Missing required 'success' field")
            return issues
        
        success = response_content.get("success")
        
        if success is True:
            # Validate success response structure
            if status_code >= 400:
                issues.append(f"Success response with error status code {status_code}")
            
            if self.validate_success_responses:
                required_fields = ["data", "timestamp"]
                for field in required_fields:
                    if field not in response_content:
                        issues.append(f"Success response missing required field: {field}")
                
                # Validate timestamp format
                timestamp = response_content.get("timestamp")
                if timestamp and not isinstance(timestamp, str):
                    issues.append("Timestamp must be a string")
        
        elif success is False:
            # Validate error response structure
            if status_code < 400:
                issues.append(f"Error response with success status code {status_code}")
            
            error = response_content.get("error", {})
            if not isinstance(error, dict):
                issues.append("Error field must be an object")
                return issues
            
            required_error_fields = ["code", "message", "error_id", "timestamp"]
            for field in required_error_fields:
                if field not in error:
                    issues.append(f"Error response missing required field: error.{field}")
            
            # Validate error code format
            error_code = error.get("code")
            if error_code and not isinstance(error_code, str):
                issues.append("Error code must be a string")
            
            # Validate error_id format
            error_id = error.get("error_id")
            if error_id and not isinstance(error_id, str):
                issues.append("Error ID must be a string")
            
            # Validate timestamp format
            timestamp = error.get("timestamp")
            if timestamp and not isinstance(timestamp, str):
                issues.append("Error timestamp must be a string")
        
        else:
            issues.append("Success field must be true or false")
        
        return issues


class RequestContextMiddleware(BaseHTTPMiddleware):
    """
    Middleware that adds request context and IDs for tracing.
    This helps with debugging and correlating errors across services.
    """
    
    def __init__(self, app):
        super().__init__(app)
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Generate unique request ID
        import uuid
        request_id = f"req_{uuid.uuid4().hex[:12]}"
        
        # Store request context in request state
        request.state.request_id = request_id
        request.state.start_time = time.time()
        
        # Add request ID to logs
        logger.info(
            f"Request started: {request.method} {request.url.path}",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "client_ip": getattr(request.client, 'host', 'unknown'),
                "user_agent": request.headers.get("user-agent", "")
            }
        )
        
        try:
            response = await call_next(request)
            
            # Calculate request duration
            duration_ms = (time.time() - request.state.start_time) * 1000
            
            # Log request completion
            logger.info(
                f"Request completed: {request.method} {request.url.path} "
                f"- {response.status_code} in {duration_ms:.2f}ms",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": duration_ms
                }
            )
            
            return response
            
        except Exception as e:
            duration_ms = (time.time() - request.state.start_time) * 1000
            
            logger.error(
                f"Request failed: {request.method} {request.url.path} "
                f"- {type(e).__name__} in {duration_ms:.2f}ms",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "error_type": type(e).__name__,
                    "duration_ms": duration_ms
                },
                exc_info=True
            )
            
            raise