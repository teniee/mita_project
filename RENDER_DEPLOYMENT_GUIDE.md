# MITA Finance Backend - Production Deployment Guide

## 🚨 Current Issue: Backend Service Not Accessible

The MITA authentication system is failing because the backend servers are not properly deployed or accessible:

- ❌ `https://mita-production.onrender.com` returns 404 (service not found)
- ❌ `https://mita-docker-ready-project-manus.onrender.com` times out
- ❌ Mobile app cannot authenticate users due to backend unavailability

## 🎯 Solution: Deploy Backend to Render.com

### Prerequisites

1. **GitHub Repository**: Code must be pushed to GitHub
2. **Render.com Account**: Sign up at https://render.com
3. **OpenAI API Key**: Required for AI features
4. **Database**: PostgreSQL instance (Render provides this)

### Step 1: Deploy Using Render.yaml (Recommended)

The repository now includes a `render.yaml` configuration file for Infrastructure as Code deployment.

#### 1.1 Commit and Push Changes
```bash
# Run the deployment script
./deploy_to_render.sh

# Or manually:
git add .
git commit -m "Deploy MITA backend to Render"
git push origin main
```

#### 1.2 Deploy via Render Dashboard
1. Go to https://dashboard.render.com
2. Click **"New +"** → **"Blueprint"**
3. Connect your GitHub repository
4. Select the `render.yaml` file
5. Review the configuration and click **"Apply"**

### Step 2: Manual Web Service Creation (Alternative)

If Blueprint deployment doesn't work:

#### 2.1 Create Web Service
1. Go to https://dashboard.render.com
2. Click **"New +"** → **"Web Service"**
3. Connect your GitHub repository
4. Configure:
   - **Name**: `mita-production`
   - **Environment**: Python 3
   - **Build Command**: `pip install --upgrade pip && pip install -r requirements.txt`
   - **Start Command**: `python start_optimized.py`
   - **Plan**: Starter (Free) or Starter+ ($7/month for better performance)

#### 2.2 Create PostgreSQL Database
1. In Render Dashboard, click **"New +"** → **"PostgreSQL"**
2. Configure:
   - **Name**: `mita-production-db`
   - **Database Name**: `mita_production`
   - **User**: `mita_user`
   - **Plan**: Starter (Free)

### Step 3: Configure Environment Variables

In your web service's **Environment** tab, add these variables:

#### Required Variables
```bash
SECRET_KEY=<generate with: openssl rand -hex 32>
JWT_SECRET=<generate with: openssl rand -hex 32>
DATABASE_URL=<PostgreSQL External Database URL from Render>
OPENAI_API_KEY=<Your OpenAI API key>
ENVIRONMENT=production
```

#### Optional Variables
```bash
REDIS_URL=redis://localhost:6379/0
ALLOWED_ORIGINS=*
SENTRY_DSN=<Your Sentry DSN for error tracking>
FIREBASE_JSON=<Firebase service account JSON for push notifications>
```

### Step 4: Generate Secure Keys

Run these commands locally to generate secure keys:
```bash
# Generate SECRET_KEY
openssl rand -hex 32

# Generate JWT_SECRET  
openssl rand -hex 32
```

Copy these values to your Render environment variables.

### Step 5: Database Setup

1. **Get Database URL**: Copy the "External Database URL" from your PostgreSQL service
2. **Set DATABASE_URL**: Add this as an environment variable in your web service
3. **Database Migrations**: Migrations will run automatically on startup

### Step 6: Deploy and Verify

#### 6.1 Deploy
- Render automatically deploys when you push to the main branch
- Or click **"Manual Deploy"** in the dashboard

#### 6.2 Verify Deployment
Test these endpoints after deployment:

```bash
# Health check - should return 200 OK
curl https://mita-production.onrender.com/health

# Expected response:
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
  }
}

# Test API endpoints
curl https://mita-production.onrender.com/api/auth/login
curl https://mita-production.onrender.com/emergency-test
```

### Step 7: Update Mobile App (If Needed)

The mobile app is already configured to use the production URL, but verify:

**File**: `mobile_app/lib/config.dart`
```dart
const String defaultApiBaseUrl = 'https://mita-production.onrender.com/api';
```

## 🔧 Infrastructure Monitoring

### Health Checks
- **Endpoint**: `/health`
- **Interval**: 30 seconds
- **Timeout**: 10 seconds
- **Retries**: 3

### Performance Monitoring
- **Application**: Sentry integration for error tracking
- **Database**: PostgreSQL performance metrics in Render dashboard
- **Logs**: Available in Render dashboard under "Logs" tab

### Scaling Configuration
- **Free Tier**: Spins down after 15 minutes of inactivity
- **Paid Tier**: Always-on service for production
- **Auto-scaling**: Configure based on CPU/memory usage

## 🚨 Troubleshooting

### Common Issues

#### 1. 502 Bad Gateway
**Cause**: App not binding to correct port
**Solution**: Ensure `PORT` environment variable is used (already configured)

#### 2. Database Connection Issues
**Cause**: Invalid DATABASE_URL or database not ready
**Solution**: 
- Verify DATABASE_URL format: `postgresql+psycopg2://user:pass@host:port/db`
- Check database service status in Render dashboard

#### 3. Missing Environment Variables
**Cause**: Required variables not set
**Solution**: Check `/health` endpoint for missing configuration

#### 4. Slow Cold Starts (Free Tier)
**Cause**: Service spins down after inactivity
**Solution**: 
- Upgrade to paid plan for always-on service
- Implement external health check ping every 10 minutes

### Debug Steps

1. **Check Logs**: Render Dashboard → Service → Logs tab
2. **Health Check**: Visit `/health` endpoint for detailed status
3. **Environment**: Verify all required variables are set
4. **Database**: Ensure PostgreSQL service is running
5. **Build**: Check build logs for dependency issues

## 🔐 Security Considerations

### Environment Variables
- Never commit secrets to Git
- Use Render's environment variable system
- Rotate secrets regularly

### Network Security
- HTTPS enforced by default
- CORS configured for mobile app origins
- Rate limiting enabled on API endpoints

### Database Security
- SSL connections enforced
- Connection pooling configured
- Regular backups enabled by Render

## 📊 Expected Performance

### Response Times
- **Health Check**: < 200ms
- **Authentication**: < 500ms
- **API Calls**: < 1s (99th percentile)

### Availability
- **Target**: 99.9% uptime
- **Health Checks**: Automatic restart on failures
- **Monitoring**: Sentry for error tracking

## 🚀 Next Steps After Deployment

1. **Monitor Health**: Check `/health` endpoint regularly
2. **Test Mobile App**: Verify authentication and API calls work
3. **Set Up Monitoring**: Configure Sentry for error tracking
4. **Performance Testing**: Load test critical endpoints
5. **Backup Strategy**: Verify database backups are running
6. **Documentation**: Update API documentation with production URLs

## 📞 Support

If deployment fails:
1. Check Render service logs for specific error messages
2. Verify all environment variables are correctly set
3. Test database connectivity from the Render dashboard
4. Ensure GitHub repository has latest code changes
5. Try manual deployment if automatic deployment fails

The deployment script (`deploy_to_render.sh`) provides step-by-step guidance and can be run locally to validate configuration before deployment.