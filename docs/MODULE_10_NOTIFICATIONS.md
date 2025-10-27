# MODULE 10: Notifications - Complete Implementation

## Overview

The Notifications Module provides a comprehensive notification system for the MITA application with support for:
- Push notifications via Firebase Cloud Messaging (FCM)
- Rich notifications with images and actions
- Priority-based notification delivery
- User notification preferences
- Notification history and tracking
- Multiple notification types and categories

## Architecture

### Backend Components

#### 1. Database Model (`app/db/models/notification.py`)

**Notification Model** - Main table for storing notification history
- Full support for rich content (images, action URLs, structured data)
- Priority levels: low, medium, high, critical
- Notification types: alert, warning, info, tip, achievement, reminder, recommendation
- Status tracking: pending, sent, delivered, read, failed, cancelled
- Scheduling support for future delivery
- Expiration support for time-sensitive notifications
- Grouping support for related notifications

**Key Features:**
- Read tracking with timestamps
- Delivery tracking across channels (push, email, in-app)
- Error logging for failed deliveries
- Retry mechanism support
- Category-based organization (budget, transaction, goal, etc.)

#### 2. Service Layer (`app/services/notification_service.py`)

**NotificationService** - Core business logic for notifications

**Main Methods:**
```python
# Create and deliver notification
create_notification(user_id, title, message, type, priority, ...)

# Get user notifications with filters
get_user_notifications(user_id, limit, offset, unread_only, type, priority, category)

# Mark notifications as read
mark_as_read(notification_id, user_id)
mark_all_as_read(user_id)

# Delete notification
delete_notification(notification_id, user_id)

# Get unread count
get_unread_count(user_id)

# Scheduled notifications
send_scheduled_notifications()

# Cleanup old notifications
cleanup_old_notifications(days=30)
```

**Convenience Functions** for common notification types:
- `send_budget_alert()` - Budget threshold alerts
- `send_goal_achievement()` - Goal completion notifications
- `send_daily_reminder()` - Daily checkpoint reminders
- `send_ai_recommendation()` - AI-generated advice
- `send_transaction_alert()` - Transaction notifications

#### 3. API Endpoints (`app/api/notifications/routes.py`)

**Token Management:**
- `POST /notifications/register-device` - Register device for push notifications
- `POST /notifications/unregister-device` - Unregister device
- `POST /notifications/update-device` - Update device token (on refresh)

**Notification Management:**
- `GET /notifications/list` - Get notifications with filters (limit, offset, unread_only, type, priority, category)
- `GET /notifications/{notification_id}` - Get specific notification
- `POST /notifications/create` - Create new notification (admin/testing)
- `POST /notifications/{notification_id}/mark-read` - Mark notification as read
- `POST /notifications/mark-all-read` - Mark all notifications as read
- `DELETE /notifications/{notification_id}` - Delete notification
- `GET /notifications/unread-count` - Get unread notification count

**Preferences Management:**
- `GET /notifications/preferences` - Get user notification preferences
- `PUT /notifications/preferences` - Update notification preferences

**Testing:**
- `POST /notifications/test` - Send test notification

### Frontend Components

#### 1. Models (`mobile_app/lib/models/notification_model.dart`)

**NotificationModel** - Dart model matching backend schema
- Full field support with proper typing
- `fromJson()` and `toJson()` methods
- Helper methods:
  - `getRelativeTime()` - Returns "2h ago", "1d ago", etc.
  - `isExpired` - Check if notification has expired
  - `isHighPriority` - Check if high or critical priority
  - `isCritical` - Check if critical priority

**NotificationListResponse** - API response wrapper
- List of notifications
- Total count
- Unread count
- Has more flag for pagination

**NotificationPreferences** - User preferences model
- Push/email enabled toggles
- Per-category toggles (budget_alerts, goal_updates, daily_reminders, etc.)

#### 2. API Service (`mobile_app/lib/services/api_service.dart`)

**Notification Methods:**
```dart
// Get notifications with filters
Future<Map<String, dynamic>> getNotifications({
  int limit = 50,
  int offset = 0,
  bool unreadOnly = false,
  String? type,
  String? priority,
  String? category,
})

// Get specific notification
Future<Map<String, dynamic>?> getNotification(String notificationId)

// Mark as read
Future<bool> markNotificationRead(String notificationId)
Future<bool> markAllNotificationsRead()

// Delete notification
Future<bool> deleteNotification(String notificationId)

// Get unread count
Future<int> getUnreadNotificationCount()

// Preferences
Future<Map<String, dynamic>?> getNotificationPreferences()
Future<bool> updateNotificationPreferences(Map<String, dynamic> preferences)
```

#### 3. UI Screen (`mobile_app/lib/screens/notifications_screen.dart`)

**NotificationsScreen** - Modern, feature-rich notification UI

**Features:**
- ✅ Pull-to-refresh
- ✅ Unread count badge in app bar
- ✅ Swipe-to-mark-as-read (swipe right)
- ✅ Swipe-to-delete (swipe left with confirmation)
- ✅ Filter by unread only, type, priority
- ✅ Priority color coding (critical=red, high=orange, medium=blue, low=grey)
- ✅ Type-specific icons
- ✅ Rich notifications with images
- ✅ Action buttons for action URLs
- ✅ Relative timestamps ("2h ago")
- ✅ Visual distinction for unread (yellow highlight)
- ✅ Priority border for high/critical notifications
- ✅ Empty state with icon
- ✅ Mark all as read button
- ✅ Tap notification to mark as read

**Design:**
- Consistent with MITA design language (Sora/Manrope fonts, tan background)
- Smooth animations and transitions
- Material Design 3 components
- Responsive layout

## Notification Types and Use Cases

### 1. Budget Alerts (type: alert/warning)
**Triggers:**
- Budget threshold reached (50%, 75%, 90%, 100%)
- Unusual spending detected
- Budget period ending soon

**Priority:** High (100%+) / Medium (50-99%)

**Example:**
```python
await send_budget_alert(
    db=db,
    user_id=user_id,
    budget_name="Groceries",
    spent_amount=450.00,
    budget_limit=500.00,
    percentage=90.0,
)
```

### 2. Goal Achievements (type: achievement)
**Triggers:**
- Goal target reached
- Milestone completed
- Streak maintained

**Priority:** High

**Example:**
```python
await send_goal_achievement(
    db=db,
    user_id=user_id,
    goal_name="Emergency Fund",
    achieved_amount=5000.00,
)
```

### 3. Daily Reminders (type: reminder)
**Triggers:**
- Daily checkpoint time
- Unlogged transactions
- Missing budget updates

**Priority:** Low

**Example:**
```python
await send_daily_reminder(
    db=db,
    user_id=user_id,
    message="Don't forget to log your daily expenses!",
)
```

### 4. AI Recommendations (type: recommendation)
**Triggers:**
- Daily AI advice generation (8 AM)
- Spending pattern insights
- Savings opportunities

**Priority:** Medium

**Example:**
```python
await send_ai_recommendation(
    db=db,
    user_id=user_id,
    title="Savings Opportunity",
    message="You could save $50 by switching to a cheaper phone plan",
    action_url="/advice/123",
)
```

### 5. Transaction Alerts (type: info)
**Triggers:**
- Large transaction detected
- Duplicate transaction suspected
- Unusual merchant activity

**Priority:** Low/Medium

**Example:**
```python
await send_transaction_alert(
    db=db,
    user_id=user_id,
    amount=250.00,
    merchant="Best Buy",
    category="Electronics",
)
```

## Integration with Other Modules

### Module 1: Authentication
- Post-login push token registration
- Token cleanup on logout
- User-specific notification delivery

### Module 2: Financial Tracking
- Transaction alerts for large purchases
- Spending category warnings
- Budget threshold notifications

### Module 3: Goals
- Goal milestone achievements
- Progress reminders
- Goal completion celebrations

### Module 4: Daily Checkpoint
- Daily reminder notifications
- Streak maintenance alerts
- Checkpoint completion confirmations

### Module 5: Analytics
- Spending pattern insights
- Behavioral anomaly alerts
- Optimization recommendations

### Module 9: AI Advisory
- Daily budget advice (8 AM)
- Personalized financial tips
- Smart recommendations

## Push Notification Flow

### Registration Flow
1. User logs in successfully
2. Firebase FCM token is generated
3. `SecurePushTokenManager.initializePostAuthentication()` called
4. Token stored securely in device keychain/keystore
5. Token registered with backend via `/notifications/register-device`
6. Backend stores token in `push_tokens` table

### Notification Delivery Flow
1. Event triggers notification (budget alert, goal achievement, etc.)
2. `NotificationService.create_notification()` creates notification record
3. If `send_immediately=True`, delivery starts
4. Service fetches user's push tokens from database
5. For each token, sends FCM message with:
   - Title and body
   - Custom data payload (notification_id, type, priority, action_url)
   - Image URL (if available)
6. On success:
   - Notification status updated to "delivered"
   - Delivery timestamp recorded
   - Success logged to `notification_logs`
7. On failure:
   - Status updated to "failed"
   - Error message logged
   - Email fallback attempted (TODO)

### Token Refresh Flow
1. FCM token refreshes (periodic or forced)
2. `SecurePushTokenManager` detects refresh
3. Old and new tokens sent to backend
4. Backend updates token via `/notifications/update-device`
5. Old token deleted, new token stored

### Logout Flow
1. User initiates logout
2. `SecurePushTokenManager.cleanupOnLogout()` called
3. Token unregistered from backend via `/notifications/unregister-device`
4. Token removed from secure storage
5. FCM subscription cancelled

## Database Schema

### `notifications` table
```sql
CREATE TABLE notifications (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    -- Content
    title VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    type VARCHAR(50) NOT NULL DEFAULT 'info',
    priority VARCHAR(20) NOT NULL DEFAULT 'medium',

    -- Rich content
    image_url VARCHAR(500),
    action_url VARCHAR(500),
    data JSONB,

    -- Delivery tracking
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    channel VARCHAR(20),

    -- Read tracking
    is_read BOOLEAN NOT NULL DEFAULT false,
    read_at TIMESTAMP WITH TIME ZONE,

    -- Scheduling
    scheduled_for TIMESTAMP WITH TIME ZONE,
    sent_at TIMESTAMP WITH TIME ZONE,
    delivered_at TIMESTAMP WITH TIME ZONE,

    -- Error tracking
    error_message TEXT,
    retry_count VARCHAR NOT NULL DEFAULT '0',

    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    expires_at TIMESTAMP WITH TIME ZONE,

    -- Grouping
    category VARCHAR(50),
    group_key VARCHAR(100),

    -- Indexes
    INDEX idx_notifications_user_id (user_id),
    INDEX idx_notifications_is_read (is_read),
    INDEX idx_notifications_scheduled_for (scheduled_for),
    INDEX idx_notifications_created_at (created_at),
    INDEX idx_notifications_group_key (group_key),
    INDEX idx_notifications_composite (user_id, is_read, created_at)
);
```

### `push_tokens` table
```sql
CREATE TABLE push_tokens (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token VARCHAR NOT NULL UNIQUE,
    platform VARCHAR NOT NULL DEFAULT 'fcm',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),

    INDEX idx_push_tokens_user_id (user_id)
);
```

### `notification_logs` table
```sql
CREATE TABLE notification_logs (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id),
    channel VARCHAR NOT NULL,  -- 'push' or 'email'
    message VARCHAR NOT NULL,
    success BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),

    INDEX idx_notification_logs_user_id (user_id)
);
```

## Configuration

### Environment Variables
```bash
# Firebase Configuration
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json

# Email Fallback
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
```

### Firebase Project Setup
1. Create Firebase project at https://console.firebase.google.com
2. Add Android/iOS apps with package names
3. Download `google-services.json` (Android) and `GoogleService-Info.plist` (iOS)
4. Enable Cloud Messaging in Firebase Console
5. Generate service account key for backend
6. Set `GOOGLE_APPLICATION_CREDENTIALS` environment variable

### Flutter Configuration
```dart
// firebase_options.dart
static const FirebaseOptions android = FirebaseOptions(
  apiKey: 'YOUR_API_KEY',
  appId: 'YOUR_APP_ID',
  messagingSenderId: 'YOUR_SENDER_ID',
  projectId: 'mita-finance',
  storageBucket: 'mita-finance.firebasestorage.app',
);
```

## Security Considerations

### Backend Security
- ✅ All endpoints require authentication
- ✅ Users can only access their own notifications
- ✅ SQL injection protection via SQLAlchemy
- ✅ Input validation via Pydantic schemas
- ✅ Foreign key constraints with CASCADE delete
- ✅ Token uniqueness enforced at database level

### Mobile Security
- ✅ Tokens stored in secure keychain (iOS) / keystore (Android)
- ✅ Post-authentication token registration only
- ✅ Automatic token cleanup on logout
- ✅ Token refresh handling with exponential backoff
- ✅ Rate limiting on registration attempts (min 2s between)
- ✅ Comprehensive audit logging

## Testing

### Backend Unit Tests
```bash
pytest app/tests/test_notification_service.py
pytest app/tests/test_notification_routes.py
```

### Manual Testing
```bash
# Send test notification
curl -X POST http://localhost:8000/api/notifications/test \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"message": "Test notification"}'

# Get notifications
curl -X GET "http://localhost:8000/api/notifications/list?limit=10&unread_only=true" \
  -H "Authorization: Bearer <token>"

# Mark as read
curl -X POST http://localhost:8000/api/notifications/<id>/mark-read \
  -H "Authorization: Bearer <token>"
```

### Integration Testing
1. Register device on login
2. Trigger notification from another module (e.g., budget alert)
3. Verify push notification received on device
4. Check notification appears in NotificationsScreen
5. Mark notification as read
6. Verify unread count updates
7. Delete notification
8. Verify notification removed from list

## Performance Considerations

### Database Optimization
- Composite index on (user_id, is_read, created_at) for fast queries
- Automatic cleanup of old notifications (30 days default)
- Efficient pagination with limit/offset
- Expired notification filtering in queries

### API Response Time
- Target: < 100ms for list endpoint
- Target: < 50ms for unread count endpoint
- Connection pooling via SQLAlchemy
- Async/await for concurrent operations

### Push Delivery
- Batch processing for multiple tokens per user
- Exponential backoff on failures
- Circuit breaker pattern (TODO)
- Queue-based delivery for high volume (TODO)

## Future Enhancements

### Planned Features
- [ ] WebSocket support for real-time notifications
- [ ] Server-Sent Events (SSE) for live updates
- [ ] Notification templates system
- [ ] Multi-language support (i18n)
- [ ] Rate limiting per user
- [ ] Notification batching and digests
- [ ] Deep link URL validation
- [ ] Rich notification actions (quick reply, buttons)
- [ ] Notification sounds and vibration patterns
- [ ] Notification channels (Android 8+)
- [ ] Scheduled recurring notifications
- [ ] Notification analytics dashboard

### Known Limitations
- APNS (Apple Push Notification Service) disabled due to dependency conflicts
- Email fallback not fully implemented
- No support for notification groups/threads
- No support for notification snoozing
- Limited to 100 notifications per query (pagination required for more)

## Troubleshooting

### Push Notifications Not Received
1. Check FCM token is registered: `SELECT * FROM push_tokens WHERE user_id = '<user_id>'`
2. Verify Firebase credentials: `echo $GOOGLE_APPLICATION_CREDENTIALS`
3. Check notification status: `SELECT status, error_message FROM notifications WHERE user_id = '<user_id>'`
4. Verify FCM console shows no errors
5. Check device notification permissions

### Notifications Not Appearing in App
1. Verify API endpoint returns data: `/notifications/list`
2. Check authentication token is valid
3. Verify notification is not expired: `expires_at > NOW()`
4. Check Flutter logs for API errors
5. Verify NotificationModel parsing is successful

### Token Registration Failures
1. Check network connectivity
2. Verify auth token is valid
3. Check backend logs for errors
4. Verify database connection
5. Check for duplicate token conflicts

## Changelog

### Version 1.0.0 (2025-10-27)
- ✅ Initial implementation of notifications module
- ✅ Complete backend API with all CRUD operations
- ✅ Flutter UI with modern design and rich features
- ✅ FCM integration for push notifications
- ✅ Notification preferences system
- ✅ Priority-based notification delivery
- ✅ Rich notifications with images and actions
- ✅ Scheduled notifications support
- ✅ Notification history and tracking
- ✅ Integration with all MITA modules

## Maintainers
- Backend: MITA Backend Team
- Mobile: MITA Mobile Team
- Infrastructure: MITA DevOps Team

## License
Proprietary - MITA Finance © 2025
