# MITA Finance Email Service - Production Deployment Guide

## 🚀 Complete Email Service Implementation

This guide covers the production deployment of the enterprise-grade email service for MITA Finance, including SendGrid integration, queue management, and mobile app integration.

## 📋 Environment Variables Configuration

### Required Environment Variables

Add the following environment variables to your production environment:

```bash
# SendGrid Configuration (REQUIRED)
SENDGRID_API_KEY=SG.your_sendgrid_api_key_here
SMTP_FROM=noreply@mita.finance
SMTP_FROM_NAME=MITA Finance

# Alternative Email Providers (Optional)
MAILGUN_API_KEY=your_mailgun_key
MAILGUN_DOMAIN=mg.mita.finance
POSTMARK_API_KEY=your_postmark_key

# Email Queue Configuration
EMAIL_MAX_RETRIES=3
EMAIL_RETRY_DELAY=300
EMAIL_BATCH_SIZE=100
EMAIL_MAX_PROCESSING_TIME=300
EMAIL_DEAD_LETTER_RETENTION_DAYS=7

# Mobile App Integration
IOS_APP_ID=your_ios_app_id
ANDROID_PACKAGE_NAME=com.mita.finance
UNIVERSAL_LINK_DOMAIN=links.mita.finance
ANDROID_SHA256_FINGERPRINT=your_android_sha256_fingerprint

# Redis Configuration (for email queue)
UPSTASH_REDIS_URL=redis://your_upstash_redis_url
REDIS_MAX_CONNECTIONS=20
REDIS_TIMEOUT=30
```

### Development Environment Variables

For development and testing:

```bash
# Development SMTP (Optional - for testing)
SMTP_HOST=smtp.mailtrap.io
SMTP_PORT=587
SMTP_USERNAME=your_mailtrap_username
SMTP_PASSWORD=your_mailtrap_password

# Email Service Configuration
EMAIL_TEMPLATE_DEBUG=true
EMAIL_QUEUE_DEBUG=true
```

## 🔧 SendGrid Setup

### 1. Create SendGrid Account
1. Sign up at [SendGrid](https://sendgrid.com)
2. Verify your account and add your domain
3. Generate an API key with full access

### 2. Domain Authentication
1. Go to Settings > Sender Authentication
2. Add your domain (mita.finance)
3. Configure DNS records as provided by SendGrid
4. Verify domain authentication

### 3. IP Warmup (for high volume)
1. Configure dedicated IP if sending >100,000 emails/month
2. Implement IP warmup schedule
3. Monitor sender reputation

## 📧 Email Templates Deployment

### Template Files Location
```
app/templates/emails/
├── base.html                    # Base template
├── welcome.html                 # Welcome email
├── password_reset.html          # Password reset
├── email_verification.html      # Email verification
├── security_alert.html          # Security alerts
├── transaction_confirmation.html # Transaction emails
├── budget_alert.html           # Budget notifications
└── suspicious_activity.html    # Suspicious activity alerts
```

### Template Customization
1. Update branding colors in `base.html`
2. Modify company information and links
3. Test all templates with various data
4. Ensure mobile responsiveness

## 🗄️ Database Migration

Run the database migration to add email-related fields:

```bash
# Apply the migration
alembic upgrade head

# Or specifically run the email fields migration
alembic upgrade 0007_email_password_reset_fields
```

### Migration includes:
- Password reset token fields
- Email verification fields
- Indexes for performance

## 🚀 Production Deployment Steps

### 1. Deploy Code Changes

```bash
# Add email routes to main app
# In app/main.py, add:
from app.api.email.routes import router as email_router
app.include_router(email_router, prefix="/api")
```

### 2. Start Email Queue Worker

Add to your deployment script:

```python
# In your startup script or background worker
from app.services.email_queue_service import email_queue_service
import asyncio

async def start_email_worker():
    await email_queue_service.start_worker()

# Start the worker
asyncio.run(start_email_worker())
```

### 3. Configure Process Manager

For production, use a process manager like Supervisor or systemd:

```ini
# /etc/supervisor/conf.d/mita-email-worker.conf
[program:mita-email-worker]
command=/path/to/venv/bin/python -c "
import asyncio
from app.services.email_queue_service import email_queue_service
asyncio.run(email_queue_service.start_worker())
"
directory=/path/to/mita_project
user=mita
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/mita/email-worker.log
```

## 📱 Mobile App Integration

### 1. Configure Universal Links (iOS)

Create `/.well-known/apple-app-site-association`:

```json
{
  "applinks": {
    "apps": [],
    "details": [
      {
        "appID": "TEAMID.your_ios_app_id",
        "paths": [
          "/password_reset",
          "/email_verification",
          "/transaction_review",
          "/budget_alert",
          "/security_alert"
        ]
      }
    ]
  }
}
```

### 2. Configure Android App Links

Create `/.well-known/assetlinks.json`:

```json
[{
  "relation": ["delegate_permission/common.handle_all_urls"],
  "target": {
    "namespace": "android_app",
    "package_name": "com.mita.finance",
    "sha256_cert_fingerprints": ["your_sha256_fingerprint"]
  }
}]
```

### 3. Deep Link Testing

Test deep links in development:
```bash
# iOS Simulator
xcrun simctl openurl booted "mita://password_reset?token=test123"

# Android
adb shell am start -W -a android.intent.action.VIEW -d "mita://password_reset?token=test123" com.mita.finance
```

## 🔍 Monitoring and Alerting

### 1. Email Service Health Checks

Add health check endpoints:
```bash
GET /api/email/health
GET /api/email/queue/status
```

### 2. Monitoring Setup

Configure alerts for:
- Email delivery failures > 5%
- Queue size > 1000 jobs
- Worker process down
- SendGrid API errors
- High bounce rates

### 3. Logging Configuration

```python
# Configure structured logging
import logging
import json

class EmailLogFormatter(logging.Formatter):
    def format(self, record):
        log_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': record.levelname,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName
        }
        return json.dumps(log_data)

# Apply to email service logger
email_logger = logging.getLogger('app.services.email_service')
handler = logging.StreamHandler()
handler.setFormatter(EmailLogFormatter())
email_logger.addHandler(handler)
```

## 🔒 Security Configuration

### 1. Email Security Headers

Ensure your email service includes:
- SPF records
- DKIM signing (configured in SendGrid)
- DMARC policy

### 2. Rate Limiting

Configure rate limits:
```python
# Password reset: 3 attempts per 5 minutes per IP
# Email verification: 5 attempts per hour per user
# General email sending: 100 emails per hour per user
```

### 3. Token Security

- Password reset tokens expire in 2 hours
- Email verification tokens expire in 24 hours
- All tokens use cryptographically secure generation
- Tokens are invalidated after use

## 🧪 Testing and Validation

### 1. Email Template Testing

```bash
# Test template rendering
curl -X POST "/api/email/test/template" \
  -H "Content-Type: application/json" \
  -d '{
    "email_type": "welcome",
    "variables": {
      "user_name": "Test User",
      "email": "test@example.com"
    }
  }'
```

### 2. End-to-End Testing

Test complete flows:
1. User registration → Welcome email
2. Password reset request → Reset email → Password change
3. Transaction → Notification email
4. Budget threshold → Alert email

### 3. Load Testing

```python
# Test queue performance
import asyncio
from app.services.email_queue_service import queue_email
from app.services.email_service import EmailType, EmailPriority

async def load_test():
    tasks = []
    for i in range(1000):
        task = queue_email(
            to_email=f"test{i}@example.com",
            email_type=EmailType.WELCOME,
            variables={"user_name": f"User {i}", "email": f"test{i}@example.com"},
            priority=EmailPriority.NORMAL
        )
        tasks.append(task)
    
    await asyncio.gather(*tasks)
    print("Queued 1000 emails")

asyncio.run(load_test())
```

## 📊 Performance Optimization

### 1. Database Indexes

Ensure indexes are created:
```sql
CREATE INDEX idx_users_password_reset_token ON users(password_reset_token);
CREATE INDEX idx_users_email_verification_token ON users(email_verification_token);
CREATE INDEX idx_notification_logs_user_id_created ON notification_log(user_id, created_at);
```

### 2. Redis Optimization

Configure Redis for optimal queue performance:
```redis
# Redis configuration for email queue
maxmemory-policy allkeys-lru
tcp-keepalive 60
timeout 300
```

### 3. SendGrid Optimization

- Use batch email API for bulk sends
- Implement proper retry logic with exponential backoff
- Monitor API rate limits

## 🚨 Disaster Recovery

### 1. Email Queue Backup

Implement queue persistence:
```python
# Regular queue backups to database
async def backup_queue_state():
    queue_status = await email_queue_service.get_queue_status()
    # Store critical queue state in database
```

### 2. Failover Strategy

1. Primary: SendGrid API
2. Secondary: SMTP fallback
3. Tertiary: Alternative provider (Mailgun/Postmark)

### 3. Message Recovery

- Dead letter queue for failed messages
- Manual retry capability for critical emails
- Audit trail for all email operations

## ✅ Production Readiness Checklist

### Email Service
- [ ] SendGrid API key configured and tested
- [ ] Domain authentication verified
- [ ] All email templates tested and branded
- [ ] Mobile deep links configured and tested
- [ ] Queue worker running and monitored

### Database
- [ ] Migration applied successfully
- [ ] Indexes created for performance
- [ ] Backup strategy includes new tables

### Security
- [ ] SPF/DKIM/DMARC configured
- [ ] Rate limiting implemented
- [ ] Token security validated
- [ ] Security alerts tested

### Monitoring
- [ ] Health checks configured
- [ ] Alerting set up for failures
- [ ] Logging properly configured
- [ ] Metrics collection enabled

### Testing
- [ ] All email types tested end-to-end
- [ ] Mobile integration tested on both platforms
- [ ] Load testing completed
- [ ] Failover scenarios tested

## 🔗 Integration Points

### With Authentication System
- Password reset integration complete
- Email verification for new accounts
- Security alerts for suspicious activity

### With Financial Engine
- Transaction confirmation emails
- Budget alert notifications
- Goal achievement notifications

### With Mobile App
- Deep link integration for all email types
- Universal links configured
- Push notification fallback ready

## 📞 Support and Maintenance

### Regular Maintenance Tasks
- Monitor email delivery rates
- Clean up old tokens and expired data
- Review and update email templates
- Monitor queue performance
- Update security configurations

### Troubleshooting
- Check SendGrid dashboard for delivery issues
- Monitor Redis queue health
- Review application logs for errors
- Test email templates after updates

## 🎯 Success Metrics

### Key Performance Indicators
- Email delivery rate: >99%
- Queue processing time: <30 seconds
- Template rendering time: <100ms
- Mobile deep link success rate: >95%
- Security alert response time: <5 minutes

Your MITA Finance email service is now production-ready with enterprise-grade features, comprehensive monitoring, and seamless mobile integration! 🚀