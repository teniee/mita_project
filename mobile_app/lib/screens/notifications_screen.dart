import 'package:flutter/material.dart';
import '../theme/app_colors.dart';
import '../theme/app_typography.dart';
import 'package:cached_network_image/cached_network_image.dart';
import '../services/api_service.dart';
import '../models/notification_model.dart';

class NotificationsScreen extends StatefulWidget {
  const NotificationsScreen({super.key});

  @override
  State<NotificationsScreen> createState() => _NotificationsScreenState();
}

class _NotificationsScreenState extends State<NotificationsScreen> {
  final ApiService _apiService = ApiService();
  List<NotificationModel> _notifications = [];
  int _unreadCount = 0;
  bool _isLoading = true;
  bool _showUnreadOnly = false;
  String? _filterType;
  String? _filterPriority;

  @override
  void initState() {
    super.initState();
    _loadNotifications();
  }

  Future<void> _loadNotifications() async {
    setState(() => _isLoading = true);

    try {
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

      setState(() {
        _notifications = notifications;
        _unreadCount = response['unread_count'] as int? ?? 0;
        _isLoading = false;
      });
    } catch (e) {
      setState(() => _isLoading = false);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Error loading notifications: $e'),
            backgroundColor: Colors.red,
          ),
        );
      }
    }
  }

  Future<void> _markAsRead(NotificationModel notification) async {
    if (notification.isRead) return;

    final success = await _apiService.markNotificationRead(notification.id);
    if (success) {
      setState(() {
        final index = _notifications.indexWhere((n) => n.id == notification.id);
        if (index != -1) {
          _notifications[index] = notification.copyWith(
            isRead: true,
            readAt: DateTime.now(),
          );
        }
        if (_unreadCount > 0) _unreadCount--;
      });
    }
  }

  Future<void> _markAllAsRead() async {
    final success = await _apiService.markAllNotificationsRead();
    if (success) {
      setState(() {
        _notifications = _notifications.map((n) => n.copyWith(
          isRead: true,
          readAt: DateTime.now(),
        )).toList();
        _unreadCount = 0;
      });

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('All notifications marked as read'),
            backgroundColor: Colors.green,
          ),
        );
      }
    }
  }

  Future<void> _deleteNotification(NotificationModel notification) async {
    final success = await _apiService.deleteNotification(notification.id);
    if (success) {
      setState(() {
        _notifications.removeWhere((n) => n.id == notification.id);
        if (!notification.isRead && _unreadCount > 0) _unreadCount--;
      });

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Notification deleted'),
            backgroundColor: Colors.grey,
          ),
        );
      }
    }
  }

  void _showFilterMenu() {
    showModalBottomSheet(
      context: context,
      backgroundColor: const AppColors.background,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (context) => Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Filter Notifications',
              style: TextStyle(
                fontFamily: AppTypography.fontHeading,
                fontSize: 20,
                fontWeight: FontWeight.bold,
                color: AppColors.textPrimary,
              ),
            ),
            const SizedBox(height: 20),

            SwitchListTile(
              title: const Text('Show Unread Only'),
              value: _showUnreadOnly,
              onChanged: (value) {
                setState(() => _showUnreadOnly = value);
                Navigator.pop(context);
                _loadNotifications();
              },
              activeColor: const AppColors.textPrimary,
            ),

            const Divider(),

            const Text(
              'Filter by Type',
              style: TextStyle(
                fontFamily: AppTypography.fontHeading,
                fontSize: 14,
                fontWeight: FontWeight.w600,
              ),
            ),
            Wrap(
              spacing: 8,
              children: [
                'All', 'alert', 'warning', 'info', 'tip', 'achievement', 'reminder'
              ].map((type) => FilterChip(
                label: Text(type == 'All' ? 'All' : type),
                selected: type == 'All' ? _filterType == null : _filterType == type,
                onSelected: (selected) {
                  setState(() => _filterType = type == 'All' ? null : type);
                  Navigator.pop(context);
                  _loadNotifications();
                },
                selectedColor: const AppColors.textPrimary,
                labelStyle: TextStyle(
                  color: (type == 'All' ? _filterType == null : _filterType == type)
                      ? Colors.white
                      : Colors.black,
                ),
              )).toList(),
            ),

            const SizedBox(height: 16),

            const Text(
              'Filter by Priority',
              style: TextStyle(
                fontFamily: AppTypography.fontHeading,
                fontSize: 14,
                fontWeight: FontWeight.w600,
              ),
            ),
            Wrap(
              spacing: 8,
              children: ['All', 'critical', 'high', 'medium', 'low'].map((priority) =>
                FilterChip(
                  label: Text(priority == 'All' ? 'All' : priority),
                  selected: priority == 'All' ? _filterPriority == null : _filterPriority == priority,
                  onSelected: (selected) {
                    setState(() => _filterPriority = priority == 'All' ? null : priority);
                    Navigator.pop(context);
                    _loadNotifications();
                  },
                  selectedColor: const AppColors.textPrimary,
                  labelStyle: TextStyle(
                    color: (priority == 'All' ? _filterPriority == null : _filterPriority == priority)
                        ? Colors.white
                        : Colors.black,
                  ),
                )
              ).toList(),
            ),
          ],
        ),
      ),
    );
  }

  Color _getPriorityColor(String priority) {
    switch (priority) {
      case 'critical':
        return Colors.red;
      case 'high':
        return Colors.orange;
      case 'medium':
        return Colors.blue;
      case 'low':
        return Colors.grey;
      default:
        return Colors.grey;
    }
  }

  IconData _getTypeIcon(String type) {
    switch (type) {
      case 'alert':
        return Icons.error_outline;
      case 'warning':
        return Icons.warning_amber_outlined;
      case 'info':
        return Icons.info_outline;
      case 'tip':
        return Icons.lightbulb_outline;
      case 'achievement':
        return Icons.emoji_events_outlined;
      case 'reminder':
        return Icons.notifications_outlined;
      case 'recommendation':
        return Icons.recommend_outlined;
      default:
        return Icons.notifications_outlined;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const AppColors.background,
      appBar: AppBar(
        title: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Text(
              'Notifications',
              style: TextStyle(
                fontFamily: AppTypography.fontHeading,
                fontWeight: FontWeight.bold,
                color: AppColors.textPrimary,
              ),
            ),
            if (_unreadCount > 0) ...[
              const SizedBox(width: 8),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                decoration: BoxDecoration(
                  color: Colors.red,
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Text(
                  '$_unreadCount',
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 12,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
            ],
          ],
        ),
        backgroundColor: const AppColors.background,
        elevation: 0,
        iconTheme: const IconThemeData(color: AppColors.textPrimary),
        centerTitle: true,
        actions: [
          IconButton(
            icon: const Icon(Icons.filter_list),
            onPressed: _showFilterMenu,
            tooltip: 'Filter',
          ),
          if (_unreadCount > 0)
            IconButton(
              icon: const Icon(Icons.done_all),
              onPressed: _markAllAsRead,
              tooltip: 'Mark all as read',
            ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: _loadNotifications,
        color: const AppColors.textPrimary,
        child: _isLoading
            ? const Center(child: CircularProgressIndicator())
            : _notifications.isEmpty
                ? Center(
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Icon(
                          Icons.notifications_off_outlined,
                          size: 80,
                          color: Colors.grey[400],
                        ),
                        const SizedBox(height: 16),
                        Text(
                          'No notifications',
                          style: TextStyle(
                            fontFamily: AppTypography.fontHeading,
                            fontSize: 18,
                            color: Colors.grey[600],
                          ),
                        ),
                      ],
                    ),
                  )
                : ListView.builder(
                    padding: const EdgeInsets.all(16),
                    itemCount: _notifications.length,
                    itemBuilder: (context, index) {
                      final notification = _notifications[index];

                      return Dismissible(
                        key: Key(notification.id),
                        background: Container(
                          margin: const EdgeInsets.only(bottom: 16),
                          decoration: BoxDecoration(
                            color: Colors.green,
                            borderRadius: BorderRadius.circular(14),
                          ),
                          alignment: Alignment.centerLeft,
                          padding: const EdgeInsets.only(left: 20),
                          child: const Icon(Icons.check, color: Colors.white),
                        ),
                        secondaryBackground: Container(
                          margin: const EdgeInsets.only(bottom: 16),
                          decoration: BoxDecoration(
                            color: Colors.red,
                            borderRadius: BorderRadius.circular(14),
                          ),
                          alignment: Alignment.centerRight,
                          padding: const EdgeInsets.only(right: 20),
                          child: const Icon(Icons.delete, color: Colors.white),
                        ),
                        confirmDismiss: (direction) async {
                          if (direction == DismissDirection.startToEnd) {
                            // Mark as read
                            _markAsRead(notification);
                            return false;
                          } else {
                            // Delete
                            return await showDialog(
                              context: context,
                              builder: (context) => AlertDialog(
                                title: const Text('Delete Notification'),
                                content: const Text('Are you sure you want to delete this notification?'),
                                actions: [
                                  TextButton(
                                    onPressed: () => Navigator.pop(context, false),
                                    child: const Text('Cancel'),
                                  ),
                                  TextButton(
                                    onPressed: () => Navigator.pop(context, true),
                                    child: const Text('Delete', style: TextStyle(color: Colors.red)),
                                  ),
                                ],
                              ),
                            );
                          }
                        },
                        onDismissed: (direction) {
                          if (direction == DismissDirection.endToStart) {
                            _deleteNotification(notification);
                          }
                        },
                        child: _buildNotificationCard(notification),
                      );
                    },
                  ),
      ),
    );
  }

  Widget _buildNotificationCard(NotificationModel notification) {
    return GestureDetector(
      onTap: () => _markAsRead(notification),
      child: Container(
        margin: const EdgeInsets.only(bottom: 16),
        decoration: BoxDecoration(
          color: notification.isRead ? AppColors.surface : AppColors.secondary.withValues(alpha: 0.3),
          borderRadius: BorderRadius.circular(14),
          border: notification.isHighPriority
              ? Border.all(color: _getPriorityColor(notification.priority), width: 2)
              : null,
          boxShadow: [
            BoxShadow(
              color: Colors.black.withValues(alpha: 0.05),
              blurRadius: 10,
              offset: const Offset(0, 4),
            ),
          ],
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Image if available
            if (notification.imageUrl != null && notification.imageUrl!.isNotEmpty)
              ClipRRect(
                borderRadius: const BorderRadius.vertical(top: Radius.circular(14)),
                child: CachedNetworkImage(
                  imageUrl: notification.imageUrl!,
                  height: 150,
                  width: double.infinity,
                  fit: BoxFit.cover,
                  placeholder: (context, url) => Container(
                    height: 150,
                    color: Colors.grey[200],
                    child: const Center(child: CircularProgressIndicator()),
                  ),
                  errorWidget: (context, url, error) => const SizedBox.shrink(),
                ),
              ),

            Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Header with icon, title, and priority badge
                  Row(
                    children: [
                      Icon(
                        _getTypeIcon(notification.type),
                        color: _getPriorityColor(notification.priority),
                        size: 24,
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          notification.title,
                          style: TextStyle(
                            fontFamily: AppTypography.fontHeading,
                            fontWeight: FontWeight.bold,
                            fontSize: 16,
                            color: notification.isRead
                                ? Colors.black87
                                : const AppColors.textPrimary,
                          ),
                        ),
                      ),
                      if (notification.isHighPriority)
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                          decoration: BoxDecoration(
                            color: _getPriorityColor(notification.priority),
                            borderRadius: BorderRadius.circular(8),
                          ),
                          child: Text(
                            notification.priority.toUpperCase(),
                            style: const TextStyle(
                              color: Colors.white,
                              fontSize: 10,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                        ),
                    ],
                  ),
                  const SizedBox(height: 8),

                  // Message
                  Text(
                    notification.message,
                    style: TextStyle(
                      fontFamily: AppTypography.fontBody,
                      fontSize: 14,
                      color: notification.isRead ? Colors.black54 : Colors.black87,
                    ),
                    maxLines: 3,
                    overflow: TextOverflow.ellipsis,
                  ),
                  const SizedBox(height: 12),

                  // Footer with timestamp and action button
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Row(
                        children: [
                          Icon(
                            Icons.access_time,
                            size: 14,
                            color: Colors.grey[600],
                          ),
                          const SizedBox(width: 4),
                          Text(
                            notification.getRelativeTime(),
                            style: TextStyle(
                              fontFamily: AppTypography.fontBody,
                              fontSize: 12,
                              color: Colors.grey[600],
                            ),
                          ),
                        ],
                      ),

                      if (notification.actionUrl != null && notification.actionUrl!.isNotEmpty)
                        TextButton(
                          onPressed: () {
                            // TODO: Handle action URL (e.g., navigate to specific screen)
                            _markAsRead(notification);
                          },
                          child: const Text(
                            'View',
                            style: TextStyle(
                              fontFamily: AppTypography.fontHeading,
                              fontWeight: FontWeight.w600,
                              color: AppColors.textPrimary,
                            ),
                          ),
                        ),
                    ],
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
