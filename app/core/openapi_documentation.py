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


# Common error response examples
COMMON_ERROR_EXAMPLES = {
    "ValidationError": {
        "summary": "Validation Error",
        "description": "Input validation failed",
        "value": create_error_response_example(
            ErrorCode.VALIDATION_INVALID_FORMAT,
            "Invalid input data",
            {
                "validation_errors": [
                    {
                        "field": "email",
                        "message": "Invalid email format",
                        "type": "value_error.email",
                        "input": "invalid-email"
                    }
                ]
            }
        )
    },
    
    "AuthenticationError": {
        "summary": "Authentication Failed",
        "description": "Invalid credentials or expired token",
        "value": create_error_response_example(
            ErrorCode.AUTH_INVALID_CREDENTIALS,
            "Invalid email or password"
        )
    },
    
    "AuthorizationError": {
        "summary": "Access Denied",
        "description": "Insufficient permissions for this operation",
        "value": create_error_response_example(
            ErrorCode.AUTH_INSUFFICIENT_PERMISSIONS,
            "Access denied",
            {
                "required_permissions": ["premium_user"],
                "user_permissions": ["basic_user"]
            }
        )
    },
    
    "ResourceNotFound": {
        "summary": "Resource Not Found",
        "description": "The requested resource does not exist",
        "value": create_error_response_example(
            ErrorCode.RESOURCE_NOT_FOUND,
            "Transaction not found with identifier: txn_123",
            {
                "resource_type": "Transaction",
                "identifier": "txn_123"
            }
        )
    },
    
    "BusinessLogicError": {
        "summary": "Business Logic Error",
        "description": "Operation violates business rules",
        "value": create_error_response_example(
            ErrorCode.BUSINESS_BUDGET_EXCEEDED,
            "Transaction would exceed monthly budget limit",
            {
                "current_spent": 950.00,
                "budget_limit": 1000.00,
                "transaction_amount": 75.00,
                "category": "food"
            }
        )
    },
    
    "RateLimitError": {
        "summary": "Rate Limit Exceeded",
        "description": "Too many requests in a short period",
        "value": create_error_response_example(
            ErrorCode.RATE_LIMIT_EXCEEDED,
            "Rate limit exceeded. Please try again in 60 seconds",
            {
                "retry_after": 60,
                "requests_made": 100,
                "requests_limit": 100,
                "reset_time": "2024-01-15T11:00:00.000Z"
            }
        )
    },
    
    "DatabaseError": {
        "summary": "Database Error",
        "description": "Database operation failed",
        "value": create_error_response_example(
            ErrorCode.DATABASE_CONNECTION_ERROR,
            "Database connection failed"
        )
    },
    
    "InternalServerError": {
        "summary": "Internal Server Error",
        "description": "An unexpected error occurred",
        "value": create_error_response_example(
            ErrorCode.SYSTEM_INTERNAL_ERROR,
            "An unexpected error occurred"
        )
    }
}


# Authentication endpoint examples
AUTH_ENDPOINT_EXAMPLES = {
    "register": {
        "200": {
            "description": "User registered successfully",
            "content": {
                "application/json": {
                    "examples": {
                        "successful_registration": {
                            "summary": "Successful Registration",
                            "value": create_success_response_example(
                                {
                                    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                                    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                                    "token_type": "bearer",
                                    "user": {
                                        "id": "550e8400-e29b-41d4-a716-446655440000",
                                        "email": "user@example.com",
                                        "country": "US",
                                        "is_premium": False,
                                        "created_at": "2024-01-15T10:30:00.000Z"
                                    }
                                },
                                "Account created successfully",
                                {
                                    "welcome_info": {
                                        "onboarding_required": True,
                                        "features_unlocked": ["basic_budgeting", "expense_tracking"]
                                    }
                                }
                            )
                        }
                    }
                }
            }
        },
        "400": {
            "description": "Registration failed - validation error",
            "content": {
                "application/json": {
                    "examples": {
                        "email_already_exists": {
                            "summary": "Email Already Exists",
                            "value": create_error_response_example(
                                ErrorCode.RESOURCE_ALREADY_EXISTS,
                                "An account with this email address already exists",
                                {"email": "user@example.com"}
                            )
                        },
                        "weak_password": {
                            "summary": "Weak Password",
                            "value": create_error_response_example(
                                ErrorCode.VALIDATION_PASSWORD_WEAK,
                                "Password must contain: at least 8 characters, at least one uppercase letter",
                                {"requirements": ["at least 8 characters", "at least one uppercase letter"]}
                            )
                        }
                    }
                }
            }
        },
        "422": {
            "description": "Validation error",
            "content": {
                "application/json": {
                    "examples": {
                        "validation_error": COMMON_ERROR_EXAMPLES["ValidationError"]
                    }
                }
            }
        },
        "429": {
            "description": "Rate limit exceeded",
            "content": {
                "application/json": {
                    "examples": {
                        "rate_limit": COMMON_ERROR_EXAMPLES["RateLimitError"]
                    }
                }
            }
        },
        "500": {
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "examples": {
                        "internal_error": COMMON_ERROR_EXAMPLES["InternalServerError"]
                    }
                }
            }
        }
    },
    
    "login": {
        "200": {
            "description": "User logged in successfully",
            "content": {
                "application/json": {
                    "examples": {
                        "successful_login": {
                            "summary": "Successful Login",
                            "value": create_success_response_example(
                                {
                                    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                                    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                                    "token_type": "bearer",
                                    "user": {
                                        "id": "550e8400-e29b-41d4-a716-446655440000",
                                        "email": "user@example.com",
                                        "country": "US",
                                        "is_premium": True,
                                        "last_login": "2024-01-15T09:15:00.000Z"
                                    }
                                },
                                "Login successful",
                                {
                                    "login_info": {
                                        "login_time": "2024-01-15T10:30:00.000Z",
                                        "client_ip": "192.168.1.1",
                                        "requires_password_change": False
                                    }
                                }
                            )
                        }
                    }
                }
            }
        },
        "401": {
            "description": "Authentication failed",
            "content": {
                "application/json": {
                    "examples": {
                        "invalid_credentials": COMMON_ERROR_EXAMPLES["AuthenticationError"],
                        "account_locked": {
                            "summary": "Account Locked",
                            "value": create_error_response_example(
                                ErrorCode.AUTH_ACCOUNT_LOCKED,
                                "Account is inactive"
                            )
                        }
                    }
                }
            }
        },
        "422": {
            "description": "Validation error",
            "content": {
                "application/json": {
                    "examples": {
                        "validation_error": COMMON_ERROR_EXAMPLES["ValidationError"]
                    }
                }
            }
        },
        "429": {
            "description": "Rate limit exceeded",
            "content": {
                "application/json": {
                    "examples": {
                        "rate_limit": COMMON_ERROR_EXAMPLES["RateLimitError"]
                    }
                }
            }
        }
    }
}


# Financial endpoint examples
FINANCIAL_ENDPOINT_EXAMPLES = {
    "create_transaction": {
        "201": {
            "description": "Transaction created successfully",
            "content": {
                "application/json": {
                    "examples": {
                        "successful_transaction": {
                            "summary": "Transaction Created",
                            "value": create_success_response_example(
                                {
                                    "id": "txn_550e8400e29b41d4",
                                    "amount": 45.67,
                                    "category": "food",
                                    "description": "Grocery shopping",
                                    "date": "2024-01-15T10:30:00.000Z",
                                    "created_at": "2024-01-15T10:30:00.000Z"
                                },
                                "Transaction recorded successfully",
                                {
                                    "balance_impact": {
                                        "category": "food",
                                        "amount": 45.67,
                                        "remaining_budget": 254.33,
                                        "budget_exceeded": False
                                    }
                                }
                            )
                        }
                    }
                }
            }
        },
        "400": {
            "description": "Invalid transaction data",
            "content": {
                "application/json": {
                    "examples": {
                        "invalid_amount": {
                            "summary": "Invalid Amount",
                            "value": create_error_response_example(
                                ErrorCode.VALIDATION_AMOUNT_INVALID,
                                "Transaction amount must be positive",
                                {"provided_amount": -50.00}
                            )
                        },
                        "invalid_category": {
                            "summary": "Invalid Category",
                            "value": create_error_response_example(
                                ErrorCode.VALIDATION_CATEGORY_INVALID,
                                "Invalid category. Must be one of: food, dining, groceries, transportation, ...",
                                {
                                    "provided_category": "invalid_category",
                                    "valid_categories": ["food", "dining", "groceries", "transportation"]
                                }
                            )
                        }
                    }
                }
            }
        },
        "401": {
            "description": "Authentication required",
            "content": {
                "application/json": {
                    "examples": {
                        "auth_required": COMMON_ERROR_EXAMPLES["AuthenticationError"]
                    }
                }
            }
        },
        "422": {
            "description": "Business logic error",
            "content": {
                "application/json": {
                    "examples": {
                        "budget_exceeded": COMMON_ERROR_EXAMPLES["BusinessLogicError"]
                    }
                }
            }
        }
    },
    
    "list_transactions": {
        "200": {
            "description": "Transactions retrieved successfully",
            "content": {
                "application/json": {
                    "examples": {
                        "transaction_list": {
                            "summary": "Transaction List",
                            "value": create_success_response_example(
                                [
                                    {
                                        "id": "txn_550e8400e29b41d4",
                                        "amount": 45.67,
                                        "category": "food",
                                        "description": "Grocery shopping",
                                        "date": "2024-01-15T10:30:00.000Z"
                                    },
                                    {
                                        "id": "txn_550e8400e29b41d5",
                                        "amount": 12.50,
                                        "category": "transportation",
                                        "description": "Bus fare",
                                        "date": "2024-01-14T08:15:00.000Z"
                                    }
                                ],
                                "Request completed successfully",
                                {
                                    "pagination": {
                                        "current_page": 1,
                                        "page_size": 100,
                                        "total_count": 2,
                                        "total_pages": 1,
                                        "has_next": False,
                                        "has_previous": False
                                    }
                                }
                            )
                        }
                    }
                }
            }
        },
        "400": {
            "description": "Invalid query parameters",
            "content": {
                "application/json": {
                    "examples": {
                        "invalid_date_range": {
                            "summary": "Invalid Date Range",
                            "value": create_error_response_example(
                                ErrorCode.VALIDATION_DATE_INVALID,
                                "Start date must be before or equal to end date",
                                {
                                    "start_date": "2024-01-15T00:00:00.000Z",
                                    "end_date": "2024-01-10T00:00:00.000Z"
                                }
                            )
                        },
                        "invalid_pagination": {
                            "summary": "Invalid Pagination",
                            "value": create_error_response_example(
                                ErrorCode.VALIDATION_OUT_OF_RANGE,
                                "Limit parameter must be between 1 and 1000",
                                {
                                    "provided_limit": 1500,
                                    "minimum": 1,
                                    "maximum": 1000
                                }
                            )
                        }
                    }
                }
            }
        },
        "401": {
            "description": "Authentication required",
            "content": {
                "application/json": {
                    "examples": {
                        "auth_required": COMMON_ERROR_EXAMPLES["AuthenticationError"]
                    }
                }
            }
        }
    }
}


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
                    }\n                },\n                \"description\": \"Error information\"\n            }\n        }\n    }\n    \n    # Add error code enum\n    openapi_schema[\"components\"][\"schemas\"][\"ErrorCodes\"] = {\n        \"type\": \"string\",\n        \"enum\": [\n            # Authentication & Authorization (1000-1999)\n            ErrorCode.AUTH_INVALID_CREDENTIALS,\n            ErrorCode.AUTH_TOKEN_EXPIRED,\n            ErrorCode.AUTH_TOKEN_INVALID,\n            ErrorCode.AUTH_TOKEN_MISSING,\n            ErrorCode.AUTH_TOKEN_BLACKLISTED,\n            ErrorCode.AUTH_REFRESH_TOKEN_INVALID,\n            ErrorCode.AUTH_INSUFFICIENT_PERMISSIONS,\n            ErrorCode.AUTH_ACCOUNT_LOCKED,\n            ErrorCode.AUTH_PASSWORD_RESET_REQUIRED,\n            ErrorCode.AUTH_TWO_FACTOR_REQUIRED,\n            \n            # Validation Errors (2000-2999)\n            ErrorCode.VALIDATION_REQUIRED_FIELD,\n            ErrorCode.VALIDATION_INVALID_FORMAT,\n            ErrorCode.VALIDATION_OUT_OF_RANGE,\n            ErrorCode.VALIDATION_INVALID_EMAIL,\n            ErrorCode.VALIDATION_PASSWORD_WEAK,\n            ErrorCode.VALIDATION_AMOUNT_INVALID,\n            ErrorCode.VALIDATION_DATE_INVALID,\n            ErrorCode.VALIDATION_CURRENCY_INVALID,\n            ErrorCode.VALIDATION_CATEGORY_INVALID,\n            ErrorCode.VALIDATION_JSON_MALFORMED,\n            \n            # Resource Errors (3000-3999)\n            ErrorCode.RESOURCE_NOT_FOUND,\n            ErrorCode.RESOURCE_ALREADY_EXISTS,\n            ErrorCode.RESOURCE_CONFLICT,\n            ErrorCode.RESOURCE_GONE,\n            ErrorCode.RESOURCE_ACCESS_DENIED,\n            \n            # Business Logic Errors (4000-4999)\n            ErrorCode.BUSINESS_INSUFFICIENT_FUNDS,\n            ErrorCode.BUSINESS_BUDGET_EXCEEDED,\n            ErrorCode.BUSINESS_TRANSACTION_LIMIT,\n            ErrorCode.BUSINESS_INVALID_OPERATION,\n            ErrorCode.BUSINESS_ACCOUNT_SUSPENDED,\n            ErrorCode.BUSINESS_FEATURE_DISABLED,\n            ErrorCode.BUSINESS_QUOTA_EXCEEDED,\n            \n            # Database Errors (5000-5999)\n            ErrorCode.DATABASE_CONNECTION_ERROR,\n            ErrorCode.DATABASE_TIMEOUT,\n            ErrorCode.DATABASE_CONSTRAINT_VIOLATION,\n            ErrorCode.DATABASE_INTEGRITY_ERROR,\n            ErrorCode.DATABASE_QUERY_ERROR,\n            \n            # External Service Errors (6000-6999)\n            ErrorCode.EXTERNAL_SERVICE_UNAVAILABLE,\n            ErrorCode.EXTERNAL_SERVICE_TIMEOUT,\n            ErrorCode.EXTERNAL_API_ERROR,\n            ErrorCode.EXTERNAL_PAYMENT_ERROR,\n            \n            # Rate Limiting (7000-7999)\n            ErrorCode.RATE_LIMIT_EXCEEDED,\n            ErrorCode.RATE_LIMIT_QUOTA_EXCEEDED,\n            \n            # System Errors (8000-8999)\n            ErrorCode.SYSTEM_INTERNAL_ERROR,\n            ErrorCode.SYSTEM_MAINTENANCE,\n            ErrorCode.SYSTEM_CONFIGURATION_ERROR,\n            ErrorCode.SYSTEM_RESOURCE_EXHAUSTED\n        ],\n        \"description\": \"Standardized error codes used throughout the MITA Finance API\"\n    }\n    \n    # Add comprehensive API information\n    openapi_schema[\"info\"][\"contact\"] = {\n        \"name\": \"MITA Finance API Support\",\n        \"email\": \"api-support@mita.finance\",\n        \"url\": \"https://docs.mita.finance/support\"\n    }\n    \n    openapi_schema[\"info\"][\"license\"] = {\n        \"name\": \"MIT License\",\n        \"url\": \"https://opensource.org/licenses/MIT\"\n    }\n    \n    # Add server information\n    openapi_schema[\"servers\"] = [\n        {\n            \"url\": \"https://api.mita.finance\",\n            \"description\": \"Production server\"\n        },\n        {\n            \"url\": \"https://staging.api.mita.finance\",\n            \"description\": \"Staging server\"\n        },\n        {\n            \"url\": \"http://localhost:8000\",\n            \"description\": \"Local development server\"\n        }\n    ]\n    \n    # Add security schemes\n    openapi_schema[\"components\"][\"securitySchemes\"] = {\n        \"BearerAuth\": {\n            \"type\": \"http\",\n            \"scheme\": \"bearer\",\n            \"bearerFormat\": \"JWT\",\n            \"description\": \"JWT access token obtained from login or registration\"\n        }\n    }\n    \n    # Add global tags\n    openapi_schema[\"tags\"] = [\n        {\n            \"name\": \"Authentication\",\n            \"description\": \"User authentication and authorization endpoints\"\n        },\n        {\n            \"name\": \"Transactions\",\n            \"description\": \"Financial transaction management\"\n        },\n        {\n            \"name\": \"Financial\",\n            \"description\": \"Financial analysis and budget management\"\n        },\n        {\n            \"name\": \"Users\",\n            \"description\": \"User profile and account management\"\n        }\n    ]\n    \n    # Add external documentation\n    openapi_schema[\"externalDocs\"] = {\n        \"description\": \"MITA Finance API Documentation\",\n        \"url\": \"https://docs.mita.finance\"\n    }\n    \n    return openapi_schema\n\n\ndef add_endpoint_examples(openapi_schema: Dict[str, Any]) -> None:\n    \"\"\"\n    Add comprehensive error response examples to specific endpoints.\n    \"\"\"\n    \n    paths = openapi_schema.get(\"paths\", {})\n    \n    # Add examples to authentication endpoints\n    auth_endpoints = {\n        \"/api/auth/register\": AUTH_ENDPOINT_EXAMPLES[\"register\"],\n        \"/api/auth/login\": AUTH_ENDPOINT_EXAMPLES[\"login\"]\n    }\n    \n    for path, examples in auth_endpoints.items():\n        if path in paths and \"post\" in paths[path]:\n            if \"responses\" not in paths[path][\"post\"]:\n                paths[path][\"post\"][\"responses\"] = {}\n            \n            for status_code, response_info in examples.items():\n                paths[path][\"post\"][\"responses\"][status_code] = response_info\n    \n    # Add examples to transaction endpoints\n    transaction_endpoints = {\n        \"/api/transactions/\": {\n            \"post\": FINANCIAL_ENDPOINT_EXAMPLES[\"create_transaction\"],\n            \"get\": FINANCIAL_ENDPOINT_EXAMPLES[\"list_transactions\"]\n        }\n    }\n    \n    for path, methods in transaction_endpoints.items():\n        if path in paths:\n            for method, examples in methods.items():\n                if method in paths[path]:\n                    if \"responses\" not in paths[path][method]:\n                        paths[path][method][\"responses\"] = {}\n                    \n                    for status_code, response_info in examples.items():\n                        paths[path][method][\"responses\"][status_code] = response_info"