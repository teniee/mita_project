# flake8: noqa

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
from app.api.transactions.routes import router as transactions_router
from app.api.users.routes import router as users_router
from app.api.endpoints.audit import router as audit_router
from app.api.endpoints.database_performance import router as db_performance_router
from app.api.endpoints.cache_management import router as cache_management_router
from app.core.config import settings
from app.core.limiter_setup import init_rate_limiter
from app.core.async_session import init_database, close_database
from app.core.logging_config import setup_logging
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
    """Detailed health check with database status"""
    return {
        "status": "healthy",
        "service": "Mita Finance API", 
        "version": "1.0.0",
        "database": "connected",
        "timestamp": time.time()
    }

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

# Add comprehensive audit logging middleware
@app.middleware("http")
async def audit_logging_middleware(request: Request, call_next):
    return await audit_middleware(request, call_next)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time
    logging.info(
        f"{request.method} {request.url.path} completed in {duration*1000:.2f}ms with status {response.status_code}"
    )
    return response


@app.middleware("http")
async def capture_request_bodies(request: Request, call_next):
    body = await request.body()
    try:
        response = await call_next(request)
    except Exception as exc:
        with sentry_sdk.push_scope() as scope:
            scope.set_extra("request_body", body.decode("utf-8", "ignore"))
            sentry_sdk.capture_exception(exc)
        raise
    if response.status_code >= 400:
        with sentry_sdk.push_scope() as scope:
            scope.set_extra("request_body", body.decode("utf-8", "ignore"))
            sentry_sdk.capture_message(
                f"HTTP {response.status_code} for {request.url.path}"
            )
    return response


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

# Public routes with rate limiter
app.include_router(
    auth_router,
    prefix="/api",
    tags=["Authentication"],
    dependencies=[Depends(RateLimiter(times=10, seconds=60))],
)

# Protected routes
private_routers_list = [
    (financial_router, "/api/financial", ["Financial"]),
    (users_router, "/api/users", ["Users"]),
    (calendar_router, "/api/calendar", ["Calendar"]),
    (challenge_router, "/api/challenges", ["Challenges"]),
    (expense_router, "/api/expenses", ["Expenses"]),
    (goal_router, "/api/goals", ["Goals"]),
    (goals_crud_router, "/api", ["GoalsCRUD"]),
    (plan_router, "/api/plans", ["Plans"]),
    (budget_router, "/api/budgets", ["Budgets"]),
    (analytics_router, "/api/analytics", ["Analytics"]),
    (behavior_router, "/api/behavior", ["Behavior"]),
    (spend_router, "/api/spend", ["Spend"]),
    (style_router, "/api/styles", ["Styles"]),
    (insights_router, "/api", ["Insights"]),
    (habits_router, "/api", ["Habits"]),
    (ai_router, "/api/ai", ["AI"]),
    (transactions_router, "/api", ["Transactions"]),
    (iap_router, "/api/iap", ["IAP"]),
    (notifications_router, "/api/notifications", ["Notifications"]),
    (mood_router, "/api/mood", ["Mood"]),
    (referral_router, "/api/referrals", ["Referrals"]),
    (onboarding_router, "/api/onboarding", ["Onboarding"]),
    (cohort_router, "/api/cohorts", ["Cohorts"]),
    (cluster_router, "/api/clusters", ["Clusters"]),
    (checkpoint_router, "/api/checkpoints", ["Checkpoints"]),
    (drift_router, "/api/drift", ["Drift"]),
    (audit_router, "/api", ["Audit"]),
    (db_performance_router, "/api", ["Database Performance"]),
    (cache_management_router, "/api", ["Cache Management"]),
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
    """Initialize application on startup"""
    await init_rate_limiter(app)
    await init_database()

@app.on_event("shutdown")
async def on_shutdown():
    """Clean up resources on shutdown"""
    await close_database()
