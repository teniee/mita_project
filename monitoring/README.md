# MITA Monitoring & Alerting System

Complete monitoring stack with Prometheus, Alertmanager, Grafana, and automated rollback integration.

**Copyright © 2025 YAKOVLEV LTD - All Rights Reserved**

## Overview

Enterprise-grade monitoring and alerting system with:
- ✅ **Prometheus** - Metrics collection (15s scrape interval)
- ✅ **Alertmanager** - Alert routing and notifications
- ✅ **Grafana** - Visualization dashboards
- ✅ **Automated rollback integration** - Critical alerts trigger automatic deployment rollback
- ✅ **Multi-channel notifications** - Slack, PagerDuty, Email
- ✅ **50+ alert rules** - Comprehensive coverage

## Architecture

```
┌──────────────────┐
│  Application     │
│  (FastAPI)       │──────┐
│  - /metrics      │      │
│  - /health/*     │      ├──▶ Prometheus (scrape 15s)
└──────────────────┘      │         │
                          │         │ evaluate rules
┌──────────────────┐      │         ▼
│  PostgreSQL      │──────┤   Alertmanager
│  Redis           │      │         │
│  System          │──────┘         │
└──────────────────┘                │
                    ┌───────────────┼────────────────┐
                    │               │                │
                    ▼               ▼                ▼
              ┌─────────┐   ┌──────────┐   ┌───────────────┐
              │  Slack  │   │PagerDuty │   │Rollback Webhook│
              │#alerts  │   │ On-call  │   │   /trigger     │
              └─────────┘   └──────────┘   └───────┬────────┘
                                                    │
                                                    ▼
                                           Automated Rollback
                                           scripts/rollback/
```

## Quick Start

### 1. Environment Variables

Create `.env` file in monitoring directory:

```bash
# Slack Integration
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL

# Email (SendGrid)
SENDGRID_API_KEY=SG.your-api-key

# PagerDuty
PAGERDUTY_CRITICAL_KEY=your-critical-integration-key
PAGERDUTY_ERROR_KEY=your-error-integration-key

# Rollback Webhook Authentication
ROLLBACK_WEBHOOK_SECRET=your-secure-secret

# Grafana
GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=your-secure-password

# Database & Redis (for exporters)
DATABASE_URL=postgresql://user:pass@host:5432/mita
REDIS_URL=redis://redis:6379

# Rollback system
ROLLBACK_BASE_URL=https://api.mita.finance
```

### 2. Start Monitoring Stack

```bash
cd monitoring
docker-compose -f docker-compose.monitoring.yml up -d
```

### 3. Verify Services

```bash
# Prometheus
curl http://localhost:9090/api/v1/status/config

# Alertmanager
curl http://localhost:9093/api/v1/status

# Grafana
open http://localhost:3000
```

### 4. Test Notification Channels

```bash
python3 scripts/test_alertmanager.py
```

## Alert Rules

### Critical Alerts (Trigger Automatic Rollback)

| Alert Name | Condition | Rollback Trigger | Duration |
|------------|-----------|------------------|----------|
| **CriticalErrorRate** | error_rate > 20% | error_rate_threshold | 2m |
| **CriticalP95Latency** | p95 > 1.0s | latency_degradation | 2m |
| **MitaSystemUnhealthy** | health_status == 0 | health_check_failure | 1m |
| **MitaDatabaseConnectionIssues** | conn_time > 5000ms | database_error | 2m |
| **TransactionProcessingFailure** | errors > 5 in 5m | database_error | 2m |
| **RedisConnectionFailure** | no clients | database_error | 1m |
| **UserRegistrationDown** | 0 success in 10m | error_rate_threshold | 5m |

### Error Alerts (PagerDuty + Slack)

- HighErrorRate (>5%)
- DatabaseConnectionsHigh (>80 connections)
- QueueDepthCritical (>2000)
- RevenueProcessingIssue (any revenue errors)

### Warning Alerts (Slack only)

- HighP95Latency (>400ms)
- HighMemoryUsage (>85%)
- QueueDepthHigh (>500)
- Component performance degradation

## Notification Routing

### Severity-Based Routing

```yaml
CRITICAL:
  - PagerDuty (high urgency, phone/SMS)
  - Slack #mita-alerts (@here)
  - Slack #mita-incidents
  - Email (mikhail@mita.finance)
  - Rollback webhook (for specific alerts)

ERROR:
  - PagerDuty (low urgency)
  - Slack #mita-alerts (@channel)
  - Email

WARNING:
  - Slack #mita-alerts
  - Email (aggregated every 15 min)
```

### Component-Specific Routing

```yaml
Database alerts → #mita-database
Authentication alerts → #mita-security
Payment/Revenue alerts → #mita-finance-team
Rollback alerts → #mita-deployments
```

## Automated Rollback Integration

### Webhook Endpoint

**URL**: `POST /api/admin/rollback/trigger`

**Authentication**: Basic auth with `ROLLBACK_WEBHOOK_SECRET`

**Process**:
1. Alertmanager fires CRITICAL alert
2. Webhook sent to rollback endpoint
3. Alert validated and mapped to rollback trigger
4. Automated rollback script executed in background
5. Slack notification sent with progress updates

### Rollback Trigger Mapping

```python
{
    "CriticalErrorRate": {
        "trigger": "error_rate_threshold",
        "auto_rollback": True,
        "confidence": "high"
    },
    "CriticalP95Latency": {
        "trigger": "latency_degradation",
        "auto_rollback": True,
        "confidence": "high"
    },
    # ... 7 critical alerts total
}
```

### Testing Rollback Webhook

```bash
# Test without actually executing rollback
curl -X POST http://localhost:8000/api/admin/rollback/test \
  -H "Authorization: Basic your-secret" \
  -d "alert_name=CriticalErrorRate"
```

## Alert Testing

### Test Alertmanager Configuration

```bash
# Run all tests
python3 scripts/test_alertmanager.py

# Test specific alert
python3 scripts/test_alertmanager.py \
  --test-alert CriticalErrorRate \
  --severity critical
```

### Send Test Alert to Slack

```bash
curl -X POST $SLACK_WEBHOOK_URL \
  -H 'Content-Type: application/json' \
  -d '{
    "text": "🧪 Test Alert",
    "attachments": [{
      "color": "danger",
      "title": "Critical Error Rate",
      "text": "This is a test alert"
    }]
  }'
```

### Simulate Critical Alert

```bash
# Via Alertmanager API
curl -X POST http://localhost:9093/api/v1/alerts \
  -H 'Content-Type: application/json' \
  -d '[{
    "labels": {
      "alertname": "CriticalErrorRate",
      "service": "mita-backend",
      "severity": "critical"
    },
    "annotations": {
      "summary": "Test critical error rate alert",
      "description": "Error rate exceeded 20%"
    }
  }]'
```

## Monitoring Best Practices

### Alert Fatigue Prevention

1. **Tune thresholds** - Review alert frequency weekly
2. **Group related alerts** - 30s group_wait, 5m group_interval
3. **Inhibition rules** - Critical alerts suppress warnings
4. **Off-hours suppression** - WARNING alerts suppressed 18:00-08:00 EET

### Alert Review Cadence

**Weekly** (Every Monday 10:00 AM EET):
- Review alert volume
- Identify noisy alerts
- Tune thresholds
- Update runbooks

**Monthly**:
- Review MTTA and MTTR metrics
- Analyze false positive rate
- Test escalation policies
- Validate runbooks

### SLA Targets

| Metric | Target | Critical |
|--------|--------|----------|
| **MTTA** (Mean Time to Acknowledge) | <5 minutes | <2 minutes |
| **MTTR** (Mean Time to Resolve) | <15 minutes | <10 minutes |
| **False Positive Rate** | <5% | N/A |
| **Actionable Alert Rate** | >95% | >99% |

## Dashboards

### Grafana Dashboards

1. **Main Dashboard** - Overall system health
   - Request rate, error rate, latency (RED metrics)
   - Resource utilization (CPU, memory, disk)
   - Alert status

2. **Rollback Dashboard** - Deployment and rollback metrics
   - Rollback frequency
   - Rollback duration
   - Success rate
   - Trigger reasons

3. **Component Health** - Middleware component status
   - Database health
   - Redis health
   - JWT service health
   - Response times

4. **Business Metrics** - Financial and user metrics
   - Daily active users
   - Transaction success rate
   - Revenue processing
   - Registration funnel

**Access**: http://localhost:3000 (admin/your-password)

## Troubleshooting

### Alerts Not Firing

**Check Prometheus targets**:
```bash
curl http://localhost:9090/api/v1/targets
```

**Check alert rules**:
```bash
curl http://localhost:9090/api/v1/rules
```

**Check Alertmanager alerts**:
```bash
curl http://localhost:9093/api/v1/alerts
```

### Notifications Not Received

**Check Alertmanager config**:
```bash
curl http://localhost:9093/api/v1/status | jq .
```

**Test Slack webhook**:
```bash
python3 scripts/test_alertmanager.py
```

**Check Alertmanager logs**:
```bash
docker logs mita-alertmanager
```

### Rollback Not Triggered

**Check webhook endpoint**:
```bash
curl http://localhost:8000/api/admin/rollback/status
```

**Test rollback webhook**:
```bash
curl -X POST http://localhost:8000/api/admin/rollback/test \
  -H "Authorization: Basic $ROLLBACK_WEBHOOK_SECRET" \
  -d "alert_name=CriticalErrorRate"
```

**Check backend logs**:
```bash
docker logs mita-backend | grep rollback
```

## Production Deployment

### Railway Deployment

1. **Set environment variables** in Railway dashboard:
   ```
   SLACK_WEBHOOK_URL
   SENDGRID_API_KEY
   PAGERDUTY_CRITICAL_KEY
   ROLLBACK_WEBHOOK_SECRET
   ```

2. **Update Prometheus targets** for Railway services:
   ```yaml
   scrape_configs:
     - job_name: 'mita-backend'
       static_configs:
         - targets: ['mita-backend.railway.app:443']
       scheme: https
   ```

3. **Configure Alertmanager webhook** for production:
   ```yaml
   webhook_configs:
     - url: 'https://api.mita.finance/api/admin/rollback/trigger'
   ```

### Kubernetes Deployment

Use Helm charts in `/k8s/mita/`:

```bash
helm upgrade --install mita-monitoring ./k8s/monitoring \
  --namespace monitoring \
  --values k8s/monitoring/values.prod.yaml
```

## Runbooks

Every alert has a corresponding runbook:

| Alert | Runbook URL |
|-------|-------------|
| CriticalErrorRate | https://docs.mita.finance/runbooks/high-error-rate |
| CriticalP95Latency | https://docs.mita.finance/runbooks/high-latency |
| MitaSystemUnhealthy | https://docs.mita.finance/runbooks/system-unhealthy |
| TransactionProcessingFailure | https://docs.mita.finance/runbooks/transaction-failure |

**Runbook Template**: See `scripts/rollback/README.md` section 8

## Metrics Reference

### Application Metrics (FastAPI)

```
http_requests_total{method, path, status}
http_request_duration_seconds{method, path}
```

### Middleware Health Metrics

```
mita_middleware_health_status (0-1)
mita_middleware_component_health{component} (0-1)
mita_middleware_component_response_time_ms{component}
mita_cpu_usage_percent
mita_memory_usage_percent
mita_disk_usage_percent
```

### Business Metrics

```
daily_active_users
transaction_processing_errors_total
user_registration_success_total
revenue_processing_errors_total
```

## Files Structure

```
monitoring/
├── prometheus.yml              # Prometheus config
├── alertmanager.yml            # Alertmanager config (NEW)
├── app_alert_rules.yml         # Application alert rules
├── health_alert_rules.yml      # Health check alert rules
├── docker-compose.monitoring.yml  # Docker Compose stack (NEW)
├── templates/
│   └── slack.tmpl              # Slack message templates (NEW)
└── README.md                   # This file

scripts/
├── test_alertmanager.py        # Testing script (NEW)
└── rollback/
    └── ...                     # Automated rollback system

app/api/admin/
└── rollback_webhook.py         # Webhook handler (NEW)
```

## Support

**Contact:**
- Mikhail Yakovlev (CTO): mikhail@mita.finance
- Location: Varna, Bulgaria

**Slack Channels:**
- #mita-alerts - All alerts
- #mita-incidents - Active incidents
- #mita-deployments - Rollback notifications
- #mita-security - Security alerts
- #mita-database - Database alerts

**PagerDuty:**
- Service: MITA Finance Production
- Escalation: L1 (on-call) → L2 (5min) → L3 (10min) → L4 (CTO, 15min)

---

**Copyright © 2025 YAKOVLEV LTD - All Rights Reserved**

Built with ❤️ for production-grade reliability.
