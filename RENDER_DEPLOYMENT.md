# Render Deployment Guide for MITA Backend

## 🚨 Critical Issues Fixed

The backend was returning 502 Bad Gateway errors due to several deployment issues that have now been resolved:

1. **Port Binding Issue**: Fixed port binding to use Render's `$PORT` environment variable
2. **Environment Variable Validation**: Added startup validation with clear error messages
3. **Health Check Improvements**: Enhanced health checks for better monitoring
4. **Database Connection Retry**: Added retry logic for database initialization

## 🔧 What Was Fixed

### 1. Dockerfile Updates
- ✅ Fixed port binding to use `${PORT:-8000}` for Render compatibility
- ✅ Updated health check to use dynamic port
- ✅ Added startup script with environment validation

### 2. Application Improvements  
- ✅ Enhanced startup process with retry logic and better error handling
- ✅ Improved health check endpoint with detailed diagnostics
- ✅ Added comprehensive logging for debugging

### 3. New Startup Script
- ✅ Validates critical environment variables before startup
- ✅ Provides clear error messages for missing configuration
- ✅ Includes helpful debugging information

## Required Environment Variables

Set these in your **Render Dashboard** → **Environment**:

### Critical Variables (Required)
```bash
# Database (Use your Render PostgreSQL connection string)
DATABASE_URL=postgresql+psycopg2://username:password@dpg-xxxxx-pool.render.com:5432/database_name

# Security Keys (Generate with: openssl rand -hex 32)  
SECRET_KEY=your-32-character-secret-key-here
JWT_SECRET=your-32-character-jwt-secret-here

# OpenAI (Required for AI features)
OPENAI_API_KEY=sk-your-openai-api-key-here

# Environment
ENVIRONMENT=production
```

### Optional Variables
```bash
# Redis (if using external Redis)
REDIS_URL=redis://localhost:6379/0

# Email notifications
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@domain.com
SMTP_PASSWORD=your-app-password

# Error tracking
SENTRY_DSN=https://your-sentry-dsn@sentry.io/project

# CORS (Add your Flutter app domain if needed)
ALLOWED_ORIGINS=https://app.mita.finance

# Firebase (if using Firebase features)
FIREBASE_JSON={"type": "service_account", ...}
```

## Deployment Steps

1. **Go to Render Dashboard**
   - Navigate to your backend service
   - Click on "Environment" tab

2. **Add Required Variables**
   Set these exact variable names and values:
   ```
   SECRET_KEY = [Generate with: openssl rand -hex 32]
   JWT_SECRET = [Generate with: openssl rand -hex 32] 
   DATABASE_URL = [Your Render PostgreSQL URL]
   OPENAI_API_KEY = [Your OpenAI API key]
   ENVIRONMENT = production
   ```

3. **Generate Secret Keys**
   ```bash
   # Run these commands locally to generate secure keys:
   openssl rand -hex 32
   openssl rand -hex 32
   ```

4. **Deploy the Fixed Code**
   - Commit and push the fixes to your repository
   - Render will automatically deploy the changes
   - OR click "Manual Deploy" → "Deploy latest commit"

## Verification & Testing

### 1. Check Service Status
After deployment, your service should:
- ✅ Start without 502 errors
- ✅ Bind to the correct port
- ✅ Pass health checks

### 2. Test Health Endpoints
Visit these URLs (replace with your Render URL):
```bash
# Basic health check
https://your-service.onrender.com/

# Detailed health check
https://your-service.onrender.com/health
```

Expected response from `/health`:
```json
{
  "status": "healthy",
  "service": "Mita Finance API",
  "version": "1.0.0",
  "database": "connected",
  "config": {
    "jwt_secret_configured": true,
    "database_configured": true,
    "environment": "production",
    "openai_configured": true
  },
  "port": "10000"
}
```

### 3. Test API Endpoints
```bash
# Test a protected endpoint (should return 401 without auth)
curl https://your-service.onrender.com/api/users/me

# Test auth endpoint
curl -X POST https://your-service.onrender.com/api/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"testpass123"}'
```

## Troubleshooting

### If you still see 502 errors:

1. **Check Logs in Render Dashboard**
   - Go to your service → Logs tab
   - Look for startup error messages

2. **Common Issues & Solutions:**

   **Missing Environment Variables:**
   ```
   ❌ ERROR: SECRET_KEY is not set or empty
   ```
   → Add the missing variable in Render Dashboard

   **Database Connection Issues:**
   ```
   ❌ Database initialization failed
   ```
   → Verify DATABASE_URL format and database availability

   **Port Binding Issues:**
   ```
   Error binding to port
   ```
   → This should now be fixed with the PORT variable usage

3. **Verify Environment Variables**
   Check that all required variables are set correctly in Render Dashboard

4. **Database Format**
   Ensure DATABASE_URL uses this format:
   ```
   postgresql+psycopg2://username:password@host:port/database
   ```

## Next Steps

Once backend is deployed successfully:

1. **Update Flutter App Configuration**
   - Change the API base URL to your Render URL
   - Test all functionality from the mobile app

2. **Production Monitoring**
   - Monitor the health endpoint
   - Set up Sentry for error tracking
   - Check database performance

3. **Security**
   - Ensure all secrets are properly configured
   - Monitor for any security issues

## Support

If you encounter issues:
1. Check the detailed error messages in startup logs
2. Verify all environment variables are correctly set
3. Test the health endpoint for diagnostic information
4. Check database connectivity and credentials

The enhanced startup script will now provide clear guidance on what's wrong if deployment fails.