import 'package:flutter/foundation.dart';
import '../services/api_service.dart';
import '../services/logging_service.dart';
import '../models/notification_model.dart';

/// Notification state enum for tracking loading states
enum NotificationState {
  initial,
  loading,
  loaded,
  error,
}

/// Centralized notifications state management provider
/// Manages notification list, unread count, and filtering
class NotificationsProvider extends ChangeNotifier {
  final ApiService _apiService = ApiService();

  // State
  NotificationState _state = NotificationState.initial;
  List<NotificationModel> _notifications = [];
  int _unreadCount = 0;
  int _total = 0;
  bool _hasMore = false;
  String? _errorMessage;
  bool _isLoading = false;

  // Filter state
  bool _showUnreadOnly = false;
  String? _filterType;
  String? _filterPriority;

  // Getters
  NotificationState get state => _state;
  List<NotificationModel> get notifications => _notifications;
  int get unreadCount => _unreadCount;
  int get total => _total;
  bool get hasMore => _hasMore;
  String? get errorMessage => _errorMessage;
  bool get isLoading => _isLoading;
  bool get showUnreadOnly => _showUnreadOnly;
  String? get filterType => _filterType;
  String? get filterPriority => _filterPriority;

  /// Load notifications with current filters
  Future<void> loadNotifications({bool refresh = false}) async {
    if (_isLoading && !refresh) return;

    _setLoading(true);
    if (refresh || _state == NotificationState.initial) {
      _state = NotificationState.loading;
      notifyListeners();
    }

    try {
      logInfo('Loading notifications', tag: 'NOTIFICATIONS_PROVIDER', extra: {
        'unreadOnly': _showUnreadOnly,
        'filterType': _filterType,
        'filterPriority': _filterPriority,
      });

      final response = await _apiService.getNotifications(
        unreadOnly: _showUnreadOnly,
        type: _filterType,
        priority: _filterPriority,
        limit: 100,
      );

      final notificationsList = response['notifications'] as List<dynamic>? ?? [];
      final notifications = notificationsList
          .map((json) => NotificationModel.fromJson(json as Map<String, dynamic>))
          .toList();

      _notifications = notifications;
      _unreadCount = response['unread_count'] as int? ?? 0;
      _total = response['total'] as int? ?? 0;
      _hasMore = response['has_more'] as bool? ?? false;
      _state = NotificationState.loaded;
      _errorMessage = null;

      logInfo('Notifications loaded: ${notifications.length} items, $unreadCount unread',
          tag: 'NOTIFICATIONS_PROVIDER');
    } catch (e) {
      logError('Failed to load notifications: $e', tag: 'NOTIFICATIONS_PROVIDER');
      _errorMessage = e.toString();
      _state = NotificationState.error;
    } finally {
      _setLoading(false);
    }
  }

  /// Mark a single notification as read
  Future<bool> markAsRead(NotificationModel notification) async {
    if (notification.isRead) return true;

    try {
      logInfo('Marking notification ${notification.id} as read', tag: 'NOTIFICATIONS_PROVIDER');

      final success = await _apiService.markNotificationRead(notification.id);
      if (success) {
        final index = _notifications.indexWhere((n) => n.id == notification.id);
        if (index != -1) {
          _notifications[index] = notification.copyWith(
            isRead: true,
            readAt: DateTime.now(),
          );
        }
        if (_unreadCount > 0) _unreadCount--;
        notifyListeners();

        logInfo('Notification marked as read', tag: 'NOTIFICATIONS_PROVIDER');
        return true;
      }
      return false;
    } catch (e) {
      logError('Failed to mark notification as read: $e', tag: 'NOTIFICATIONS_PROVIDER');
      return false;
    }
  }

  /// Mark all notifications as read
  Future<bool> markAllAsRead() async {
    try {
      logInfo('Marking all notifications as read', tag: 'NOTIFICATIONS_PROVIDER');

      final success = await _apiService.markAllNotificationsRead();
      if (success) {
        _notifications = _notifications
            .map((n) => n.copyWith(
                  isRead: true,
                  readAt: DateTime.now(),
                ))
            .toList();
        _unreadCount = 0;
        notifyListeners();

        logInfo('All notifications marked as read', tag: 'NOTIFICATIONS_PROVIDER');
        return true;
      }
      return false;
    } catch (e) {
      logError('Failed to mark all notifications as read: $e', tag: 'NOTIFICATIONS_PROVIDER');
      return false;
    }
  }

  /// Delete a notification
  Future<bool> deleteNotification(NotificationModel notification) async {
    try {
      logInfo('Deleting notification ${notification.id}', tag: 'NOTIFICATIONS_PROVIDER');

      final success = await _apiService.deleteNotification(notification.id);
      if (success) {
        _notifications.removeWhere((n) => n.id == notification.id);
        if (!notification.isRead && _unreadCount > 0) _unreadCount--;
        notifyListeners();

        logInfo('Notification deleted', tag: 'NOTIFICATIONS_PROVIDER');
        return true;
      }
      return false;
    } catch (e) {
      logError('Failed to delete notification: $e', tag: 'NOTIFICATIONS_PROVIDER');
      return false;
    }
  }

  /// Update filter settings
  void setShowUnreadOnly(bool value) {
    if (_showUnreadOnly == value) return;
    _showUnreadOnly = value;
    notifyListeners();
    loadNotifications(refresh: true);
  }

  /// Set type filter
  void setFilterType(String? type) {
    if (_filterType == type) return;
    _filterType = type;
    notifyListeners();
    loadNotifications(refresh: true);
  }

  /// Set priority filter
  void setFilterPriority(String? priority) {
    if (_filterPriority == priority) return;
    _filterPriority = priority;
    notifyListeners();
    loadNotifications(refresh: true);
  }

  /// Clear all filters
  void clearFilters() {
    _showUnreadOnly = false;
    _filterType = null;
    _filterPriority = null;
    notifyListeners();
    loadNotifications(refresh: true);
  }

  /// Refresh notifications
  Future<void> refresh() async {
    await loadNotifications(refresh: true);
  }

  /// Get unread count from server
  Future<void> fetchUnreadCount() async {
    try {
      final count = await _apiService.getUnreadNotificationCount();
      if (count != _unreadCount) {
        _unreadCount = count;
        notifyListeners();
      }
    } catch (e) {
      logError('Failed to fetch unread count: $e', tag: 'NOTIFICATIONS_PROVIDER');
    }
  }

  /// Clear error message
  void clearError() {
    _errorMessage = null;
    notifyListeners();
  }

  /// Reset state (e.g., on logout)
  void reset() {
    _state = NotificationState.initial;
    _notifications = [];
    _unreadCount = 0;
    _total = 0;
    _hasMore = false;
    _errorMessage = null;
    _isLoading = false;
    _showUnreadOnly = false;
    _filterType = null;
    _filterPriority = null;
    notifyListeners();
  }

  // Private helper
  void _setLoading(bool loading) {
    _isLoading = loading;
    notifyListeners();
  }
}
