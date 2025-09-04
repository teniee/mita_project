# MITA Finance API - Comprehensive Error Handling Guide

## Overview

This document describes the standardized error handling system implemented across the MITA Finance FastAPI application. The system ensures consistent, reliable, and user-friendly error responses throughout the entire API.

## Key Features

### ✅ Standardized Error Response Format
All error responses follow the same structure across all endpoints:

```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_2002",
    "message": "Invalid input data",
    "error_id": "mita_507f1f77bcf8",
    "timestamp": "2024-01-15T10:30:00.000Z",
    "details": {
      "field": "email",
      "validation_errors": [...]
    }
  }
}
```

### ✅ Consistent HTTP Status Codes
- **400**: Validation errors, malformed requests
- **401**: Authentication failures (invalid credentials, expired tokens)
- **403**: Authorization failures (insufficient permissions)
- **404**: Resource not found
- **422**: Business logic violations, unprocessable entities
- **429**: Rate limiting violations
- **500**: Internal server errors
- **503**: Service unavailable, external service failures

### ✅ Comprehensive Error Codes
Standardized error codes for programmatic handling:

#### Authentication & Authorization (1000-1999)
- `AUTH_1001`: Invalid credentials
- `AUTH_1002`: Token expired
- `AUTH_1003`: Invalid token
- `AUTH_1004`: Missing token
- `AUTH_1005`: Blacklisted token
- `AUTH_1006`: Invalid refresh token
- `AUTH_1007`: Insufficient permissions
- `AUTH_1008`: Account locked
- `AUTH_1009`: Password reset required
- `AUTH_1010`: Two-factor authentication required

#### Validation Errors (2000-2999)
- `VALIDATION_2001`: Required field missing
- `VALIDATION_2002`: Invalid format
- `VALIDATION_2003`: Value out of range
- `VALIDATION_2004`: Invalid email format
- `VALIDATION_2005`: Weak password
- `VALIDATION_2006`: Invalid amount
- `VALIDATION_2007`: Invalid date
- `VALIDATION_2008`: Invalid currency
- `VALIDATION_2009`: Invalid category
- `VALIDATION_2010`: Malformed JSON

#### Resource Errors (3000-3999)
- `RESOURCE_3001`: Resource not found
- `RESOURCE_3002`: Resource already exists
- `RESOURCE_3003`: Resource conflict
- `RESOURCE_3004`: Resource gone
- `RESOURCE_3005`: Resource access denied

#### Business Logic Errors (4000-4999)
- `BUSINESS_4001`: Insufficient funds
- `BUSINESS_4002`: Budget exceeded
- `BUSINESS_4003`: Transaction limit exceeded
- `BUSINESS_4004`: Invalid operation
- `BUSINESS_4005`: Account suspended
- `BUSINESS_4006`: Feature disabled
- `BUSINESS_4007`: Quota exceeded

#### Database Errors (5000-5999)
- `DATABASE_5001`: Connection error
- `DATABASE_5002`: Timeout
- `DATABASE_5003`: Constraint violation
- `DATABASE_5004`: Integrity error
- `DATABASE_5005`: Query error

#### External Service Errors (6000-6999)
- `EXTERNAL_6001`: Service unavailable
- `EXTERNAL_6002`: Service timeout
- `EXTERNAL_6003`: API error
- `EXTERNAL_6004`: Payment error

#### Rate Limiting (7000-7999)
- `RATE_LIMIT_7001`: Rate limit exceeded
- `RATE_LIMIT_7002`: Quota exceeded

#### System Errors (8000-8999)
- `SYSTEM_8001`: Internal server error
- `SYSTEM_8002`: Maintenance mode
- `SYSTEM_8003`: Configuration error
- `SYSTEM_8004`: Resource exhausted

## Implementation Details

### Error Handler Architecture

The error handling system consists of several layers:

1. **Route Decorators** (`@handle_auth_errors`, `@handle_financial_errors`)
   - Applied at the route level for specific error handling
   - Converts common exceptions to standardized exceptions
   - Provides context-aware error processing

2. **Exception Handlers** (FastAPI exception handlers)
   - Global handlers for specific exception types
   - Converts exceptions to standardized JSON responses
   - Integrated with logging and monitoring

3. **Error Middleware** (`StandardizedErrorMiddleware`)
   - Final safety net for unhandled exceptions
   - Ensures all responses follow standardized format
   - Adds performance monitoring and request context

4. **Response Validation** (`ResponseValidationMiddleware`)
   - Validates all API responses for consistency
   - Logs validation issues for debugging
   - Ensures compliance with standardized format

### Key Components

#### `StandardizedAPIException`
Base exception class for all API errors with comprehensive context:

```python
from app.core.standardized_error_handler import (
    StandardizedAPIException,
    ValidationError,
    AuthenticationError,
    BusinessLogicError
)

# Usage examples
raise ValidationError(
    "Invalid email format",
    ErrorCode.VALIDATION_INVALID_EMAIL,
    details={"provided_email": email}
)

raise BusinessLogicError(
    "Transaction would exceed budget",
    ErrorCode.BUSINESS_BUDGET_EXCEEDED,
    details={
        "budget_limit": 1000.00,
        "current_spent": 950.00,
        "transaction_amount": 75.00
    }
)
```

#### Error Decorators
Route-level error handling decorators:

```python
from app.core.error_decorators import handle_auth_errors

@router.post("/login")
@handle_auth_errors
async def login_user(request: Request, login_data: LoginIn):
    # Any unhandled exceptions are automatically converted
    # to appropriate standardized error responses
    pass
```

#### Response Helpers
Standardized response builders:

```python
from app.utils.response_wrapper import (
    StandardizedResponse,
    AuthResponseHelper,
    FinancialResponseHelper
)

# Success response
return StandardizedResponse.success(
    data=user_data,
    message="User created successfully"
)

# Authentication success with metadata
return AuthResponseHelper.login_success(
    tokens=tokens,
    user_data=user_data,
    login_info={"client_ip": client_ip}
)

# Financial analysis response
return FinancialResponseHelper.analysis_result(
    analysis_data=results,
    analysis_type="budget_analysis",
    confidence_score=0.95
)
```

## Endpoint-Specific Error Handling

### Authentication Endpoints

#### Registration (`POST /api/auth/register`)
**Possible Errors:**
- `400`: Email already exists, weak password
- `422`: Validation errors (invalid email, missing fields)
- `429`: Rate limit exceeded
- `500`: Internal server error

**Example Error Response:**
```json
{
  "success": false,
  "error": {
    "code": "RESOURCE_3002",
    "message": "An account with this email address already exists",
    "error_id": "mita_507f1f77bcf8",
    "timestamp": "2024-01-15T10:30:00.000Z",
    "details": {
      "email": "user@example.com"
    }
  }
}
```

#### Login (`POST /api/auth/login`)
**Possible Errors:**
- `401`: Invalid credentials, account locked
- `422`: Validation errors
- `429`: Rate limit exceeded
- `500`: Internal server error

### Financial Endpoints

#### Create Transaction (`POST /api/transactions/`)
**Possible Errors:**
- `400`: Invalid amount, invalid category
- `401`: Authentication required
- `422`: Budget exceeded, business logic violations
- `500`: Internal server error

#### List Transactions (`GET /api/transactions/`)
**Possible Errors:**
- `400`: Invalid pagination, invalid date range
- `401`: Authentication required
- `500`: Internal server error

### Budget and Analysis Endpoints

#### Installment Evaluation (`POST /api/financial/installment-evaluate`)
**Possible Errors:**
- `400`: Invalid price, invalid installment period
- `401`: Authentication required
- `422`: Business logic errors
- `500`: Internal server error

## Error Monitoring and Logging

### Comprehensive Logging
All errors are logged with comprehensive context:

```json
{
  "error_id": "mita_507f1f77bcf8",
  "error_type": "ValidationError",
  "error_message": "Invalid email format",
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2024-01-15T10:30:00.000Z",
  "method": "POST",
  "url": "/api/auth/register",
  "client_ip": "192.168.1.1",
  "user_agent": "Mozilla/5.0...",
  "request_id": "req_507f1f77bcf8"
}
```

### Sentry Integration
Critical errors are automatically sent to Sentry with:
- Error context and user information
- Request details and stack traces
- Custom tags for error categorization
- Performance monitoring integration

### Performance Monitoring
- Request/response time tracking
- Slow operation detection
- Error rate monitoring
- Resource utilization alerts

## Frontend Integration Guide

### Error Handling Best Practices

#### 1. Check Response Structure
```javascript
async function makeAPICall(url, options) {
  const response = await fetch(url, options);
  const data = await response.json();
  
  if (!data.success) {
    // Handle standardized error
    const { code, message, details, error_id } = data.error;
    
    switch (code) {
      case 'AUTH_1001':
        // Redirect to login
        break;
      case 'VALIDATION_2002':
        // Show field validation errors
        showValidationErrors(details.validation_errors);
        break;
      case 'RATE_LIMIT_7001':
        // Show rate limit message with retry time
        showRateLimit(details.retry_after);
        break;
      default:
        // Generic error handling
        showGenericError(message, error_id);
    }
    
    return null;
  }
  
  return data.data;
}
```

#### 2. Display User-Friendly Messages
```javascript
const ERROR_MESSAGES = {
  'AUTH_1001': 'Invalid email or password. Please try again.',
  'AUTH_1002': 'Your session has expired. Please log in again.',
  'VALIDATION_2004': 'Please enter a valid email address.',
  'BUSINESS_4002': 'This transaction would exceed your monthly budget.',
  'RATE_LIMIT_7001': 'Too many requests. Please wait before trying again.',
  'SYSTEM_8001': 'Something went wrong. Please try again or contact support.'
};

function getDisplayMessage(errorCode, defaultMessage) {
  return ERROR_MESSAGES[errorCode] || defaultMessage;
}
```

#### 3. Handle Validation Errors
```javascript
function showValidationErrors(validationErrors) {
  validationErrors.forEach(error => {
    const field = document.querySelector(`[name="${error.field}"]`);
    if (field) {
      field.setCustomValidity(error.message);
      field.reportValidity();
    }
  });
}
```

#### 4. Implement Retry Logic
```javascript
async function makeAPICallWithRetry(url, options, maxRetries = 3) {
  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      const result = await makeAPICall(url, options);
      return result;
    } catch (error) {
      if (error.code === 'RATE_LIMIT_7001' && attempt < maxRetries) {
        const retryAfter = error.details?.retry_after || 60;
        await new Promise(resolve => setTimeout(resolve, retryAfter * 1000));
        continue;
      }
      
      if (error.code?.startsWith('SYSTEM_') && attempt < maxRetries) {
        await new Promise(resolve => setTimeout(resolve, Math.pow(2, attempt) * 1000));
        continue;
      }
      
      throw error;
    }
  }
}
```

## Testing Error Scenarios

### Unit Testing
```python
import pytest
from app.core.standardized_error_handler import ValidationError, ErrorCode

def test_validation_error_creation():
    error = ValidationError(
        "Invalid email format",
        ErrorCode.VALIDATION_INVALID_EMAIL,
        details={"provided_email": "invalid-email"}
    )
    
    assert error.message == "Invalid email format"
    assert error.error_code == ErrorCode.VALIDATION_INVALID_EMAIL
    assert error.status_code == 422
    assert error.details["provided_email"] == "invalid-email"
    assert error.error_id.startswith("mita_")
```

### Integration Testing
```python
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_registration_with_invalid_email():
    response = client.post("/api/auth/register", json={
        "email": "invalid-email",
        "password": "password123",
        "country": "US"
    })
    
    assert response.status_code == 422
    assert response.json()["success"] is False
    assert response.json()["error"]["code"] == "VALIDATION_2004"
    assert "error_id" in response.json()["error"]
    assert "timestamp" in response.json()["error"]

def test_transaction_with_negative_amount():
    # Login first to get token
    login_response = client.post("/api/auth/login", json={
        "email": "test@example.com",
        "password": "password123"
    })
    token = login_response.json()["data"]["access_token"]
    
    response = client.post("/api/transactions/", 
        headers={"Authorization": f"Bearer {token}"},
        json={
            "amount": -50.00,
            "category": "food",
            "description": "Invalid transaction"
        }
    )
    
    assert response.status_code == 422
    assert response.json()["success"] is False
    assert response.json()["error"]["code"] == "VALIDATION_2006"
```

### Load Testing Error Scenarios
```python
import asyncio
import aiohttp

async def test_rate_limiting():
    async with aiohttp.ClientSession() as session:
        # Make rapid requests to trigger rate limiting
        tasks = []
        for i in range(150):  # Exceed rate limit
            task = session.post('http://localhost:8000/api/auth/login', 
                json={"email": "test@example.com", "password": "wrong"})
            tasks.append(task)
        
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Check that rate limiting responses are properly formatted
        rate_limited_responses = [
            r for r in responses 
            if hasattr(r, 'status') and r.status == 429
        ]
        
        assert len(rate_limited_responses) > 0
        
        for response in rate_limited_responses:
            data = await response.json()
            assert data["success"] is False
            assert data["error"]["code"] == "RATE_LIMIT_7001"
            assert "retry_after" in data["error"]["details"]
```

## Migration Guide

### From Legacy Error Handling

#### Before (Inconsistent)
```python
# Different error formats across endpoints
raise HTTPException(status_code=400, detail="Invalid email")
return {"error": "User not found"}
return JSONResponse({"success": False, "message": "Failed"}, status_code=500)
```

#### After (Standardized)
```python
# Consistent error handling
raise ValidationError("Invalid email format", ErrorCode.VALIDATION_INVALID_EMAIL)
raise ResourceNotFoundError("User", user_id)
raise StandardizedAPIException("Operation failed", ErrorCode.SYSTEM_INTERNAL_ERROR, 500)
```

### Updating Existing Routes

1. **Add Error Decorators**
   ```python
   @router.post("/endpoint")
   @handle_auth_errors  # Add appropriate decorator
   async def endpoint_handler():
       pass
   ```

2. **Replace HTTPException**
   ```python
   # Before
   raise HTTPException(status_code=404, detail="User not found")
   
   # After
   raise ResourceNotFoundError("User", user_id)
   ```

3. **Use Standardized Responses**
   ```python
   # Before
   return {"data": result, "status": "success"}
   
   # After
   return StandardizedResponse.success(data=result, message="Operation completed")
   ```

## Troubleshooting

### Common Issues

#### 1. Response Format Validation Errors
**Issue**: API responses don't follow standardized format
**Solution**: Ensure all routes use `StandardizedResponse` helpers or proper decorators

#### 2. Error Code Inconsistency
**Issue**: Same error types have different codes across endpoints
**Solution**: Use the predefined `ErrorCode` constants and map similar errors consistently

#### 3. Missing Error Context
**Issue**: Error responses lack sufficient details for debugging
**Solution**: Always include relevant details in error exceptions:
```python
raise ValidationError(
    "Invalid transaction amount",
    ErrorCode.VALIDATION_AMOUNT_INVALID,
    details={
        "provided_amount": amount,
        "minimum_amount": 0.01,
        "maximum_amount": 100000.00
    }
)
```

#### 4. Performance Impact
**Issue**: Error handling adds latency to responses
**Solution**: Error handling is optimized for production use with:
- Async logging operations
- Efficient error serialization
- Conditional debug information
- Cached error response templates

### Debugging Tools

#### 1. Error ID Tracking
Use error IDs to trace specific error instances:
```bash
grep "mita_507f1f77bcf8" /var/log/mita-api/*.log
```

#### 2. Error Rate Monitoring
Monitor error rates by endpoint and error type:
```python
# Custom metrics collection
from app.core.metrics import increment_error_counter

increment_error_counter(
    endpoint="/api/transactions/",
    error_code="VALIDATION_2006",
    user_id=user_id
)
```

#### 3. Response Validation Logs
Check middleware logs for response format issues:
```bash
grep "Response validation issues" /var/log/mita-api/app.log
```

## Performance Considerations

### Optimizations Implemented

1. **Lazy Error Serialization**: Error details are only computed when needed
2. **Efficient Logging**: Uses structured logging with async handlers
3. **Response Caching**: Common error response templates are cached
4. **Context Minimization**: Debug information only included in development mode
5. **Exception Path Optimization**: Common error paths are optimized for speed

### Performance Impact

- **Overhead**: < 1ms additional processing time per request
- **Memory**: Minimal memory overhead (~50KB for error handling components)
- **Logging**: Async logging prevents I/O blocking
- **Serialization**: Efficient JSON serialization for error responses

## Security Considerations

### Information Disclosure Prevention

1. **Stack Traces**: Never exposed in production error responses
2. **Internal Details**: Database errors mapped to generic messages
3. **User Data**: Sensitive information sanitized in error logs
4. **Debug Information**: Only included in development mode
5. **Error IDs**: Use unpredictable identifiers for security

### Security Headers

Error responses include security headers:
```
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
```

### Rate Limiting Integration

Error responses respect rate limiting:
- Include `Retry-After` headers for 429 responses
- Log excessive error rates for security monitoring
- Integrate with DDoS protection systems

## Conclusion

The standardized error handling system provides:

✅ **Consistency**: All errors follow the same format and conventions
✅ **Reliability**: Comprehensive coverage with fallback mechanisms  
✅ **User Experience**: Clear, actionable error messages
✅ **Developer Experience**: Easy debugging with error IDs and context
✅ **Monitoring**: Complete observability with logging and metrics
✅ **Security**: Protection against information disclosure
✅ **Performance**: Minimal overhead with optimized processing
✅ **Maintainability**: Centralized error handling reduces code duplication

This system ensures that all API users receive consistent, helpful error information while providing developers with the tools needed to debug and resolve issues efficiently.