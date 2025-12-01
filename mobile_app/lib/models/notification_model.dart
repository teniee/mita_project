/// Notification Model for MITA
/// Represents a notification with rich content support
class NotificationModel {
  final String id;
  final String userId;
  final String title;
  final String message;
  final String
      type; // alert, warning, info, tip, achievement, reminder, recommendation
  final String priority; // low, medium, high, critical
  final String? imageUrl;
  final String? actionUrl;
  final Map<String, dynamic>? data;
  final String status; // pending, sent, delivered, read, failed, cancelled
  final String? channel; // push, email, in_app
  final bool isRead;
  final DateTime? readAt;
  final DateTime? scheduledFor;
  final DateTime? sentAt;
  final DateTime? deliveredAt;
  final String? errorMessage;
  final DateTime createdAt;
  final DateTime updatedAt;
  final DateTime? expiresAt;
  final String? category; // budget, transaction, goal, etc.
  final String? groupKey;

  NotificationModel({
    required this.id,
    required this.userId,
    required this.title,
    required this.message,
    required this.type,
    required this.priority,
    this.imageUrl,
    this.actionUrl,
    this.data,
    required this.status,
    this.channel,
    required this.isRead,
    this.readAt,
    this.scheduledFor,
    this.sentAt,
    this.deliveredAt,
    this.errorMessage,
    required this.createdAt,
    required this.updatedAt,
    this.expiresAt,
    this.category,
    this.groupKey,
  });

  factory NotificationModel.fromJson(Map<String, dynamic> json) {
    return NotificationModel(
      id: json['id'] as String,
      userId: json['user_id'] as String,
      title: json['title'] as String,
      message: json['message'] as String,
      type: json['type'] as String,
      priority: json['priority'] as String,
      imageUrl: json['image_url'] as String?,
      actionUrl: json['action_url'] as String?,
      data: json['data'] as Map<String, dynamic>?,
      status: json['status'] as String,
      channel: json['channel'] as String?,
      isRead: json['is_read'] as bool,
      readAt: json['read_at'] != null
          ? DateTime.parse(json['read_at'] as String)
          : null,
      scheduledFor: json['scheduled_for'] != null
          ? DateTime.parse(json['scheduled_for'] as String)
          : null,
      sentAt: json['sent_at'] != null
          ? DateTime.parse(json['sent_at'] as String)
          : null,
      deliveredAt: json['delivered_at'] != null
          ? DateTime.parse(json['delivered_at'] as String)
          : null,
      errorMessage: json['error_message'] as String?,
      createdAt: DateTime.parse(json['created_at'] as String),
      updatedAt: DateTime.parse(json['updated_at'] as String),
      expiresAt: json['expires_at'] != null
          ? DateTime.parse(json['expires_at'] as String)
          : null,
      category: json['category'] as String?,
      groupKey: json['group_key'] as String?,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'user_id': userId,
      'title': title,
      'message': message,
      'type': type,
      'priority': priority,
      'image_url': imageUrl,
      'action_url': actionUrl,
      'data': data,
      'status': status,
      'channel': channel,
      'is_read': isRead,
      'read_at': readAt?.toIso8601String(),
      'scheduled_for': scheduledFor?.toIso8601String(),
      'sent_at': sentAt?.toIso8601String(),
      'delivered_at': deliveredAt?.toIso8601String(),
      'error_message': errorMessage,
      'created_at': createdAt.toIso8601String(),
      'updated_at': updatedAt.toIso8601String(),
      'expires_at': expiresAt?.toIso8601String(),
      'category': category,
      'group_key': groupKey,
    };
  }

  NotificationModel copyWith({
    String? id,
    String? userId,
    String? title,
    String? message,
    String? type,
    String? priority,
    String? imageUrl,
    String? actionUrl,
    Map<String, dynamic>? data,
    String? status,
    String? channel,
    bool? isRead,
    DateTime? readAt,
    DateTime? scheduledFor,
    DateTime? sentAt,
    DateTime? deliveredAt,
    String? errorMessage,
    DateTime? createdAt,
    DateTime? updatedAt,
    DateTime? expiresAt,
    String? category,
    String? groupKey,
  }) {
    return NotificationModel(
      id: id ?? this.id,
      userId: userId ?? this.userId,
      title: title ?? this.title,
      message: message ?? this.message,
      type: type ?? this.type,
      priority: priority ?? this.priority,
      imageUrl: imageUrl ?? this.imageUrl,
      actionUrl: actionUrl ?? this.actionUrl,
      data: data ?? this.data,
      status: status ?? this.status,
      channel: channel ?? this.channel,
      isRead: isRead ?? this.isRead,
      readAt: readAt ?? this.readAt,
      scheduledFor: scheduledFor ?? this.scheduledFor,
      sentAt: sentAt ?? this.sentAt,
      deliveredAt: deliveredAt ?? this.deliveredAt,
      errorMessage: errorMessage ?? this.errorMessage,
      createdAt: createdAt ?? this.createdAt,
      updatedAt: updatedAt ?? this.updatedAt,
      expiresAt: expiresAt ?? this.expiresAt,
      category: category ?? this.category,
      groupKey: groupKey ?? this.groupKey,
    );
  }

  /// Get relative time string (e.g., "2h ago", "1d ago")
  String getRelativeTime() {
    final now = DateTime.now();
    final difference = now.difference(createdAt);

    if (difference.inMinutes < 1) {
      return 'Just now';
    } else if (difference.inMinutes < 60) {
      return '${difference.inMinutes}m ago';
    } else if (difference.inHours < 24) {
      return '${difference.inHours}h ago';
    } else if (difference.inDays < 7) {
      return '${difference.inDays}d ago';
    } else if (difference.inDays < 30) {
      return '${(difference.inDays / 7).floor()}w ago';
    } else {
      return '${(difference.inDays / 30).floor()}mo ago';
    }
  }

  /// Check if notification is expired
  bool get isExpired {
    if (expiresAt == null) return false;
    return DateTime.now().isAfter(expiresAt!);
  }

  /// Check if notification is high priority
  bool get isHighPriority {
    return priority == 'high' || priority == 'critical';
  }

  /// Check if notification is critical
  bool get isCritical {
    return priority == 'critical';
  }
}

/// Notification List Response
class NotificationListResponse {
  final List<NotificationModel> notifications;
  final int total;
  final int unreadCount;
  final bool hasMore;

  NotificationListResponse({
    required this.notifications,
    required this.total,
    required this.unreadCount,
    required this.hasMore,
  });

  factory NotificationListResponse.fromJson(Map<String, dynamic> json) {
    return NotificationListResponse(
      notifications: (json['notifications'] as List<dynamic>)
          .map((e) => NotificationModel.fromJson(e as Map<String, dynamic>))
          .toList(),
      total: json['total'] as int,
      unreadCount: json['unread_count'] as int,
      hasMore: json['has_more'] as bool,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'notifications': notifications.map((e) => e.toJson()).toList(),
      'total': total,
      'unread_count': unreadCount,
      'has_more': hasMore,
    };
  }
}

/// Notification Preferences Model
class NotificationPreferences {
  final bool pushEnabled;
  final bool emailEnabled;
  final bool budgetAlerts;
  final bool goalUpdates;
  final bool dailyReminders;
  final bool aiRecommendations;
  final bool transactionAlerts;
  final bool achievementNotifications;

  NotificationPreferences({
    required this.pushEnabled,
    required this.emailEnabled,
    required this.budgetAlerts,
    required this.goalUpdates,
    required this.dailyReminders,
    required this.aiRecommendations,
    required this.transactionAlerts,
    required this.achievementNotifications,
  });

  factory NotificationPreferences.fromJson(Map<String, dynamic> json) {
    return NotificationPreferences(
      pushEnabled: json['push_enabled'] as bool? ?? true,
      emailEnabled: json['email_enabled'] as bool? ?? true,
      budgetAlerts: json['budget_alerts'] as bool? ?? true,
      goalUpdates: json['goal_updates'] as bool? ?? true,
      dailyReminders: json['daily_reminders'] as bool? ?? true,
      aiRecommendations: json['ai_recommendations'] as bool? ?? true,
      transactionAlerts: json['transaction_alerts'] as bool? ?? true,
      achievementNotifications:
          json['achievement_notifications'] as bool? ?? true,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'push_enabled': pushEnabled,
      'email_enabled': emailEnabled,
      'budget_alerts': budgetAlerts,
      'goal_updates': goalUpdates,
      'daily_reminders': dailyReminders,
      'ai_recommendations': aiRecommendations,
      'transaction_alerts': transactionAlerts,
      'achievement_notifications': achievementNotifications,
    };
  }

  NotificationPreferences copyWith({
    bool? pushEnabled,
    bool? emailEnabled,
    bool? budgetAlerts,
    bool? goalUpdates,
    bool? dailyReminders,
    bool? aiRecommendations,
    bool? transactionAlerts,
    bool? achievementNotifications,
  }) {
    return NotificationPreferences(
      pushEnabled: pushEnabled ?? this.pushEnabled,
      emailEnabled: emailEnabled ?? this.emailEnabled,
      budgetAlerts: budgetAlerts ?? this.budgetAlerts,
      goalUpdates: goalUpdates ?? this.goalUpdates,
      dailyReminders: dailyReminders ?? this.dailyReminders,
      aiRecommendations: aiRecommendations ?? this.aiRecommendations,
      transactionAlerts: transactionAlerts ?? this.transactionAlerts,
      achievementNotifications:
          achievementNotifications ?? this.achievementNotifications,
    );
  }
}
