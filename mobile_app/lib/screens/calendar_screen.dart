import 'package:flutter/material.dart';
import '../services/api_service.dart';
import 'dart:async';
import '../services/logging_service.dart';

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
    _liveUpdateTimer = Timer.periodic(const Duration(seconds: 45), (timer) {
      if (mounted && !isRedistributing) {
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
        calendarData = [];
        isLoading = false;
        error = e.toString();
      });
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
            // Calendar grid
            AnimatedBuilder(
              animation: _redistributionAnimation,
              builder: (context, child) {
                return Transform.scale(
                  scale: isRedistributing ? 1.0 - (_redistributionAnimation.value * 0.02) : 1.0,
                  child: GridView.builder(
                    shrinkWrap: true,
                    physics: const NeverScrollableScrollPhysics(),
                    itemCount: calendarData.length,
                    gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                      crossAxisCount: 7,
                      crossAxisSpacing: 8,
                      mainAxisSpacing: 8,
                      childAspectRatio: 0.75, // Taller cells for more content
                    ),
                    itemBuilder: (context, index) {
                      final day = calendarData[index];
                      final dayNumber = day['day'] as int;
                      final status = day['status'] as String;
                      final limit = day['limit'] as int;
                      final spent = day['spent'] as int? ?? 0;
                      final isToday = dayNumber == today.day && 
                                     currentMonth.month == today.month && 
                                     currentMonth.year == today.year;
                      
                      return _buildEnhancedDayCell(
                        dayNumber: dayNumber,
                        limit: limit,
                        spent: spent,
                        status: status,
                        isToday: isToday,
                        colorScheme: colorScheme,
                      );
                    },
                  ),
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
            padding: const EdgeInsets.all(16.0),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
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
                          'Spending Status',
                          style: textTheme.titleMedium?.copyWith(
                            fontWeight: FontWeight.w600,
                            color: colorScheme.onSurface,
                          ),
                        ),
                        const SizedBox(height: 12),
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            _buildStatusIndicator('On Track', colorScheme.primary, colorScheme.onPrimary),
                            _buildStatusIndicator('Warning', colorScheme.tertiary, colorScheme.onTertiary),
                            _buildStatusIndicator('Over Budget', colorScheme.error, colorScheme.onError),
                          ],
                        ),
                      ],
                    ),
                  ),
                ),

                // Enhanced Calendar Grid
                if (isLoading)
                  const Center(
                    child: Padding(
                      padding: EdgeInsets.all(32.0),
                      child: CircularProgressIndicator(),
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
        onPressed: () => Navigator.pushNamed(context, '/add_expense'),
        icon: const Icon(Icons.add_rounded),
        label: const Text('Add Expense'),
        tooltip: 'Add new expense',
      ),
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