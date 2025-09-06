# MITA Finance - Comprehensive Sentry Monitoring Guide

## Table of Contents
1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Setup and Configuration](#setup-and-configuration)
4. [Error Monitoring](#error-monitoring)
5. [Performance Monitoring](#performance-monitoring)
6. [Financial Application Specific Monitoring](#financial-application-specific-monitoring)
7. [Alert Rules and Notifications](#alert-rules-and-notifications)
8. [Compliance and Audit](#compliance-and-audit)
9. [Troubleshooting Guide](#troubleshooting-guide)
10. [Best Practices](#best-practices)
11. [API Reference](#api-reference)

---

## Overview

MITA Finance uses a comprehensive Sentry monitoring solution designed specifically for financial services applications. This implementation provides:

- **Complete Error Tracking** - Backend and mobile error capture with financial context
- **Performance Monitoring** - Real-time performance tracking with compliance awareness
- **Security Monitoring** - Authentication and security event tracking
- **Compliance Reporting** - PCI DSS and financial regulation compliance monitoring
- **Custom Alert Rules** - Financial operation specific alerting
- **Audit Trail** - Complete audit logging for financial compliance

### Key Features

- 🔒 **PCI DSS Compliant** - Sensitive data filtering and secure monitoring
- 💰 **Financial Context** - Transaction, payment, and user context tracking
- ⚡ **Real-time Alerts** - Immediate notification for critical financial errors
- 📊 **Performance Tracking** - API and database performance monitoring
- 📱 **Mobile Integration** - Comprehensive Flutter app monitoring
- 🔍 **Custom Filtering** - Financial data sanitization before sending to Sentry
- 📈 **Release Tracking** - Deployment and version tracking
- 📋 **Compliance Reporting** - Automated compliance and audit reports

---

## Architecture

### Backend Monitoring Stack

```
┌─────────────────────────────────────────────────────────┐
│                 MITA Finance Backend                     │
├─────────────────────────────────────────────────────────┤
│  FastAPI Application                                    │
│  ┌─────────────────┐  ┌─────────────────┐              │
│  │ Sentry Service  │  │ Performance     │              │
│  │                 │  │ Monitor         │              │
│  └─────────────────┘  └─────────────────┘              │
│  ┌─────────────────────────────────────────────────────┐ │
│  │         Financial Middleware                        │ │
│  │ - Context Tracking  - Error Filtering              │ │
│  │ - User Context      - Performance Monitoring       │ │
│  └─────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────┤
│                  Sentry SDK                             │
│ - Error Capture    - Performance Tracking              │
│ - Breadcrumbs      - Release Tracking                  │
│ - Custom Context   - Data Filtering                    │
└─────────────────────────────────────────────────────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │   Sentry.io     │
                    │   Platform      │
                    └─────────────────┘
```

### Mobile Monitoring Stack

```
┌─────────────────────────────────────────────────────────┐
│                MITA Finance Mobile                      │
├─────────────────────────────────────────────────────────┤
│  Flutter Application                                    │
│  ┌─────────────────┐  ┌─────────────────┐              │
│  │ Sentry Service  │  │ Performance     │              │
│  │                 │  │ Monitor         │              │
│  └─────────────────┘  └─────────────────┘              │
│  ┌─────────────────────────────────────────────────────┐ │
│  │        Error Boundary Widgets                       │ │
│  │ - Screen Context    - User Context                  │ │
│  │ - Error Recovery    - Breadcrumb Tracking           │ │
│  └─────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────┤
│                Sentry Flutter SDK                       │
│ - Crash Detection  - Performance Tracking              │
│ - User Interaction - Network Monitoring                │
│ - Custom Context   - Data Filtering                    │
└─────────────────────────────────────────────────────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │   Sentry.io     │
                    │   Platform      │
                    └─────────────────┘
```

---

## Setup and Configuration

### Backend Setup

#### 1. Environment Variables

Create a `.env` file with the following variables:

```bash
# Sentry Configuration
SENTRY_DSN=https://your-dsn@sentry.io/project-id
SENTRY_ENVIRONMENT=production
SENTRY_RELEASE=mita-finance@1.0.0

# Alert Webhooks
SLACK_FINANCE_WEBHOOK=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
SLACK_SECURITY_WEBHOOK=https://hooks.slack.com/services/YOUR/SECURITY/URL
PAGERDUTY_FINANCE_KEY=your-pagerduty-integration-key

# Sentry API Access
SENTRY_ORG=your-org-slug
SENTRY_PROJECT_BACKEND=mita-backend
SENTRY_PROJECT_MOBILE=mita-mobile
SENTRY_AUTH_TOKEN=your-auth-token
```

#### 2. Initialize Backend Monitoring

The backend is automatically configured through `main.py`. The configuration includes:

- **Environment-specific sampling rates**
- **Financial data filtering**
- **Performance monitoring**
- **Compliance context**

```python
from app.services.sentry_service import sentry_service
from app.middleware.sentry_financial_middleware import FinancialSentryMiddleware

# Middleware is automatically applied
app.add_middleware(FinancialSentryMiddleware)
```

#### 3. Financial Operations Monitoring

Use the financial operation decorators for automatic monitoring:

```python
from app.middleware.sentry_financial_middleware import financial_operation_monitor
from app.services.sentry_service import FinancialErrorCategory

@financial_operation_monitor(
    operation_name="process_payment",
    category=FinancialErrorCategory.PAYMENT_PROCESSING,
    track_performance=True,
    require_user=True
)
async def process_payment(user_id: str, amount: float, currency: str):
    # Payment processing logic
    pass
```

### Mobile Setup

#### 1. Initialize Flutter Sentry

The mobile app is configured in `main.dart`:

```dart
import 'services/sentry_service.dart';

void main() async {
  // Initialize Sentry
  await sentryService.initialize(
    dsn: const String.fromEnvironment('SENTRY_DSN'),
    environment: const String.fromEnvironment('ENVIRONMENT'),
    release: const String.fromEnvironment('SENTRY_RELEASE'),
  );
  
  // Run app with error boundary
  runApp(const MITAApp());
}
```

#### 2. Screen Monitoring

Use error boundaries for comprehensive screen monitoring:

```dart
import 'widgets/sentry_error_boundary.dart';

// Wrap screens with error boundaries
SentryErrorBoundary(
  screenName: 'TransactionScreen',
  userId: currentUser.id,
  child: TransactionScreen(),
)
```

#### 3. Performance Monitoring

Monitor financial operations:

```dart
import 'services/performance_monitor.dart';

// Monitor API requests
final result = await performanceMonitor.monitorApiRequest(
  operation: 'fetchTransactions',
  request: () => apiService.getTransactions(),
  userId: user.id,
);

// Monitor financial calculations
final budget = await performanceMonitor.monitorFinancialOperation(
  operation: 'budgetCalculation',
  calculation: () => calculateBudget(),
  userId: user.id,
  currency: 'USD',
);
```

---

## Error Monitoring

### Error Categories

MITA Finance uses specialized error categories:

| Category | Description | Severity |
|----------|-------------|----------|
| `authentication` | Login/logout failures | High |
| `transaction_processing` | Transaction errors | Critical |
| `payment_processing` | Payment failures | Critical |
| `budget_calculation` | Budget computation errors | High |
| `financial_analysis` | Analysis failures | Medium |
| `security_violation` | Security breaches | Critical |
| `compliance_issue` | Compliance violations | Critical |

### Custom Error Capture

#### Backend Error Capture

```python
from app.services.sentry_service import capture_financial_error, FinancialErrorCategory

try:
    # Risky financial operation
    result = await process_transaction(user_id, amount)
except Exception as e:
    await capture_financial_error(
        exception=e,
        category=FinancialErrorCategory.TRANSACTION_PROCESSING,
        severity=FinancialSeverity.CRITICAL,
        user_id=user_id,
        transaction_id=transaction_id,
        amount=amount,
        currency=currency,
        additionalContext={
            'payment_method': payment_method,
            'merchant': merchant_name
        }
    )
    raise
```

#### Mobile Error Capture

```dart
import 'services/sentry_service.dart';

try {
  // Risky operation
  await processPayment();
} catch (error, stackTrace) {
  await sentryService.capturePaymentError(
    error,
    userId: user.id,
    paymentMethod: 'credit_card',
    amount: 100.0,
    currency: 'USD',
    screenName: 'PaymentScreen',
    stackTrace: stackTrace.toString(),
  );
  rethrow;
}
```

### Error Context

All errors automatically include:

- **User Context** - User ID, subscription tier, account type
- **Financial Context** - Transaction details, amounts, currencies
- **Request Context** - API endpoints, methods, parameters
- **Compliance Context** - PCI DSS requirements, data classification
- **Performance Context** - Response times, slow operations

### Data Sanitization

Sensitive financial data is automatically filtered:

```python
# Automatically redacted fields:
sensitive_keys = {
    'password', 'token', 'secret', 'key',
    'card_number', 'cvv', 'pin', 'ssn',
    'account_number', 'routing_number', 'iban'
}
```

---

## Performance Monitoring

### Performance Thresholds

#### API Endpoints (Production)

| Method | Default Threshold | Financial Endpoints |
|--------|------------------|---------------------|
| GET | 500ms | 300ms (balance, profile) |
| POST | 1000ms | 800ms (transactions) |
| PUT | 800ms | 1000ms (payments) |
| DELETE | 600ms | 500ms |

#### Database Operations

| Operation | Threshold |
|-----------|-----------|
| SELECT | 200ms |
| INSERT | 300ms |
| UPDATE | 400ms |
| DELETE | 250ms |

#### Financial Operations

| Operation | Threshold |
|-----------|-----------|
| Transaction Processing | 1000ms |
| Budget Calculation | 1500ms |
| Financial Analysis | 3000ms |
| Payment Processing | 1200ms |

### Performance Monitoring Usage

#### Backend Performance Monitoring

```python
from app.services.performance_monitor_enhanced import monitor_financial_operation

async with monitor_financial_operation(
    operation_name="calculate_monthly_budget",
    user_id=user.id,
    additional_context={
        'budget_period': 'monthly',
        'categories_count': len(categories)
    }
) as transaction:
    
    # Perform budget calculation
    result = await calculate_budget(user.id, categories)
    
    # Add result metadata
    transaction.set_data("calculated_categories", len(result))
    transaction.set_data("total_budget", result.total_amount)
    
    return result
```

#### Mobile Performance Monitoring

```dart
// Monitor screen rendering
await performanceMonitor.monitorScreenRender(
  screenName: 'BudgetScreen',
  operation: () async {
    // Screen rendering logic
    await loadBudgetData();
    await buildUI();
  },
  userId: user.id,
);

// Monitor API requests
final transactions = await performanceMonitor.monitorApiRequest(
  operation: 'fetchTransactions',
  request: () => api.getTransactions(userId),
  userId: user.id,
  endpoint: '/api/transactions',
);
```

### Performance Alerts

Automatic alerts are triggered when:

- API responses exceed thresholds
- Database queries are slow
- Financial calculations take too long
- Mobile screens render slowly
- Network requests timeout

---

## Financial Application Specific Monitoring

### Transaction Monitoring

Every financial transaction is comprehensively monitored:

```python
from app.core.sentry_context_manager import financial_transaction_context

async with financial_transaction_context(
    user_id=user.id,
    operation="payment_processing",
    transaction_id=transaction.id,
    amount=transaction.amount,
    currency=transaction.currency
) as ctx:
    
    # Process payment
    result = await payment_processor.process(transaction)
    
    # Add success metadata
    ctx.set_result(result)
    ctx.add_metadata("payment_method", result.payment_method)
    ctx.add_metadata("merchant", result.merchant)
```

### User Financial Context

Comprehensive user context for all operations:

```python
from app.core.sentry_context_manager import UserContext, set_financial_user

user_ctx = UserContext(
    user_id=user.id,
    email=user.email,
    subscription_tier=user.subscription_tier,
    account_type=user.account_type,
    risk_level=user.risk_assessment,
    location=user.location,
    last_login=user.last_login
)

set_financial_user(user_ctx)
```

### Compliance Context

All operations include compliance metadata:

```python
from app.core.sentry_context_manager import set_compliance_context

set_compliance_context(
    regulation="PCI_DSS",
    requirement="3.4_Secure_Cardholder_Data",
    status="compliant",
    details={
        "encryption_used": True,
        "access_logged": True,
        "data_retention": "compliant"
    }
)
```

### Security Event Monitoring

Security events are automatically captured:

```python
from app.core.sentry_context_manager import set_security_context

# Failed login attempt
set_security_context(
    event_type="failed_login",
    severity="high",
    details={
        "ip_address": request.client.host,
        "user_agent": request.headers.get("user-agent"),
        "attempt_count": failed_attempts
    },
    user_id=user_id
)
```

---

## Alert Rules and Notifications

### Production Alert Rules

#### Critical Financial Errors
- **Trigger**: Any error with `financial_service=true` and `severity=critical`
- **Threshold**: 1 error within 1 minute
- **Actions**: Email, Slack, PagerDuty
- **Escalation**: Immediate

#### Payment Processing Failures
- **Trigger**: Payment processing errors
- **Threshold**: 3 errors in 5 minutes
- **Actions**: Email to payments team, Slack alert
- **Escalation**: 15 minutes

#### Authentication Security Events
- **Trigger**: Authentication security violations
- **Threshold**: 1 event within 1 minute
- **Actions**: Security team email, PagerDuty
- **Escalation**: Immediate

#### High Error Rate
- **Trigger**: Error rate > 5% of total requests
- **Threshold**: 5% error rate in 5 minutes
- **Actions**: DevOps team notification
- **Escalation**: 15 minutes

### Notification Channels

#### Slack Integration
- **#finance-alerts** - Financial operation errors
- **#security-alerts** - Security violations
- **#payments-critical** - Payment processing issues
- **#compliance-critical** - Compliance violations

#### Email Notifications
- **finance-team@mita.finance** - Financial errors
- **security@mita.finance** - Security events
- **compliance@mita.finance** - Compliance issues

#### PagerDuty Integration
- **Finance Critical** - Payment and transaction failures
- **Security Critical** - Authentication and security violations
- **Compliance Critical** - PCI DSS violations

### Setting Up Alerts

1. **Configure Environment Variables**:
```bash
export SLACK_FINANCE_WEBHOOK="https://hooks.slack.com/services/..."
export PAGERDUTY_FINANCE_KEY="your-integration-key"
```

2. **Run Alert Setup Script**:
```bash
python scripts/setup_sentry_alerts.py \
  --org your-org-slug \
  --project mita-backend \
  --environment production
```

3. **Validate Configuration**:
```bash
python scripts/setup_sentry_alerts.py \
  --org your-org-slug \
  --project mita-backend \
  --validate-only
```

---

## Compliance and Audit

### PCI DSS Compliance

MITA Finance Sentry implementation is PCI DSS compliant:

- **Data Minimization** - Only necessary data is sent to Sentry
- **Sensitive Data Filtering** - Card numbers, PINs, and other sensitive data are automatically redacted
- **Secure Transmission** - All data is transmitted over HTTPS
- **Access Control** - Sentry access is restricted to authorized personnel
- **Audit Logging** - All access and modifications are logged

### Audit Trail

Comprehensive audit logging is maintained:

```python
from app.core.sentry_context_manager import sentry_context_manager

# Get audit trail for compliance reporting
audit_trail = sentry_context_manager.get_audit_trail(
    user_id=user.id,
    event_type=AuditEventType.TRANSACTION_CREATE,
    hours_back=24
)

# Export compliance report
sentry_context_manager.export_compliance_report(
    output_file="compliance_report.json",
    user_id=user.id,
    days_back=30
)
```

### Data Retention

| Data Type | Retention Period | Compliance Requirement |
|-----------|------------------|-------------------------|
| Error Logs | 7 years | PCI DSS |
| Performance Data | 1 year | Internal |
| Audit Logs | 7 years | PCI DSS, SOX |
| Debug Data | 30 days | Internal |

### Compliance Reports

Automated compliance reports are generated:

- **Daily** - Security event summary
- **Weekly** - Performance and error trends
- **Monthly** - Comprehensive compliance report
- **Quarterly** - Executive summary for audit

---

## Troubleshooting Guide

### Common Issues

#### 1. Sentry Not Capturing Errors

**Problem**: Errors are not appearing in Sentry
**Solution**:
```bash
# Check Sentry DSN configuration
echo $SENTRY_DSN

# Verify Sentry service initialization
python -c "from app.services.sentry_service import sentry_service; print(sentry_service.initialized)"

# Test error capture
python scripts/test_sentry_integration.py
```

#### 2. Performance Data Missing

**Problem**: Performance metrics not showing up
**Solution**:
```python
# Check performance monitoring configuration
from app.services.performance_monitor_enhanced import performance_monitor

# Verify sampling rate
print(f"Traces sample rate: {os.getenv('SENTRY_TRACES_SAMPLE_RATE', 'default')}")

# Enable debug mode temporarily
export SENTRY_DEBUG=true
```

#### 3. Sensitive Data Appearing in Sentry

**Problem**: Sensitive financial data visible in error reports
**Solution**:
```python
# Verify data filtering is active
from app.main import filter_sensitive_data

# Check sensitive keys configuration
from app.middleware.sentry_financial_middleware import FinancialSentryMiddleware

# Add additional sensitive fields if needed
sensitive_keys.add('your_custom_field')
```

#### 4. Alerts Not Firing

**Problem**: Expected alerts are not being triggered
**Solution**:
```bash
# Verify alert rules configuration
python scripts/setup_sentry_alerts.py --list-rules --org your-org --project your-project

# Check webhook configurations
curl -X POST $SLACK_FINANCE_WEBHOOK -d '{"text": "Test message"}'

# Validate PagerDuty integration
python scripts/test_pagerduty_integration.py
```

### Debug Mode

Enable debug mode for troubleshooting:

```bash
# Backend debug
export SENTRY_DEBUG=true
export ENVIRONMENT=development

# Mobile debug
flutter run --dart-define=SENTRY_DEBUG=true
```

### Health Check Endpoints

Monitor Sentry integration health:

```bash
# Check backend Sentry health
curl https://your-api.com/api/health/sentry

# Get error monitoring status
curl https://your-api.com/api/health/error-monitoring
```

---

## Best Practices

### Error Handling

1. **Always Include Context**:
```python
await capture_financial_error(
    exception=e,
    category=FinancialErrorCategory.TRANSACTION_PROCESSING,
    user_id=user.id,
    transaction_id=transaction.id,
    additional_context={
        'operation_step': 'payment_verification',
        'payment_method': payment_method
    }
)
```

2. **Use Appropriate Severity Levels**:
- `SECURITY_CRITICAL` - Security breaches, unauthorized access
- `CRITICAL` - Payment failures, transaction errors
- `HIGH` - Authentication failures, system errors
- `MEDIUM` - Validation errors, business logic issues
- `LOW` - Information, warnings

3. **Include User Context**:
```python
# Always set user context for financial operations
set_financial_user(UserContext(
    user_id=user.id,
    subscription_tier=user.tier,
    risk_level=user.risk_assessment
))
```

### Performance Monitoring

1. **Monitor Critical Paths**:
```python
# Always monitor financial operations
@financial_operation_monitor(
    operation_name="process_transaction",
    category=FinancialErrorCategory.TRANSACTION_PROCESSING
)
async def process_transaction():
    pass
```

2. **Set Appropriate Thresholds**:
- Financial operations: < 1000ms
- User-facing APIs: < 500ms
- Background tasks: < 5000ms

3. **Use Breadcrumbs Effectively**:
```python
add_financial_breadcrumb(
    message="Starting payment verification",
    data={
        'payment_method': method,
        'amount': amount,
        'verification_step': 'initial'
    }
)
```

### Security and Compliance

1. **Always Filter Sensitive Data**:
```python
# Sensitive data is automatically filtered, but verify
def is_sensitive_field(field_name):
    sensitive_patterns = ['card', 'pin', 'ssn', 'account']
    return any(pattern in field_name.lower() for pattern in sensitive_patterns)
```

2. **Include Compliance Context**:
```python
set_compliance_context(
    regulation="PCI_DSS",
    requirement="specific_requirement",
    status="compliant"
)
```

3. **Maintain Audit Trails**:
```python
# Audit events are automatically recorded, but you can add custom events
sentry_context_manager._record_audit_event(
    event_type=AuditEventType.CONFIGURATION_CHANGE,
    user_id=admin_user.id,
    details={'changed_setting': 'payment_threshold'}
)
```

### Mobile Best Practices

1. **Use Error Boundaries**:
```dart
// Wrap all screens with error boundaries
SentryErrorBoundary(
  screenName: 'PaymentScreen',
  userId: user.id,
  child: PaymentScreen(),
)
```

2. **Monitor User Interactions**:
```dart
await performanceMonitor.monitorUserInteraction(
  interaction: 'payment_button_tap',
  durationMs: 50,
  screenName: 'PaymentScreen',
  additionalContext: {'amount': amount}
);
```

3. **Handle Network Errors**:
```dart
try {
  await apiCall();
} catch (e) {
  await sentryService.captureNetworkError(
    e,
    endpoint: '/api/payments',
    method: 'POST',
    screenName: currentScreen,
  );
}
```

---

## API Reference

### Backend Sentry Service

#### `capture_financial_error()`

```python
async def capture_financial_error(
    exception: Exception,
    category: FinancialErrorCategory = FinancialErrorCategory.SYSTEM_ERROR,
    severity: FinancialSeverity = FinancialSeverity.MEDIUM,
    user_id: Optional[str] = None,
    transaction_id: Optional[str] = None,
    amount: Optional[float] = None,
    currency: Optional[str] = None,
    request: Optional[Request] = None,
    additional_context: Optional[Dict[str, Any]] = None
) -> str:
    """
    Capture financial-specific errors with enhanced context
    
    Returns:
        str: Event ID from Sentry
    """
```

#### `monitor_financial_performance()`

```python
@contextmanager
def monitor_financial_performance(
    operation_name: str,
    operation_type: str = "financial_operation",
    user_id: Optional[str] = None,
    transaction_data: Optional[Dict[str, Any]] = None
):
    """Context manager for performance monitoring of financial operations"""
```

### Mobile Sentry Service

#### `captureFinancialError()`

```dart
Future<SentryId> captureFinancialError(
  dynamic exception, {
  FinancialErrorCategory category = FinancialErrorCategory.systemError,
  FinancialSeverity severity = FinancialSeverity.medium,
  String? stackTrace,
  String? userId,
  String? transactionId,
  double? amount,
  String? currency,
  String? screenName,
  Map<String, dynamic>? additionalContext,
  Map<String, String>? tags,
})
```

#### `monitorScreenRender()`

```dart
Future<T> monitorScreenRender<T>({
  required String screenName,
  required Future<T> Function() operation,
  String? userId,
  Map<String, dynamic>? additionalContext,
})
```

### Performance Monitor API

#### `monitor_api_request()`

```python
@asynccontextmanager
async def monitor_api_request(
    request: Request,
    user_id: Optional[str] = None,
    additional_context: Optional[Dict[str, Any]] = None
):
    """Monitor API request performance"""
```

#### `get_performance_summary()`

```python
def get_performance_summary(
    last_hours: int = 1,
    category: Optional[PerformanceCategory] = None
) -> Dict[str, Any]:
    """Get performance summary for the last N hours"""
```

---

## Support and Maintenance

### Monitoring Health

Regular health checks ensure monitoring is working properly:

```bash
# Daily health check
curl https://api.mita.finance/health/sentry

# Weekly performance review
python scripts/generate_performance_report.py --days 7

# Monthly compliance report
python scripts/generate_compliance_report.py --month $(date +%Y-%m)
```

### Updates and Maintenance

1. **Weekly**: Review alert rules and thresholds
2. **Monthly**: Update sensitive data filters
3. **Quarterly**: Compliance and audit review
4. **Annually**: Security and configuration audit

### Getting Help

- **Documentation Issues**: Create issue in project repository
- **Alert Configuration**: Contact DevOps team
- **Compliance Questions**: Contact compliance team
- **Emergency Issues**: Use PagerDuty escalation

---

This comprehensive Sentry monitoring setup provides production-ready error tracking, performance monitoring, and compliance-aware logging for MITA Finance. The implementation follows financial services best practices while maintaining PCI DSS compliance and providing actionable insights for maintaining system reliability and user experience.