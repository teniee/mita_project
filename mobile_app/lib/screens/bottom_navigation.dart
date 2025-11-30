import 'dart:developer' as dev;
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import '../theme/app_colors.dart';
import '../theme/app_typography.dart';
import 'dart:async';
import '../services/expense_state_service.dart';
import '../services/logging_service.dart';
import 'main_screen.dart';
import 'calendar_screen.dart';
import 'goals_screen.dart';
import 'insights_screen.dart';
import 'habits_screen.dart';
import 'mood_screen.dart';

class BottomNavigation extends StatefulWidget {
  const BottomNavigation({super.key});

  @override
  State<BottomNavigation> createState() => _BottomNavigationState();
}

class _BottomNavigationState extends State<BottomNavigation> with TickerProviderStateMixin {
  int _currentIndex = 0;
  final ExpenseStateService _expenseStateService = ExpenseStateService();
  StreamSubscription<Map<String, dynamic>>? _expenseAddedSubscription;
  late AnimationController _navigationAnimationController;
  late Animation<double> _navigationAnimation;
  late AnimationController _tabSwitchController;
  late Animation<double> _tabSwitchAnimation;
  late AnimationController _pulseController;
  late Animation<double> _pulseAnimation;

  // Keep screen instances to maintain state
  late final List<Widget> _screens = [
    const MainScreen(),
    const CalendarScreen(),
    const GoalsScreen(),
    const InsightsScreen(),
    const HabitsScreen(),
    const MoodScreen(),
  ];

  @override
  void initState() {
    super.initState();
    if (kDebugMode) dev.log('BottomNavigation initState called', name: 'BottomNavigation');
    _initializeAnimations();
    _subscribeToExpenseUpdates();
    if (kDebugMode) dev.log('BottomNavigation initState completed', name: 'BottomNavigation');
  }

  void _initializeAnimations() {
    _navigationAnimationController = AnimationController(
      duration: const Duration(milliseconds: 300),
      vsync: this,
    );
    _navigationAnimation = Tween<double>(
      begin: 0.0,
      end: 1.0,
    ).animate(CurvedAnimation(
      parent: _navigationAnimationController,
      curve: Curves.easeInOut,
    ));

    _tabSwitchController = AnimationController(
      duration: const Duration(milliseconds: 400),
      vsync: this,
    );
    _tabSwitchAnimation = Tween<double>(
      begin: 0.0,
      end: 1.0,
    ).animate(CurvedAnimation(
      parent: _tabSwitchController,
      curve: Curves.easeOutCubic,
    ));

    _pulseController = AnimationController(
      duration: const Duration(milliseconds: 1200),
      vsync: this,
    );
    _pulseAnimation = Tween<double>(
      begin: 1.0,
      end: 1.2,
    ).animate(CurvedAnimation(
      parent: _pulseController,
      curve: Curves.easeInOut,
    ));
  }

  void _subscribeToExpenseUpdates() {
    // Listen for expense additions to provide navigation feedback
    _expenseAddedSubscription = _expenseStateService.expenseAdded.listen(
      (expenseData) {
        // Animate navigation bar to indicate update
        _navigationAnimationController.forward().then((_) {
          _navigationAnimationController.reverse();
        });

        // Pulse the current tab if it's relevant to the update
        if (_currentIndex == 0 || _currentIndex == 1) {
          // Main or Calendar
          _pulseController.forward().then((_) {
            _pulseController.reverse();
          });
        }

        logDebug('Navigation received expense update', tag: 'BOTTOM_NAV', extra: {
          'currentIndex': _currentIndex,
          'expenseAmount': expenseData['amount'],
        });
      },
    );
  }

  @override
  void dispose() {
    _expenseAddedSubscription?.cancel();
    _navigationAnimationController.dispose();
    _tabSwitchController.dispose();
    _pulseController.dispose();
    super.dispose();
  }

  final List<BottomNavigationBarItem> _items = const [
    BottomNavigationBarItem(
      icon: Icon(Icons.home),
      label: 'Home',
    ),
    BottomNavigationBarItem(
      icon: Icon(Icons.calendar_today),
      label: 'Calendar',
    ),
    BottomNavigationBarItem(
      icon: Icon(Icons.flag),
      label: 'Goals',
    ),
    BottomNavigationBarItem(
      icon: Icon(Icons.bar_chart),
      label: 'Insights',
    ),
    BottomNavigationBarItem(
      icon: Icon(Icons.check_circle),
      label: 'Habits',
    ),
    BottomNavigationBarItem(
      icon: Icon(Icons.mood),
      label: 'Mood',
    ),
  ];

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;

    return Scaffold(
      body: IndexedStack(
        index: _currentIndex,
        children: _screens,
      ),
      bottomNavigationBar: Container(
        decoration: BoxDecoration(
          color: colorScheme.surface,
          boxShadow: [
            BoxShadow(
              color: colorScheme.primary.withValues(alpha: 0.08),
              blurRadius: 12,
              offset: const Offset(0, -1),
              spreadRadius: 0,
            ),
            BoxShadow(
              color: Colors.black.withValues(alpha: 0.03),
              blurRadius: 24,
              offset: const Offset(0, -4),
              spreadRadius: 0,
            ),
          ],
        ),
        child: SafeArea(
          child: AnimatedBuilder(
            animation: _navigationAnimation,
            builder: (context, child) {
              return Transform.translate(
                offset: Offset(0, _navigationAnimation.value * 2),
                child: BottomNavigationBar(
                  currentIndex: _currentIndex,
                  onTap: _onNavigationTap,
                  selectedItemColor: colorScheme.primary,
                  unselectedItemColor: colorScheme.onSurfaceVariant,
                  backgroundColor: Colors.transparent,
                  elevation: 0,
                  type: BottomNavigationBarType.fixed,
                  enableFeedback: true,
                  selectedLabelStyle: TextStyle(
                    fontFamily: AppTypography.fontHeading,
                    fontWeight: FontWeight.w600,
                    fontSize: 11,
                    color: colorScheme.primary,
                  ),
                  unselectedLabelStyle: TextStyle(
                    fontFamily: AppTypography.fontBody,
                    fontWeight: FontWeight.w400,
                    fontSize: 10,
                    color: colorScheme.onSurfaceVariant,
                  ),
                  selectedIconTheme: IconThemeData(
                    color: colorScheme.primary,
                    size: 24,
                  ),
                  unselectedIconTheme: IconThemeData(
                    color: colorScheme.onSurfaceVariant,
                    size: 22,
                  ),
                  items: _items.map((item) {
                    final index = _items.indexOf(item);
                    final isSelected = _currentIndex == index;

                    return BottomNavigationBarItem(
                      icon: AnimatedBuilder(
                        animation: _pulseAnimation,
                        builder: (context, child) {
                          final scale = isSelected && (_currentIndex == 0 || _currentIndex == 1)
                              ? _pulseAnimation.value
                              : 1.0;

                          return AnimatedBuilder(
                            animation: _tabSwitchAnimation,
                            builder: (context, child) {
                              return Transform.scale(
                                scale: scale * (1.0 + (_tabSwitchAnimation.value * 0.1)),
                                child: Container(
                                  padding: const EdgeInsets.symmetric(vertical: 4),
                                  decoration: isSelected
                                      ? BoxDecoration(
                                          borderRadius: BorderRadius.circular(12),
                                          color:
                                              colorScheme.primaryContainer.withValues(alpha: 0.1),
                                        )
                                      : null,
                                  child: Icon(
                                    (item.icon as Icon).icon,
                                    size: isSelected ? 26 : 22,
                                    color: isSelected
                                        ? colorScheme.primary
                                        : colorScheme.onSurfaceVariant,
                                  ),
                                ),
                              );
                            },
                          );
                        },
                      ),
                      label: item.label,
                      tooltip: item.label,
                    );
                  }).toList(),
                ),
              );
            },
          ),
        ),
      ),
    );
  }

  void _onNavigationTap(int index) {
    if (index == _currentIndex) {
      // Double tap on current tab - refresh if it's calendar or main screen
      if (index == 0 || index == 1) {
        _handleScreenRefresh(index);
      }
      return;
    }

    // Animate tab switch
    _tabSwitchController.forward().then((_) {
      _tabSwitchController.reverse();
    });

    setState(() {
      _currentIndex = index;
    });

    // Log navigation for analytics
    logDebug('Navigation tab changed', tag: 'BOTTOM_NAV', extra: {
      'previousIndex': _currentIndex,
      'newIndex': index,
      'screenName': _getScreenName(index),
    });

    // If navigating to calendar screen, ensure it has the latest data
    if (index == 1) {
      _ensureCalendarDataFreshness();
    }
  }

  String _getScreenName(int index) {
    switch (index) {
      case 0:
        return 'Main';
      case 1:
        return 'Calendar';
      case 2:
        return 'Goals';
      case 3:
        return 'Insights';
      case 4:
        return 'Habits';
      case 5:
        return 'Mood';
      default:
        return 'Unknown';
    }
  }

  void _handleScreenRefresh(int index) {
    logDebug('Double tap refresh requested', tag: 'BOTTOM_NAV', extra: {
      'screenIndex': index,
      'screenName': _getScreenName(index),
    });

    // Trigger refresh on expense state service
    _expenseStateService.refreshCalendarData();

    // Show feedback
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Row(
          children: [
            const SizedBox(
              width: 16,
              height: 16,
              child: CircularProgressIndicator(
                strokeWidth: 2,
                valueColor: AlwaysStoppedAnimation<Color>(Colors.white),
              ),
            ),
            const SizedBox(width: 12),
            Text(
              'Refreshing ${_getScreenName(index)}...',
              style: const TextStyle(
                fontFamily: AppTypography.fontBody,
                fontSize: 14,
              ),
            ),
          ],
        ),
        duration: const Duration(seconds: 1),
        behavior: SnackBarBehavior.floating,
        backgroundColor: AppColors.textPrimary,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(8),
        ),
      ),
    );
  }

  void _ensureCalendarDataFreshness() {
    // Check if calendar data is stale (older than 20 seconds)
    final timeSinceUpdate = DateTime.now().difference(_expenseStateService.lastUpdated);

    if (timeSinceUpdate.inSeconds > 20) {
      // Reduced for fast backend
      logDebug('Calendar data is stale, triggering refresh', tag: 'BOTTOM_NAV', extra: {
        'timeSinceUpdate': timeSinceUpdate.inSeconds,
      });

      // Trigger a gentle refresh
      Timer(const Duration(milliseconds: 500), () {
        _expenseStateService.refreshCalendarData();
      });
    }
  }
}
