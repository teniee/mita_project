#!/bin/bash
# MITA Backend Startup Script for Render Deployment
# This script validates environment variables and starts the application

set -e  # Exit on any error

echo "🚀 Starting MITA Finance Backend..."
echo "Environment: ${ENVIRONMENT:-development}"
echo "Port: ${PORT:-8000}"

# Function to check if a variable is set and not empty
check_env_var() {
    local var_name=$1
    local var_value=${!var_name}
    
    if [[ -z "$var_value" ]]; then
        echo "❌ ERROR: $var_name is not set or empty"
        return 1
    else
        echo "✅ $var_name is configured"
        return 0
    fi
}

# Function to check optional variables
check_optional_var() {
    local var_name=$1
    local var_value=${!var_name}
    
    if [[ -z "$var_value" ]]; then
        echo "⚠️  WARNING: $var_name is not set (optional)"
    else
        echo "✅ $var_name is configured"
    fi
}

echo ""
echo "🔍 Checking environment configuration..."

# Check critical environment variables for production
if [[ "${ENVIRONMENT}" == "production" ]]; then
    echo "Production environment detected - validating required variables..."
    
    critical_vars=(
        "DATABASE_URL"
        "SECRET_KEY" 
        "JWT_SECRET"
        "OPENAI_API_KEY"
    )
    
    all_critical_vars_set=true
    
    for var in "${critical_vars[@]}"; do
        if ! check_env_var "$var"; then
            all_critical_vars_set=false
        fi
    done
    
    if [[ "$all_critical_vars_set" == "false" ]]; then
        echo ""
        echo "❌ DEPLOYMENT FAILED: Missing critical environment variables"
        echo ""
        echo "📝 To fix this issue:"
        echo "1. Go to your Render Dashboard"
        echo "2. Navigate to your service → Environment tab"
        echo "3. Add the missing environment variables listed above"
        echo "4. Redeploy your service"
        echo ""
        echo "💡 Generate secret keys with:"
        echo "   openssl rand -hex 32"
        echo ""
        exit 1
    fi
    
    echo ""
    echo "✅ All critical environment variables are configured"
else
    echo "Development environment detected - skipping strict validation"
fi

# Redis configuration check — at least one provider required in production
# Supports: REDIS_URL (standard), UPSTASH_REDIS_REST_URL (Upstash REST), UPSTASH_REDIS_URL (Upstash direct)
echo ""
echo "🔍 Checking Redis configuration..."
redis_configured=false

if [[ -n "$REDIS_URL" ]]; then
    echo "✅ REDIS_URL is configured (standard Redis)"
    redis_configured=true
fi

if [[ -n "$UPSTASH_REDIS_REST_URL" ]]; then
    echo "✅ UPSTASH_REDIS_REST_URL is configured (Upstash REST API)"
    redis_configured=true
    if [[ -z "$UPSTASH_REDIS_REST_TOKEN" ]]; then
        echo "⚠️  WARNING: UPSTASH_REDIS_REST_TOKEN is missing — Upstash REST API will not authenticate"
    fi
fi

if [[ -n "$UPSTASH_REDIS_URL" ]]; then
    echo "✅ UPSTASH_REDIS_URL is configured (Upstash direct)"
    redis_configured=true
fi

if [[ "$redis_configured" == "false" ]]; then
    echo ""
    echo "╔══════════════════════════════════════════════════════════════════╗"
    echo "║  ⚠️  WARNING: No Redis configuration found                      ║"
    echo "║  Using in-memory fallbacks (degraded mode)                      ║"
    echo "╠══════════════════════════════════════════════════════════════════╣"
    echo "║  Affected features:                                            ║"
    echo "║  - Rate limiting → per-process in-memory                       ║"
    echo "║  - Task queue → background tasks may be dropped                ║"
    echo "║  - Token blacklisting → JWT revocation unavailable             ║"
    echo "║  - Caching → single-process in-memory only                     ║"
    echo "║                                                                 ║"
    echo "║  Add REDIS_URL, UPSTASH_REDIS_REST_URL, or UPSTASH_REDIS_URL  ║"
    echo "║  to restore full functionality.                                ║"
    echo "╚══════════════════════════════════════════════════════════════════╝"
    echo ""
fi

# Sentry error monitoring check — critical for production observability
echo ""
echo "🔍 Checking Sentry error monitoring..."

if [[ -n "$SENTRY_DSN" ]]; then
    echo "✅ SENTRY_DSN is configured — error monitoring active"
else
    if [[ "${ENVIRONMENT}" == "production" ]]; then
        echo ""
        echo "╔══════════════════════════════════════════════════════════════════╗"
        echo "║  ⚠️  WARNING: SENTRY_DSN is not configured                      ║"
        echo "║  Error monitoring is DISABLED in production!                     ║"
        echo "╠══════════════════════════════════════════════════════════════════╣"
        echo "║  Without Sentry, these capabilities are unavailable:            ║"
        echo "║  - Unhandled exception alerts → errors happen silently          ║"
        echo "║  - Performance transaction tracing → no latency visibility      ║"
        echo "║  - Error grouping and trends → no degradation detection         ║"
        echo "║  - Release health tracking → blind deploys                      ║"
        echo "║                                                                 ║"
        echo "║  Set SENTRY_DSN in your environment variables to enable.        ║"
        echo "╚══════════════════════════════════════════════════════════════════╝"
        echo ""
    else
        echo "⚠️  WARNING: SENTRY_DSN not configured — error monitoring disabled (OK for development)"
    fi
fi

echo ""
echo "🔍 Checking optional variables..."

# Check optional variables (Redis and Sentry handled above, not listed here)
optional_vars=(
    "SMTP_HOST"
    "UPSTASH_AUTH_TOKEN"
)

for var in "${optional_vars[@]}"; do
    check_optional_var "$var"
done

# Database URL format validation for PostgreSQL
if [[ -n "$DATABASE_URL" ]]; then
    if [[ "$DATABASE_URL" == *"postgresql"* ]] || [[ "$DATABASE_URL" == *"postgres"* ]]; then
        echo "✅ PostgreSQL database URL detected"
    else
        echo "⚠️  WARNING: DATABASE_URL format may not be compatible"
    fi
fi

echo ""
echo "🔄 Running database migrations..."
echo "Command: alembic upgrade head"
echo ""

# Run database migrations
# Temporarily disable exit-on-error to capture migration exit code
set +e
python -m alembic upgrade head
MIGRATION_EXIT_CODE=$?
set -e

if [ $MIGRATION_EXIT_CODE -ne 0 ]; then
    if [[ "${ENVIRONMENT}" == "production" ]]; then
        echo ""
        echo "╔══════════════════════════════════════════════════════════════════╗"
        echo "║  ❌ FATAL: Database migration failed in production!             ║"
        echo "║  Application startup ABORTED to prevent data corruption.       ║"
        echo "╠══════════════════════════════════════════════════════════════════╣"
        echo "║  Possible causes:                                              ║"
        echo "║  - Database unreachable (check DATABASE_URL)                   ║"
        echo "║  - Migration conflict (concurrent schema changes)              ║"
        echo "║  - Missing table or column (manual DB modification)            ║"
        echo "║  - Connection limit exhausted (Supabase/Railway)               ║"
        echo "║                                                                ║"
        echo "║  DO NOT start the app with an outdated schema.                 ║"
        echo "║  Fix the migration issue and redeploy.                         ║"
        echo "╚══════════════════════════════════════════════════════════════════╝"
        echo ""
        exit 1
    else
        echo ""
        echo "⚠️  WARNING: Migration failed in development mode."
        echo "   The application may not work correctly without migrations."
        echo "   Continuing anyway..."
        echo ""
    fi
else
    echo "✅ Migrations completed successfully"
fi

echo ""
echo "🔄 Starting application..."

# Worker configuration — read from WEB_CONCURRENCY env var (set in render.yaml / Railway)
# Default to 1 worker if not set, ensuring safe single-process fallback
WORKERS="${WEB_CONCURRENCY:-1}"

# Validate worker count: must be a positive integer between 1 and 16
if ! [[ "$WORKERS" =~ ^[0-9]+$ ]] || [ "$WORKERS" -lt 1 ] || [ "$WORKERS" -gt 16 ]; then
    echo "⚠️  WARNING: Invalid WEB_CONCURRENCY value '${WEB_CONCURRENCY}' — falling back to 1 worker"
    WORKERS=1
fi

echo "✅ Worker processes: ${WORKERS}"

# Detect uvloop availability for high-performance event loop
UVLOOP_ARG=""
if python -c "import uvloop" 2>/dev/null; then
    UVLOOP_ARG="--loop uvloop"
    echo "✅ uvloop detected — using high-performance event loop"
else
    echo "⚠️  uvloop not available — falling back to default asyncio event loop"
fi

echo "Command: uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers ${WORKERS} --access-log ${UVLOOP_ARG}"
echo ""

# Start the application
exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port "${PORT:-8000}" \
    --workers "${WORKERS}" \
    --access-log \
    $UVLOOP_ARG