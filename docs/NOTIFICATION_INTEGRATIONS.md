# Notification System Integrations

Complete guide to the integrated notification system across all MITA modules.

## Overview

The notification system is fully integrated with:
- **Goals Module**: Achievement and progress notifications
- **Transactions Module**: Large transaction alerts
- **Budget Module**: Overspending warnings and budget alerts
- **Scheduled Tasks**: Daily reminders, overdue goals, weekly summaries

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                  Application Modules                     │
│  (Goals, Transactions, Budget, Analytics, etc.)         │
└───────────────────────┬─────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│          NotificationIntegration Helper                  │
│  • Easy-to-use wrapper for all notification types       │
│  • Template-based notifications                          │
│  • Error handling and logging                           │
└───────────────────────┬─────────────────────────────────┘
                        │
          ┌─────────────┼─────────────┐
          ▼             ▼             ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│Notification  │ │Notification  │ │   Push       │
│  Service     │ │  Templates   │ │  Service     │
│              │ │              │ │              │
│ • Create     │ │ • Goals      │ │ • FCM        │
│ • Store      │ │ • Budget     │ │ • APNS       │
│ • Deliver    │ │ • Tips       │ │ • Rich       │
│ • Track      │ │ • AI         │ │   Notifs     │
└──────────────┘ └──────────────┘ └──────────────┘
```

## Integration Points

### 1. Goals Module Integration

**File**: `app/api/goals/routes.py`

**Notifications Sent**:

| Event | Notification Type | Priority | Trigger |
|-------|------------------|----------|---------|
| Goal Created | Info | Medium | POST /goals/ |
| Goal Progress Milestone | Achievement | High (75%+), Medium | POST /goals/{id}/add_savings |
| Goal Completed | Achievement | High | Auto when progress reaches 100% |
| Goal Manually Completed | Achievement | High | POST /goals/{id}/complete |

**Example Integration**:

```python
from app.services.notification_integration import get_notification_integration

# In create_goal endpoint
notifier = get_notification_integration(db)
notifier.notify_goal_created(
    user_id=user.id,
    goal_title=goal.title,
    target_amount=float(goal.target_amount)
)
```

**Progress Milestones**:
- Notifications sent at: **25%, 50%, 75%, 90%** progress
- Automatic milestone detection in `notify_goal_progress()`
- No spam - only sends at exact milestones

### 2. Transactions Module Integration

**File**: `app/api/transactions/services.py`

**Notifications Sent**:

| Event | Notification Type | Priority | Trigger |
|-------|------------------|----------|---------|
| Large Transaction | Info | Medium | Transaction > $200 |

**Configuration**:

```python
LARGE_TRANSACTION_THRESHOLD = Decimal('200.00')
```

**Example Integration**:

```python
# In add_transaction function
if amount > LARGE_TRANSACTION_THRESHOLD:
    notifier = get_notification_integration(db)
    notifier.notify_large_transaction(
        user_id=user.id,
        amount=float(amount),
        category=txn.category,
        merchant=txn.merchant
    )
```

**Customization**:
- Threshold can be adjusted per user preferences
- Can be disabled in notification preferences
- Includes merchant info if available

### 3. Budget Alert System

**File**: `app/services/budget_alert_service.py`

**Notifications Sent**:

| Event | Notification Type | Priority | Trigger |
|-------|------------------|----------|---------|
| Budget Warning | Warning | High | Spent ≥ 80% of budget |
| Budget Exceeded | Alert | Critical | Spent ≥ 100% of budget |
| Monthly Summary | Info | Medium | End of month |

**Integration Point**: `app/services/core/engine/expense_tracker.py`

**Auto-Checking**:
```python
# Automatically checks after every transaction
def apply_transaction_to_plan(db: Session, txn: Transaction):
    # ... add transaction to plan ...

    # Check budget alerts
    if plan and plan.planned_amount > 0:
        alert_service = get_budget_alert_service(db)
        alert_service.check_single_category(
            user_id=txn.user_id,
            category=txn.category,
            spent_amount=plan.spent_amount,
            budget_limit=plan.planned_amount
        )
```

**Alert Thresholds**:
- **Warning**: 80% of budget spent
- **Danger**: 100% of budget spent (exceeded)

### 4. Scheduled Notifications

**File**: `app/services/scheduled_notifications.py`

**Scheduled Tasks**:

| Task | Frequency | Description |
|------|-----------|-------------|
| Daily Budget Reminder | Daily 8 AM | Remaining budget and daily allowance |
| Overdue Goals Check | Daily | Reminder for overdue goals (weekly) |
| Goals Due Soon | Daily | Alert 7 days before deadline |
| Weekly Progress Report | Sundays | Summary of goals and savings |
| Motivational Tips | Every 3 days | Random financial tips |

**Setup with Cron**:

```bash
# Add to crontab
0 8 * * * cd /path/to/mita && python -c "from app.services.scheduled_notifications import run_scheduled_notifications; run_scheduled_notifications()"
```

**Setup with APScheduler** (Recommended):

```python
# In your FastAPI app startup
from apscheduler.schedulers.background import BackgroundScheduler
from app.services.scheduled_notifications import run_scheduled_notifications

scheduler = BackgroundScheduler()
scheduler.add_job(run_scheduled_notifications, 'cron', hour=8, minute=0)
scheduler.start()
```

**Example Usage**:

```python
from app.services.scheduled_notifications import get_scheduled_notification_service

service = get_scheduled_notification_service(db)

# Run all scheduled tasks
results = service.run_all_scheduled_tasks()

# Or run specific task
service.check_overdue_goals()
service.send_daily_budget_reminders()
```

## Notification Templates

**File**: `app/services/notification_templates.py`

**Available Templates**:

### Goals
- `goal_created(title, target_amount)`
- `goal_progress_milestone(title, progress, saved, target)`
- `goal_completed(title, final_amount, days_taken?)`
- `goal_overdue(title, days_overdue)`
- `goal_due_soon(title, days_remaining, remaining_amount)`

### Budget
- `budget_warning(category, spent, limit, percentage)`
- `budget_exceeded(category, spent, limit, overage)`
- `budget_on_track(category, remaining)`
- `monthly_budget_summary(total_spent, total_budget, categories_over)`

### Transactions
- `large_transaction(amount, category, merchant?)`
- `transaction_added_to_goal(amount, goal_title, progress)`
- `recurring_transaction_detected(category, amount)`

### AI & Insights
- `ai_recommendation(recommendation, potential_savings?)`
- `spending_pattern_alert(insight)`
- `savings_opportunity(category, amount)`

### Daily Reminders
- `daily_budget_reminder(remaining_budget, days_left)`
- `weekly_progress_report(goals_on_track, total_saved)`
- `motivational_tip(tip)`

**Example**:

```python
from app.services.notification_templates import NotificationTemplates

templates = NotificationTemplates()
template = templates.goal_completed(
    goal_title="Emergency Fund",
    final_amount=5000.0,
    days_taken=180
)

# Returns:
# {
#     "title": "🎉 Goal Achieved!",
#     "message": "Congratulations! You've completed 'Emergency Fund' and saved $5,000.00 in 180 days!",
#     "type": "achievement",
#     "priority": "high",
#     "category": "goal_updates",
#     "data": {"celebration": True, "confetti": True}
# }
```

## NotificationIntegration Helper

**File**: `app/services/notification_integration.py`

**Purpose**: Simplifies sending notifications from any module.

**Usage**:

```python
from app.services.notification_integration import get_notification_integration

notifier = get_notification_integration(db)

# Goals
notifier.notify_goal_created(user_id, title, amount)
notifier.notify_goal_progress(user_id, title, progress, saved, target)
notifier.notify_goal_completed(user_id, title, amount, days?)

# Budget
notifier.notify_budget_warning(user_id, category, spent, limit, percentage)
notifier.notify_budget_exceeded(user_id, category, spent, limit, overage)

# Transactions
notifier.notify_large_transaction(user_id, amount, category, merchant?)

# Custom
notifier.send_custom_notification(
    user_id=user_id,
    title="Custom Title",
    message="Custom message",
    notification_type="info",
    priority="medium"
)
```

**Features**:
- ✅ Template-based notifications
- ✅ Automatic error handling (non-blocking)
- ✅ Logging for debugging
- ✅ Push notification support
- ✅ Rich notification support (images, actions)

## Error Handling

All notification integrations are **non-blocking**:

```python
try:
    notifier.notify_goal_created(...)
except Exception as e:
    # Log error but don't fail the main operation
    logger.error(f"Failed to send notification: {e}")
```

**Benefits**:
- Main operations (create goal, add transaction) never fail due to notifications
- All errors are logged for monitoring
- Users still get notifications if the service recovers

## Testing Notifications

### Manual Testing

```python
from app.core.session import SessionLocal
from app.services.notification_integration import get_notification_integration
from uuid import UUID

db = SessionLocal()
notifier = get_notification_integration(db)

# Test goal notification
notifier.notify_goal_created(
    user_id=UUID("your-user-id"),
    goal_title="Test Goal",
    target_amount=1000.0
)

# Test budget alert
notifier.notify_budget_warning(
    user_id=UUID("your-user-id"),
    category="food",
    spent=850.0,
    limit=1000.0,
    percentage=85.0
)

db.close()
```

### API Testing

```bash
# Create a goal (should trigger notification)
curl -X POST http://localhost:8000/api/v1/goals/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Test Goal",
    "target_amount": 1000,
    "category": "Savings"
  }'

# Add savings (should trigger progress notification at milestones)
curl -X POST http://localhost:8000/api/v1/goals/{goal_id}/add_savings \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"amount": 250}'

# Create large transaction (should trigger notification if > $200)
curl -X POST http://localhost:8000/api/v1/transactions/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "amount": 300,
    "category": "shopping",
    "description": "Test large transaction",
    "spent_at": "2025-10-28T10:00:00Z"
  }'
```

### Check Notifications

```bash
# List user notifications
curl http://localhost:8000/api/v1/notifications/list \
  -H "Authorization: Bearer YOUR_TOKEN"

# Get unread count
curl http://localhost:8000/api/v1/notifications/unread-count \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## Monitoring & Analytics

### Logs to Monitor

```bash
# Check notification logs
grep "notification sent" /var/log/mita/app.log

# Check for errors
grep "Failed to send.*notification" /var/log/mita/app.log

# Budget alert stats
grep "Budget.*alert sent" /var/log/mita/app.log

# Scheduled task results
grep "Scheduled notifications completed" /var/log/mita/app.log
```

### Key Metrics

- **Notification Delivery Rate**: % of notifications successfully delivered
- **Push Notification CTR**: Click-through rate on push notifications
- **Read Rate**: % of in-app notifications marked as read
- **Budget Alert Frequency**: Number of budget alerts per user per month
- **Goal Completion Notifications**: Correlation with goal achievement rates

## Configuration

### User Preferences

Users can control notifications via `/notifications/preferences`:

```json
{
  "push_enabled": true,
  "email_enabled": false,
  "budget_alerts": true,
  "goal_updates": true,
  "daily_reminders": true,
  "ai_recommendations": true,
  "transaction_alerts": false,
  "achievement_notifications": true
}
```

### System Configuration

**Environment Variables**:

```bash
# Firebase Cloud Messaging
GOOGLE_APPLICATION_CREDENTIALS=/app/config/google-vision-credentials.json

# Notification settings
NOTIFICATION_BATCH_SIZE=100
LARGE_TRANSACTION_THRESHOLD=200.00
BUDGET_WARNING_THRESHOLD=0.80
BUDGET_DANGER_THRESHOLD=1.00
```

## Best Practices

1. **Always use NotificationIntegration helper** - Don't call NotificationService directly
2. **Use templates** - Don't hardcode notification messages
3. **Non-blocking** - Never let notifications fail the main operation
4. **Log everything** - Use structured logging for debugging
5. **Respect user preferences** - Check preferences before sending
6. **Avoid spam** - Use milestone checks for progress notifications
7. **Test thoroughly** - Test both success and failure scenarios

## Troubleshooting

### Notifications not sending

1. Check notification service is running
2. Verify Firebase credentials are configured
3. Check user has valid push token registered
4. Review logs for errors
5. Verify user notification preferences

### Budget alerts not working

1. Ensure `planned_amount` is set in DailyPlan
2. Check expense_tracker integration is active
3. Verify budget_alert_service is imported correctly
4. Review logs for budget check errors

### Scheduled tasks not running

1. Verify cron job or APScheduler is configured
2. Check database connection in background task
3. Review scheduled task logs
4. Test run manually first

## Future Enhancements

- [ ] Email notifications support
- [ ] SMS notifications for critical alerts
- [ ] In-app notification sound customization
- [ ] Rich notification actions (Quick reply, Snooze)
- [ ] Notification batching/grouping
- [ ] A/B testing for notification content
- [ ] Machine learning for optimal send times
- [ ] Multi-language support
- [ ] Notification templates management UI

## Related Documentation

- [MODULE_10_NOTIFICATIONS.md](./MODULE_10_NOTIFICATIONS.md) - Core notification system
- [FIREBASE_SETUP.md](./FIREBASE_SETUP.md) - Firebase configuration
- API Documentation: `/api/v1/notifications/*` endpoints

---

**Last Updated**: 2025-10-28
**Version**: 1.0
**Status**: Production Ready ✅
