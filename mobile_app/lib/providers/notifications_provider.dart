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
  NotificationsProvider({ApiService? apiService})
      : _apiService = apiService ?? ApiService();

  final ApiService _apiService;
  int _sessionGeneration = 0;
  int _notificationsRequestId = 0;
  int _unreadCountRequestId = 0;

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

    final generation = _sessionGeneration;
    final requestId = ++_notificationsRequestId;
    final unreadCountRequestId = ++_unreadCountRequestId;
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

      if (!_isCurrentNotificationsRequest(generation, requestId)) return;

      final notificationsList =
          response['notifications'] as List<dynamic>? ?? [];
      final notifications = notificationsList
          .map((json) =>
              NotificationModel.fromJson(json as Map<String, dynamic>))
          .toList();

      _notifications = notifications;

      if (_isCurrentUnreadCountRequest(generation, unreadCountRequestId)) {
        final unreadCountData = response['unread_count'];
        _unreadCount = (unreadCountData == null)
            ? 0
            : (unreadCountData is num)
                ? unreadCountData.toInt()
                : (unreadCountData is String
                    ? int.tryParse(unreadCountData) ?? 0
                    : 0);
      }

      final totalData = response['total'];
      _total = (totalData == null)
          ? 0
          : (totalData is num)
              ? totalData.toInt()
              : (totalData is String ? int.tryParse(totalData) ?? 0 : 0);

      _hasMore = response['has_more'] as bool? ?? false;
      _state = NotificationState.loaded;
      _errorMessage = null;

      logInfo(
          'Notifications loaded: ${notifications.length} items, $unreadCount unread',
          tag: 'NOTIFICATIONS_PROVIDER');
    } catch (e) {
      logError('Failed to load notifications: $e',
          tag: 'NOTIFICATIONS_PROVIDER');
      if (!_isCurrentNotificationsRequest(generation, requestId)) return;
      _errorMessage = e.toString();
      _state = NotificationState.error;
    } finally {
      if (_isCurrentNotificationsRequest(generation, requestId)) {
        _setLoading(false);
      }
    }
  }

  /// Mark a single notification as read
  Future<bool> markAsRead(NotificationModel notification) async {
    if (notification.isRead) return true;

    final generation = _sessionGeneration;
    _invalidateNotificationSnapshot();
    try {
      logInfo('Marking notification ${notification.id} as read',
          tag: 'NOTIFICATIONS_PROVIDER');

      final success = await _apiService.markNotificationRead(notification.id);
      if (!_isCurrentSession(generation)) return false;
      if (success) {
        _invalidateNotificationSnapshot();
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
      logError('Failed to mark notification as read: $e',
          tag: 'NOTIFICATIONS_PROVIDER');
      return false;
    }
  }

  /// Mark all notifications as read
  Future<bool> markAllAsRead() async {
    final generation = _sessionGeneration;
    _invalidateNotificationSnapshot();
    try {
      logInfo('Marking all notifications as read',
          tag: 'NOTIFICATIONS_PROVIDER');

      final success = await _apiService.markAllNotificationsRead();
      if (!_isCurrentSession(generation)) return false;
      if (success) {
        _invalidateNotificationSnapshot();
        _notifications = _notifications
            .map((n) => n.copyWith(
                  isRead: true,
                  readAt: DateTime.now(),
                ))
            .toList();
        _unreadCount = 0;
        notifyListeners();

        logInfo('All notifications marked as read',
            tag: 'NOTIFICATIONS_PROVIDER');
        return true;
      }
      return false;
    } catch (e) {
      logError('Failed to mark all notifications as read: $e',
          tag: 'NOTIFICATIONS_PROVIDER');
      return false;
    }
  }

  /// Delete a notification
  Future<bool> deleteNotification(NotificationModel notification) async {
    final generation = _sessionGeneration;
    _invalidateNotificationSnapshot();
    try {
      logInfo('Deleting notification ${notification.id}',
          tag: 'NOTIFICATIONS_PROVIDER');

      final success = await _apiService.deleteNotification(notification.id);
      if (!_isCurrentSession(generation)) return false;
      if (success) {
        _invalidateNotificationSnapshot();
        _notifications.removeWhere((n) => n.id == notification.id);
        if (!notification.isRead && _unreadCount > 0) _unreadCount--;
        notifyListeners();

        logInfo('Notification deleted', tag: 'NOTIFICATIONS_PROVIDER');
        return true;
      }
      return false;
    } catch (e) {
      logError('Failed to delete notification: $e',
          tag: 'NOTIFICATIONS_PROVIDER');
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
    final generation = _sessionGeneration;
    final requestId = ++_unreadCountRequestId;
    try {
      final count = await _apiService.getUnreadNotificationCount();
      if (!_isCurrentUnreadCountRequest(generation, requestId)) return;
      if (count != _unreadCount) {
        _unreadCount = count;
        notifyListeners();
      }
    } catch (e) {
      logError('Failed to fetch unread count: $e',
          tag: 'NOTIFICATIONS_PROVIDER');
    }
  }

  /// Clear error message
  void clearError() {
    _errorMessage = null;
    notifyListeners();
  }

  /// Discard all state owned by the previous authenticated account.
  void resetSession() {
    _sessionGeneration++;
    _notificationsRequestId++;
    _unreadCountRequestId++;
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

  /// Backwards-compatible alias for existing logout callers.
  void reset() => resetSession();

  // Private helper
  void _setLoading(bool loading) {
    _isLoading = loading;
    notifyListeners();
  }

  bool _isCurrentSession(int generation) => generation == _sessionGeneration;

  bool _isCurrentNotificationsRequest(int generation, int requestId) =>
      _isCurrentSession(generation) && requestId == _notificationsRequestId;

  bool _isCurrentUnreadCountRequest(int generation, int requestId) =>
      _isCurrentSession(generation) && requestId == _unreadCountRequestId;

  void _invalidateNotificationSnapshot() {
    _notificationsRequestId++;
    _unreadCountRequestId++;
    _isLoading = false;
    if (_state == NotificationState.loading) {
      _state = _notifications.isEmpty
          ? NotificationState.initial
          : NotificationState.loaded;
    }
  }
}
