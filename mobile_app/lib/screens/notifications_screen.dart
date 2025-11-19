import 'package:flutter/material.dart';
import 'package:cached_network_image/cached_network_image.dart';
import 'package:provider/provider.dart';
import '../theme/app_colors.dart';
import '../theme/app_typography.dart';
import '../providers/notifications_provider.dart';
import '../models/notification_model.dart';

class NotificationsScreen extends StatefulWidget {
  const NotificationsScreen({super.key});

  @override
  State<NotificationsScreen> createState() => _NotificationsScreenState();
}

class _NotificationsScreenState extends State<NotificationsScreen> {
  @override
  void initState() {
    super.initState();
    // Load notifications when screen is first shown
    WidgetsBinding.instance.addPostFrameCallback((_) {
      final provider = context.read<NotificationsProvider>();
      if (provider.state == NotificationState.initial) {
        provider.loadNotifications();
      }
    });
  }

  void _showFilterMenu() {
    final provider = context.read<NotificationsProvider>();

    showModalBottomSheet(
      context: context,
      backgroundColor: const Color(0xFFFFF9F0),
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (context) => StatefulBuilder(
        builder: (context, setSheetState) => Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'Filter Notifications',
                style: TextStyle(
                  fontFamily: 'Sora',
                  fontSize: 20,
                  fontWeight: FontWeight.bold,
                  color: Color(0xFF193C57),
                ),
              ),
              const SizedBox(height: 20),

              SwitchListTile(
                title: const Text('Show Unread Only'),
                value: provider.showUnreadOnly,
                onChanged: (value) {
                  Navigator.pop(context);
                  provider.setShowUnreadOnly(value);
                },
                activeColor: const Color(0xFF193C57),
              ),

              const Divider(),

              const Text(
                'Filter by Type',
                style: TextStyle(
                  fontFamily: 'Sora',
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
                  selected: type == 'All' ? provider.filterType == null : provider.filterType == type,
                  onSelected: (selected) {
                    Navigator.pop(context);
                    provider.setFilterType(type == 'All' ? null : type);
                  },
                  selectedColor: const Color(0xFF193C57),
                  labelStyle: TextStyle(
                    color: (type == 'All' ? provider.filterType == null : provider.filterType == type)
                        ? Colors.white
                        : Colors.black,
                  ),
                )).toList(),
              ),

              const SizedBox(height: 16),

              const Text(
                'Filter by Priority',
                style: TextStyle(
                  fontFamily: 'Sora',
                  fontSize: 14,
                  fontWeight: FontWeight.w600,
                ),
              ),
              Wrap(
                spacing: 8,
                children: ['All', 'critical', 'high', 'medium', 'low'].map((priority) =>
                  FilterChip(
                    label: Text(priority == 'All' ? 'All' : priority),
                    selected: priority == 'All' ? provider.filterPriority == null : provider.filterPriority == priority,
                    onSelected: (selected) {
                      Navigator.pop(context);
                      provider.setFilterPriority(priority == 'All' ? null : priority);
                    },
                    selectedColor: const Color(0xFF193C57),
                    labelStyle: TextStyle(
                      color: (priority == 'All' ? provider.filterPriority == null : provider.filterPriority == priority)
                          ? Colors.white
                          : Colors.black,
                    ),
                  )
                ).toList(),
              ),
            ],
          ),
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
    // Watch the provider for reactive updates
    final provider = context.watch<NotificationsProvider>();
    final notifications = provider.notifications;
    final unreadCount = provider.unreadCount;
    final isLoading = provider.isLoading;

    return Scaffold(
      backgroundColor: const Color(0xFFFFF9F0),
      appBar: AppBar(
        title: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Text(
              'Notifications',
              style: TextStyle(
                fontFamily: 'Sora',
                fontWeight: FontWeight.bold,
                color: Color(0xFF193C57),
              ),
            ),
            if (unreadCount > 0) ...[
              const SizedBox(width: 8),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                decoration: BoxDecoration(
                  color: Colors.red,
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Text(
                  '$unreadCount',
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
        backgroundColor: const Color(0xFFFFF9F0),
        elevation: 0,
        iconTheme: const IconThemeData(color: Color(0xFF193C57)),
        centerTitle: true,
        actions: [
          IconButton(
            icon: const Icon(Icons.filter_list),
            onPressed: _showFilterMenu,
            tooltip: 'Filter',
          ),
          if (unreadCount > 0)
            IconButton(
              icon: const Icon(Icons.done_all),
              onPressed: () async {
                final success = await provider.markAllAsRead();
                if (success && mounted) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(
                      content: Text('All notifications marked as read'),
                      backgroundColor: Colors.green,
                    ),
                  );
                }
              },
              tooltip: 'Mark all as read',
            ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: provider.refresh,
        color: const Color(0xFF193C57),
        child: _buildBody(provider, notifications, isLoading),
      ),
    );
  }

  Widget _buildBody(NotificationsProvider provider, List<NotificationModel> notifications, bool isLoading) {
    if (isLoading && notifications.isEmpty) {
      return const Center(child: CircularProgressIndicator());
    }

    if (provider.state == NotificationState.error && notifications.isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              Icons.error_outline,
              size: 80,
              color: Colors.red[300],
            ),
            const SizedBox(height: 16),
            Text(
              'Error loading notifications',
              style: TextStyle(
                fontFamily: 'Sora',
                fontSize: 18,
                color: Colors.grey[600],
              ),
            ),
            const SizedBox(height: 8),
            TextButton(
              onPressed: () => provider.loadNotifications(refresh: true),
              child: const Text('Retry'),
            ),
          ],
        ),
      );
    }

    if (notifications.isEmpty) {
      return Center(
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
                fontFamily: 'Sora',
                fontSize: 18,
                color: Colors.grey[600],
              ),
            ),
          ],
        ),
      );
    }

    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: notifications.length,
      itemBuilder: (context, index) {
        final notification = notifications[index];

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
              provider.markAsRead(notification);
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
          onDismissed: (direction) async {
            if (direction == DismissDirection.endToStart) {
              final success = await provider.deleteNotification(notification);
              if (success && mounted) {
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(
                    content: Text('Notification deleted'),
                    backgroundColor: Colors.grey,
                  ),
                );
              }
            }
          },
          child: _buildNotificationCard(notification, provider),
        );
      },
    );
  }

  Widget _buildNotificationCard(NotificationModel notification, NotificationsProvider provider) {
    return GestureDetector(
      onTap: () => provider.markAsRead(notification),
      child: Container(
        margin: const EdgeInsets.only(bottom: 16),
        decoration: BoxDecoration(
          color: notification.isRead ? Colors.white : const Color(0xFFFFEEC0),
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
                            fontFamily: 'Sora',
                            fontWeight: FontWeight.bold,
                            fontSize: 16,
                            color: notification.isRead
                                ? Colors.black87
                                : const Color(0xFF193C57),
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
                      fontFamily: 'Manrope',
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
                              fontFamily: 'Manrope',
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
                            provider.markAsRead(notification);
                          },
                          child: const Text(
                            'View',
                            style: TextStyle(
                              fontFamily: 'Sora',
                              fontWeight: FontWeight.w600,
                              color: Color(0xFF193C57),
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
