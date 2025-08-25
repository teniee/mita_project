#!/bin/bash

# MITA Redis Render Deployment Script
# This script helps configure Redis for Render deployment

set -e

echo "🚀 MITA Redis Configuration for Render Deployment"
echo "=================================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo -e "${BLUE}$1${NC}"
}

# Check if Redis URL is provided
if [ -z "$UPSTASH_REDIS_URL" ] && [ -z "$REDIS_URL" ]; then
    print_error "No Redis URL provided!"
    echo ""
    echo "Please set one of these environment variables:"
    echo "  export UPSTASH_REDIS_URL='redis://:token@your-redis.upstash.io:6379'"
    echo "  export REDIS_URL='redis://:token@your-redis.upstash.io:6379'"
    echo ""
    echo "Or provide it as an argument:"
    echo "  ./deploy_redis_render.sh redis://:token@your-redis.upstash.io:6379"
    exit 1
fi

# Use provided Redis URL or environment variable
if [ ! -z "$1" ]; then
    REDIS_URL="$1"
    print_status "Using Redis URL from argument"
elif [ ! -z "$UPSTASH_REDIS_URL" ]; then
    REDIS_URL="$UPSTASH_REDIS_URL"
    print_status "Using UPSTASH_REDIS_URL from environment"
else
    print_status "Using REDIS_URL from environment"
fi

print_header "Step 1: Validating Redis Connection"
echo "Testing Redis connectivity..."

# Test Redis connection
if command -v redis-cli &> /dev/null; then
    if redis-cli -u "$REDIS_URL" ping &> /dev/null; then
        print_status "✅ Redis connection successful"
        
        # Get Redis info
        print_status "Redis Server Information:"
        redis-cli -u "$REDIS_URL" info server | grep -E "(redis_version|uptime_in_seconds|role)" || true
        
        # Test basic operations
        redis-cli -u "$REDIS_URL" set "mita:test:$(date +%s)" "deployment_test" EX 60 &> /dev/null
        print_status "✅ Redis write test successful"
        
    else
        print_error "❌ Redis connection failed"
        echo "Please check your Redis URL and ensure the Redis server is accessible"
        exit 1
    fi
else
    print_warning "redis-cli not found. Skipping connection test."
    print_warning "Install redis-tools to test connection: apt-get install redis-tools"
fi

print_header "Step 2: Environment Configuration Check"

# Validate Redis URL format
if [[ "$REDIS_URL" =~ ^redis(s)?://.*$ ]]; then
    print_status "✅ Redis URL format is valid"
    if [[ "$REDIS_URL" =~ ^rediss://.*$ ]]; then
        print_status "✅ SSL/TLS connection detected"
    fi
else
    print_error "❌ Invalid Redis URL format"
    echo "Redis URL must start with 'redis://' or 'rediss://'"
    exit 1
fi

# Extract Redis host for logging (without credentials)
REDIS_HOST=$(echo "$REDIS_URL" | sed -E 's|redis(s)?://([^@]*@)?([^:]+).*|\3|')
print_status "Redis Host: $REDIS_HOST"

print_header "Step 3: Render Environment Variables"

echo ""
print_status "Set these environment variables in your Render service dashboard:"
echo ""
echo "# Primary Redis Configuration"
echo "UPSTASH_REDIS_URL=${REDIS_URL}"
echo "REDIS_URL=${REDIS_URL}"
echo ""
echo "# Redis Connection Settings"
echo "REDIS_MAX_CONNECTIONS=20"
echo "REDIS_TIMEOUT=30"
echo "REDIS_RETRY_ON_TIMEOUT=true"
echo ""

print_header "Step 4: Render Service Configuration"

if [ -f "render.yaml" ]; then
    print_status "✅ render.yaml found"
    
    # Check if Redis configuration is present
    if grep -q "UPSTASH_REDIS_URL\|REDIS_URL" render.yaml; then
        print_status "✅ Redis configuration found in render.yaml"
    else
        print_error "❌ Redis configuration missing from render.yaml"
        echo "Please update render.yaml with Redis environment variables"
    fi
else
    print_error "❌ render.yaml not found"
    echo "Please ensure you're in the project root directory"
fi

print_header "Step 5: Application Health Check"

# Check if the health endpoint configuration exists
if [ -f "app/api/health/production_health.py" ]; then
    print_status "✅ Health check endpoint found"
    
    if grep -q "redis\|Redis" "app/api/health/production_health.py"; then
        print_status "✅ Redis health check configured"
    else
        print_warning "⚠️  Redis health check may not be configured"
    fi
else
    print_warning "⚠️  Health check endpoint not found"
fi

print_header "Step 6: Pre-Deployment Checklist"

echo ""
print_status "Before deploying to Render, ensure:"
echo "  ✓ Upstash Redis database is created and active"
echo "  ✓ TLS/SSL is enabled on your Redis instance"
echo "  ✓ Redis backup schedule is configured"
echo "  ✓ Environment variables are set in Render dashboard"
echo "  ✓ render.yaml has been updated with Redis configuration"
echo ""

print_header "Step 7: Post-Deployment Validation"

echo ""
print_status "After deployment, test these endpoints:"
echo ""
echo "# Health Check"
echo "curl https://your-app.onrender.com/health"
echo ""
echo "# Redis Metrics"
echo "curl https://your-app.onrender.com/metrics | grep redis"
echo ""
echo "# Rate Limiting Test (should work without errors)"
echo "curl -H \"Authorization: Bearer your-token\" https://your-app.onrender.com/auth/login"
echo ""

print_header "Step 8: Monitoring Setup"

echo ""
print_status "Monitor these Redis metrics after deployment:"
echo "  • Connection count and health"
echo "  • Memory usage and hit ratio"
echo "  • Command rate and latency"
echo "  • Error rate and availability"
echo ""

print_header "Troubleshooting"

echo ""
print_status "Common issues and solutions:"
echo ""
echo "❌ Connection refused:"
echo "   → Check Redis URL format and credentials"
echo "   → Verify Redis instance is active in provider dashboard"
echo ""
echo "❌ Authentication failed:"
echo "   → Verify Redis token in connection string"
echo "   → Check token hasn't expired"
echo ""
echo "❌ High latency:"
echo "   → Choose Redis region closer to Render"
echo "   → Monitor connection pool utilization"
echo ""

print_header "Support Resources"

echo ""
print_status "Documentation and Support:"
echo "  📚 MITA Redis Guide: ./REDIS_DEPLOYMENT_GUIDE.md"
echo "  📚 Upstash Docs: https://docs.upstash.com/"
echo "  📚 Render Docs: https://render.com/docs/"
echo ""

if [ -f "REDIS_DEPLOYMENT_GUIDE.md" ]; then
    print_status "✅ Detailed Redis deployment guide available: REDIS_DEPLOYMENT_GUIDE.md"
else
    print_warning "⚠️  Redis deployment guide not found"
fi

echo ""
print_status "🎉 Redis configuration for Render deployment is ready!"
print_status "Remember to set the environment variables in your Render dashboard before deploying."
echo ""

# Create a summary file
cat > redis_deployment_summary.txt << EOF
MITA Redis Deployment Summary
============================

Redis URL: $REDIS_HOST
Connection Test: ✅ Successful
SSL/TLS: $(if [[ "$REDIS_URL" =~ ^rediss://.*$ ]]; then echo "✅ Enabled"; else echo "❌ Disabled"; fi)

Environment Variables for Render:
UPSTASH_REDIS_URL=$REDIS_URL
REDIS_URL=$REDIS_URL
REDIS_MAX_CONNECTIONS=20
REDIS_TIMEOUT=30
REDIS_RETRY_ON_TIMEOUT=true

Next Steps:
1. Set environment variables in Render dashboard
2. Deploy application
3. Test health endpoint: https://your-app.onrender.com/health
4. Monitor Redis metrics and performance

Generated: $(date)
EOF

print_status "📄 Summary saved to: redis_deployment_summary.txt"