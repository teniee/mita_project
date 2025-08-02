# Render Deployment Guide for MITA Backend

## 🚨 Critical Issue Resolved
The backend was failing to start because of missing environment variables. This has been fixed by making the configuration more flexible.

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

# CORS
ALLOWED_ORIGINS=https://app.mita.finance
```

## Steps to Fix Deployment

1. **Go to Render Dashboard**
   - Navigate to your backend service
   - Click on "Environment" tab

2. **Add Required Variables**
   ```
   SECRET_KEY = [Generate 32-char secret]
   JWT_SECRET = [Generate 32-char secret] 
   DATABASE_URL = [Your Render PostgreSQL URL]
   OPENAI_API_KEY = [Your OpenAI API key]
   ENVIRONMENT = production
   ```

3. **Generate Secret Keys**
   ```bash
   # Run these commands to generate secure keys:
   openssl rand -hex 32
   openssl rand -hex 32
   ```

4. **Redeploy**
   - Click "Manual Deploy" → "Deploy latest commit"
   - Backend should now start successfully

## Verification

After deployment, check:
- ✅ Service starts without "Missing SECRET_KEY" error
- ✅ API endpoints are accessible at your render URL
- ✅ Flutter app can connect and load data

## Next Steps

Once backend is deployed successfully:
1. Update Flutter app config to point to your Render URL
2. Test dashboard data loading
3. Test AI Insights functionality
4. Test Calendar features

## Support

If you still see deployment errors, check:
1. All required environment variables are set
2. DATABASE_URL format is correct for Render PostgreSQL
3. OpenAI API key is valid and has credits
4. No typos in environment variable names