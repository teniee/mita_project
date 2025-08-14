# flake8: noqa

# Fix for Python 3.10+ collections compatibility BEFORE any other imports
import collections
import collections.abc
if not hasattr(collections, "MutableMapping"):
    collections.MutableMapping = collections.abc.MutableMapping
if not hasattr(collections, "MutableSet"):
    collections.MutableSet = collections.abc.MutableSet
if not hasattr(collections, "Iterable"):
    collections.Iterable = collections.abc.Iterable
if not hasattr(collections, "Mapping"):
    collections.Mapping = collections.abc.Mapping

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
from app.api.plan.routes import router as plan_router
from app.api.referral.routes import router as referral_router
from app.api.spend.routes import router as spend_router
from app.api.style.routes import router as style_router
from app.api.tasks.routes import router as tasks_router
from app.api.transactions.routes import router as transactions_router
from app.api.users.routes import router as users_router
from app.api.endpoints.audit import router as audit_router
from app.api.endpoints.database_performance import router as db_performance_router
from app.api.endpoints.cache_management import router as cache_management_router
from app.api.endpoints.feature_flags import router as feature_flags_router
from app.core.config import settings
from app.core.limiter_setup import init_rate_limiter
from app.core.async_session import init_database, close_database
from app.core.logging_config import setup_logging
from app.core.feature_flags import get_feature_flag_manager, is_feature_enabled
from app.core.deployment_optimizations import apply_platform_optimizations
from app.middleware.audit_middleware import audit_middleware
from app.core.error_handler import (
    MITAException, ValidationException, 
    mita_exception_handler, validation_exception_handler,
    sqlalchemy_exception_handler, generic_exception_handler
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
sentry_sdk.init(
    dsn=os.getenv("SENTRY_DSN"),
    integrations=[FastApiIntegration(), RqIntegration()],
    traces_sample_rate=1.0,
    send_default_pii=True,
)

# Initialize comprehensive logging
setup_logging()

# Apply platform-specific optimizations
deployment_config = apply_platform_optimizations()

# Initialize logger after logging setup
logger = logging.getLogger(__name__)
logger.info(f"Applied optimizations for platform: {deployment_config['platform']}")

app = FastAPI(title="Mita Finance API", version="1.0.0")

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
        "upstash_configured": bool(os.getenv("UPSTASH_AUTH_TOKEN")),
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

# Security and CORS middlewares
app.add_middleware(HTTPSRedirectMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
        
        # Send to Sentry for critical errors only
        sentry_sdk.capture_exception(exc)
        raise


# Minimal audit middleware for auth endpoints only
@app.middleware("http") 
async def selective_audit_middleware(request: Request, call_next):
    """Apply audit logging only to auth endpoints for better performance"""
    # Only audit auth endpoints to reduce overhead
    if request.url.path.startswith("/api/auth"):
        return await audit_middleware(request, call_next)
    else:
        # Skip audit for all other endpoints
        return await call_next(request)


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
    (cohort_router, "/api", ["Cohorts"]),
    (cluster_router, "/api", ["Clusters"]),
    (checkpoint_router, "/api", ["Checkpoints"]),
    (drift_router, "/api", ["Drift"]),
    (audit_router, "/api", ["Audit"]),
    (db_performance_router, "/api", ["Database Performance"]),
    (cache_management_router, "/api", ["Cache Management"]),
    (feature_flags_router, "/api", ["Feature Flags"]),
]

for router, prefix, tags in private_routers_list:
    app.include_router(
        router,
        prefix=prefix,
        tags=tags,
        dependencies=[Depends(get_current_user)],
    )

# ---- Exception Handlers ----

# Custom MITA exceptions
app.add_exception_handler(MITAException, mita_exception_handler)

# Pydantic validation errors
app.add_exception_handler(ValidationError, validation_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)

# Database errors
app.add_exception_handler(SQLAlchemyError, sqlalchemy_exception_handler)

# HTTP exceptions
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    from app.core.error_handler import ErrorHandler
    return ErrorHandler.create_error_response(exc, request)

# Generic exception handler (catch-all)
app.add_exception_handler(Exception, generic_exception_handler)


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
            
            # Rate limiter with timeout
            try:
                await asyncio.wait_for(init_rate_limiter(app), timeout=3.0)
                services_status["rate_limiter"] = True
                logging.info("✅ Rate limiter ready")
            except asyncio.TimeoutError:
                logging.warning("⚠️ Rate limiter init timed out - continuing without it")
            except Exception as e:
                logging.warning(f"⚠️ Rate limiter init failed: {e}")
            
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
    await close_database()
