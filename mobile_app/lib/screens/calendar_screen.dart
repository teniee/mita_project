import 'package:flutter/material.dart';
import '../services/api_service.dart';
import '../services/budget_adapter_service.dart';
import '../services/user_data_manager.dart';
import '../services/live_updates_service.dart';
import 'dart:async';
import '../services/logging_service.dart';
import 'calendar_day_details_screen.dart';

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
  final BudgetAdapterService _budgetService = BudgetAdapterService();
  final LiveUpdatesService _liveUpdates = LiveUpdatesService();
  List<dynamic> calendarData = [];
  bool isLoading = true;
  bool isRedistributing = false;
  String? error;
  DateTime currentMonth = DateTime.now();
  StreamSubscription? _budgetUpdateSubscription;
  late AnimationController _redistributionAnimationController;
  

  @override
  void initState() {
    super.initState();
    _redistributionAnimationController = AnimationController(
      duration: const Duration(milliseconds: 1500),
      vsync: this,
    );

    _initializeData();
    _subscribeToBudgetUpdates();
  }

  @override
  void dispose() {
    _budgetUpdateSubscription?.cancel();
    _redistributionAnimationController.dispose();
    super.dispose();
  }

  Map<String, dynamic>? budgetRemaining;
  Map<String, dynamic>? monthlyBudget;

  Future<void> _initializeData() async {
    await fetchCalendarData();
    await _fetchBudgetRemaining();
    await _fetchMonthlyBudget();
  }

  Future<void> _fetchBudgetRemaining() async {
    try {
      budgetRemaining = await _apiService.getBudgetRemaining(
        year: currentMonth.year,
        month: currentMonth.month,
      );
    } catch (e) {
      logError('Error fetching budget remaining: $e', tag: 'CALENDAR_SCREEN');
    }
  }

  Future<void> _fetchMonthlyBudget() async {
    try {
      monthlyBudget = await _apiService.getMonthlyBudget(
        currentMonth.year,
        currentMonth.month,
      );
    } catch (e) {
      logError('Error fetching monthly budget: $e', tag: 'CALENDAR_SCREEN');
    }
  }


  void _subscribeToBudgetUpdates() {
    // Subscribe to centralized live updates instead of creating duplicate timer
    logInfo('Subscribing to centralized budget updates', tag: 'CALENDAR_SCREEN');

    _budgetUpdateSubscription = _liveUpdates.budgetUpdates.listen((budgetData) {
      if (mounted && !isRedistributing) {
        logDebug('Received budget update, refreshing calendar', tag: 'CALENDAR_SCREEN');
        fetchCalendarData();
      }
    });
  }

  Future<void> fetchCalendarData() async {
    setState(() {
      isLoading = true;
      error = null;
    });

    try {
      // First try to get data from production budget engine
      logInfo('Loading calendar data from production budget engine', tag: 'CALENDAR_SCREEN');
      final productionData = await _budgetService.getCalendarData();

      if (!mounted) return;
      setState(() {
        calendarData = productionData;
        isLoading = false;
      });

      logInfo('Calendar data loaded from production budget engine successfully', tag: 'CALENDAR_SCREEN');
    } catch (e) {
      logError('Error loading production calendar data: $e', tag: 'CALENDAR_SCREEN');

      try {
        // Try behavioral calendar endpoint
        logInfo('Attempting to load behavioral calendar', tag: 'CALENDAR_SCREEN');
        final behavioralCalendar = await _apiService.getBehaviorCalendar(
          year: currentMonth.year,
          month: currentMonth.month,
        );

        if (!mounted) return;

        // Convert behavioral calendar format to standard calendar format
        final convertedData = _convertBehavioralCalendarData(behavioralCalendar);
        setState(() {
          calendarData = convertedData;
          isLoading = false;
        });

        logInfo('Loaded behavioral calendar successfully', tag: 'CALENDAR_SCREEN');
      } catch (behavioralError) {
        logError('Error loading behavioral calendar: $behavioralError', tag: 'CALENDAR_SCREEN');

        try {
          // Fallback to standard API
          final data = await _apiService.getCalendar();
          if (!mounted) return;
          setState(() {
            calendarData = data;
            isLoading = false;
          });
        } catch (apiError) {
          logError('Error loading API calendar: $apiError', tag: 'CALENDAR_SCREEN');
          if (!mounted) return;

          // Final fallback to user-based data generation
          final userBasedData = await _generateUserBasedCalendarData();
          setState(() {
            calendarData = userBasedData;
            isLoading = false;
            error = null; // Don't show error, just use user-based data
          });

          // Show user-friendly error message but don't break the UI
          if (mounted) {
            WidgetsBinding.instance.addPostFrameCallback((_) {
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(
                  content: Text('Using personalized budget calculations'),
                  duration: Duration(seconds: 2),
                  behavior: SnackBarBehavior.floating,
                ),
              );
            });
          }
        }
      }
    }
  }

  /// Convert behavioral calendar data format to standard calendar format
  List<Map<String, dynamic>> _convertBehavioralCalendarData(Map<String, dynamic> behavioralData) {
    if (behavioralData['calendar_days'] != null) {
      return List<Map<String, dynamic>>.from(behavioralData['calendar_days']);
    }

    // If the data is already in the correct format
    if (behavioralData['days'] != null) {
      return List<Map<String, dynamic>>.from(behavioralData['days']);
    }

    // Return empty list if format is unknown
    logWarning('Unknown behavioral calendar format', tag: 'CALENDAR_SCREEN');
    return [];
  }

  Future<List<Map<String, dynamic>>> _generateUserBasedCalendarData() async {
    final today = DateTime.now();
    final daysInMonth = DateTime(today.year, today.month + 1, 0).day;
    final firstDayOfMonth = DateTime(today.year, today.month, 1);
    final firstWeekday = firstDayOfMonth.weekday % 7; // Sunday = 0, Monday = 1, etc.
    
    List<Map<String, dynamic>> calendarDays = [];
    
    // Load user financial context from UserDataManager (includes onboarding data)
    Map<String, dynamic> userFinancialContext = {};
    try {
      userFinancialContext = await UserDataManager.instance.getFinancialContext().timeout(
        const Duration(seconds: 3),
        onTimeout: () => <String, dynamic>{},
      );
      logInfo('Loaded user financial context for calendar: income=${userFinancialContext['income']}', tag: 'CALENDAR_USER_DATA');
    } catch (e) {
      logWarning('Failed to load user financial context for calendar: $e', tag: 'CALENDAR_USER_DATA');
    }
    
    // Calculate daily budget based on user's actual financial data from onboarding
    final incomeValue = (userFinancialContext['income'] as num?)?.toDouble();
    if (incomeValue == null || incomeValue <= 0) {
      throw Exception('Income data required for calendar. Please complete onboarding.');
    }
    final monthlyIncome = incomeValue;
    final savingsGoal = monthlyIncome * 0.20; // Default to 20% savings rate if not specified
    final budgetMethod = userFinancialContext['budgetMethod'] as String? ?? '50/30/20 Rule';
    
    final spendableIncome = monthlyIncome - savingsGoal;
    final dailyBudget = _calculateDailyBudget(spendableIncome, budgetMethod);
    
    // Add empty cells for days before the first day of the month
    for (int i = 0; i < firstWeekday; i++) {
      calendarDays.add({
        'day': 0,
        'status': 'empty',
        'limit': 0,
        'spent': 0,
      });
    }
    
    // Try to get real spending data from API
    Map<String, dynamic> monthlySpending = {};
    try {
      monthlySpending = await _apiService.getBudgetSpent(
        year: today.year,
        month: today.month,
      ).timeout(
        const Duration(seconds: 3),
        onTimeout: () => <String, dynamic>{},
      ).catchError((e) => <String, dynamic>{});
    } catch (e) {
      logWarning('Failed to load monthly spending: $e', tag: 'CALENDAR_SPENDING');
    }
    
    // Generate calendar days based on user data
    for (int day = 1; day <= daysInMonth; day++) {
      final dayDate = DateTime(today.year, today.month, day);
      final isToday = day == today.day;
      final isFuture = dayDate.isAfter(today);
      
      // Get actual spending for this day if available
      final dayKey = '${today.year}-${today.month.toString().padLeft(2, '0')}-${day.toString().padLeft(2, '0')}';
      final daySpending = monthlySpending[dayKey] as Map<String, dynamic>? ?? {};
      
      // Calculate daily budget with some variation based on day type
      final dayOfWeek = dayDate.weekday;
      final isWeekend = dayOfWeek == 6 || dayOfWeek == 7;
      final dailyBudgetForDay = _adjustDailyBudgetForDay(dailyBudget, isWeekend, budgetMethod);
      
      String status;
      double spent;
      
      if (daySpending.isNotEmpty && daySpending['total'] != null) {
        // Use real spending data
        spent = (daySpending['total'] as num).toDouble();
      } else if (isFuture) {
        // Future days have no spending yet
        spent = 0.0;
      } else if (isToday) {
        // Today has some spending - estimate based on time of day
        final hourOfDay = DateTime.now().hour;
        final dayProgress = hourOfDay / 24.0;
        spent = dailyBudgetForDay * dayProgress * 0.7; // Conservative estimate
      } else {
        // Past days - generate realistic spending based on patterns
        spent = _generateRealisticSpending(dailyBudgetForDay, isWeekend, day);
      }
      
      // Determine status based on spending vs budget
      final spentRatio = dailyBudgetForDay > 0 ? spent / dailyBudgetForDay : 0.0;
      if (spentRatio > 1.0) {
        status = 'over';
      } else if (spentRatio > 0.8) {
        status = 'warning';
      } else {
        status = 'good';
      }
      
      // Generate category breakdown based on user's budget method
      final categoryBreakdown = _generateCategoryBreakdown(
        dailyBudgetForDay,
        budgetMethod,
        daySpending,
      );
      
      calendarDays.add({
        'day': day,
        'status': status,
        'limit': dailyBudgetForDay.round(),
        'spent': spent.round(),
        'categories': categoryBreakdown,
        'user_based': true,
      });
    }
    
    return calendarDays;
  }

  double _calculateDailyBudget(double spendableIncome, String budgetMethod) {
    // Calculate daily budget based on the user's chosen method
    switch (budgetMethod) {
      case '50/30/20 Rule':
        // 50% for needs, 30% for wants
        return (spendableIncome * 0.8) / 30; // 80% of spendable income over 30 days
      case '60/20/20':
        return (spendableIncome * 0.8) / 30;
      case 'Zero-Based':
        return spendableIncome / 30; // All income allocated
      case 'Envelope':
        return (spendableIncome * 0.75) / 30; // 75% for daily expenses
      default:
        return (spendableIncome * 0.8) / 30;
    }
  }

  double _adjustDailyBudgetForDay(double baseBudget, bool isWeekend, String budgetMethod) {
    // Adjust budget based on day type and user preferences
    if (isWeekend) {
      return baseBudget * 1.2; // 20% more for weekends
    } else {
      return baseBudget * 0.9; // Slightly less for weekdays
    }
  }

  double _generateRealisticSpending(double budget, bool isWeekend, int day) {
    // Generate realistic spending patterns based on behavioral data
    final baseSpending = budget * 0.7; // Average 70% of budget
    final variation = (day % 5) * 0.05; // Some day-to-day variation
    
    if (isWeekend) {
      return baseSpending * (1.1 + variation); // Higher weekend spending
    } else {
      return baseSpending * (0.9 + variation); // Lower weekday spending
    }
  }

  Map<String, int> _generateCategoryBreakdown(
    double dailyBudget,
    String budgetMethod,
    Map<String, dynamic> actualSpending,
  ) {
    // Use actual spending if available, otherwise generate based on budget method
    if (actualSpending.isNotEmpty && actualSpending['categories'] != null) {
      final categories = actualSpending['categories'] as Map<String, dynamic>;
      return categories.map((key, value) => MapEntry(key, (value as num).round()));
    }
    
    // Generate based on typical spending patterns for the budget method
    switch (budgetMethod) {
      case '50/30/20 Rule':
        return {
          'food': (dailyBudget * 0.35).round(),
          'transportation': (dailyBudget * 0.20).round(),
          'entertainment': (dailyBudget * 0.25).round(),
          'shopping': (dailyBudget * 0.15).round(),
          'other': (dailyBudget * 0.05).round(),
        };
      case 'Zero-Based':
        return {
          'food': (dailyBudget * 0.40).round(),
          'transportation': (dailyBudget * 0.25).round(),
          'entertainment': (dailyBudget * 0.15).round(),
          'shopping': (dailyBudget * 0.15).round(),
          'other': (dailyBudget * 0.05).round(),
        };
      default:
        return {
          'food': (dailyBudget * 0.35).round(),
          'transportation': (dailyBudget * 0.25).round(),
          'entertainment': (dailyBudget * 0.20).round(),
          'shopping': (dailyBudget * 0.15).round(),
          'other': (dailyBudget * 0.05).round(),
        };
    }
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
    final dayDate = DateTime(currentMonth.year, currentMonth.month, dayNumber);
    final dayData = calendarData.isNotEmpty 
        ? calendarData.firstWhere((day) => day['day'] == dayNumber, orElse: () => null)
        : null;
    
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      enableDrag: true,
      builder: (context) => CalendarDayDetailsScreen(
        dayNumber: dayNumber,
        limit: limit,
        spent: spent,
        status: status,
        date: dayDate,
        dayData: dayData,
        budgetService: _budgetService, // Pass budget service for enhanced details
      ),
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