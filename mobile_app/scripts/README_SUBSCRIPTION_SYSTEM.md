# MITA Subscription Management System

## Overview

This comprehensive subscription management system handles premium feature access control, receipt validation, and subscription lifecycle management for the MITA financial application. It provides production-ready infrastructure for managing App Store and Google Play Store subscriptions with 99.9% uptime requirements.

## Features

### Core Functionality
- **Apple App Store Receipt Validation**: Production-grade receipt verification with Apple's servers
- **Google Play Store Receipt Validation**: Integration with Google Play Developer API
- **Premium Feature Management**: Granular control over premium feature access
- **Subscription Lifecycle Management**: Handle active, expired, cancelled, and grace period states
- **Real-time Status Updates**: Immediate premium feature revocation when subscriptions expire
- **Audit Trail**: Comprehensive logging for financial compliance

### Production Features
- **High Availability**: Designed for 99.9% uptime with automatic failover
- **Security**: Encrypted data storage, secure API communications, and access controls
- **Monitoring**: Comprehensive metrics, alerting, and health checks
- **Scalability**: Horizontal scaling support with load balancing
- **Compliance**: GDPR, PCI DSS, and financial regulation compliance
- **Error Recovery**: Automatic retry logic and graceful error handling

### Financial Compliance
- **Audit Logging**: 7-year retention for financial compliance
- **Data Integrity**: Transaction-based updates with rollback capability
- **Revenue Tracking**: Real-time revenue monitoring and reporting
- **Fraud Detection**: Suspicious activity monitoring and alerting

## System Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Mobile App    │    │   Backend API   │    │  Subscription   │
│                 │────│                 │────│   Manager       │
│  IAP Service    │    │  Premium APIs   │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                        │
                         ┌─────────────────┐           │
                         │   PostgreSQL    │───────────┘
                         │   Database      │
                         └─────────────────┘
                                  │
        ┌─────────────────┬───────┴───────┬─────────────────┐
        │                 │               │                 │
┌───────▼────┐   ┌────────▼───┐  ┌───────▼────┐   ┌────────▼───┐
│Apple Store │   │Google Play │  │ Monitoring │   │  Alerting  │
│    API     │   │    API     │  │ (Grafana)  │   │(PagerDuty) │
└────────────┘   └────────────┘  └────────────┘   └────────────┘
```

## Installation

### Prerequisites

- Docker 20.10+
- Docker Compose 1.27+
- Python 3.11+
- PostgreSQL 15+
- Git
- 4GB RAM minimum
- 20GB disk space

### Environment Setup

1. **Clone and Navigate**:
   ```bash
   cd /path/to/mita_project/mobile_app/scripts
   ```

2. **Create Environment File**:
   ```bash
   cp .env.example .env
   ```

3. **Configure Environment Variables**:
   ```bash
   # Database Configuration
   DB_NAME=mita
   DB_USER=mita_subscription
   DB_PASSWORD=your_secure_password_here
   
   # Apple App Store Configuration
   APPLE_SHARED_SECRET=your_apple_shared_secret
   
   # Google Play Store Configuration
   GOOGLE_PACKAGE_NAME=com.mita.finance
   
   # Monitoring Configuration
   SENTRY_DSN=https://your-sentry-dsn@sentry.io/project-id
   
   # Grafana Configuration
   GRAFANA_ADMIN_USER=admin
   GRAFANA_ADMIN_PASSWORD=secure_admin_password
   ```

4. **Setup Secrets Directory**:
   ```bash
   mkdir -p secrets
   chmod 700 secrets
   ```

5. **Add Service Account File**:
   ```bash
   # Place your Google service account JSON file
   cp /path/to/google_service_account.json secrets/
   chmod 600 secrets/google_service_account.json
   ```

### Deployment

#### Option 1: Automated Deployment (Recommended)
```bash
./deploy_subscription_system.sh
```

#### Option 2: Manual Deployment
```bash
# Build images
docker build -f Dockerfile.subscription-manager -t mita/subscription-manager:latest .

# Start services
docker-compose -f docker-compose.subscription.yml up -d

# Setup database
docker-compose exec postgres psql -U mita_subscription -d mita -f /docker-entrypoint-initdb.d/01-schema.sql

# Install cron jobs
crontab crontab_subscription_management
```

### Post-Deployment Verification

1. **Check Service Health**:
   ```bash
   curl http://localhost:8080/health
   ```

2. **Verify Database**:
   ```bash
   docker-compose exec postgres pg_isready
   ```

3. **Test Receipt Validation**:
   ```bash
   python3 refresh_premium_status.py --test-mode
   ```

## Configuration

### Database Schema

The system uses a comprehensive PostgreSQL schema with the following key tables:

- `user_subscriptions`: Main subscription records
- `user_feature_flags`: Premium feature access control
- `subscription_audit_log`: Compliance and audit trail
- `premium_feature_usage`: Usage analytics and limits
- `subscription_metrics`: Business intelligence data

### Premium Features

The system manages these premium features:

| Feature | Description | Free Limit | Premium Limit |
|---------|-------------|------------|---------------|
| Advanced OCR | High-accuracy receipt processing | 5/day | Unlimited |
| Batch Processing | Multiple receipt upload | 0 | 50 receipts |
| Premium Insights | Advanced financial analytics | None | Full access |
| Enhanced Analytics | Historical data and trends | 30 days | Unlimited |
| Unlimited Transactions | Transaction history | 100/month | Unlimited |
| Custom Categories | Personal spending categories | 0 | Unlimited |
| Data Export | Export financial data | 1/day | Unlimited |
| Priority Support | Fast customer support | 48h email | 4h multi-channel |

### Subscription States

- **Active**: Valid subscription with full premium access
- **Expired**: Subscription ended, premium features revoked
- **Cancelled**: User cancelled, may have remaining time
- **Grace Period**: Payment failed, temporary premium access
- **Billing Retry**: Apple/Google retrying payment
- **Refunded**: Subscription refunded, premium revoked

## API Integration

### Mobile App Integration

Update your mobile app's IAP service:

```dart
// Initialize the IAP service
final iapService = IapService();
await iapService.initialize();

// Check premium status
final isPremium = await iapService.isPremiumUser();

// Check specific feature access
final hasAdvancedOcr = await iapService.hasFeature(PremiumFeature.advancedOcr);

// Listen to premium status changes
iapService.premiumStatusStream.listen((isPremium) {
  // Update UI based on premium status
});
```

### Backend API Endpoints

Add these endpoints to your backend:

```python
# Premium status endpoint
GET /users/{user_id}/premium-status

# Premium features endpoint  
GET /users/{user_id}/premium-features

# Receipt validation endpoint
POST /iap/validate

# Feature usage tracking
POST /analytics/feature-usage

# Subscription status update
PUT /subscriptions/{subscription_id}/status
```

## Monitoring and Alerting

### Service URLs

- **Subscription Manager**: http://localhost:8080
- **Grafana Dashboard**: http://localhost:3000
- **Prometheus Metrics**: http://localhost:9090
- **Health Check**: http://localhost:8080/health
- **Metrics Endpoint**: http://localhost:8080/metrics

### Key Metrics

1. **Business Metrics**:
   - Monthly Recurring Revenue (MRR)
   - Churn Rate
   - Conversion Rate (Trial to Paid)
   - Premium Feature Usage

2. **Technical Metrics**:
   - Receipt Validation Success Rate (Target: >99.5%)
   - API Response Time (Target: <2s p95)
   - Database Query Time (Target: <100ms p95)
   - System Uptime (Target: >99.9%)

3. **Security Metrics**:
   - Failed Validation Attempts
   - Suspicious Activity Patterns
   - Feature Access Violations

### Alerting Rules

Critical alerts (PagerDuty):
- Subscription service down
- High receipt validation failure rate (>10%)
- Database connection exhaustion (>90%)

Warning alerts (Slack):
- High churn rate (>5% daily)
- Low validation success rate (<95%)
- Many subscriptions expiring without renewal

## Maintenance

### Daily Tasks
- Subscription status verification (automated)
- Premium feature access updates (automated)
- Health checks and monitoring (automated)

### Weekly Tasks
- Subscription health reports
- Database performance optimization
- Security scan and updates

### Monthly Tasks
- Financial reporting
- Subscription analytics
- Data archival for compliance

### Manual Tasks
- Apple/Google API credential updates
- Security certificate renewals
- Emergency subscription fixes

## Troubleshooting

### Common Issues

1. **Receipt Validation Failures**:
   ```bash
   # Check Apple/Google API connectivity
   curl -X POST https://buy.itunes.apple.com/verifyReceipt
   
   # Verify credentials
   python3 scripts/test_api_credentials.py
   
   # Check logs
   docker-compose logs subscription-manager | grep "validation"
   ```

2. **Database Connection Issues**:
   ```bash
   # Check database health
   docker-compose exec postgres pg_isready
   
   # Check connection pool
   curl http://localhost:8080/metrics | grep db_connections
   
   # Restart database
   docker-compose restart postgres
   ```

3. **Premium Feature Access Issues**:
   ```bash
   # Check user premium status
   docker-compose exec postgres psql -U mita_subscription -d mita \
     -c "SELECT * FROM users WHERE id = 'user_id_here';"
   
   # Check feature flags
   docker-compose exec postgres psql -U mita_subscription -d mita \
     -c "SELECT * FROM user_feature_flags WHERE user_id = 'user_id_here';"
   
   # Force refresh
   python3 refresh_premium_status.py --user-id "user_id_here"
   ```

### Log Locations

- Application Logs: `/var/log/mita/subscription_manager.log`
- Audit Logs: `/var/log/mita/subscription_audit.log`
- Error Logs: `/var/log/mita/error.log`
- Docker Logs: `docker-compose logs [service_name]`

### Performance Tuning

1. **Database Optimization**:
   ```bash
   # Analyze query performance
   docker-compose exec postgres psql -U mita_subscription -d mita \
     -c "SELECT * FROM pg_stat_statements ORDER BY total_time DESC LIMIT 10;"
   
   # Update statistics
   docker-compose exec postgres psql -U mita_subscription -d mita \
     -c "ANALYZE;"
   ```

2. **Memory Management**:
   ```bash
   # Check memory usage
   docker stats
   
   # Adjust container limits
   # Edit docker-compose.subscription.yml memory limits
   ```

3. **Network Performance**:
   ```bash
   # Test API response times
   curl -w "%{time_total}" http://localhost:8080/health
   
   # Check connection pool settings
   curl http://localhost:8080/metrics | grep connection
   ```

## Security

### Access Controls
- Database access restricted to service accounts
- API endpoints require authentication
- Secrets stored in encrypted volumes
- Network isolation between services

### Data Protection
- Receipt data encrypted at rest
- TLS encryption for all API communications
- Personal data anonymization for analytics
- GDPR compliance with data deletion

### Monitoring
- Failed authentication attempts tracked
- Unusual subscription patterns detected
- Security audit logs maintained
- Regular vulnerability scans

## Backup and Recovery

### Automated Backups
- Database: Daily encrypted backups
- Configuration: Weekly backups
- Logs: Continuous log shipping
- Metrics: 90-day retention

### Recovery Procedures
1. Database recovery from backup
2. Service configuration restoration
3. Certificate and credential recovery
4. Full system disaster recovery

### RTO/RPO Targets
- Recovery Time Objective (RTO): 1 hour
- Recovery Point Objective (RPO): 15 minutes

## Support and Contacts

### Development Team
- **Lead Developer**: MITA DevOps Team
- **Email**: devops@mita.com
- **Slack**: #mita-subscription-support

### Emergency Contacts
- **PagerDuty**: Subscription service alerts
- **On-call Engineer**: 24/7 support for critical issues
- **Business Team**: Revenue and compliance issues

### Documentation Updates
- Version: 1.0.0
- Last Updated: $(date)
- Next Review: Quarterly

## License and Compliance

This subscription management system is designed to meet:
- GDPR data protection requirements
- PCI DSS financial compliance
- Apple App Store guidelines
- Google Play Store policies
- Financial services regulations

For compliance questions, contact: compliance@mita.com

---

**Important**: This system handles financial transactions and user billing. Always test changes in a staging environment before production deployment. Follow change management procedures for all updates.