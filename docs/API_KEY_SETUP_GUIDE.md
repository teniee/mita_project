# MITA Finance - Production API Key Setup Guide

This comprehensive guide provides step-by-step instructions for configuring all external service API keys required for production deployment of the MITA Finance platform.

## 🚨 CRITICAL PRODUCTION REQUIREMENTS

The following API keys are **CRITICAL** and the system will not function properly without them:

### 1. **OpenAI API Key** (REQUIRED)
- **Purpose**: AI-powered financial analysis, advice generation, and expense categorization
- **Environment Variable**: `OPENAI_API_KEY`
- **Format**: `sk-...` (starts with "sk-")

#### How to Get:
1. Go to [OpenAI Platform](https://platform.openai.com/)
2. Sign up or log into your account
3. Navigate to API Keys section
4. Create a new API key
5. Copy the key (starts with `sk-`)

#### Recommended Settings:
- **Model**: `gpt-4o-mini` (cost-effective for production)
- **Rate Limits**: Set appropriate limits for your usage
- **Usage Monitoring**: Enable to track costs

#### Monthly Cost Estimate:
- Expected usage: ~$50-200/month for moderate traffic
- Monitor usage through OpenAI dashboard

---

### 2. **Sentry DSN** (REQUIRED)
- **Purpose**: Error monitoring, performance tracking, and real-time alerts
- **Environment Variable**: `SENTRY_DSN`
- **Format**: `https://...@sentry.io/...`

#### How to Get:
1. Go to [Sentry.io](https://sentry.io/)
2. Create account and new project
3. Select "Python" as the platform
4. Copy the DSN from project settings
5. Configure alerts and performance monitoring

#### Recommended Settings:
- **Error Rate Alerts**: > 5% in 5 minutes
- **Performance Alerts**: > 2s average response time
- **Release Tracking**: Enable for deployment monitoring

---

### 3. **Upstash Redis** (REQUIRED)
- **Purpose**: Caching, rate limiting, and session storage
- **Environment Variables**: 
  - `UPSTASH_REDIS_URL`
  - `UPSTASH_REDIS_REST_URL`
  - `UPSTASH_REDIS_REST_TOKEN`

#### How to Get:
1. Go to [Upstash](https://upstash.com/)
2. Create account and new Redis database
3. Choose region closest to your deployment
4. Copy connection details from dashboard
5. Use REST API for serverless environments

#### Recommended Settings:
- **Memory**: 256MB minimum for production
- **Region**: Same as your deployment region
- **Persistence**: Enable for data durability

---

### 4. **SendGrid API Key** (REQUIRED)
- **Purpose**: Transactional emails (password resets, notifications)
- **Environment Variables**:
  - `SENDGRID_API_KEY`
  - `SMTP_PASSWORD` (same as API key)

#### How to Get:
1. Go to [SendGrid](https://sendgrid.com/)
2. Create account and verify domain
3. Generate API key in Settings > API Keys
4. Grant "Full Access" or specific mail permissions
5. Verify domain authentication

#### Domain Setup:
- Add CNAME records for domain authentication
- Configure sender authentication
- Set up dedicated IP (optional, for high volume)

---

## 🔧 IMPORTANT EXTERNAL SERVICES

These services enhance functionality but aren't critical for basic operation:

### 5. **Firebase/Google Cloud** (IMPORTANT)
- **Purpose**: Push notifications for mobile app
- **Environment Variables**:
  - `FIREBASE_JSON` (service account JSON)
  - `FIREBASE_PROJECT_ID`
  - `FIREBASE_CLIENT_EMAIL`

#### How to Get:
1. Go to [Firebase Console](https://console.firebase.google.com/)
2. Create new project or use existing
3. Enable Cloud Messaging
4. Generate service account key
5. Download JSON credentials

#### Mobile App Setup:
- Configure iOS and Android apps
- Upload APNs certificates for iOS
- Configure FCM for Android

---

### 6. **AWS S3** (IMPORTANT)
- **Purpose**: File storage, backups, and static assets
- **Environment Variables**:
  - `AWS_ACCESS_KEY_ID`
  - `AWS_SECRET_ACCESS_KEY`
  - `AWS_S3_BUCKET`

#### How to Get:
1. Go to [AWS Console](https://console.aws.amazon.com/)
2. Create IAM user with S3 permissions
3. Generate access keys
4. Create S3 bucket for production
5. Configure bucket policies

#### Required Permissions:
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:GetObject",
                "s3:PutObject",
                "s3:DeleteObject",
                "s3:ListBucket"
            ],
            "Resource": [
                "arn:aws:s3:::mita-production-storage",
                "arn:aws:s3:::mita-production-storage/*"
            ]
        }
    ]
}
```

---

## 🔄 OPTIONAL SERVICES

These services provide additional features:

### 7. **Apple Services** (OPTIONAL)
- **App Store Connect**: `APPSTORE_SHARED_SECRET`
- **APNs**: `APNS_KEY_ID`, `APNS_TEAM_ID`, `APNS_KEY`

### 8. **Stripe** (OPTIONAL)
- **Purpose**: Payment processing for premium features
- **Environment Variables**: `STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY`

### 9. **Plaid** (OPTIONAL)
- **Purpose**: Bank account linking for automatic transaction import
- **Environment Variables**: `PLAID_CLIENT_ID`, `PLAID_SECRET`

---

## 🚀 DEPLOYMENT SETUP

### Render.com Configuration

1. **Set Environment Variables in Render Dashboard**:
   ```bash
   # Go to your service settings in Render
   # Add each environment variable with sync: false
   OPENAI_API_KEY=sk-your-actual-key-here
   SENTRY_DSN=https://your-dsn@sentry.io/project-id
   SENDGRID_API_KEY=SG.your-key-here
   UPSTASH_REDIS_URL=redis://your-redis-url
   # ... etc
   ```

2. **Database Configuration**:
   - DATABASE_URL will be auto-provided by Render PostgreSQL service
   - Ensure database plan supports expected load

3. **Security Settings**:
   - All API keys should be marked as `sync: false`
   - Never commit actual keys to repository
   - Use different keys for staging vs production

---

## 🔧 CONFIGURATION VALIDATION

Run the production API configuration script:

```bash
# Validate all API keys
python scripts/configure_production_apis.py

# Run full configuration with connection tests
python scripts/configure_production_apis.py --save-report

# Output as JSON for automation
python scripts/configure_production_apis.py --output-format json
```

### Expected Output:
```
MITA FINANCE API CONFIGURATION REPORT
====================================
Overall Status: HEALTHY
Health Score: 100.0%

SUMMARY:
  Total Api Keys: 8
  Valid Keys: 8
  Invalid Keys: 0
  Missing Keys: 0
  Services Connected: 6

SERVICE CONNECTIONS:
  ✅ openai: connected
  ✅ sentry: connected
  ✅ redis: connected
  ✅ sendgrid: connected
  ✅ firebase: connected
  ✅ aws_s3: connected

RECOMMENDATIONS:
  • All API configurations are valid and ready for production!
```

---

## 🔒 SECURITY BEST PRACTICES

### API Key Security:
1. **Never commit keys to version control**
2. **Use environment variables only**
3. **Set up key rotation schedule** (90 days)
4. **Monitor key usage and alerts**
5. **Use least-privilege permissions**

### Key Rotation:
```bash
# Automated key rotation (run monthly)
python scripts/rotate_api_keys.py --dry-run
python scripts/rotate_api_keys.py --execute
```

### Monitoring:
- Set up alerts for API key failures
- Monitor usage quotas and billing
- Track error rates per service
- Set up PagerDuty integration for critical alerts

---

## 📊 MONITORING AND ALERTS

### Health Check Endpoints:
- `/health` - Overall system health
- `/health/apis` - API key status
- `/health/external-services` - Service connectivity

### Recommended Alerts:
1. **API Key Validation Failures**: > 5% in 10 minutes
2. **Service Connection Failures**: Any service down > 2 minutes
3. **Rate Limit Warnings**: > 80% of quota used
4. **Cost Alerts**: Monthly spend > expected budget

---

## 🆘 TROUBLESHOOTING

### Common Issues:

#### OpenAI API Errors:
- `401 Unauthorized`: Invalid API key
- `429 Rate Limit`: Increase rate limits or implement backoff
- `500 Internal Error`: Check OpenAI status page

#### Sentry Not Receiving Events:
- Verify DSN format
- Check project permissions
- Ensure environment matches

#### Redis Connection Issues:
- Verify URL format includes auth
- Check network connectivity
- Validate Redis instance is running

#### Email Delivery Problems:
- Verify domain authentication
- Check spam folder
- Validate SendGrid IP reputation

---

## 📞 SUPPORT CONTACTS

### Service Support:
- **OpenAI**: [help.openai.com](https://help.openai.com/)
- **Sentry**: [sentry.io/support](https://sentry.io/support/)
- **SendGrid**: [support.sendgrid.com](https://support.sendgrid.com/)
- **Upstash**: [upstash.com/docs](https://upstash.com/docs)
- **AWS**: [aws.amazon.com/support](https://aws.amazon.com/support/)

### Emergency Contacts:
- **Production Issues**: [Your PagerDuty/Oncall]
- **Security Issues**: [Your Security Team]
- **Billing Issues**: [Your Finance Team]

---

## ✅ DEPLOYMENT CHECKLIST

Before going to production:

- [ ] All critical API keys configured and validated
- [ ] Health checks passing
- [ ] Error monitoring setup and tested
- [ ] Rate limiting configured appropriately
- [ ] Backup and monitoring systems operational
- [ ] Security scan completed
- [ ] Load testing completed
- [ ] Rollback plan documented
- [ ] Team notified of deployment
- [ ] Post-deployment monitoring in place

---

*Last updated: September 2025*
*Version: 1.0.0*