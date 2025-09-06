"""
OpenAPI Documentation Generator with Standardized Error Examples
This module provides comprehensive OpenAPI documentation that includes
standardized error response examples for all endpoints in the MITA Finance API.
"""
from typing import Dict, Any, List, Optional
from fastapi import status
from fastapi.openapi.utils import get_openapi
from app.core.standardized_error_handler import ErrorCode


def create_error_response_example(
    error_code: str,
    message: str,
    details: Optional[Dict[str, Any]] = None,
    error_id: str = "mita_507f1f77bcf8",
    timestamp: str = "2024-01-15T10:30:00.000Z"
) -> Dict[str, Any]:
    """Create a standardized error response example for OpenAPI documentation"""
    return {
        "success": False,
        "error": {
            "code": error_code,
            "message": message,
            "error_id": error_id,
            "timestamp": timestamp,
            "details": details or {}
        }
    }


def create_success_response_example(
    data: Any,
    message: str = "Request completed successfully",
    meta: Optional[Dict[str, Any]] = None,
    request_id: str = "req_507f1f77bcf8",
    timestamp: str = "2024-01-15T10:30:00.000Z"
) -> Dict[str, Any]:
    """Create a standardized success response example for OpenAPI documentation"""
    example = {
        "success": True,
        "message": message,
        "data": data,
        "timestamp": timestamp,
        "request_id": request_id
    }
    if meta:
        example["meta"] = meta
    return example


def get_standardized_openapi_schema(app, title: str, version: str, description: str) -> Dict[str, Any]:
    """
    Generate OpenAPI schema with comprehensive error response documentation.
    """
    # Get base schema
    openapi_schema = get_openapi(
        title=title,
        version=version,
        description=description,
        routes=app.routes,
    )
    
    # Add standardized error components
    if "components" not in openapi_schema:
        openapi_schema["components"] = {}
    if "schemas" not in openapi_schema["components"]:
        openapi_schema["components"]["schemas"] = {}
    
    # Add standardized response schemas
    openapi_schema["components"]["schemas"]["StandardizedSuccessResponse"] = {
        "type": "object",
        "required": ["success", "message", "data", "timestamp", "request_id"],
        "properties": {
            "success": {
                "type": "boolean",
                "example": True,
                "description": "Indicates if the request was successful"
            },
            "message": {
                "type": "string",
                "example": "Request completed successfully",
                "description": "Human-readable message describing the result"
            },
            "data": {
                "description": "Response data (structure varies by endpoint)"
            },
            "timestamp": {
                "type": "string",
                "format": "date-time",
                "example": "2024-01-15T10:30:00.000Z",
                "description": "ISO 8601 timestamp of when the response was generated"
            },
            "request_id": {
                "type": "string",
                "example": "req_507f1f77bcf8",
                "description": "Unique identifier for request tracing"
            },
            "meta": {
                "type": "object",
                "description": "Additional metadata (pagination, analysis info, etc.)"
            }
        }
    }
    
    openapi_schema["components"]["schemas"]["StandardizedErrorResponse"] = {
        "type": "object",
        "required": ["success", "error"],
        "properties": {
            "success": {
                "type": "boolean",
                "example": False,
                "description": "Indicates if the request was successful"
            },
            "error": {
                "type": "object",
                "required": ["code", "message", "error_id", "timestamp"],
                "properties": {
                    "code": {
                        "type": "string",
                        "example": "VALIDATION_2002",
                        "description": "Standardized error code for programmatic handling"
                    },
                    "message": {
                        "type": "string",
                        "example": "Invalid input data",
                        "description": "Human-readable error message"
                    },
                    "error_id": {
                        "type": "string",
                        "example": "mita_507f1f77bcf8",
                        "description": "Unique error identifier for support and debugging"
                    },
                    "timestamp": {
                        "type": "string",
                        "format": "date-time",
                        "example": "2024-01-15T10:30:00.000Z",
                        "description": "ISO 8601 timestamp of when the error occurred"
                    },
                    "details": {
                        "type": "object",
                        "description": "Additional error details and context"
                    }
                },
                "description": "Error information"
            }
        }
    }
    
    # Add error code enum
    openapi_schema["components"]["schemas"]["ErrorCodes"] = {
        "type": "string",
        "enum": [
            # Authentication & Authorization (1000-1999)
            ErrorCode.AUTH_INVALID_CREDENTIALS,
            ErrorCode.AUTH_TOKEN_EXPIRED,
            ErrorCode.AUTH_TOKEN_INVALID,
            ErrorCode.AUTH_TOKEN_MISSING,
            ErrorCode.AUTH_TOKEN_BLACKLISTED,
            ErrorCode.AUTH_REFRESH_TOKEN_INVALID,
            ErrorCode.AUTH_INSUFFICIENT_PERMISSIONS,
            ErrorCode.AUTH_ACCOUNT_LOCKED,
            ErrorCode.AUTH_PASSWORD_RESET_REQUIRED,
            ErrorCode.AUTH_TWO_FACTOR_REQUIRED,
            
            # Validation Errors (2000-2999)
            ErrorCode.VALIDATION_REQUIRED_FIELD,
            ErrorCode.VALIDATION_INVALID_FORMAT,
            ErrorCode.VALIDATION_OUT_OF_RANGE,
            ErrorCode.VALIDATION_INVALID_EMAIL,
            ErrorCode.VALIDATION_PASSWORD_WEAK,
            ErrorCode.VALIDATION_AMOUNT_INVALID,
            ErrorCode.VALIDATION_DATE_INVALID,
            ErrorCode.VALIDATION_CURRENCY_INVALID,
            ErrorCode.VALIDATION_CATEGORY_INVALID,
            ErrorCode.VALIDATION_JSON_MALFORMED,
            
            # Resource Errors (3000-3999)
            ErrorCode.RESOURCE_NOT_FOUND,
            ErrorCode.RESOURCE_ALREADY_EXISTS,
            ErrorCode.RESOURCE_CONFLICT,
            ErrorCode.RESOURCE_GONE,
            ErrorCode.RESOURCE_ACCESS_DENIED,
            
            # Business Logic Errors (4000-4999)
            ErrorCode.BUSINESS_INSUFFICIENT_FUNDS,
            ErrorCode.BUSINESS_BUDGET_EXCEEDED,
            ErrorCode.BUSINESS_TRANSACTION_LIMIT,
            ErrorCode.BUSINESS_INVALID_OPERATION,
            ErrorCode.BUSINESS_ACCOUNT_SUSPENDED,
            ErrorCode.BUSINESS_FEATURE_DISABLED,
            ErrorCode.BUSINESS_QUOTA_EXCEEDED,
            
            # Database Errors (5000-5999)
            ErrorCode.DATABASE_CONNECTION_ERROR,
            ErrorCode.DATABASE_TIMEOUT,
            ErrorCode.DATABASE_CONSTRAINT_VIOLATION,
            ErrorCode.DATABASE_INTEGRITY_ERROR,
            ErrorCode.DATABASE_QUERY_ERROR,
            
            # External Service Errors (6000-6999)
            ErrorCode.EXTERNAL_SERVICE_UNAVAILABLE,
            ErrorCode.EXTERNAL_SERVICE_TIMEOUT,
            ErrorCode.EXTERNAL_API_ERROR,
            ErrorCode.EXTERNAL_PAYMENT_ERROR,
            
            # Rate Limiting (7000-7999)
            ErrorCode.RATE_LIMIT_EXCEEDED,
            ErrorCode.RATE_LIMIT_QUOTA_EXCEEDED,
            
            # System Errors (8000-8999)
            ErrorCode.SYSTEM_INTERNAL_ERROR,
            ErrorCode.SYSTEM_MAINTENANCE,
            ErrorCode.SYSTEM_CONFIGURATION_ERROR,
            ErrorCode.SYSTEM_RESOURCE_EXHAUSTED
        ],
        "description": "Standardized error codes used throughout the MITA Finance API"
    }
    
    # Add comprehensive API information
    openapi_schema["info"]["contact"] = {
        "name": "MITA Finance API Support",
        "email": "api-support@mita.finance",
        "url": "https://docs.mita.finance/support"
    }
    
    openapi_schema["info"]["license"] = {
        "name": "MIT License",
        "url": "https://opensource.org/licenses/MIT"
    }
    
    # Add server information
    openapi_schema["servers"] = [
        {
            "url": "https://api.mita.finance",
            "description": "Production server"
        },
        {
            "url": "https://staging.api.mita.finance",
            "description": "Staging server"
        },
        {
            "url": "http://localhost:8000",
            "description": "Local development server"
        }
    ]
    
    # Add security schemes
    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "JWT access token obtained from login or registration"
        }
    }
    
    # Add global tags
    openapi_schema["tags"] = [
        {
            "name": "Authentication",
            "description": "User authentication and authorization endpoints"
        },
        {
            "name": "Transactions",
            "description": "Financial transaction management"
        },
        {
            "name": "Financial",
            "description": "Financial analysis and budget management"
        },
        {
            "name": "Users",
            "description": "User profile and account management"
        }
    ]
    
    # Add external documentation
    openapi_schema["externalDocs"] = {
        "description": "MITA Finance API Documentation",
        "url": "https://docs.mita.finance"
    }
    
    return openapi_schema