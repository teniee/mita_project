import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../services/advanced_financial_engine.dart';
import '../theme/app_colors.dart';
import '../theme/app_typography.dart';
import '../providers/notifications_provider.dart';
import '../models/notification_model.dart';

/// Intelligent Notifications Widget
///
/// Displays smart, contextual financial notifications powered by the
/// Advanced Financial Engine, including behavioral insights, spending alerts,
/// predictive warnings, and personalized recommendations.
class IntelligentNotificationsWidget extends StatefulWidget {
  final AdvancedFinancialEngine financialEngine;
  final bool showOnlyHighPriority;
  final int maxNotifications;
  final VoidCallback? onNotificationTap;

  const IntelligentNotificationsWidget({
    super.key,
    required this.financialEngine,
    this.showOnlyHighPriority = false,
    this.maxNotifications = 5,
    this.onNotificationTap,
  });

  @override
  State<IntelligentNotificationsWidget> createState() =>
      _IntelligentNotificationsWidgetState();
}

class _IntelligentNotificationsWidgetState
    extends State<IntelligentNotificationsWidget>
    with TickerProviderStateMixin {
  late AnimationController _fadeController;
  late AnimationController _slideController;
  late Animation<double> _fadeAnimation;
  late Animation<Offset> _slideAnimation;

  bool _isExpanded = false;

  @override
  void initState() {
    super.initState();
    _initializeAnimations();
    // Load notifications via provider after widget is built
    WidgetsBinding.instance.addPostFrameCallback((_) {
      final provider = context.read<NotificationsProvider>();
      if (provider.state == NotificationState.initial) {
        provider.loadNotifications();
      }
    });
  }

  void _initializeAnimations() {
    _fadeController = AnimationController(
      duration: const Duration(milliseconds: 300),
      vsync: this,
    );

    _slideController = AnimationController(
      duration: const Duration(milliseconds: 400),
      vsync: this,
    );

    _fadeAnimation = Tween<double>(
      begin: 0.0,
      end: 1.0,
    ).animate(CurvedAnimation(
      parent: _fadeController,
      curve: Curves.easeInOut,
    ));

    _slideAnimation = Tween<Offset>(
      begin: const Offset(-1.0, 0.0),
      end: Offset.zero,
    ).animate(CurvedAnimation(
      parent: _slideController,
      curve: Curves.elasticOut,
    ));

    _fadeController.forward();
  }

  @override
  void dispose() {
    _fadeController.dispose();
    _slideController.dispose();
    super.dispose();
  }

  List<Map<String, dynamic>> _getFilteredNotifications(
      List<NotificationModel> notifications) {
    var filtered = notifications
        .map((n) => {
              'id': n.id,
              'type': n.type,
              'priority': n.priority,
              'title': n.title,
              'message': n.message,
              'timestamp': n.createdAt.toIso8601String(),
              'isRead': n.isRead,
            })
        .toList();

    if (widget.showOnlyHighPriority) {
      filtered = filtered.where((notification) {
        final priority = notification['priority'] as String? ?? 'low';
        return priority == 'high' || priority == 'critical';
      }).toList();
    }

    return filtered.take(widget.maxNotifications).toList();
  }

  @override
  Widget build(BuildContext context) {
    // Use provider for notifications state
    final provider = context.watch<NotificationsProvider>();
    final filteredNotifications =
        _getFilteredNotifications(provider.notifications);

    if (filteredNotifications.isEmpty && !provider.isLoading) {
      return const SizedBox.shrink();
    }

    return FadeTransition(
      opacity: _fadeAnimation,
      child: Card(
        elevation: 3,
        margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        child: Container(
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(16),
            gradient: LinearGradient(
              colors: [
                AppColors.deepBlue,
                AppColors.deepBlueLight.withValues(alpha: 0.9),
              ],
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
            ),
          ),
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Header
                Row(
                  children: [
                    Container(
                      padding: const EdgeInsets.all(8),
                      decoration: BoxDecoration(
                        color: Colors.white.withValues(alpha: 0.2),
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: const Icon(
                        Icons.notifications_active,
                        color: Colors.white,
                        size: 20,
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Text(
                            'Smart Insights',
                            style: TextStyle(
                              fontFamily: AppTypography.fontHeading,
                              fontWeight: FontWeight.bold,
                              fontSize: 16,
                              color: Colors.white,
                            ),
                          ),
                          Text(
                            '${filteredNotifications.length} notification${filteredNotifications.length != 1 ? 's' : ''}',
                            style: TextStyle(
                              fontFamily: AppTypography.fontBody,
                              fontSize: 12,
                              color: Colors.white.withValues(alpha: 0.7),
                            ),
                          ),
                        ],
                      ),
                    ),
                    if (filteredNotifications.length > 1)
                      GestureDetector(
                        onTap: () {
                          setState(() {
                            _isExpanded = !_isExpanded;
                          });
                        },
                        child: Container(
                          padding: const EdgeInsets.all(4),
                          child: Icon(
                            _isExpanded ? Icons.expand_less : Icons.expand_more,
                            color: Colors.white.withValues(alpha: 0.7),
                            size: 20,
                          ),
                        ),
                      ),
                  ],
                ),

                const SizedBox(height: 16),

                // Notifications List
                AnimatedContainer(
                  duration: const Duration(milliseconds: 300),
                  height: _isExpanded
                      ? (filteredNotifications.length * 70.0).clamp(0, 350)
                      : 70,
                  child: ListView.builder(
                    physics: _isExpanded
                        ? null
                        : const NeverScrollableScrollPhysics(),
                    itemCount: _isExpanded ? filteredNotifications.length : 1,
                    itemBuilder: (context, index) {
                      final notification = filteredNotifications[index];
                      return SlideTransition(
                        position: _slideAnimation,
                        child: _buildNotificationItem(notification, index == 0),
                      );
                    },
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildNotificationItem(
      Map<String, dynamic> notification, bool isFirst) {
    final type = notification['type'] as String? ?? 'info';
    final title = notification['title'] as String? ?? '';
    final message = notification['message'] as String? ?? '';
    final priority = notification['priority'] as String? ?? 'medium';
    final timestamp = notification['timestamp'] as String?;

    final notificationInfo = _getNotificationInfo(type, priority);

    return Container(
      margin: EdgeInsets.only(bottom: isFirst ? 0 : 8),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: notificationInfo.color.withValues(alpha: 0.3),
          width: 1,
        ),
      ),
      child: InkWell(
        onTap: widget.onNotificationTap,
        borderRadius: BorderRadius.circular(12),
        child: Row(
          children: [
            // Priority Indicator
            Container(
              width: 4,
              height: 40,
              decoration: BoxDecoration(
                color: notificationInfo.color,
                borderRadius: BorderRadius.circular(2),
              ),
            ),

            const SizedBox(width: 12),

            // Icon
            Container(
              padding: const EdgeInsets.all(6),
              decoration: BoxDecoration(
                color: notificationInfo.color.withValues(alpha: 0.2),
                borderRadius: BorderRadius.circular(6),
              ),
              child: Icon(
                notificationInfo.icon,
                color: notificationInfo.color,
                size: 16,
              ),
            ),

            const SizedBox(width: 12),

            // Content
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    title,
                    style: TextStyle(
                      fontFamily: AppTypography.fontHeading,
                      fontWeight: FontWeight.w600,
                      fontSize: 13,
                      color: Colors.white.withValues(alpha: 0.95),
                    ),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                  if (message.isNotEmpty) ...[
                    const SizedBox(height: 2),
                    Text(
                      message,
                      style: TextStyle(
                        fontFamily: AppTypography.fontBody,
                        fontSize: 11,
                        color: Colors.white.withValues(alpha: 0.7),
                      ),
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ],
                ],
              ),
            ),

            // Timestamp
            if (timestamp != null) ...[
              const SizedBox(width: 8),
              Column(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  Text(
                    _formatTimestamp(timestamp),
                    style: TextStyle(
                      fontFamily: AppTypography.fontBody,
                      fontSize: 10,
                      color: Colors.white.withValues(alpha: 0.5),
                    ),
                  ),
                  const SizedBox(height: 4),
                  Container(
                    padding:
                        const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                    decoration: BoxDecoration(
                      color: notificationInfo.color.withValues(alpha: 0.3),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Text(
                      priority.toUpperCase(),
                      style: TextStyle(
                        fontFamily: AppTypography.fontBody,
                        fontSize: 8,
                        color: notificationInfo.color,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ),
                ],
              ),
            ],
          ],
        ),
      ),
    );
  }

  NotificationInfo _getNotificationInfo(String type, String priority) {
    // Determine color and icon based on type and priority
    switch (type) {
      case 'alert':
        return NotificationInfo(
          color: Colors.red.shade300,
          icon: Icons.warning,
        );
      case 'warning':
        return NotificationInfo(
          color: Colors.orange.shade300,
          icon: Icons.info,
        );
      case 'tip':
        return NotificationInfo(
          color: Colors.blue.shade300,
          icon: Icons.lightbulb,
        );
      case 'achievement':
        return NotificationInfo(
          color: Colors.green.shade300,
          icon: Icons.celebration,
        );
      case 'reminder':
        return NotificationInfo(
          color: Colors.purple.shade300,
          icon: Icons.schedule,
        );
      default:
        // Adjust based on priority
        switch (priority) {
          case 'high':
          case 'critical':
            return NotificationInfo(
              color: Colors.red.shade300,
              icon: Icons.priority_high,
            );
          case 'medium':
            return NotificationInfo(
              color: Colors.yellow.shade300,
              icon: Icons.notifications,
            );
          default:
            return NotificationInfo(
              color: Colors.grey.shade300,
              icon: Icons.info_outline,
            );
        }
    }
  }

  String _formatTimestamp(String timestamp) {
    try {
      final dateTime = DateTime.parse(timestamp);
      final now = DateTime.now();
      final difference = now.difference(dateTime);

      if (difference.inMinutes < 60) {
        return '${difference.inMinutes}m';
      } else if (difference.inHours < 24) {
        return '${difference.inHours}h';
      } else if (difference.inDays < 7) {
        return '${difference.inDays}d';
      } else {
        return '${(difference.inDays / 7).floor()}w';
      }
    } catch (e) {
      return 'now';
    }
  }
}

class NotificationInfo {
  final Color color;
  final IconData icon;

  NotificationInfo({
    required this.color,
    required this.icon,
  });
}

/// Compact version of intelligent notifications for dashboard widgets
class CompactIntelligentNotifications extends StatelessWidget {
  final AdvancedFinancialEngine financialEngine;
  final VoidCallback? onTap;

  const CompactIntelligentNotifications({
    super.key,
    required this.financialEngine,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: financialEngine,
      builder: (context, child) {
        // FUTURE FEATURE: Intelligent notifications backend integration
        // This will be connected to AI-powered notification service in a future release
        final notifications = <Map<String, dynamic>>[];

        if (notifications.isEmpty) {
          return const SizedBox.shrink();
        }

        final highPriorityCount = notifications.where((n) {
          final priority = n['priority'] as String? ?? 'low';
          return priority == 'high' || priority == 'critical';
        }).length;

        return GestureDetector(
          onTap: onTap,
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            decoration: BoxDecoration(
              color: highPriorityCount > 0
                  ? Colors.red.shade50
                  : Colors.blue.shade50,
              borderRadius: BorderRadius.circular(20),
              border: Border.all(
                color: highPriorityCount > 0
                    ? Colors.red.shade200
                    : Colors.blue.shade200,
              ),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(
                  highPriorityCount > 0
                      ? Icons.warning
                      : Icons.notifications_active,
                  size: 16,
                  color: highPriorityCount > 0
                      ? Colors.red.shade600
                      : Colors.blue.shade600,
                ),
                const SizedBox(width: 6),
                Text(
                  '${notifications.length} insight${notifications.length != 1 ? 's' : ''}',
                  style: TextStyle(
                    fontFamily: AppTypography.fontBody,
                    fontSize: 12,
                    fontWeight: FontWeight.w600,
                    color: highPriorityCount > 0
                        ? Colors.red.shade700
                        : Colors.blue.shade700,
                  ),
                ),
                if (highPriorityCount > 0) ...[
                  const SizedBox(width: 4),
                  Container(
                    padding:
                        const EdgeInsets.symmetric(horizontal: 4, vertical: 1),
                    decoration: BoxDecoration(
                      color: Colors.red.shade600,
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Text(
                      highPriorityCount.toString(),
                      style: const TextStyle(
                        fontFamily: AppTypography.fontBody,
                        fontSize: 10,
                        fontWeight: FontWeight.w600,
                        color: Colors.white,
                      ),
                    ),
                  ),
                ],
              ],
            ),
          ),
        );
      },
    );
  }
}
