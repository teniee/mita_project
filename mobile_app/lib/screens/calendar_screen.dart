import 'package:flutter/material.dart';
import '../services/api_service.dart';
import 'dart:async';
import '../utils/string_extensions.dart';
import '../services/logging_service.dart';

class CalendarScreen extends StatefulWidget {
  const CalendarScreen({Key? key}) : super(key: key);

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
  Map<String, dynamic> _budgetSuggestions = {};
  List<dynamic> _redistributionHistory = [];
  String _budgetMode = 'default';
  Timer? _liveUpdateTimer;
  late AnimationController _redistributionAnimationController;
  late Animation<double> _redistributionAnimation;
  
  // AI Insights for Calendar
  Map<String, dynamic>? _aiSnapshot;
  Map<String, dynamic>? _spendingPatterns;
  Map<String, dynamic>? _weeklyInsights;
  List<Map<String, dynamic>> _spendingAnomalies = [];
  Map<String, String> _dayAdviceCache = {};

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
    await _fetchBudgetSuggestions();
    await _fetchBudgetMode();
    await _fetchRedistributionHistory();
    await _fetchAIInsights();
  }

  Future<void> _fetchAIInsights() async {
    try {
      final futures = await Future.wait([
        _apiService.getLatestAISnapshot().catchError((e) => <String, dynamic>{}),
        _apiService.getSpendingPatterns().catchError((e) => <String, dynamic>{}),
        _apiService.getAIWeeklyInsights().catchError((e) => <String, dynamic>{}),
        _apiService.getSpendingAnomalies().catchError((e) => <Map<String, dynamic>>[]),
      ]);

      if (mounted) {
        setState(() {
          _aiSnapshot = futures[0] as Map<String, dynamic>?;
          _spendingPatterns = futures[1] as Map<String, dynamic>?;
          _weeklyInsights = futures[2] as Map<String, dynamic>?;
          _spendingAnomalies = futures[3] as List<Map<String, dynamic>>;
        });
      }
    } catch (e) {
      logError('Error fetching AI insights: $e');
    }
  }

  Future<String> _getAIDayAdvice(String status, {List<String>? recommendations, String? date}) async {
    final key = '$status-$date';
    if (_dayAdviceCache.containsKey(key)) {
      return _dayAdviceCache[key]!;
    }

    try {
      final advice = await _apiService.getAIDayStatusExplanation(
        status,
        recommendations: recommendations,
        date: date,
      );
      _dayAdviceCache[key] = advice;
      return advice;
    } catch (e) {
      final fallbackAdvice = _getFallbackAdvice(status);
      _dayAdviceCache[key] = fallbackAdvice;
      return fallbackAdvice;
    }
  }

  String _getFallbackAdvice(String status) {
    switch (status.toLowerCase()) {
      case 'good':
        return 'Great job staying within your budget today! Keep up the good work.';
      case 'warning':
        return 'You\'re approaching your daily limit. Consider reviewing your remaining expenses.';
      case 'over':
        return 'You\'ve exceeded your daily budget. Try to be more mindful of spending tomorrow.';
      default:
        return 'Track your spending carefully to stay on budget.';
    }
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

  Future<void> _fetchBudgetSuggestions() async {
    try {
      final suggestions = await _apiService.getBudgetSuggestions();
      if (mounted) {
        setState(() {
          _budgetSuggestions = suggestions;
        });
      }
    } catch (e) {
      logError('Error loading budget suggestions: $e');
    }
  }

  Future<void> _fetchBudgetMode() async {
    try {
      final mode = await _apiService.getBudgetMode();
      if (mounted) {
        setState(() {
          _budgetMode = mode;
        });
      }
    } catch (e) {
      logError('Error loading budget mode: $e');
    }
  }

  Future<void> _fetchRedistributionHistory() async {
    try {
      final history = await _apiService.getBudgetRedistributionHistory();
      if (mounted) {
        setState(() {
          _redistributionHistory = history;
        });
      }
    } catch (e) {
      logError('Error loading redistribution history: $e');
    }
  }

  Future<void> _triggerCalendarRedistribution() async {
    setState(() {
      isRedistributing = true;
    });
    
    _redistributionAnimationController.forward();

    try {
      // Convert calendar data to redistribution format
      Map<String, Map<String, dynamic>> calendarDict = {};
      for (var day in calendarData) {
        final dayNum = day['day'].toString();
        calendarDict[dayNum] = {
          'total': (day['spent'] ?? 0).toDouble(),
          'limit': (day['limit'] ?? 0).toDouble(),
        };
      }

      // Trigger redistribution
      final result = await _apiService.redistributeCalendarBudget(calendarDict);
      
      // Refresh data after redistribution
      await _initializeData();
      
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: const Row(
              children: [
                Icon(Icons.check_circle, color: Colors.white),
                SizedBox(width: 8),
                Text('Calendar budget redistributed successfully!'),
              ],
            ),
            duration: const Duration(seconds: 3),
            backgroundColor: Theme.of(context).colorScheme.primary,
            behavior: SnackBarBehavior.floating,
          ),
        );
      }
    } catch (e) {
      logError('Error during calendar redistribution: $e');
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: const Row(
              children: [
                Icon(Icons.error, color: Colors.white),
                SizedBox(width: 8),
                Text('Failed to redistribute budget. Please try again.'),
              ],
            ),
            duration: const Duration(seconds: 3),
            backgroundColor: Theme.of(context).colorScheme.error,
            behavior: SnackBarBehavior.floating,
          ),
        );
      }
    } finally {
      if (mounted) {
        setState(() {
          isRedistributing = false;
        });
        _redistributionAnimationController.reset();
      }
    }
  }

  Color _getDayColor(String status) {
    final colorScheme = Theme.of(context).colorScheme;
    switch (status.toLowerCase()) {
      case 'over':
        return colorScheme.error;
      case 'warning':
        return colorScheme.tertiary;
      case 'good':
      default:
        return colorScheme.primary;
    }
  }

  Color _getOnDayColor(String status) {
    final colorScheme = Theme.of(context).colorScheme;
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

  String _getMonthName(int month) {
    const months = [
      'January', 'February', 'March', 'April', 'May', 'June',
      'July', 'August', 'September', 'October', 'November', 'December'
    ];
    return months[month - 1];
  }

  String _getBudgetModeDisplayName(String mode) {
    switch (mode) {
      case 'strict':
        return 'Strict';
      case 'flexible':
        return 'Flexible';
      case 'behavioral':
        return 'Behavioral';
      case 'goal':
        return 'Goal-Oriented';
      default:
        return 'Standard';
    }
  }

  Color _getBudgetModeColor(String mode) {
    switch (mode) {
      case 'strict':
        return const Color(0xFFFF5C5C);
      case 'flexible':
        return const Color(0xFF84FAA1);
      case 'behavioral':
        return const Color(0xFF6B73FF);
      case 'goal':
        return const Color(0xFFFFD25F);
      default:
        return Colors.grey;
    }
  }

  Widget _buildSmartActionsCard() {
    final colorScheme = Theme.of(context).colorScheme;
    
    return Card(
      elevation: 3,
      margin: const EdgeInsets.only(bottom: 16),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Row(
                  children: [
                    Icon(Icons.auto_fix_high, color: colorScheme.primary),
                    const SizedBox(width: 8),
                    Text(
                      'Smart Budget Actions',
                      style: TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.w600,
                        color: colorScheme.onSurface,
                      ),
                    ),
                  ],
                ),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                  decoration: BoxDecoration(
                    color: _getBudgetModeColor(_budgetMode).withOpacity(0.1),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Text(
                    _getBudgetModeDisplayName(_budgetMode),
                    style: TextStyle(
                      fontSize: 12,
                      fontWeight: FontWeight.w500,
                      color: _getBudgetModeColor(_budgetMode),
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: AnimatedBuilder(
                    animation: _redistributionAnimation,
                    builder: (context, child) {
                      return ElevatedButton.icon(
                        onPressed: isRedistributing ? null : _triggerCalendarRedistribution,
                        icon: isRedistributing 
                          ? Transform.rotate(
                              angle: _redistributionAnimation.value * 2 * 3.14159,
                              child: const Icon(Icons.sync, size: 18),
                            )
                          : const Icon(Icons.balance, size: 18),
                        label: Text(isRedistributing ? 'Redistributing...' : 'Redistribute'),
                        style: ElevatedButton.styleFrom(
                          backgroundColor: colorScheme.primary,
                          foregroundColor: colorScheme.onPrimary,
                          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                          padding: const EdgeInsets.symmetric(vertical: 12),
                        ),
                      );
                    },
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: ElevatedButton.icon(
                    onPressed: () => Navigator.pushNamed(context, '/daily_budget'),
                    icon: const Icon(Icons.insights, size: 18),
                    label: const Text('View Details'),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: colorScheme.secondary,
                      foregroundColor: colorScheme.onSecondary,
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                      padding: const EdgeInsets.symmetric(vertical: 12),
                    ),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildBudgetInsights() {
    final colorScheme = Theme.of(context).colorScheme;
    
    return Card(
      elevation: 2,
      margin: const EdgeInsets.only(bottom: 16),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(Icons.psychology, color: colorScheme.primary),
                const SizedBox(width: 8),
                Text(
                  'AI Calendar Insights',
                  style: TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.w600,
                    color: colorScheme.onSurface,
                  ),
                ),
                const Spacer(),
                GestureDetector(
                  onTap: () => Navigator.pushNamed(context, '/insights'),
                  child: Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                    decoration: BoxDecoration(
                      color: colorScheme.primary.withOpacity(0.1),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Text(
                      'View All',
                      style: TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.w500,
                        color: colorScheme.primary,
                      ),
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),
            
            // AI Snapshot Summary
            if (_aiSnapshot != null) ...[
              _buildAISnapshotSummary(),
              const SizedBox(height: 12),
            ],
            
            // Spending Patterns
            if (_spendingPatterns != null) ...[
              _buildSpendingPatternsPreview(),
              const SizedBox(height: 12),
            ],
            
            // Weekly Insights
            if (_weeklyInsights != null) ...[
              _buildWeeklyInsightsPreview(),
              const SizedBox(height: 12),
            ],
            
            // Anomalies Alert
            if (_spendingAnomalies.isNotEmpty) ...[
              _buildAnomaliesAlert(),
              const SizedBox(height: 12),
            ],
            
            // Budget Suggestions
            if (_budgetSuggestions.isNotEmpty) ...[
              _buildBudgetSuggestionsPreview(),
            ],
            
            // Recent redistribution activity
            if (_redistributionHistory.isNotEmpty) ...[
              const SizedBox(height: 16),
              Text(
                'Recent Activity',
                style: TextStyle(
                  fontSize: 14,
                  fontWeight: FontWeight.w500,
                  color: colorScheme.onSurface.withOpacity(0.8),
                ),
              ),
              const SizedBox(height: 8),
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: colorScheme.primary.withOpacity(0.1),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Row(
                      children: [
                        Icon(Icons.sync_alt, size: 16, color: colorScheme.primary),
                        const SizedBox(width: 8),
                        Text(
                          '${_redistributionHistory.length} recent transfers',
                          style: TextStyle(
                            fontSize: 13,
                            color: colorScheme.onSurface,
                          ),
                        ),
                      ],
                    ),
                    TextButton(
                      onPressed: () => Navigator.pushNamed(context, '/daily_budget'),
                      child: Text(
                        'View All',
                        style: TextStyle(
                          fontSize: 12,
                          color: colorScheme.primary,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ],
        ),
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
          'Smart Calendar - ${_getMonthName(currentMonth.month)} ${currentMonth.year}',
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
                // Smart actions card
                _buildSmartActionsCard(),
                
                // AI Budget insights
                _buildBudgetInsights(),

                // Month header with spending summary
                Card(
                  elevation: 2,
                  margin: const EdgeInsets.only(bottom: 24),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                  child: Padding(
                    padding: const EdgeInsets.all(16.0),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            Text(
                              'Monthly Overview',
                              style: textTheme.titleMedium?.copyWith(
                                fontWeight: FontWeight.w600,
                                color: colorScheme.onSurface,
                              ),
                            ),
                            if (isRedistributing)
                              Container(
                                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
                                decoration: BoxDecoration(
                                  color: colorScheme.primary.withOpacity(0.1),
                                  borderRadius: BorderRadius.circular(12),
                                ),
                                child: Row(
                                  mainAxisSize: MainAxisSize.min,
                                  children: [
                                    SizedBox(
                                      width: 12,
                                      height: 12,
                                      child: CircularProgressIndicator(
                                        strokeWidth: 2,
                                        color: colorScheme.primary,
                                      ),
                                    ),
                                    const SizedBox(width: 6),
                                    Text(
                                      'Redistributing...',
                                      style: TextStyle(
                                        fontSize: 12,
                                        color: colorScheme.primary,
                                        fontWeight: FontWeight.w500,
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                          ],
                        ),
                        const SizedBox(height: 12),
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            _buildStatusIndicator('Good', colorScheme.primary, colorScheme.onPrimary),
                            _buildStatusIndicator('Warning', colorScheme.tertiary, colorScheme.onTertiary),
                            _buildStatusIndicator('Over Budget', colorScheme.error, colorScheme.onError),
                          ],
                        ),
                      ],
                    ),
                  ),
                ),

                // Calendar grid
                if (isLoading)
                  const Center(
                    child: Padding(
                      padding: EdgeInsets.all(32.0),
                      child: CircularProgressIndicator(),
                    ),
                  )
                else if (error != null)
                  Card(
                    elevation: 1,
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                    child: Padding(
                      padding: const EdgeInsets.all(24.0),
                      child: Column(
                        children: [
                          Icon(
                            Icons.error_outline_rounded,
                            size: 48,
                            color: colorScheme.error,
                          ),
                          const SizedBox(height: 16),
                          Text(
                            'Unable to load smart calendar',
                            style: textTheme.titleMedium?.copyWith(
                              color: colorScheme.onSurface,
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
                          const SizedBox(height: 16),
                          FilledButton.icon(
                            onPressed: _initializeData,
                            icon: const Icon(Icons.refresh_rounded),
                            label: const Text('Retry'),
                          ),
                        ],
                      ),
                    ),
                  )
                else if (calendarData.isEmpty)
                  Card(
                    elevation: 1,
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                    child: Padding(
                      padding: const EdgeInsets.all(24.0),
                      child: Column(
                        children: [
                          Icon(
                            Icons.auto_fix_high,
                            size: 48,
                            color: colorScheme.primary,
                          ),
                          const SizedBox(height: 16),
                          Text(
                            'No smart calendar data available',
                            style: textTheme.titleMedium?.copyWith(
                              color: colorScheme.onSurface,
                            ),
                          ),
                          const SizedBox(height: 8),
                          Text(
                            'Complete your budget setup to unlock AI-powered spending insights',
                            style: textTheme.bodyMedium?.copyWith(
                              color: colorScheme.onSurface.withValues(alpha: 0.7),
                            ),
                            textAlign: TextAlign.center,
                          ),
                        ],
                      ),
                    ),
                  )
                else
                  AnimatedBuilder(
                    animation: _redistributionAnimation,
                    builder: (context, child) {
                      return Transform.scale(
                        scale: isRedistributing ? 1.0 - (_redistributionAnimation.value * 0.05) : 1.0,
                        child: GridView.builder(
                          shrinkWrap: true,
                          physics: const NeverScrollableScrollPhysics(),
                          itemCount: calendarData.length,
                          gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                            crossAxisCount: 7, // 7 days in a week
                            crossAxisSpacing: 8,
                            mainAxisSpacing: 8,
                            childAspectRatio: 0.8,
                          ),
                          itemBuilder: (context, index) {
                            final day = calendarData[index];
                            final dayNumber = day['day'] as int;
                            final status = day['status'] as String;
                            final limit = day['limit'] as int;
                            final spent = day['spent'] as int? ?? 0;
                            final isRecentlyRedistributed = _redistributionHistory.any(
                              (transfer) => 
                                transfer['from'] == dayNumber.toString() || 
                                transfer['to'] == dayNumber.toString()
                            );

                            return AnimatedContainer(
                              duration: const Duration(milliseconds: 500),
                              child: Material(
                                elevation: isRecentlyRedistributed && isRedistributing ? 6 : 2,
                                borderRadius: BorderRadius.circular(12),
                                color: _getDayColor(status),
                                child: InkWell(
                                  borderRadius: BorderRadius.circular(12),
                                  onTap: () => Navigator.pushNamed(
                                    context, 
                                    '/daily_budget',
                                    arguments: {'day': dayNumber, 'month': currentMonth.month, 'year': currentMonth.year},
                                  ),
                                  child: Container(
                                    padding: const EdgeInsets.all(8.0),
                                    decoration: BoxDecoration(
                                      borderRadius: BorderRadius.circular(12),
                                      border: isRecentlyRedistributed && !isRedistributing
                                        ? Border.all(color: colorScheme.primary, width: 2)
                                        : null,
                                    ),
                                    child: Column(
                                      mainAxisAlignment: MainAxisAlignment.center,
                                      children: [
                                        Row(
                                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                          children: [
                                            Text(
                                              dayNumber.toString(),
                                              style: textTheme.titleLarge?.copyWith(
                                                fontWeight: FontWeight.bold,
                                                color: _getOnDayColor(status),
                                              ),
                                            ),
                                            if (isRecentlyRedistributed && !isRedistributing)
                                              Icon(
                                                Icons.auto_fix_high,
                                                size: 12,
                                                color: _getOnDayColor(status).withOpacity(0.8),
                                              ),
                                          ],
                                        ),
                                        const SizedBox(height: 4),
                                        Text(
                                          '\$$limit',
                                          style: textTheme.bodySmall?.copyWith(
                                            color: _getOnDayColor(status).withValues(alpha: 0.8),
                                            fontWeight: FontWeight.w500,
                                          ),
                                        ),
                                        if (spent > 0) ...[
                                          const SizedBox(height: 2),
                                          Text(
                                            'Spent: \$$spent',
                                            style: textTheme.bodySmall?.copyWith(
                                              color: _getOnDayColor(status).withValues(alpha: 0.7),
                                              fontSize: 10,
                                            ),
                                          ),
                                          const SizedBox(height: 2),
                                          LinearProgressIndicator(
                                            value: (spent / limit).clamp(0.0, 1.0),
                                            backgroundColor: _getOnDayColor(status).withOpacity(0.3),
                                            valueColor: AlwaysStoppedAnimation<Color>(_getOnDayColor(status)),
                                            minHeight: 2,
                                          ),
                                        ],
                                      ],
                                    ),
                                  ),
                                ),
                              ),
                            );
                          },
                        ),
                      );
                    },
                  ),
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

  Widget _buildAISnapshotSummary() {
    final rating = _aiSnapshot!['rating'] ?? 'B';
    final risk = _aiSnapshot!['risk'] ?? 'moderate';
    final colorScheme = Theme.of(context).colorScheme;
    
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: colorScheme.primary.withOpacity(0.05),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: colorScheme.primary.withOpacity(0.2),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(
                Icons.assessment,
                size: 16,
                color: colorScheme.primary,
              ),
              const SizedBox(width: 6),
              Text(
                'Financial Rating',
                style: TextStyle(
                  fontSize: 14,
                  fontWeight: FontWeight.w600,
                  color: colorScheme.onSurface,
                ),
              ),
              const Spacer(),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                decoration: BoxDecoration(
                  color: _getRatingColor(rating).withOpacity(0.1),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Text(
                  rating,
                  style: TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.bold,
                    color: _getRatingColor(rating),
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            _aiSnapshot!['summary'] ?? 'AI analysis of your spending patterns',
            style: TextStyle(
              fontSize: 12,
              color: colorScheme.onSurface.withOpacity(0.8),
              height: 1.3,
            ),
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
          ),
        ],
      ),
    );
  }

  Widget _buildSpendingPatternsPreview() {
    final patterns = List<String>.from(_spendingPatterns!['patterns'] ?? []);
    if (patterns.isEmpty) return Container();
    
    final colorScheme = Theme.of(context).colorScheme;
    
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.orange.withOpacity(0.05),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: Colors.orange.withOpacity(0.2),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(
                Icons.trending_up,
                size: 16,
                color: Colors.orange,
              ),
              const SizedBox(width: 6),
              Text(
                'Spending Patterns',
                style: TextStyle(
                  fontSize: 14,
                  fontWeight: FontWeight.w600,
                  color: colorScheme.onSurface,
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Wrap(
            spacing: 6,
            runSpacing: 4,
            children: patterns.take(3).map((pattern) => Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
              decoration: BoxDecoration(
                color: Colors.orange.withOpacity(0.1),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Text(
                _formatPatternName(pattern),
                style: const TextStyle(
                  fontSize: 10,
                  fontWeight: FontWeight.w500,
                  color: Colors.orange,
                ),
              ),
            )).toList(),
          ),
        ],
      ),
    );
  }

  Widget _buildWeeklyInsightsPreview() {
    final insights = _weeklyInsights!['insights'] ?? '';
    final trend = _weeklyInsights!['trend'] ?? 'stable';
    final colorScheme = Theme.of(context).colorScheme;
    
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.blue.withOpacity(0.05),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: Colors.blue.withOpacity(0.2),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(
                Icons.calendar_view_week,
                size: 16,
                color: Colors.blue,
              ),
              const SizedBox(width: 6),
              Text(
                'Weekly Trend',
                style: TextStyle(
                  fontSize: 14,
                  fontWeight: FontWeight.w600,
                  color: colorScheme.onSurface,
                ),
              ),
              const Spacer(),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                decoration: BoxDecoration(
                  color: _getTrendColor(trend).withOpacity(0.1),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(
                      _getTrendIcon(trend),
                      size: 12,
                      color: _getTrendColor(trend),
                    ),
                    const SizedBox(width: 2),
                    Text(
                      trend.capitalize(),
                      style: TextStyle(
                        fontSize: 10,
                        fontWeight: FontWeight.w500,
                        color: _getTrendColor(trend),
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            insights.length > 80 ? '${insights.substring(0, 80)}...' : insights,
            style: TextStyle(
              fontSize: 12,
              color: colorScheme.onSurface.withOpacity(0.8),
              height: 1.3,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildAnomaliesAlert() {
    final colorScheme = Theme.of(context).colorScheme;
    
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.red.withOpacity(0.05),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: Colors.red.withOpacity(0.3),
        ),
      ),
      child: Row(
        children: [
          const Icon(
            Icons.warning_amber,
            size: 16,
            color: Colors.red,
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              '${_spendingAnomalies.length} spending anomaly detected',
              style: TextStyle(
                fontSize: 12,
                fontWeight: FontWeight.w500,
                color: colorScheme.onSurface,
              ),
            ),
          ),
          const Icon(
            Icons.arrow_forward_ios,
            size: 12,
            color: Colors.red,
          ),
        ],
      ),
    );
  }

  Widget _buildBudgetSuggestionsPreview() {
    final suggestions = _budgetSuggestions['suggestions'] as List<dynamic>? ?? [];
    if (suggestions.isEmpty) return Container();
    
    final colorScheme = Theme.of(context).colorScheme;
    
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.green.withOpacity(0.05),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: Colors.green.withOpacity(0.2),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(
                Icons.lightbulb_outline,
                size: 16,
                color: Colors.green,
              ),
              const SizedBox(width: 6),
              Text(
                'Budget Suggestions',
                style: TextStyle(
                  fontSize: 14,
                  fontWeight: FontWeight.w600,
                  color: colorScheme.onSurface,
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            suggestions.first['text'] ?? 'Smart budget optimization available',
            style: TextStyle(
              fontSize: 12,
              color: colorScheme.onSurface.withOpacity(0.8),
              height: 1.3,
            ),
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
          ),
        ],
      ),
    );
  }

  Color _getRatingColor(String rating) {
    switch (rating.toUpperCase()) {
      case 'A':
      case 'A+':
        return Colors.green;
      case 'B':
      case 'B+':
        return Colors.blue;
      case 'C':
      case 'C+':
        return Colors.orange;
      default:
        return Colors.red;
    }
  }

  IconData _getTrendIcon(String trend) {
    switch (trend.toLowerCase()) {
      case 'improving':
        return Icons.trending_up;
      case 'declining':
        return Icons.trending_down;
      default:
        return Icons.trending_flat;
    }
  }

  Color _getTrendColor(String trend) {
    switch (trend.toLowerCase()) {
      case 'improving':
        return Colors.green;
      case 'declining':
        return Colors.red;
      default:
        return Colors.orange;
    }
  }

  String _formatPatternName(String pattern) {
    return pattern
        .replaceAll('_', ' ')
        .split(' ')
        .map((word) => word.capitalize())
        .join(' ');
  }
}

