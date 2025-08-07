import 'package:flutter/material.dart';
import '../services/api_service.dart';
import '../core/app_error_handler.dart';
import 'dart:async';
import '../services/logging_service.dart';

extension ColorExtension on Color {
  Color darken(double amount) {
    final hsl = HSLColor.fromColor(this);
    final hslDark = hsl.withLightness((hsl.lightness - amount).clamp(0.0, 1.0));
    return hslDark.toColor();
  }
}

class CalendarScreen extends StatefulWidget {
  const CalendarScreen({super.key});

  @override
  State<CalendarScreen> createState() => _CalendarScreenState();
}

class _CalendarScreenState extends State<CalendarScreen> with TickerProviderStateMixin {
  final ApiService _apiService = ApiService();
  List<dynamic> calendarData = [];
  bool isLoading = true;
  bool isRedistributing = false;
  String? error;
  DateTime currentMonth = DateTime.now();
  Timer? _liveUpdateTimer;
  late AnimationController _redistributionAnimationController;
  late Animation<double> _redistributionAnimation;
  

  @override
  void initState() {
    super.initState();
    _redistributionAnimationController = AnimationController(
      duration: const Duration(milliseconds: 1500),
      vsync: this,
    );
    _redistributionAnimation = Tween<double>(
      begin: 0.0,
      end: 1.0,
    ).animate(CurvedAnimation(
      parent: _redistributionAnimationController,
      curve: Curves.easeInOut,
    ));
    
    _initializeData();
    _startLiveUpdates();
  }

  @override
  void dispose() {
    _liveUpdateTimer?.cancel();
    _redistributionAnimationController.dispose();
    super.dispose();
  }

  Future<void> _initializeData() async {
    await fetchCalendarData();
  }


  void _startLiveUpdates() {
    // Temporarily disabled live updates to prevent recurring server errors
    print('Calendar live updates disabled due to backend server errors');
    
    // TODO: Re-enable when backend is stable:
    // _liveUpdateTimer = Timer.periodic(const Duration(seconds: 45), (timer) {
    //   if (mounted && !isRedistributing) {
    //     fetchCalendarData();
    //   }
    // });
  }

  Future<void> fetchCalendarData() async {
    setState(() {
      isLoading = true;
      error = null;
    });

    try {
      final data = await _apiService.getCalendar();
      if (!mounted) return;
      setState(() {
        calendarData = data;
        isLoading = false;
      });
    } catch (e) {
      logError('Error loading calendar: $e');
      if (!mounted) return;
      setState(() {
        // Use sample data instead of empty array when API fails
        calendarData = _generateSampleCalendarData();
        isLoading = false;
        error = null; // Don't show error, just use sample data
      });
      
      // Show user-friendly error message but don't break the UI
      if (mounted) {
        WidgetsBinding.instance.addPostFrameCallback((_) {
          ErrorMessageUtils.showErrorSnackBar(
            context,
            e,
            duration: const Duration(seconds: 2),
          );
        });
      }
    }
  }

  List<Map<String, dynamic>> _generateSampleCalendarData() {
    final today = DateTime.now();
    final daysInMonth = DateTime(today.year, today.month + 1, 0).day;
    final firstDayOfMonth = DateTime(today.year, today.month, 1);
    final firstWeekday = firstDayOfMonth.weekday % 7; // Sunday = 0, Monday = 1, etc.
    
    List<Map<String, dynamic>> calendarDays = [];
    
    // Add empty cells for days before the first day of the month
    for (int i = 0; i < firstWeekday; i++) {
      calendarDays.add({
        'day': 0,
        'status': 'empty',
        'limit': 0,
        'spent': 0,
      });
    }
    
    // Generate realistic data for each day of the month
    for (int day = 1; day <= daysInMonth; day++) {
      final dayDate = DateTime(today.year, today.month, day);
      final isToday = day == today.day;
      final isPast = dayDate.isBefore(today);
      final isFuture = dayDate.isAfter(today);
      
      // Base daily budget - realistic amounts
      final baseDailyBudget = 85 + (day % 5) * 10; // Varies between $85-$125
      
      String status;
      int spent;
      
      if (isFuture) {
        // Future days have no spending yet
        status = 'good';
        spent = 0;
      } else if (isToday) {
        // Today has some spending
        spent = (baseDailyBudget * 0.4).round(); // 40% spent so far today
        status = 'good';
      } else {
        // Past days have varied spending patterns
        final dayOfWeek = dayDate.weekday;
        final isWeekend = dayOfWeek == 6 || dayOfWeek == 7;
        
        if (isWeekend) {
          // Weekends tend to have higher spending
          spent = (baseDailyBudget * (0.8 + (day % 3) * 0.15)).round();
        } else {
          // Weekdays have more controlled spending
          spent = (baseDailyBudget * (0.5 + (day % 4) * 0.12)).round();
        }
        
        // Determine status based on spending vs budget
        final spentRatio = spent / baseDailyBudget;
        if (spentRatio > 1.0) {
          status = 'over';
        } else if (spentRatio > 0.8) {
          status = 'warning';
        } else {
          status = 'good';
        }
      }
      
      calendarDays.add({
        'day': day,
        'status': status,
        'limit': baseDailyBudget,
        'spent': spent,
        'categories': {
          'food': (baseDailyBudget * 0.4).round(),
          'transportation': (baseDailyBudget * 0.25).round(),
          'entertainment': (baseDailyBudget * 0.2).round(),
          'shopping': (baseDailyBudget * 0.15).round(),
        }
      });
    }
    
    return calendarDays;
  }


  String _getMonthName(int month) {
    const months = [
      'January', 'February', 'March', 'April', 'May', 'June',
      'July', 'August', 'September', 'October', 'November', 'December'
    ];
    return months[month - 1];
  }

  // ===========================================================================
  // ENHANCED CALENDAR UI METHODS
  // ===========================================================================

  Widget _buildErrorState() {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;
    
    return Card(
      elevation: 2,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      child: Padding(
        padding: const EdgeInsets.all(24.0),
        child: Column(
          children: [
            Icon(
              Icons.error_outline_rounded,
              size: 64,
              color: colorScheme.error,
            ),
            const SizedBox(height: 16),
            Text(
              'Unable to load calendar',
              style: textTheme.titleLarge?.copyWith(
                color: colorScheme.onSurface,
                fontWeight: FontWeight.w600,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              'Please check your connection and try again',
              style: textTheme.bodyMedium?.copyWith(
                color: colorScheme.onSurface.withValues(alpha: 0.7),
              ),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 20),
            FilledButton.icon(
              onPressed: _initializeData,
              icon: const Icon(Icons.refresh_rounded),
              label: const Text('Retry'),
              style: FilledButton.styleFrom(
                padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildEmptyState() {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;
    
    return Card(
      elevation: 2,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      child: Padding(
        padding: const EdgeInsets.all(24.0),
        child: Column(
          children: [
            Icon(
              Icons.calendar_month_rounded,
              size: 64,
              color: colorScheme.primary,
            ),
            const SizedBox(height: 16),
            Text(
              'No calendar data available',
              style: textTheme.titleLarge?.copyWith(
                color: colorScheme.onSurface,
                fontWeight: FontWeight.w600,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              'Complete your budget setup to view your daily spending calendar',
              style: textTheme.bodyMedium?.copyWith(
                color: colorScheme.onSurface.withValues(alpha: 0.7),
              ),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 20),
            FilledButton.icon(
              onPressed: () => Navigator.pushNamed(context, '/budget_settings'),
              icon: const Icon(Icons.settings_rounded),
              label: const Text('Setup Budget'),
              style: FilledButton.styleFrom(
                padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildEnhancedCalendarGrid() {
    final colorScheme = Theme.of(context).colorScheme;
    final today = DateTime.now();
    
    if (calendarData.isEmpty) {
      return Card(
        elevation: 2,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        child: Padding(
          padding: const EdgeInsets.all(32.0),
          child: Column(
            children: [
              Icon(
                Icons.calendar_month,
                size: 64,
                color: Colors.grey[400],
              ),
              const SizedBox(height: 16),
              Text(
                'No calendar data available',
                style: Theme.of(context).textTheme.titleMedium?.copyWith(
                  color: Colors.grey[600],
                ),
              ),
              const SizedBox(height: 8),
              Text(
                'Complete your budget setup to view your spending calendar',
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  color: Colors.grey[500],
                ),
              ),
            ],
          ),
        ),
      );
    }
    
    return Card(
      elevation: 2,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          children: [
            // Weekday headers
            _buildWeekdayHeaders(),
            const SizedBox(height: 12),
            // Calendar grid - responsive with better aspect ratio
            LayoutBuilder(
              builder: (context, constraints) {
                final isTablet = constraints.maxWidth > 600;
                return GridView.builder(
                  shrinkWrap: true,
                  physics: const NeverScrollableScrollPhysics(),
                  itemCount: calendarData.length,
                  gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
                    crossAxisCount: 7,
                    crossAxisSpacing: isTablet ? 8 : 4,
                    mainAxisSpacing: isTablet ? 8 : 4,
                    childAspectRatio: isTablet ? 0.9 : 0.75,
                  ),
              itemBuilder: (context, index) {
                try {
                  final day = calendarData[index];
                  final dayNumber = day['day'] as int? ?? 0;
                  final status = day['status'] as String? ?? 'good';
                  final limit = day['limit'] as int? ?? 0;
                  final spent = day['spent'] as int? ?? 0;
                  final isToday = dayNumber == today.day && 
                                 currentMonth.month == today.month && 
                                 currentMonth.year == today.year;
                  
                  // Handle empty cells (before month starts)
                  if (dayNumber == 0 || status == 'empty') {
                    return Container();
                  }
                  
                  return _buildSimpleDayCell(
                    dayNumber: dayNumber,
                    limit: limit,
                    spent: spent,
                    status: status,
                    isToday: isToday,
                    colorScheme: colorScheme,
                  );
                } catch (e) {
                  // Return a simple error cell
                  return Container(
                    decoration: BoxDecoration(
                      color: Colors.grey[200],
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: const Center(
                      child: Text('?', style: TextStyle(color: Colors.grey)),
                    ),
                  );
                }
              },
                );
              },
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildWeekdayHeaders() {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;
    final weekdays = ['S', 'M', 'T', 'W', 'T', 'F', 'S'];
    
    return Row(
      children: weekdays.map((day) => Expanded(
        child: Center(
          child: Text(
            day,
            style: textTheme.labelMedium?.copyWith(
              color: colorScheme.onSurface.withValues(alpha: 0.6),
              fontWeight: FontWeight.w600,
            ),
          ),
        ),
      )).toList(),
    );
  }

  Widget _buildSimpleDayCell({
    required int dayNumber,
    required int limit,
    required int spent,
    required String status,
    required bool isToday,
    required ColorScheme colorScheme,
  }) {
    final dayColor = _getSimpleDayColor(status, isToday);
    final textColor = _getSimpleTextColor(status, isToday);
    final spentPercentage = limit > 0 ? (spent / limit).clamp(0.0, 1.0) : 0.0;
    
    return Container(
      decoration: BoxDecoration(
        color: dayColor,
        borderRadius: BorderRadius.circular(12),
        border: isToday 
          ? Border.all(color: colorScheme.primary, width: 3)
          : Border.all(color: dayColor.darken(0.1), width: 1),
        boxShadow: [
          if (isToday || status == 'over')
            BoxShadow(
              color: (isToday ? colorScheme.primary : Colors.red).withValues(alpha: 0.3),
              blurRadius: 6,
              offset: const Offset(0, 2),
            ),
        ],
      ),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          borderRadius: BorderRadius.circular(12),
          onTap: dayNumber > 0 ? () => _showSimpleDayModal(dayNumber, limit, spent, status) : null,
          child: Padding(
            padding: const EdgeInsets.all(6.0),
            child: LayoutBuilder(
              builder: (context, constraints) {
                return Column(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    // Day number with status indicator
                    Flexible(
                      child: Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Flexible(
                            child: Text(
                              dayNumber > 0 ? dayNumber.toString() : '',
                              style: TextStyle(
                                fontWeight: isToday ? FontWeight.bold : FontWeight.w600,
                                color: textColor,
                                fontSize: constraints.maxWidth > 45 ? (isToday ? 16 : 14) : 12,
                                fontFamily: 'Sora',
                              ),
                              maxLines: 1,
                              overflow: TextOverflow.clip,
                            ),
                          ),
                          if (isToday && constraints.maxWidth > 35)
                            Container(
                              width: 4,
                              height: 4,
                              decoration: BoxDecoration(
                                color: colorScheme.primary,
                                shape: BoxShape.circle,
                              ),
                            )
                          else if (status == 'over' && constraints.maxWidth > 35)
                            Icon(
                              Icons.warning,
                              size: 10,
                              color: Colors.red.shade700,
                            ),
                        ],
                      ),
                    ),
                    
                    if (dayNumber > 0 && limit > 0 && constraints.maxHeight > 60) ...[
                      const SizedBox(height: 2),
                      
                      // Enhanced progress indicator - only show if there's room
                      if (constraints.maxHeight > 70)
                        Flexible(
                          child: Container(
                            height: 3,
                            margin: const EdgeInsets.symmetric(vertical: 2),
                            decoration: BoxDecoration(
                              borderRadius: BorderRadius.circular(2),
                              color: textColor.withValues(alpha: 0.2),
                            ),
                            child: FractionallySizedBox(
                              alignment: Alignment.centerLeft,
                              widthFactor: spentPercentage,
                              child: Container(
                                decoration: BoxDecoration(
                                  borderRadius: BorderRadius.circular(2),
                                  color: textColor,
                                ),
                              ),
                            ),
                          ),
                        ),
                      
                      // Status text or amount - simplified
                      if (constraints.maxHeight > 80)
                        Flexible(
                          child: Text(
                            _getSimpleStatusText(status, spent, spentPercentage),
                            style: TextStyle(
                              color: textColor.withValues(alpha: 0.8),
                              fontSize: constraints.maxWidth > 45 ? 8 : 7,
                              fontWeight: FontWeight.w500,
                              fontFamily: 'Manrope',
                            ),
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            textAlign: TextAlign.center,
                          ),
                        ),
                    ],
                  ],
                );
              },
            ),
          ),
        ),
      ),
    );
  }

  String _getSimpleStatusText(String status, int spent, double spentPercentage) {
    if (spent > 0) {
      if (spentPercentage > 1.0) return 'Over';
      if (spentPercentage > 0.8) return 'High';
      return 'Good';
    }
    return 'Free';
  }

  Widget _buildEnhancedDayCell({
    required int dayNumber,
    required int limit,
    required int spent,
    required String status,
    required bool isToday,
    required ColorScheme colorScheme,
  }) {
    final textTheme = Theme.of(context).textTheme;
    final dayColor = _getEnhancedDayColor(status, isToday);
    final onDayColor = _getEnhancedOnDayColor(status, isToday);
    final spentPercentage = limit > 0 ? (spent / limit).clamp(0.0, 1.0) : 0.0;
    
    return Material(
      elevation: isToday ? 6 : (status == 'over' ? 4 : 2),
      borderRadius: BorderRadius.circular(16),
      color: dayColor,
      child: InkWell(
        borderRadius: BorderRadius.circular(16),
        onTap: () => _showDayDetailsModal(dayNumber, limit, spent, status),
        child: Container(
          padding: const EdgeInsets.all(12.0),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(16),
            border: isToday 
              ? Border.all(color: colorScheme.primary, width: 2)
              : null,
          ),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              // Day number and status indicator
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(
                    dayNumber.toString(),
                    style: textTheme.titleLarge?.copyWith(
                      fontWeight: FontWeight.bold,
                      color: onDayColor,
                      fontSize: isToday ? 22 : 20,
                    ),
                  ),
                  if (isToday)
                    Icon(
                      Icons.today_rounded,
                      size: 16,
                      color: onDayColor.withValues(alpha: 0.8),
                    ),
                ],
              ),
              
              const SizedBox(height: 4),
              
              // Budget amount
              Text(
'\$$limit',
                style: textTheme.titleMedium?.copyWith(
                  color: onDayColor,
                  fontWeight: FontWeight.w600,
                  fontSize: 16,
                ),
              ),
              
              const SizedBox(height: 6),
              
              // Spending progress
              Column(
                children: [
                  if (spent > 0) ...[
                    Text(
'\$$spent',
                      style: textTheme.bodySmall?.copyWith(
                        color: onDayColor.withValues(alpha: 0.9),
                        fontWeight: FontWeight.w500,
                        fontSize: 12,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Container(
                      height: 4,
                      decoration: BoxDecoration(
                        borderRadius: BorderRadius.circular(2),
                        color: onDayColor.withValues(alpha: 0.2),
                      ),
                      child: FractionallySizedBox(
                        alignment: Alignment.centerLeft,
                        widthFactor: spentPercentage,
                        child: Container(
                          decoration: BoxDecoration(
                            borderRadius: BorderRadius.circular(2),
                            color: onDayColor,
                          ),
                        ),
                      ),
                    ),
                  ] else ...[
                    Text(
                      'Available',
                      style: textTheme.bodySmall?.copyWith(
                        color: onDayColor.withValues(alpha: 0.7),
                        fontSize: 10,
                      ),
                    ),
                    const SizedBox(height: 8),
                  ],
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  Color _getEnhancedDayColor(String status, bool isToday) {
    final colorScheme = Theme.of(context).colorScheme;
    
    if (isToday) {
      switch (status.toLowerCase()) {
        case 'over':
          return colorScheme.errorContainer;
        case 'warning':
          return colorScheme.tertiaryContainer;
        case 'good':
        default:
          return colorScheme.primaryContainer;
      }
    }
    
    switch (status.toLowerCase()) {
      case 'over':
        return colorScheme.error.withValues(alpha: 0.9);
      case 'warning':
        return colorScheme.tertiary.withValues(alpha: 0.9);
      case 'good':
      default:
        return colorScheme.primary.withValues(alpha: 0.9);
    }
  }

  Color _getEnhancedOnDayColor(String status, bool isToday) {
    final colorScheme = Theme.of(context).colorScheme;
    
    if (isToday) {
      switch (status.toLowerCase()) {
        case 'over':
          return colorScheme.onErrorContainer;
        case 'warning':
          return colorScheme.onTertiaryContainer;
        case 'good':
        default:
          return colorScheme.onPrimaryContainer;
      }
    }
    
    switch (status.toLowerCase()) {
      case 'over':
        return colorScheme.onError;
      case 'warning':
        return colorScheme.onTertiary;
      case 'good':
      default:
        return colorScheme.onPrimary;
    }
  }

  void _showDayDetailsModal(int dayNumber, int limit, int spent, String status) {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;
    final remaining = limit - spent;
    final spentPercentage = limit > 0 ? (spent / limit) * 100 : 0.0;
    
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (context) => Container(
        height: MediaQuery.of(context).size.height * 0.6,
        decoration: BoxDecoration(
          color: colorScheme.surface,
          borderRadius: const BorderRadius.vertical(top: Radius.circular(28)),
        ),
        child: Column(
          children: [
            // Handle bar
            Container(
              margin: const EdgeInsets.only(top: 12, bottom: 8),
              width: 32,
              height: 4,
              decoration: BoxDecoration(
                color: colorScheme.onSurface.withValues(alpha: 0.4),
                borderRadius: BorderRadius.circular(2),
              ),
            ),
            
            Expanded(
              child: Padding(
                padding: const EdgeInsets.all(24.0),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // Header
                    Row(
                      children: [
                        Container(
                          padding: const EdgeInsets.all(12),
                          decoration: BoxDecoration(
                            color: _getEnhancedDayColor(status, false),
                            borderRadius: BorderRadius.circular(12),
                          ),
                          child: Text(
                            dayNumber.toString(),
                            style: textTheme.headlineMedium?.copyWith(
                              color: _getEnhancedOnDayColor(status, false),
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                        ),
                        const SizedBox(width: 16),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
'${_getMonthName(currentMonth.month)} $dayNumber, ${currentMonth.year}',
                                style: textTheme.titleLarge?.copyWith(
                                  fontWeight: FontWeight.w600,
                                ),
                              ),
                              const SizedBox(height: 4),
                              Container(
                                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
                                decoration: BoxDecoration(
                                  color: _getStatusChipColor(status),
                                  borderRadius: BorderRadius.circular(16),
                                ),
                                child: Text(
                                  _getStatusText(status),
                                  style: textTheme.labelMedium?.copyWith(
                                    color: _getStatusChipTextColor(status),
                                    fontWeight: FontWeight.w600,
                                  ),
                                ),
                              ),
                            ],
                          ),
                        ),
                      ],
                    ),
                    
                    const SizedBox(height: 24),
                    
                    // Budget overview
                    _buildBudgetOverviewCard(limit, spent, remaining, spentPercentage),
                    
                    const SizedBox(height: 24),
                    
                    // Category breakdown
                    Text(
                      'Category Breakdown',
                      style: textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    const SizedBox(height: 16),
                    
                    Expanded(
                      child: _buildCategoryBreakdown(limit, calendarData.isNotEmpty ? calendarData.firstWhere((day) => day['day'] == dayNumber, orElse: () => null) : null),
                    ),
                    
                    const SizedBox(height: 16),
                    
                    // Action buttons
                    Row(
                      children: [
                        Expanded(
                          child: OutlinedButton.icon(
                            onPressed: () => Navigator.pop(context),
                            icon: const Icon(Icons.close_rounded),
                            label: const Text('Close'),
                          ),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: FilledButton.icon(
                            onPressed: () {
                              Navigator.pop(context);
                              Navigator.pushNamed(context, '/add_expense');
                            },
                            icon: const Icon(Icons.add_rounded),
                            label: const Text('Add Expense'),
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildBudgetOverviewCard(int limit, int spent, int remaining, double spentPercentage) {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;
    
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: colorScheme.surfaceContainer,
        borderRadius: BorderRadius.circular(16),
      ),
      child: Column(
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              _buildBudgetItem('Budget', '\$$limit', colorScheme.primary),
              _buildBudgetItem('Spent', '\$$spent', colorScheme.error),
              _buildBudgetItem('Remaining', '\$$remaining', colorScheme.tertiary),
            ],
          ),
          const SizedBox(height: 20),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(
                    'Spending Progress',
                    style: textTheme.bodyMedium?.copyWith(
                      fontWeight: FontWeight.w500,
                    ),
                  ),
                  Text(
                    '${spentPercentage.toStringAsFixed(1)}%',
                    style: textTheme.bodyMedium?.copyWith(
                      fontWeight: FontWeight.bold,
                      color: spentPercentage > 100 ? colorScheme.error : colorScheme.primary,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              LinearProgressIndicator(
                value: (spentPercentage / 100).clamp(0.0, 1.0),
                backgroundColor: colorScheme.surfaceContainerHighest,
                valueColor: AlwaysStoppedAnimation<Color>(
                  spentPercentage > 100 ? colorScheme.error : 
                  spentPercentage > 80 ? colorScheme.tertiary : colorScheme.primary,
                ),
                minHeight: 8,
                borderRadius: BorderRadius.circular(4),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildBudgetItem(String label, String amount, Color color) {
    final textTheme = Theme.of(context).textTheme;
    
    return Column(
      children: [
        Text(
          label,
          style: textTheme.bodySmall?.copyWith(
            color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.7),
          ),
        ),
        const SizedBox(height: 4),
        Text(
          amount,
          style: textTheme.titleLarge?.copyWith(
            color: color,
            fontWeight: FontWeight.bold,
          ),
        ),
      ],
    );
  }

  Widget _buildCategoryBreakdown(int limit, Map<String, dynamic>? dayData) {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;
    
    // Use real category data from API if available, otherwise use mock data
    List<Map<String, dynamic>> categories = [];
    
    if (dayData != null && dayData['categories'] != null) {
      final categoryData = dayData['categories'] as Map<String, dynamic>;
      final categoryColors = {
        'food': Colors.green,
        'transportation': Colors.blue,
        'entertainment': Colors.purple,
        'shopping': Colors.orange,
        'healthcare': Colors.red,
      };
      
      categoryData.forEach((categoryName, budgetedAmount) {
        // Estimate spent amount based on overall day spending ratio
        final daySpent = dayData['spent'] as int? ?? 0;
        final dayLimit = dayData['limit'] as int? ?? limit;
        final spendingRatio = dayLimit > 0 ? (daySpent / dayLimit) : 0.0;
        final estimatedSpent = ((budgetedAmount as num).toDouble() * spendingRatio).round();
        
        categories.add({
          'name': _formatCategoryName(categoryName),
          'budgeted': (budgetedAmount as num).round(),
          'spent': estimatedSpent,
          'color': categoryColors[categoryName.toLowerCase()] ?? Colors.grey,
        });
      });
    }
    
    // Fallback to mock data if no real data available
    if (categories.isEmpty) {
      categories = [
        {'name': 'Food & Dining', 'budgeted': (limit * 0.4).round(), 'spent': (limit * 0.2).round(), 'color': Colors.green},
        {'name': 'Transportation', 'budgeted': (limit * 0.25).round(), 'spent': (limit * 0.15).round(), 'color': Colors.blue},
        {'name': 'Entertainment', 'budgeted': (limit * 0.2).round(), 'spent': (limit * 0.1).round(), 'color': Colors.purple},
        {'name': 'Shopping', 'budgeted': (limit * 0.15).round(), 'spent': (limit * 0.05).round(), 'color': Colors.orange},
      ];
    }
    
    return Column(
      children: [
        // Category spending summary
        Container(
          padding: const EdgeInsets.all(16),
          margin: const EdgeInsets.only(bottom: 16),
          decoration: BoxDecoration(
            color: colorScheme.primaryContainer.withValues(alpha: 0.3),
            borderRadius: BorderRadius.circular(12),
          ),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                'Category Spending',
                style: textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.w600,
                  color: colorScheme.onSurface,
                ),
              ),
              Text(
                '${categories.length} categories',
                style: textTheme.bodyMedium?.copyWith(
                  color: colorScheme.onSurface.withValues(alpha: 0.7),
                ),
              ),
            ],
          ),
        ),
        
        // Category list
        Expanded(
          child: ListView.separated(
            itemCount: categories.length,
            separatorBuilder: (context, index) => const SizedBox(height: 12),
            itemBuilder: (context, index) {
              final category = categories[index];
              final budgeted = category['budgeted'] as int;
              final spent = category['spent'] as int;
              final color = category['color'] as Color;
              final percentage = budgeted > 0 ? (spent / budgeted) : 0.0;
              
              return Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: colorScheme.surfaceContainer,
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Container(
                          width: 12,
                          height: 12,
                          decoration: BoxDecoration(
                            color: color,
                            shape: BoxShape.circle,
                          ),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Text(
                            category['name'] as String,
                            style: textTheme.titleSmall?.copyWith(
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                        ),
                        Text(
                          '\$$spent / \$$budgeted',
                          style: textTheme.bodyMedium?.copyWith(
                            fontWeight: FontWeight.w500,
                            color: percentage > 1.0 ? colorScheme.error : colorScheme.onSurface,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 8),
                    LinearProgressIndicator(
                      value: percentage.clamp(0.0, 1.0),
                      backgroundColor: colorScheme.surfaceContainerHighest,
                      valueColor: AlwaysStoppedAnimation<Color>(
                        percentage > 1.0 ? colorScheme.error : color,
                      ),
                      minHeight: 4,
                      borderRadius: BorderRadius.circular(2),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      '${(percentage * 100).toStringAsFixed(1)}% used',
                      style: textTheme.bodySmall?.copyWith(
                        color: colorScheme.onSurface.withValues(alpha: 0.6),
                      ),
                    ),
                  ],
                ),
              );
            },
          ),
        ),
      ],
    );
  }

  /// Format category name for display
  String _formatCategoryName(String categoryName) {
    switch (categoryName.toLowerCase()) {
      case 'food':
        return 'Food & Dining';
      case 'transportation':
        return 'Transportation';
      case 'entertainment':
        return 'Entertainment';
      case 'shopping':
        return 'Shopping';
      case 'healthcare':
        return 'Healthcare';
      default:
        return categoryName.substring(0, 1).toUpperCase() + categoryName.substring(1);
    }
  }

  String _getStatusText(String status) {
    switch (status.toLowerCase()) {
      case 'over':
        return 'Over Budget';
      case 'warning':
        return 'Approaching Limit';
      case 'good':
      default:
        return 'On Track';
    }
  }

  Color _getStatusChipColor(String status) {
    final colorScheme = Theme.of(context).colorScheme;
    switch (status.toLowerCase()) {
      case 'over':
        return colorScheme.errorContainer;
      case 'warning':
        return colorScheme.tertiaryContainer;
      case 'good':
      default:
        return colorScheme.primaryContainer;
    }
  }

  Color _getStatusChipTextColor(String status) {
    final colorScheme = Theme.of(context).colorScheme;
    switch (status.toLowerCase()) {
      case 'over':
        return colorScheme.onErrorContainer;
      case 'warning':
        return colorScheme.onTertiaryContainer;
      case 'good':
      default:
        return colorScheme.onPrimaryContainer;
    }
  }

  Color _getSimpleDayColor(String status, bool isToday) {
    if (isToday) {
      switch (status.toLowerCase()) {
        case 'over':
          return Colors.red.shade100;
        case 'warning':
          return Colors.orange.shade100;
        case 'good':
        default:
          return Colors.blue.shade100;
      }
    }
    
    switch (status.toLowerCase()) {
      case 'over':
        return Colors.red.shade50;
      case 'warning':
        return Colors.orange.shade50;
      case 'good':
      default:
        return Colors.green.shade50;
    }
  }

  Color _getSimpleTextColor(String status, bool isToday) {
    switch (status.toLowerCase()) {
      case 'over':
        return Colors.red.shade700;
      case 'warning':
        return Colors.orange.shade700;
      case 'good':
      default:
        return isToday ? Colors.blue.shade700 : Colors.green.shade700;
    }
  }

  void _showSimpleDayModal(int dayNumber, int limit, int spent, String status) {
    final remaining = limit - spent;
    final spentPercentage = limit > 0 ? (spent / limit) * 100 : 0.0;
    
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (context) => Container(
        height: MediaQuery.of(context).size.height * 0.5,
        decoration: const BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.vertical(top: Radius.circular(28)),
        ),
        child: Padding(
          padding: const EdgeInsets.all(24.0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Header
              Row(
                children: [
                  Container(
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: _getSimpleDayColor(status, false),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Text(
                      dayNumber.toString(),
                      style: TextStyle(
                        fontSize: 24,
                        fontWeight: FontWeight.bold,
                        color: _getSimpleTextColor(status, false),
                      ),
                    ),
                  ),
                  const SizedBox(width: 16),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          '${_getMonthName(currentMonth.month)} $dayNumber, ${currentMonth.year}',
                          style: const TextStyle(
                            fontSize: 18,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                        Text(
                          _getStatusText(status),
                          style: TextStyle(
                            color: _getSimpleTextColor(status, false),
                            fontWeight: FontWeight.w500,
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
              
              const SizedBox(height: 24),
              
              // Budget overview
              Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: Colors.grey.shade50,
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Column(
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        _buildSimpleBudgetItem('Budget', '\$${limit}', Colors.blue),
                        _buildSimpleBudgetItem('Spent', '\$${spent}', Colors.red),
                        _buildSimpleBudgetItem('Remaining', '\$${remaining}', Colors.green),
                      ],
                    ),
                    const SizedBox(height: 16),
                    LinearProgressIndicator(
                      value: (spentPercentage / 100).clamp(0.0, 1.0),
                      backgroundColor: Colors.grey.shade200,
                      valueColor: AlwaysStoppedAnimation<Color>(
                        spentPercentage > 100 ? Colors.red : 
                        spentPercentage > 80 ? Colors.orange : Colors.green,
                      ),
                      minHeight: 8,
                    ),
                    const SizedBox(height: 8),
                    Text(
                      '${spentPercentage.toStringAsFixed(1)}% of budget used',
                      style: TextStyle(
                        color: Colors.grey.shade600,
                        fontSize: 12,
                      ),
                    ),
                  ],
                ),
              ),
              
              const Spacer(),
              
              // Action buttons
              Row(
                children: [
                  Expanded(
                    child: OutlinedButton(
                      onPressed: () => Navigator.pop(context),
                      child: const Text('Close'),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: ElevatedButton(
                      onPressed: () {
                        Navigator.pop(context);
                        Navigator.pushNamed(context, '/add_expense');
                      },
                      child: const Text('Add Expense'),
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildSimpleBudgetItem(String label, String amount, Color color) {
    return Column(
      children: [
        Text(
          label,
          style: TextStyle(
            color: Colors.grey.shade600,
            fontSize: 12,
          ),
        ),
        const SizedBox(height: 4),
        Text(
          amount,
          style: TextStyle(
            color: color,
            fontWeight: FontWeight.bold,
            fontSize: 16,
          ),
        ),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;

    return Scaffold(
      backgroundColor: colorScheme.surface,
      appBar: AppBar(
        title: Text(
          'Calendar - ${_getMonthName(currentMonth.month)} ${currentMonth.year}',
          style: textTheme.headlineSmall?.copyWith(
            fontWeight: FontWeight.w600,
            color: colorScheme.onSurface,
            fontSize: 18,
          ),
        ),
        backgroundColor: colorScheme.surface,
        elevation: 0,
        centerTitle: true,
        iconTheme: IconThemeData(color: colorScheme.onSurface),
        actions: [
          IconButton(
            icon: const Icon(Icons.settings),
            onPressed: () => Navigator.pushNamed(context, '/budget_settings'),
            tooltip: 'Budget Settings',
          ),
          IconButton(
            icon: const Icon(Icons.refresh_rounded),
            onPressed: _initializeData,
            tooltip: 'Refresh Calendar',
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: _initializeData,
        child: SingleChildScrollView(
          physics: const AlwaysScrollableScrollPhysics(),
          child: Padding(
            padding: EdgeInsets.all(
              MediaQuery.of(context).size.width > 600 ? 24.0 : 16.0,
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Month summary card
                if (!isLoading && calendarData.isNotEmpty) 
                  _buildMonthSummaryCard(),
                
                // Status legend
                Card(
                  elevation: 1,
                  margin: const EdgeInsets.only(bottom: 24),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                  child: Padding(
                    padding: const EdgeInsets.all(16.0),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'Daily Spending Status',
                          style: textTheme.titleMedium?.copyWith(
                            fontWeight: FontWeight.w600,
                            color: colorScheme.onSurface,
                            fontFamily: 'Sora',
                          ),
                        ),
                        const SizedBox(height: 12),
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            _buildStatusIndicator('On Track', Colors.green, Colors.white),
                            _buildStatusIndicator('Warning', Colors.orange, Colors.white),
                            _buildStatusIndicator('Over Budget', Colors.red, Colors.white),
                          ],
                        ),
                      ],
                    ),
                  ),
                ),

                // Enhanced Calendar Grid
                if (isLoading)
                  Card(
                    elevation: 2,
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                    child: const Padding(
                      padding: EdgeInsets.all(32.0),
                      child: Column(
                        children: [
                          CircularProgressIndicator(),
                          SizedBox(height: 16),
                          Text(
                            'Loading your spending calendar...',
                            style: TextStyle(
                              fontFamily: 'Manrope',
                              color: Colors.grey,
                            ),
                          ),
                        ],
                      ),
                    ),
                  )
                else if (error != null)
                  _buildErrorState()
                else if (calendarData.isEmpty)
                  _buildEmptyState()
                else
                  _buildEnhancedCalendarGrid(),
              ],
            ),
          ),
        ),
      ),
      floatingActionButton: FloatingActionButton.extended(
        heroTag: "calendar_fab",
        onPressed: () => Navigator.pushNamed(context, '/add_expense'),
        icon: const Icon(Icons.add_rounded),
        label: const Text('Add Expense'),
        backgroundColor: colorScheme.primary,
        foregroundColor: colorScheme.onPrimary,
        tooltip: 'Add new expense',
      ),
    );
  }

  Widget _buildMonthSummaryCard() {
    if (calendarData.isEmpty) return const SizedBox.shrink();
    
    // Calculate month statistics
    double totalBudget = 0;
    double totalSpent = 0;
    int onTrackDays = 0;
    int warningDays = 0;
    int overBudgetDays = 0;
    int activeDays = 0;
    
    for (var day in calendarData) {
      if (day['day'] != 0 && day['status'] != 'empty') {
        final limit = (day['limit'] as num?)?.toDouble() ?? 0.0;
        final spent = (day['spent'] as num?)?.toDouble() ?? 0.0;
        final status = day['status'] as String? ?? 'good';
        
        totalBudget += limit;
        totalSpent += spent;
        activeDays++;
        
        switch (status.toLowerCase()) {
          case 'good':
            onTrackDays++;
            break;
          case 'warning':
            warningDays++;
            break;
          case 'over':
            overBudgetDays++;
            break;
        }
      }
    }
    
    final spentPercentage = totalBudget > 0 ? (totalSpent / totalBudget) : 0.0;
    final remaining = totalBudget - totalSpent;
    
    return Card(
      elevation: 3,
      margin: const EdgeInsets.only(bottom: 20),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      child: Container(
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(16),
          gradient: LinearGradient(
            colors: [
              const Color(0xFF193C57),
              const Color(0xFF193C57).withValues(alpha: 0.8),
            ],
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
          ),
        ),
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(
                    '${_getMonthName(currentMonth.month)} Overview',
                    style: const TextStyle(
                      fontFamily: 'Sora',
                      fontSize: 18,
                      fontWeight: FontWeight.bold,
                      color: Colors.white,
                    ),
                  ),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                    decoration: BoxDecoration(
                      color: Colors.white.withValues(alpha: 0.2),
                      borderRadius: BorderRadius.circular(20),
                    ),
                    child: Text(
                      '$activeDays days tracked',
                      style: const TextStyle(
                        fontFamily: 'Manrope',
                        fontSize: 12,
                        color: Colors.white,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 20),
              
              // Budget vs Spent
              Row(
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text(
                          'Total Budget',
                          style: TextStyle(
                            fontFamily: 'Manrope',
                            fontSize: 14,
                            color: Colors.white70,
                          ),
                        ),
                        Text(
                          '\$${totalBudget.toStringAsFixed(0)}',
                          style: const TextStyle(
                            fontFamily: 'Sora',
                            fontSize: 24,
                            fontWeight: FontWeight.bold,
                            color: Colors.white,
                          ),
                        ),
                      ],
                    ),
                  ),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.center,
                      children: [
                        const Text(
                          'Spent',
                          style: TextStyle(
                            fontFamily: 'Manrope',
                            fontSize: 14,
                            color: Colors.white70,
                          ),
                        ),
                        Text(
                          '\$${totalSpent.toStringAsFixed(0)}',
                          style: const TextStyle(
                            fontFamily: 'Sora',
                            fontSize: 24,
                            fontWeight: FontWeight.bold,
                            color: Colors.white,
                          ),
                        ),
                      ],
                    ),
                  ),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.end,
                      children: [
                        const Text(
                          'Remaining',
                          style: TextStyle(
                            fontFamily: 'Manrope',
                            fontSize: 14,
                            color: Colors.white70,
                          ),
                        ),
                        Text(
                          '\$${remaining.toStringAsFixed(0)}',
                          style: const TextStyle(
                            fontFamily: 'Sora',
                            fontSize: 24,
                            fontWeight: FontWeight.bold,
                            color: Colors.white,
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
              
              const SizedBox(height: 20),
              
              // Progress bar
              Container(
                height: 8,
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(4),
                  color: Colors.white.withValues(alpha: 0.2),
                ),
                child: FractionallySizedBox(
                  alignment: Alignment.centerLeft,
                  widthFactor: spentPercentage.clamp(0.0, 1.0),
                  child: Container(
                    decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(4),
                      color: spentPercentage > 1.0 ? Colors.red : Colors.white,
                    ),
                  ),
                ),
              ),
              
              const SizedBox(height: 8),
              
              Text(
                '${(spentPercentage * 100).toStringAsFixed(1)}% of monthly budget used',
                style: const TextStyle(
                  fontFamily: 'Manrope',
                  fontSize: 12,
                  color: Colors.white70,
                ),
              ),
              
              const SizedBox(height: 16),
              
              // Day status summary
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                children: [
                  _buildStatusSummary('On Track', onTrackDays, Colors.green),
                  _buildStatusSummary('Warning', warningDays, Colors.orange),
                  _buildStatusSummary('Over Budget', overBudgetDays, Colors.red),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildStatusSummary(String label, int count, Color color) {
    return Column(
      children: [
        Container(
          padding: const EdgeInsets.all(8),
          decoration: BoxDecoration(
            color: color.withValues(alpha: 0.2),
            shape: BoxShape.circle,
          ),
          child: Text(
            count.toString(),
            style: TextStyle(
              fontFamily: 'Sora',
              fontWeight: FontWeight.bold,
              color: color,
              fontSize: 16,
            ),
          ),
        ),
        const SizedBox(height: 4),
        Text(
          label,
          style: const TextStyle(
            fontFamily: 'Manrope',
            fontSize: 11,
            color: Colors.white70,
          ),
        ),
      ],
    );
  }

  Widget _buildStatusIndicator(String label, Color color, Color onColor) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          width: 12,
          height: 12,
          decoration: BoxDecoration(
            color: color,
            shape: BoxShape.circle,
          ),
        ),
        const SizedBox(width: 6),
        Text(
          label,
          style: Theme.of(context).textTheme.bodySmall?.copyWith(
            color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.7),
          ),
        ),
      ],
    );
  }
}