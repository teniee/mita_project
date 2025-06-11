# flake8: noqa
import os

# --- Раннее создание firebase.json, до всех импортов ---
firebase_path = "/tmp/firebase.json"  # ← здесь замена

if "FIREBASE_JSON" in os.environ:
    with open(firebase_path, "w") as f:
        f.write(os.environ["FIREBASE_JSON"])
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = firebase_path
    os.environ["GOOGLE_CREDENTIALS_PATH"] = firebase_path


import logging
import time

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi_limiter.depends import RateLimiter
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.cors import CORSMiddleware

from app.api.analytics.routes import router as analytics_router

# New style routers from subdirectories
from app.api.auth.routes import router as auth_router
from app.api.auth_api import router as auth_router_legacy  # Renamed to avoid conflict
from app.api.behavior.routes import router as behavior_router
from app.api.budget.routes import router as budget_router
from app.api.calendar_api_extensions import router as calendar_ext_router
from app.api.calendar_api_redistribute import router as redistribute_router
from app.api.calendar_api_sql import router as calendar_router
from app.api.calendar_api_summary import router as summary_router
from app.api.challenge.routes import router as challenge_router
from app.api.checkpoint.routes import router as checkpoint_router
from app.api.cluster.routes import router as cluster_router
from app.api.cohort.routes import router as cohort_router
from app.api.dependencies import get_current_user
from app.api.drift.routes import router as drift_router
from app.api.expense.routes import router as expense_router
from app.api.financial.routes import router as financial_router
from app.api.goal.routes import router as goal_router
from app.api.iap.routes import router as iap_router
from app.api.ocr_api import router as ocr_router
from app.api.ocr_google_api import router as ocr_google_router
from app.api.ocr_image_api import router as ocr_image_router
from app.api.onboarding.routes import router as onboarding_router
from app.api.plan.routes import router as plan_router
from app.api.referral.routes import router as referral_router
from app.api.spend.routes import router as spend_router
from app.api.style.routes import router as style_router
from app.api.transactions.routes import (
    router as transactions_router,  # This is likely the intended transactions_router
)
from app.api.transactions_sql import (
    router as transactions_sql_router,  # Renamed to avoid conflict
)
from app.api.users.routes import router as users_router
from app.core.limiter_setup import init_rate_limiter
from app.utils.response_wrapper import error_response, success_response

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Mita Finance API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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


# Include public routers (order might matter if prefixes overlap, ensure unique paths)
# Mount legacy auth routes under the same `/api` prefix so the
# Google login endpoint becomes `/api/auth/google` as expected by the
# mobile application.
app.include_router(auth_router_legacy, prefix="/api", tags=["auth_legacy"])
app.include_router(ocr_google_router, prefix="/api/v0/ocr/google", tags=["ocr_legacy"])
app.include_router(ocr_image_router, prefix="/api/v0/ocr/image", tags=["ocr_legacy"])
app.include_router(ocr_router, prefix="/api/v0/ocr", tags=["ocr_legacy"])
app.include_router(
    summary_router, prefix="/api/v0/calendar/summary", tags=["calendar_legacy"]
)
app.include_router(
    redistribute_router,
    prefix="/api/v0/calendar/redistribute",
    tags=["calendar_legacy"],
)
app.include_router(
    calendar_ext_router, prefix="/api/v0/calendar/extensions", tags=["calendar_legacy"]
)
app.include_router(
    transactions_sql_router,
    prefix="/api/v0/transactions_sql",
    tags=["transactions_legacy"],
)

# Include new style public routers (auth is usually public for login/register)
app.include_router(
    auth_router,
    prefix="/api/auth",
    tags=["Authentication"],
    dependencies=[Depends(RateLimiter(times=10, seconds=60))],
)

# Include new style private routers (protected by auth)
private_routers_list = [
    (financial_router, "/api/financial", ["Financial"]),
    (users_router, "/api/users", ["Users"]),
    (calendar_router, "/api/calendar", ["Calendar"]),
    (challenge_router, "/api/challenges", ["Challenges"]),
    (expense_router, "/api/expenses", ["Expenses"]),
    (goal_router, "/api/goals", ["Goals"]),
    (plan_router, "/api/plans", ["Plans"]),
    (budget_router, "/api/budgets", ["Budgets"]),
    (analytics_router, "/api/analytics", ["Analytics"]),
    (behavior_router, "/api/behavior", ["Behavior"]),
    (spend_router, "/api/spend", ["Spend"]),
    (style_router, "/api/styles", ["Styles"]),
    (transactions_router, "/api/transactions", ["Transactions"]),
    (iap_router, "/api/iap", ["IAP"]),
    (referral_router, "/api/referrals", ["Referrals"]),
    (onboarding_router, "/api/onboarding", ["Onboarding"]),
    (cohort_router, "/api/cohorts", ["Cohorts"]),
    (cluster_router, "/api/clusters", ["Clusters"]),
    (checkpoint_router, "/api/checkpoints", ["Checkpoints"]),
    (drift_router, "/api/drift", ["Drift"]),
]

for router_item, prefix, tags_list in private_routers_list:
    app.include_router(
        router_item,
        prefix=prefix,
        tags=tags_list,
        dependencies=[Depends(get_current_user)],
    )


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


@app.on_event("startup")
async def on_startup():
    await init_rate_limiter(app)
