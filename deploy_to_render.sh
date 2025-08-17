#!/bin/bash

# MITA Finance Backend - Render.com Deployment Script
# This script helps deploy the MITA backend to Render.com

set -e

echo "🚀 MITA Finance Backend - Render.com Deployment"
echo "==============================================="

# Check if we're in a git repository
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    echo "❌ Error: Not in a git repository"
    exit 1
fi

# Check if we're on the main branch
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
if [ "$CURRENT_BRANCH" != "main" ]; then
    echo "⚠️  Warning: You're on branch '$CURRENT_BRANCH', not 'main'"
    echo "   Render deployments typically use the main branch"
    read -p "   Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Check for required environment files
echo "📋 Checking deployment requirements..."

# Check for essential files
REQUIRED_FILES=(
    "requirements.txt"
    "app/main.py"
    "start_optimized.py"
    "render.yaml"
    "Dockerfile"
)

for file in "${REQUIRED_FILES[@]}"; do
    if [ ! -f "$file" ]; then
        echo "❌ Missing required file: $file"
        exit 1
    fi
    echo "✅ Found: $file"
done

# Generate secret keys if they don't exist
echo "🔐 Generating secure keys for deployment..."

SECRET_KEY=$(openssl rand -hex 32)
JWT_SECRET=$(openssl rand -hex 32)

echo "Generated secure keys:"
echo "SECRET_KEY: $SECRET_KEY"
echo "JWT_SECRET: $JWT_SECRET"
echo ""

# Validate Python dependencies
echo "🐍 Validating Python dependencies..."
if python3 -c "import fastapi, uvicorn, sqlalchemy, psycopg2, redis" > /dev/null 2>&1; then
    echo "✅ Core dependencies available"
else
    echo "⚠️  Some dependencies might be missing, but Render will install them"
fi

# Check for database migrations
if [ -d "alembic/versions" ] && [ "$(ls -A alembic/versions)" ]; then
    echo "✅ Database migrations found"
else
    echo "⚠️  No database migrations found - this might cause issues"
fi

# Display deployment instructions
echo ""
echo "🎯 Next Steps for Render.com Deployment:"
echo "========================================"
echo ""
echo "1. 📤 PUSH TO GITHUB:"
echo "   git add ."
echo "   git commit -m 'Deploy MITA backend to Render'"
echo "   git push origin main"
echo ""
echo "2. 🌐 CREATE RENDER SERVICE:"
echo "   • Go to https://dashboard.render.com"
echo "   • Click 'New +' → 'Web Service'"
echo "   • Connect your GitHub repository"
echo "   • Use these settings:"
echo "     - Name: mita-production"
echo "     - Environment: Python 3"
echo "     - Build Command: pip install --upgrade pip && pip install -r requirements.txt"
echo "     - Start Command: python start_optimized.py"
echo "     - Plan: Starter (Free) or Starter+ (Paid)"
echo ""
echo "3. 🔧 CONFIGURE ENVIRONMENT VARIABLES:"
echo "   In Render Dashboard → Environment tab, add:"
echo ""
echo "   Required Variables:"
echo "   SECRET_KEY = $SECRET_KEY"
echo "   JWT_SECRET = $JWT_SECRET"
echo "   DATABASE_URL = [Your PostgreSQL URL from Render]"
echo "   OPENAI_API_KEY = [Your OpenAI API key]"
echo "   ENVIRONMENT = production"
echo ""
echo "   Optional Variables:"
echo "   REDIS_URL = redis://localhost:6379/0"
echo "   ALLOWED_ORIGINS = *"
echo "   SENTRY_DSN = [Your Sentry DSN for error tracking]"
echo ""
echo "4. 🗄️  CREATE DATABASE:"
echo "   • In Render Dashboard, create a new PostgreSQL database"
echo "   • Name: mita-production-db"
echo "   • Copy the 'External Database URL' to DATABASE_URL environment variable"
echo ""
echo "5. 🚀 DEPLOY:"
echo "   • Render will automatically deploy when you push to main branch"
echo "   • OR click 'Manual Deploy' in the Render dashboard"
echo ""
echo "6. ✅ VERIFY DEPLOYMENT:"
echo "   • Check https://mita-production.onrender.com/health"
echo "   • Should return JSON with status: 'healthy'"
echo "   • Test API endpoints: https://mita-production.onrender.com/api/auth/login"
echo ""
echo "7. 📱 UPDATE MOBILE APP:"
echo "   • Update mobile_app/lib/config.dart"
echo "   • Change API URL to: https://mita-production.onrender.com/api"
echo ""

# Offer to commit and push
echo "💾 Commit and Push Changes?"
echo "=========================="
read -p "Would you like to commit and push these changes now? (y/N): " -n 1 -r
echo

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "📤 Committing changes..."
    git add .
    git commit -m "Deploy MITA backend to Render.com

🔧 Deployment Configuration:
- Added render.yaml for Render.com deployment
- Created deployment script with instructions
- Backend ready for production deployment

🚀 Expected Results:
- https://mita-production.onrender.com/health should return 200 OK
- API endpoints accessible at /api/auth/* routes
- Mobile app can connect to production backend

🤖 Generated with Claude Code
Co-Authored-By: Claude <noreply@anthropic.com>"
    
    echo "🚀 Pushing to GitHub..."
    git push origin main
    
    echo ""
    echo "✅ Changes pushed to GitHub!"
    echo "🌐 Now go to https://dashboard.render.com to create your web service"
    echo "📋 Use the instructions above to complete the deployment"
else
    echo "📝 Changes ready to commit. Run the deployment when ready:"
    echo "   git add ."
    echo "   git commit -m 'Deploy MITA backend to Render'"
    echo "   git push origin main"
fi

echo ""
echo "🎉 Deployment preparation complete!"
echo "📖 Follow the instructions above to deploy to Render.com"