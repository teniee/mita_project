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

echo ""
echo "🔍 Checking optional variables..."

# Check optional variables
optional_vars=(
    "REDIS_URL"
    "SENTRY_DSN"
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
python -m alembic upgrade head

if [ $? -ne 0 ]; then
    echo "❌ Migration failed! Attempting to continue anyway..."
    echo "⚠️  The application may not work correctly without migrations"
else
    echo "✅ Migrations completed successfully"
fi

echo ""
echo "🔄 Starting application..."

# Detect uvloop availability for high-performance event loop
UVLOOP_ARG=""
if python -c "import uvloop" 2>/dev/null; then
    UVLOOP_ARG="--loop uvloop"
    echo "✅ uvloop detected — using high-performance event loop"
else
    echo "⚠️  uvloop not available — falling back to default asyncio event loop"
fi

echo "Command: uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1 --access-log ${UVLOOP_ARG}"
echo ""

# Start the application
exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port "${PORT:-8000}" \
    --workers 1 \
    --access-log \
    $UVLOOP_ARG