# flake8: noqa

import os
import logging
import time

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
from fastapi_limiter.depends import RateLimiter
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.cors import CORSMiddleware

import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.rq import RqIntegration

from app.api.auth.routes import router as auth_router
from app.api.analytics.routes import router as analytics_router
from app.api.ai.routes import router as ai_router
from app.api.behavior.routes import router as behavior_router
from app.api.budget.routes import router as budget_router
from app.api.calendar.routes import router as calendar_router
from app.api.challenge.routes import router as challenge_router
from app.api.checkpoint.routes import router as checkpoint_router
from app.api.cluster.routes import router as cluster_router
from app.api.cohort.routes import router as cohort_router
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
from app.api.dependencies import get_current_user
from app.core.config import settings
from app.core.limiter_setup import init_rate_limiter
from app.utils.response_wrapper import error_response

# ---- Sentry setup ----
sentry_sdk.init(
    dsn=os.getenv("SENTRY_DSN"),
    integrations=[FastApiIntegration(), RqIntegration()],
    traces_sample_rate=1.0,
    send_default_pii=True,
)

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Mita Finance API", version="1.0.0")

# ---- Middlewares ----

app.add_middleware(HTTPSRedirectMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Content-Security-Policy"] = "default-src 'self'"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=()"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    return response

# ---- Routers ----

# Public routes with rate limiter
app.include_router(
    auth_router,
    prefix="/api/auth",
    tags=["Authentication"],
    dependencies=[Depends(RateLimiter(times=10, seconds=60))]
)

# Protected routes
private_routers_list = [
    (financial_router, "/api/financial", ["Financial"]),
    (users_router, "/api/users", ["Users"]),
    (calendar_router, "/api/calendar", ["Calendar"]),
    (challenge_router, "/api/challenges", ["Challenges"]),
    (expense_router, "/api/expenses", ["Expenses"]),
    (goal_router, "/api/goals", ["Goals"]),
    (goals_crud_router, "/api/goals", ["GoalsCRUD"]),
    (plan_router, "/api/plans", ["Plans"]),
    (budget_router, "/api/budgets", ["Budgets"]),
    (analytics_router, "/api/analytics", ["Analytics"]),
    (behavior_router, "/api/behavior", ["Behavior"]),
    (spend_router, "/api/spend", ["Spend"]),
    (style_router, "/api/styles", ["Styles"]),
    (insights_router, "/api/insights", ["Insights"]),
    (habits_router, "/api/habits", ["Habits"]),
    (ai_router, "/api/ai", ["AI"]),
    (transactions_router, "/api/transactions", ["Transactions"]),
    (iap_router, "/api/iap", ["IAP"]),
    (notifications_router, "/api/notifications", ["Notifications"]),
    (mood_router, "/api/mood", ["Mood"]),
    (referral_router, "/api/referrals", ["Referrals"]),
    (onboarding_router, "/api/onboarding", ["Onboarding"]),
    (cohort_router, "/api/cohorts", ["Cohorts"]),
    (cluster_router, "/api/clusters", ["Clusters"]),
    (checkpoint_router, "/api/checkpoints", ["Checkpoints"]),
    (drift_router, "/api/drift", ["Drift"]),
]

for router, prefix, tags in private_routers_list:
    app.include_router(
        router,
        prefix=prefix,
        tags=tags,
        dependencies=[Depends(get_current_user)],
    )

# ---- Exception Handlers ----

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    logging.error(f"HTTPException: {exc.detail}")
    return error_response(error_message=exc.detail, status_code=exc.status_code)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logging.error(f"ValidationError: {exc.errors()}")
    return error_response(error_message=str(exc), status_code=422)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logging.error(f"Unhandled error: {exc}")
    return error_response(error_message="Internal server error", status_code=500)

# ---- Startup ----

@app.on_event("startup")
async def on_startup():
    await init_rate_limiter(app)
