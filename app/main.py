# flake8: noqa
# MITA Finance API - Production Ready

import asyncio
import json
import logging
import os
import time

import firebase_admin
import sentry_sdk
from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
from fastapi.responses import JSONResponse
from fastapi_limiter.depends import RateLimiter
from firebase_admin import credentials
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.rq import RqIntegration
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.cors import CORSMiddleware

from app.api.ai.routes import router as ai_router
from app.api.analytics.routes import router as analytics_router
from app.api.auth.routes import router as auth_router
from app.api.behavior.routes import router as behavior_router
from app.api.budget.routes import router as budget_router
from app.api.calendar.routes import router as calendar_router
from app.api.challenge.routes import router as challenge_router
from app.api.checkpoint.routes import router as checkpoint_router
from app.api.cluster.routes import router as cluster_router
from app.api.cohort.routes import router as cohort_router
from app.api.dashboard.routes import router as dashboard_router
from app.api.dependencies import get_current_user
from app.api.drift.routes import router as drift_router
from app.api.expense.routes import router as expense_router
from app.api.financial.routes import router as financial_router
from app.api.goal.routes import router as goal_router
from app.api.goals.routes import router as goals_crud_router
from app.api.habits.routes import router as habits_router
from app.api.iap.routes import router as iap_router
from app.api.insights.routes import router as insights_router
from app.api.mood.routes import router as mood_router
from app.api.notifications.routes import router as notifications_router
from app.api.onboarding.routes import router as onboarding_router
from app.api.ocr.routes import router as ocr_router
from app.api.plan.routes import router as plan_router
from app.api.referral.routes import router as referral_router
from app.api.spend.routes import router as spend_router
from app.api.style.routes import router as style_router
from app.api.tasks.routes import router as tasks_router
from app.api.transactions.routes import router as transactions_router
from app.api.users.routes import router as users_router
from app.api.email.routes import router as email_router
from app.api.installments.routes import router as installments_router
from app.api.endpoints.audit import router as audit_router
from app.api.endpoints.database_performance import router as db_performance_router
from app.api.endpoints.cache_management import router as cache_management_router
from app.api.endpoints.feature_flags import router as feature_flags_router
from app.api.health.external_services_routes import router as external_services_health_router
from app.core.config import settings
from app.core.limiter_setup import init_rate_limiter
from app.core.async_session import init_database, close_database
from app.core.simple_rate_limiter import check_api_rate_limit
from app.core.logging_config import setup_logging
from app.core.feature_flags import get_feature_flag_manager, is_feature_enabled
from app.core.deployment_optimizations import apply_platform_optimizations
from app.middleware.audit_middleware import audit_middleware
from app.core.error_handler import (
    MITAException, ValidationException, RateLimitException,
    mita_exception_handler, validation_exception_handler,
    rate_limit_exception_handler, sqlalchemy_exception_handler, generic_exception_handler
)
from app.utils.response_wrapper import error_response
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

# ---- Firebase Admin SDK init ----
if not firebase_admin._apps:
    firebase_json = os.environ.get("FIREBASE_JSON")
    if firebase_json:
        cred = credentials.Certificate(json.loads(firebase_json))
    else:
        cred_path = os.getenv("GOOGLE_SERVICE_ACCOUNT") or os.getenv(
            "GOOGLE_APPLICATION_CREDENTIALS"
        )
        if cred_path and os.path.exists(cred_path):
            cred = credentials.Certificate(cred_path)
        else:
            cred = credentials.ApplicationDefault()

    firebase_admin.initialize_app(cred)

# ---- Sentry setup ----
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from sentry_sdk.integrations.asyncpg import AsyncPGIntegration
from sentry_sdk.integrations.redis import RedisIntegration
from sentry_sdk.integrations.httpx import HttpxIntegration
from sentry_sdk.integrations.logging import LoggingIntegration
import sentry_sdk
from sentry_sdk import set_user, set_tag, set_context

# Configure Sentry logging integration
sentry_logging = LoggingIntegration(
    level=logging.INFO,  # Capture info and above as breadcrumbs
    event_level=logging.ERROR  # Send errors and above as events
)

def configure_sentry():
    """Configure Sentry with comprehensive error monitoring for financial services"""
    sentry_dsn = os.getenv("SENTRY_DSN")
    environment = os.getenv("ENVIRONMENT", "development")
    
    if not sentry_dsn:
        logger.warning("Sentry DSN not configured - error monitoring disabled")
        return
    
    # Determine sample rates based on environment
    if environment == "production":
        traces_sample_rate = 0.1  # 10% of transactions for production
        profiles_sample_rate = 0.1  # 10% profiling in production
    elif environment == "staging":
        traces_sample_rate = 0.5  # 50% for staging
        profiles_sample_rate = 0.5
    else:
        traces_sample_rate = 1.0  # 100% for development
        profiles_sample_rate = 1.0
    
    sentry_sdk.init(
        dsn=sentry_dsn,
        environment=environment,
        
        # Comprehensive integrations for financial services
        integrations=[
            FastApiIntegration(
                auto_enable=True,
                transaction_style="endpoint",
                failed_request_status_codes=[400, range(500, 600)]
            ),
            RqIntegration(),
            SqlalchemyIntegration(
                auto_enable=True
            ),
            AsyncPGIntegration(),
            RedisIntegration(),
            HttpxIntegration(),
            sentry_logging
        ],
        
        # Performance monitoring
        traces_sample_rate=traces_sample_rate,
        profiles_sample_rate=profiles_sample_rate,
        
        # Security and compliance for financial services
        send_default_pii=False,  # Don't send PII data by default
        
        # Release and version tracking
        release=os.getenv("SENTRY_RELEASE", "mita-finance@1.0.0"),
        
        # Server metadata
        server_name=os.getenv("SERVER_NAME", "mita-api-server"),
        
        # Custom configuration
        max_breadcrumbs=50,
        attach_stacktrace=True,
        
        # Custom before_send filter
        before_send=filter_sensitive_data,
        before_send_transaction=filter_sensitive_transactions,
        
        # Custom error sampling
        sample_rate=1.0,  # Capture all errors
        
        # Debug mode for development
        debug=environment == "development",
        
        # Custom tags for financial services
        _experiments={
            "profiles_sample_rate": profiles_sample_rate,
        }
    )
    
    # Set global context for financial services
    set_context("application", {
        "name": "MITA Finance API",
        "version": "1.0.0",
        "type": "financial_services",
        "compliance": "PCI_DSS"
    })
    
    # Set global tags
    set_tag("service", "mita-api")
    set_tag("component", "backend")
    set_tag("environment", environment)
    
    logger.info(f"Sentry error monitoring initialized for {environment} environment")

def filter_sensitive_data(event, hint):
    """Filter out sensitive financial data before sending to Sentry"""
    
    # Remove sensitive keys from request data
    sensitive_keys = {
        'password', 'token', 'secret', 'key', 'authorization',
        'card_number', 'cvv', 'pin', 'ssn', 'tax_id',
        'account_number', 'routing_number', 'sort_code',
        'iban', 'swift', 'bank_account'
    }
    
    def sanitize_dict(data):
        if isinstance(data, dict):
            sanitized = {}
            for key, value in data.items():
                key_lower = key.lower()
                if any(sensitive_key in key_lower for sensitive_key in sensitive_keys):
                    sanitized[key] = "[REDACTED]"
                elif isinstance(value, dict):
                    sanitized[key] = sanitize_dict(value)
                elif isinstance(value, list):
                    sanitized[key] = [sanitize_dict(item) if isinstance(item, dict) else item for item in value]
                else:
                    sanitized[key] = value
            return sanitized
        return data
    
    # Sanitize request data
    if 'request' in event:
        if 'data' in event['request']:
            event['request']['data'] = sanitize_dict(event['request']['data'])
        if 'query_string' in event['request']:
            # Remove sensitive query parameters
            query_string = event['request']['query_string']
            if query_string and any(key in query_string.lower() for key in sensitive_keys):
                event['request']['query_string'] = "[REDACTED]"
    
    # Sanitize extra data
    if 'extra' in event:
        event['extra'] = sanitize_dict(event['extra'])
    
    # Add financial service context
    if 'tags' not in event:
        event['tags'] = {}
    
    event['tags']['financial_service'] = True
    event['tags']['pci_compliant'] = True
    
    return event

def filter_sensitive_transactions(event, hint):
    """Filter sensitive data from transaction events"""
    
    # Add financial context to transactions
    if 'contexts' not in event:
        event['contexts'] = {}
    
    event['contexts']['financial_operation'] = {
        'type': 'financial_transaction',
        'compliance_level': 'pci_dss',
        'data_classification': 'confidential'
    }
    
    return event

# Initialize comprehensive logging first
setup_logging()

# Initialize logger after logging setup
logger = logging.getLogger(__name__)

# Initialize Sentry (now that logger is available)
configure_sentry()

# Validate dependencies before continuing startup
from app.core.dependency_validator import validate_dependencies_on_startup
validate_dependencies_on_startup()

# Apply platform-specific optimizations
deployment_config = apply_platform_optimizations()
logger.info(f"Applied optimizations for platform: {deployment_config['platform']}")

# Import standardized error handling middleware and documentation
from app.middleware.standardized_error_middleware import (
    StandardizedErrorMiddleware,
    ResponseValidationMiddleware,
    RequestContextMiddleware
)
from app.core.openapi_documentation import (
    get_standardized_openapi_schema
)

# Create FastAPI app with enhanced documentation
app = FastAPI(
    title="MITA Finance API",
    version="1.0.0",
    description="""
## MITA Finance API

A comprehensive financial management API with standardized error handling and response formats.

### Features

- **Standardized Error Responses**: All errors follow a consistent format with proper error codes
- **Comprehensive Validation**: Input validation with detailed error messages
- **Security**: JWT-based authentication with rate limiting
- **Financial Operations**: Transaction management, budget tracking, and financial analysis
- **Audit Logging**: Comprehensive request and security event logging

### Error Handling

This API uses a standardized error response format across all endpoints:

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

### Authentication

Most endpoints require authentication via JWT tokens sent via the Authorization header:

```
Authorization: Bearer <access_token>
```

**Security Architecture:**
- **Stateless JWT Authentication**: All tokens sent via Authorization header only
- **No Cookie-Based Auth**: CSRF protection not required (no session cookies)
- **Token Security**: Short-lived access tokens (2 hours) with refresh rotation
- **CORS Protection**: Strict origin allowlist with credential support

For security architecture details, see: `app/core/security_notes.py`

### Rate Limiting

API endpoints are rate-limited to ensure fair usage. Rate limit information is provided in response headers.
    """.strip(),
    contact={
        "name": "MITA Finance API Support",
        "email": "api-support@mita.finance"
    },
    license_info={
        "name": "MIT License",
        "url": "https://opensource.org/licenses/MIT"
    }
)

# ---- Health Check Endpoint ----
@app.get("/")
async def health_check():
    """Simple health check endpoint"""
    return {
        "status": "healthy", 
        "service": "Mita Finance API",
        "version": "1.0.0",
        "message": "API is running successfully!"
    }

# Debug endpoint removed - use /health for production health checks


# Debug auth endpoint removed - use /api/auth/ routes for authentication


# Debug register endpoint removed - use /api/auth/register for registration

# ---- REMOVED EMERGENCY ENDPOINTS ----
# Emergency endpoints have been integrated into the main authentication system
# All registration and authentication should go through /api/auth/ routes
# This eliminates the architectural debt and provides proper security integration


# Emergency test endpoint removed - use /health for server status checks


# SECURITY FIX: GET-based authentication endpoint removed due to critical security vulnerability
# - Passwords were exposed in URL parameters, server logs, and browser history
# - This violates PCI DSS compliance and financial application security standards
# - Use POST /flutter-register endpoint instead for secure authentication
# 
# @app.get("/flutter-register") - REMOVED FOR SECURITY


# SECURITY FIX: GET-based login endpoint removed due to critical security vulnerability
# - Passwords were exposed in URL parameters, server logs, and browser history  
# - This violates PCI DSS compliance and financial application security standards
# - Use secure POST endpoints for authentication instead
#
# @app.get("/flutter-login") - REMOVED FOR SECURITY


# Flutter registration endpoint removed - use /api/auth/register for all registration


@app.get("/health")
async def detailed_health_check():
    """Detailed health check with database status and performance metrics"""
    from app.core.async_session import check_database_health
    from app.core.performance_cache import get_cache_stats
    
    # Check environment configuration
    config_status = {
        "jwt_secret_configured": bool(settings.JWT_SECRET or settings.SECRET_KEY),
        "database_configured": bool(settings.DATABASE_URL),
        "environment": settings.ENVIRONMENT,
        "upstash_configured": bool(os.getenv("UPSTASH_REDIS_REST_URL") and os.getenv("UPSTASH_REDIS_REST_TOKEN")),
        "upstash_rest_api": bool(os.getenv("UPSTASH_REDIS_REST_URL") and os.getenv("UPSTASH_REDIS_REST_TOKEN")),
        "openai_configured": bool(settings.OPENAI_API_KEY)
    }
    
    # Check database health
    database_status = "unknown"
    database_error = None
    
    try:
        db_healthy = await asyncio.wait_for(check_database_health(), timeout=1.0)  # Very short timeout for responsive health checks
        database_status = "connected" if db_healthy else "disconnected"
    except asyncio.TimeoutError:
        database_status = "timeout"
        database_error = "Database health check timed out"
    except Exception as e:
        database_status = "error"
        database_error = str(e)
    
    # Get performance cache statistics
    cache_stats = get_cache_stats()
    
    # Determine overall status
    overall_status = "healthy"
    if database_status != "connected":
        overall_status = "degraded"
    if not config_status["jwt_secret_configured"] or not config_status["database_configured"]:
        overall_status = "unhealthy"
    
    response = {
        "status": overall_status,
        "service": "Mita Finance API", 
        "version": "1.0.0",
        "database": database_status,
        "config": config_status,
        "cache_stats": cache_stats,
        "timestamp": time.time(),
        "port": os.getenv("PORT", "8000")
    }
    
    if database_error:
        response["database_error"] = database_error
    
    return response

# ---- Middlewares ----

# Add standardized error handling middleware (first for comprehensive coverage)
app.add_middleware(StandardizedErrorMiddleware, include_request_details=settings.DEBUG)
app.add_middleware(ResponseValidationMiddleware, validate_success_responses=settings.DEBUG)
app.add_middleware(RequestContextMiddleware)

# Security and CORS middlewares
app.add_middleware(HTTPSRedirectMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- CSRF Protection: NOT IMPLEMENTED (by design) ----
# MITA uses stateless JWT authentication via Authorization headers only.
# CSRF protection is not required because:
# 1. No session cookies or cookie-based authentication
# 2. Browsers don't automatically send Authorization headers (CSRF attack vector closed)
# 3. All tokens sent via header, returned in response body (never in cookies)
# See: app/core/security_notes.py and docs/adr/ADR-20251115-csrf-protection-analysis.md

# Lightweight performance monitoring middleware

@app.middleware("http")
async def performance_logging_middleware(request: Request, call_next):
    """Lightweight middleware for critical error handling only"""
    start_time = time.time()
    
    try:
        response = await call_next(request)
        duration = time.time() - start_time
        
        # Only log very slow requests to reduce I/O overhead
        if duration > 2.0:  # Only log requests taking more than 2 seconds
            logger.warning(
                f"SLOW REQUEST: {request.method} {request.url.path} "
                f"completed in {duration*1000:.0f}ms with status {response.status_code}"
            )
            
        return response
        
    except Exception as exc:
        duration = time.time() - start_time
        logger.error(
            f"ERROR: {request.method} {request.url.path} failed after {duration*1000:.0f}ms: {exc}"
        )
        
        # Send to Sentry with comprehensive context
        with sentry_sdk.push_scope() as scope:
            scope.set_tag("error_type", "middleware_exception")
            scope.set_tag("endpoint", request.url.path)
            scope.set_tag("method", request.method)
            scope.set_context("request", {
                "url": str(request.url),
                "method": request.method,
                "headers": dict(request.headers),
                "duration_ms": duration * 1000
            })
            
            # Extract user context if available
            try:
                auth_header = request.headers.get("Authorization")
                if auth_header and auth_header.startswith("Bearer "):
                    raw_token = auth_header.replace("Bearer ", "").strip()

                    # If token is empty or looks like garbage, consider unauthenticated
                    if not raw_token or raw_token == ".":
                        scope.set_tag("user_authenticated", False)
                    else:
                        try:
                            from app.services.auth_jwt_service import get_token_info
                            token_info = get_token_info(raw_token)
                            if token_info:
                                scope.set_user({"id": token_info.get("user_id")})
                                scope.set_tag("user_authenticated", True)
                            else:
                                scope.set_tag("user_authenticated", False)
                        except Exception:
                            # Error decoding token - not 502, just "unauthenticated"
                            scope.set_tag("user_authenticated", False)
                else:
                    scope.set_tag("user_authenticated", False)
            except Exception:
                scope.set_tag("user_authenticated", False)
            
            sentry_sdk.capture_exception(exc)
        raise


# RESTORED: Optimized audit middleware with separate database connections to prevent deadlocks
# The previous audit middleware caused database deadlocks due to concurrent sessions.
# This new implementation uses a separate connection pool and async queuing to prevent issues.

@app.middleware("http")
async def optimized_audit_middleware(request: Request, call_next):
    """
    Lightweight audit middleware with performance optimizations.
    Uses separate database pool and async queuing to prevent deadlocks.
    """
    from app.core.audit_logging import audit_logger
    import time
    
    # Skip audit logging for health checks and static content
    skip_paths = ["/", "/health", "/debug", "/emergency-test", "/docs", "/redoc", "/openapi.json"]
    if request.url.path in skip_paths:
        return await call_next(request)
    
    start_time = time.time()
    user_id = None
    session_id = None
    
    try:
        # Process the request
        response = await call_next(request)
        response_time_ms = (time.time() - start_time) * 1000
        
        # Extract user info from token if present (non-blocking)
        try:
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                raw_token = auth_header.replace("Bearer ", "").strip()

                # If token is empty or looks like garbage, skip parsing
                if raw_token and raw_token != ".":
                    try:
                        from app.services.auth_jwt_service import get_token_info
                        token_info = get_token_info(raw_token)
                        if token_info:
                            user_id = token_info.get("user_id")
                            session_id = token_info.get("jti")
                    except Exception:
                        # Error decoding token - continue without user info
                        pass
        except Exception:
            # Don't let token parsing errors affect the request
            pass
        
        # Only log significant events to reduce overhead
        should_log = (
            response_time_ms > 1000 or  # Slow requests
            response.status_code >= 400 or  # Errors
            request.url.path.startswith("/api/auth/") or  # Authentication endpoints
            request.url.path.startswith("/api/users/") or  # User management
            request.url.path.startswith("/api/transactions/")  # Financial operations
        )
        
        if should_log:
            # Use fire-and-forget async logging (non-blocking)
            import asyncio
            asyncio.create_task(audit_logger.log_request_response(
                request=request,
                response=response,
                response_time_ms=response_time_ms,
                user_id=user_id,
                session_id=session_id
            ))
        
        return response
        
    except Exception as exc:
        response_time_ms = (time.time() - start_time) * 1000
        
        # Log errors with fire-and-forget async logging
        import asyncio
        asyncio.create_task(audit_logger.log_request_response(
            request=request,
            response=None,
            response_time_ms=response_time_ms,
            user_id=user_id,
            session_id=session_id,
            error_message=str(exc)[:500]
        ))
        
        raise


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Strict-Transport-Security"] = (
        "max-age=63072000; includeSubDomains"
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    if request.url.path.startswith("/docs") or request.url.path.startswith("/redoc"):
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net"
        )
    else:
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net"
        )
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=()"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    return response


# ---- Routers ----

# Public routes with optimized rate limiting
app.include_router(
    auth_router,
    prefix="/api",
    tags=["Authentication"],
    # Removed heavy rate limiter dependency for performance - rate limiting handled in routes
)

# Protected routes - Fixed duplicate path segments
# Each router already has its own prefix, so we only add /api base
private_routers_list = [
    (financial_router, "/api", ["Financial"]),
    (users_router, "/api", ["Users"]),
    (email_router, "/api", ["Email"]),
    (dashboard_router, "/api", ["Dashboard"]),
    (calendar_router, "/api", ["Calendar"]),
    (challenge_router, "/api", ["Challenges"]),
    (expense_router, "/api", ["Expenses"]),
    (goal_router, "/api", ["Goals"]),
    (goals_crud_router, "/api", ["GoalsCRUD"]),
    (plan_router, "/api", ["Plans"]),
    (budget_router, "/api", ["Budgets"]),
    (analytics_router, "/api", ["Analytics"]),
    (behavior_router, "/api", ["Behavior"]),
    (spend_router, "/api", ["Spend"]),
    (style_router, "/api", ["Styles"]),
    (tasks_router, "/api", ["Tasks"]),
    (insights_router, "/api", ["Insights"]),
    (habits_router, "/api", ["Habits"]),
    (ai_router, "/api", ["AI"]),
    (transactions_router, "/api", ["Transactions"]),
    (iap_router, "/api", ["IAP"]),
    (notifications_router, "/api", ["Notifications"]),
    (mood_router, "/api", ["Mood"]),
    (referral_router, "/api", ["Referrals"]),
    (onboarding_router, "/api", ["Onboarding"]),
    (ocr_router, "/api", ["OCR"]),
    (cohort_router, "/api", ["Cohorts"]),
    (cluster_router, "/api", ["Clusters"]),
    (checkpoint_router, "/api", ["Checkpoints"]),
    (drift_router, "/api", ["Drift"]),
    (audit_router, "/api", ["Audit"]),
    (db_performance_router, "/api", ["Database Performance"]),
    (cache_management_router, "/api", ["Cache Management"]),
    (feature_flags_router, "/api", ["Feature Flags"]),
    (installments_router, "/api", ["Installments"]),
    (external_services_health_router, "", ["Health"]),  # No /api prefix for health endpoints
]

for router, prefix, tags in private_routers_list:
    app.include_router(
        router,
        prefix=prefix,
        tags=tags,
        dependencies=[Depends(get_current_user), Depends(check_api_rate_limit)],
    )

# ---- STANDARDIZED EXCEPTION HANDLERS ----

# Import the new standardized error handling system
from app.core.standardized_error_handler import (
    StandardizedAPIException,
    StandardizedErrorHandler,
    AuthenticationError,
    AuthorizationError,
    ValidationError as StandardizedValidationError,
    ResourceNotFoundError,
    BusinessLogicError,
    DatabaseError as StandardizedDatabaseError,
    RateLimitError as StandardizedRateLimitError
)

# Standardized API exceptions
@app.exception_handler(StandardizedAPIException)
async def standardized_exception_handler(request: Request, exc: StandardizedAPIException):
    """Handle all standardized API exceptions"""
    return StandardizedErrorHandler.create_response(exc, request)

# Authentication errors
@app.exception_handler(AuthenticationError)
async def auth_exception_handler(request: Request, exc: AuthenticationError):
    """Handle authentication errors"""
    return StandardizedErrorHandler.create_response(exc, request)

# Authorization errors
@app.exception_handler(AuthorizationError)
async def authz_exception_handler(request: Request, exc: AuthorizationError):
    """Handle authorization errors"""
    return StandardizedErrorHandler.create_response(exc, request)

# Validation errors (both Pydantic and custom)
@app.exception_handler(ValidationError)
async def pydantic_validation_handler(request: Request, exc: ValidationError):
    """Handle Pydantic validation errors"""
    return StandardizedErrorHandler.create_response(exc, request)

@app.exception_handler(RequestValidationError)
async def request_validation_handler(request: Request, exc: RequestValidationError):
    """Handle FastAPI request validation errors"""
    return StandardizedErrorHandler.create_response(exc, request)

@app.exception_handler(StandardizedValidationError)
async def custom_validation_handler(request: Request, exc: StandardizedValidationError):
    """Handle custom validation errors"""
    return StandardizedErrorHandler.create_response(exc, request)

# Database errors
@app.exception_handler(SQLAlchemyError)
async def database_exception_handler(request: Request, exc: SQLAlchemyError):
    """Handle SQLAlchemy database errors"""
    from app.core.standardized_error_handler import map_database_error
    mapped_error = map_database_error(exc)
    return StandardizedErrorHandler.create_response(mapped_error, request)

# Rate limiting errors
@app.exception_handler(StandardizedRateLimitError)
async def rate_limit_handler(request: Request, exc: StandardizedRateLimitError):
    """Handle rate limiting errors"""
    return StandardizedErrorHandler.create_response(exc, request)

# HTTP exceptions (FastAPI/Starlette)
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Handle FastAPI/Starlette HTTP exceptions"""
    return StandardizedErrorHandler.create_response(exc, request)

# Legacy MITA exceptions (for backward compatibility)
app.add_exception_handler(MITAException, mita_exception_handler)
app.add_exception_handler(RateLimitException, rate_limit_exception_handler)

# Generic exception handler (catch-all for unexpected errors)
@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """Handle all other unexpected exceptions"""
    return StandardizedErrorHandler.create_response(exc, request)


# ---- Enhanced OpenAPI Documentation ----

@app.get("/openapi.json", include_in_schema=False)
async def get_enhanced_openapi():
    """Return enhanced OpenAPI schema with comprehensive error documentation"""
    if not hasattr(app, "openapi_schema") or app.openapi_schema is None:
        app.openapi_schema = get_standardized_openapi_schema(
            app=app,
            title="MITA Finance API",
            version="1.0.0",
            description=app.description
        )
    
    return app.openapi_schema


# ---- Startup ----


@app.on_event("startup")
async def on_startup():
    """Initialize application on startup with optimized performance"""
    try:
        logging.info("🚀 Starting MITA Finance API initialization...")
        
        # Initialize lightweight components first for faster startup
        tasks = []
        
        # Fast startup: Initialize only critical components
        logging.info("🚀 Starting fast initialization...")
        
        # Initialize feature flags (fast, synchronous)
        try:
            get_feature_flag_manager()
            logging.info("✅ Feature flags ready")
        except Exception as e:
            logging.warning(f"⚠️ Feature flags init warning: {e}")
        
        # Initialize critical services with short timeouts
        async def init_critical_services():
            services_status = {"rate_limiter": False, "database": False}
            
            # Rate limiter - RESTORED with lazy initialization
            try:
                await init_rate_limiter(app)
                services_status["rate_limiter"] = True
                logging.info("✅ Rate limiter configured with lazy initialization")
            except Exception as e:
                logging.warning(f"⚠️ Rate limiter init failed: {e}")
                app.state.redis_available = False
            
            # Database with minimal retry
            try:
                await asyncio.wait_for(init_database(), timeout=5.0)
                services_status["database"] = True
                logging.info("✅ Database ready")
            except asyncio.TimeoutError:
                logging.warning("⚠️ Database init timed out - will retry on first request")
            except Exception as e:
                logging.warning(f"⚠️ Database init failed: {e}")
            
            return services_status
        
        # Initialize critical services
        services_status = await init_critical_services()
        
        # Initialize optimized audit system
        try:
            from app.core.audit_logging import initialize_audit_system
            await asyncio.wait_for(initialize_audit_system(), timeout=3.0)
            services_status["audit_system"] = True
            logging.info("✅ Optimized audit system initialized")
        except asyncio.TimeoutError:
            logging.warning("⚠️ Audit system init timed out - will initialize on first use")
            services_status["audit_system"] = False
        except Exception as e:
            logging.warning(f"⚠️ Audit system init failed: {e}")
            services_status["audit_system"] = False
        
        # Log startup status
        ready_services = sum(services_status.values())
        total_services = len(services_status)
        logging.info(f"🎯 Fast startup complete: {ready_services}/{total_services} services ready")
        
        logging.info("🎉 MITA Finance API startup completed successfully!")
        
    except Exception as e:
        logging.error(f"💥 Startup error: {e}")
        import sentry_sdk
        sentry_sdk.capture_exception(e)
        # Don't exit - let the application start and show health check errors
        logging.warning("⚠️ Application starting with limited functionality")

@app.on_event("shutdown")
async def on_shutdown():
    """Clean up resources on shutdown"""
    try:
        # Close audit system connections
        from app.core.audit_logging import _audit_db_pool
        await _audit_db_pool.close()
        logging.info("✅ Audit system connections closed")
    except Exception as e:
        logging.error(f"❌ Error closing audit system: {e}")
    
    # Close main database connections
    await close_database()
