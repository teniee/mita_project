import 'dart:developer' as dev;
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../theme/app_colors.dart';
import '../theme/app_typography.dart';
import '../providers/user_provider.dart';
import '../providers/budget_provider.dart';
import '../providers/transaction_provider.dart';
import '../services/income_service.dart';
import '../services/logging_service.dart';

class MainScreen extends StatefulWidget {
  const MainScreen({super.key});

  @override
  State<MainScreen> createState() => _MainScreenState();
}

class _MainScreenState extends State<MainScreen> {
  final IncomeService _incomeService = IncomeService();

  // Income tier info (derived from user provider)
  IncomeTier? _incomeTier;
  double _monthlyIncome = 0.0;

  // AI Insights Data (can be moved to a separate provider later)
  Map<String, dynamic>? aiSnapshot;
  Map<String, dynamic>? financialHealthScore;
  Map<String, dynamic>? weeklyInsights;
  List<Map<String, dynamic>> spendingAnomalies = [];

  // Local advice data
  Map<String, dynamic>? latestAdvice;

  // Income-based data
  Map<String, dynamic>? incomeClassification;
  Map<String, dynamic>? peerComparison;
  Map<String, dynamic>? cohortInsights;

  @override
  void initState() {
    super.initState();
    if (kDebugMode)
      dev.log('initState called - starting initialization', name: 'MainScreen');

    // Initialize providers after first frame
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _initializeProviders();
    });

    if (kDebugMode)
      dev.log('initState completed - initialization scheduled',
          name: 'MainScreen');
  }

  /// Initialize providers and load data
  Future<void> _initializeProviders() async {
    try {
      if (kDebugMode)
        dev.log('_initializeProviders started', name: 'MainScreen');

      final userProvider = context.read<UserProvider>();
      final budgetProvider = context.read<BudgetProvider>();
      final transactionProvider = context.read<TransactionProvider>();

      // Initialize user provider first
      await userProvider.initialize();
      if (kDebugMode) dev.log('UserProvider initialized', name: 'MainScreen');

      // Check if user needs to complete onboarding
      final financialContext = userProvider.financialContext;
      if (financialContext['needs_onboarding'] == true) {
        logInfo('User needs to complete onboarding - redirecting',
            tag: 'MAIN_SCREEN');
        if (mounted) {
          Navigator.pushReplacementNamed(context, '/onboarding_location');
          return;
        }
      }

      // Initialize budget and transaction providers in parallel
      await Future.wait([
        budgetProvider.initialize(),
        transactionProvider.initialize(),
      ]);
      if (kDebugMode)
        dev.log('Budget and Transaction providers initialized',
            name: 'MainScreen');

      // Update income-based data from user provider
      _updateIncomeData(userProvider);

      logDebug('All providers initialized successfully', tag: 'MAIN_SCREEN');
    } catch (e) {
      if (kDebugMode)
        dev.log('ERROR in _initializeProviders: $e',
            name: 'MainScreen', error: e);
      logError('Error initializing providers: $e', tag: 'MAIN_SCREEN');
    }
  }

  /// Update income-based data from user provider
  void _updateIncomeData(UserProvider userProvider) {
    final financialContext = userProvider.financialContext;

    // Check for API errors
    if (financialContext['api_error'] == true) {
      logWarning('API error detected in financial context', tag: 'MAIN_SCREEN');
      return;
    }

    // Check for incomplete onboarding
    if (financialContext['incomplete_onboarding'] == true) {
      logWarning('Incomplete onboarding detected', tag: 'MAIN_SCREEN');
      _loadSafeIncompleteState();
      return;
    }

    // Extract income from financial context
    final income = (financialContext['income'] as num?)?.toDouble() ?? 0.0;

    if (income > 0) {
      _monthlyIncome = income;
      _incomeTier = _incomeService.classifyIncome(_monthlyIncome);

      // Set up income-based data
      incomeClassification = _getDefaultIncomeClassification();
      peerComparison = _getDefaultPeerComparison();
      cohortInsights = _getDefaultCohortInsights();
      latestAdvice = _getDefaultAdvice();

      // Update financial health score from budget insights
      final budgetProvider = context.read<BudgetProvider>();
      if (budgetProvider.budgetSuggestions['confidence'] != null) {
        financialHealthScore = {
          'score':
              (budgetProvider.budgetSuggestions['confidence'] * 100).round(),
          'grade': _getGradeFromConfidence(
              budgetProvider.budgetSuggestions['confidence']),
        };
      }
    } else {
      _loadSafeIncompleteState();
    }

    if (mounted) {
      setState(() {});
    }
  }

  /// Load safe incomplete state when user has incomplete/missing data
  void _loadSafeIncompleteState() {
    if (kDebugMode)
      dev.log('_loadSafeIncompleteState() called', name: 'MainScreen');

    // Set safe default values for incomplete state
    _monthlyIncome = 0.0;
    _incomeTier = null;

    latestAdvice = {
      'text':
          'Complete your profile setup to get personalized financial insights and budget recommendations.',
      'title': 'Complete Your Profile',
      'action': 'complete_profile',
    };

    // Set empty income-based data
    incomeClassification = null;
    peerComparison = null;
    cohortInsights = null;

    aiSnapshot = null;
    financialHealthScore = null;
    weeklyInsights = null;
    spendingAnomalies = [];

    logDebug('Safe incomplete state loaded - user can complete profile',
        tag: 'MAIN_SCREEN');
  }

  /// User-initiated refresh
  Future<void> refreshData() async {
    try {
      final userProvider = context.read<UserProvider>();
      final budgetProvider = context.read<BudgetProvider>();
      final transactionProvider = context.read<TransactionProvider>();

      // Refresh all providers
      await Future.wait([
        userProvider.refreshUserData(),
        budgetProvider.loadAllBudgetData(),
        transactionProvider.loadRecentTransactions(),
      ]);

      // Update income data
      _updateIncomeData(userProvider);

      // Show brief success message
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Dashboard refreshed'),
            duration: Duration(seconds: 1),
            behavior: SnackBarBehavior.floating,
          ),
        );
      }
    } catch (e) {
      logWarning('Manual refresh failed: $e', tag: 'MAIN_SCREEN');
    }
  }

  Map<String, dynamic>? _getDefaultIncomeClassification() {
    if (_monthlyIncome <= 0 || _incomeTier == null) {
      return null;
    }
    return {
      'monthly_income': _monthlyIncome,
      'tier': _incomeTier.toString().split('.').last,
      'tier_name': _incomeService.getIncomeTierName(_incomeTier!),
      'range': _incomeService.getIncomeRangeString(_incomeTier!),
    };
  }

  Map<String, dynamic>? _getDefaultPeerComparison() {
    if (_monthlyIncome <= 0) {
      return null;
    }
    return {
      'error': 'Peer comparison data not available',
      'your_spending': null,
      'peer_average': null,
      'peer_median': null,
      'percentile': null,
      'categories': {},
      'insights': [
        'Peer comparison data will be available once you start tracking expenses'
      ],
    };
  }

  Map<String, dynamic>? _getDefaultCohortInsights() {
    if (_monthlyIncome <= 0) {
      return null;
    }
    return {
      'error': 'Cohort insights data not available',
      'cohort_size': null,
      'your_rank': null,
      'percentile': null,
      'top_insights': [
        'Cohort insights will be available once you start tracking expenses'
      ],
    };
  }

  Map<String, dynamic> _getDefaultAdvice() => {
        'text':
            'Start tracking your expenses to receive personalized financial insights and advice.',
        'title': 'Getting Started',
      };

  List<Map<String, dynamic>> _generateWeekData() {
    final days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
    return List.generate(
        7,
        (index) => {
              'day': days[index],
              'status': 'neutral',
            });
  }

  Widget _buildErrorState(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;

    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24.0),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              Icons.error_outline_rounded,
              size: 80,
              color: colorScheme.error,
            ),
            const SizedBox(height: 24),
            Text(
              'Unable to load dashboard',
              style: textTheme.headlineSmall?.copyWith(
                fontWeight: FontWeight.bold,
                color: colorScheme.onSurface,
              ),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 16),
            Text(
              'Please check your connection and try again',
              textAlign: TextAlign.center,
              style: textTheme.bodyLarge?.copyWith(
                color: colorScheme.onSurfaceVariant,
              ),
            ),
            const SizedBox(height: 32),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton.icon(
                onPressed: refreshData,
                icon: const Icon(Icons.refresh_rounded),
                label: const Text('Try Again'),
                style: ElevatedButton.styleFrom(
                  padding: const EdgeInsets.symmetric(vertical: 16),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;

    // Watch providers for reactive updates
    final userProvider = context.watch<UserProvider>();
    final budgetProvider = context.watch<BudgetProvider>();
    final transactionProvider = context.watch<TransactionProvider>();

    // Determine loading and error states from providers
    final isLoading = userProvider.isLoading ||
        budgetProvider.isLoading ||
        transactionProvider.isLoading;

    final hasError = userProvider.errorMessage != null ||
        budgetProvider.errorMessage != null;

    // Get dashboard data from budget provider
    final dashboardData =
        _buildDashboardData(userProvider, budgetProvider, transactionProvider);

    return Scaffold(
      backgroundColor: colorScheme.surface,
      body: SafeArea(
        child: isLoading && userProvider.state == UserState.loading
            ? Center(
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    CircularProgressIndicator(
                      color: colorScheme.primary,
                    ),
                    const SizedBox(height: 16),
                    Text(
                      'Loading your dashboard...',
                      style: textTheme.bodyLarge?.copyWith(
                        color: colorScheme.onSurface.withValues(alpha: 0.7),
                      ),
                    ),
                  ],
                ),
              )
            : hasError
                ? _buildErrorState(context)
                : RefreshIndicator(
                    onRefresh: refreshData,
                    child: LayoutBuilder(
                      builder: (context, constraints) {
                        return SingleChildScrollView(
                          physics: const AlwaysScrollableScrollPhysics(),
                          child: ConstrainedBox(
                            constraints: BoxConstraints(
                              minHeight: constraints.maxHeight,
                            ),
                            child: Padding(
                              padding: EdgeInsets.symmetric(
                                horizontal:
                                    MediaQuery.of(context).size.width > 600
                                        ? 32.0
                                        : 16.0,
                                vertical: 12.0,
                              ),
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  // Header
                                  _buildHeader(userProvider),
                                  const SizedBox(height: 16),

                                  // Balance Card
                                  _buildBalanceCard(dashboardData),
                                  const SizedBox(height: 16),

                                  // Budget Targets
                                  _buildBudgetTargets(dashboardData),
                                  const SizedBox(height: 16),

                                  // Mini Calendar
                                  _buildMiniCalendar(dashboardData),
                                  const SizedBox(height: 16),

                                  // MODULE 5: Active Goals
                                  _buildActiveGoals(dashboardData),
                                  const SizedBox(height: 16),

                                  // MODULE 5: Active Challenges
                                  _buildActiveChallenges(dashboardData),
                                  const SizedBox(height: 16),

                                  // AI Insights
                                  _buildAIInsightsCard(dashboardData),
                                  const SizedBox(height: 16),

                                  // Recent Transactions
                                  _buildRecentTransactions(transactionProvider),

                                  // Bottom padding for floating action button
                                  const SizedBox(height: 80),
                                ],
                              ),
                            ),
                          ),
                        );
                      },
                    ),
                  ),
      ),
      floatingActionButton: !hasError && !isLoading
          ? Semantics(
              button: true,
              label: 'Add Expense - Record a new expense transaction',
              child: FloatingActionButton.extended(
                heroTag: "main_fab",
                onPressed: () {
                  Navigator.pushNamed(context, '/add_expense');
                },
                icon: const Icon(Icons.add_rounded),
                label: const Text('Add Expense'),
                backgroundColor: colorScheme.primary,
                foregroundColor: colorScheme.onPrimary,
                tooltip: 'Add new expense',
              ),
            )
          : null,
    );
  }

  /// Build dashboard data from providers
  Map<String, dynamic> _buildDashboardData(
    UserProvider userProvider,
    BudgetProvider budgetProvider,
    TransactionProvider transactionProvider,
  ) {
    final financialContext = userProvider.financialContext;
    final hasIncompleteProfile =
        financialContext['incomplete_onboarding'] == true ||
            _monthlyIncome <= 0;
    final hasNetworkError = financialContext['api_error'] == true;

    return {
      'balance': budgetProvider.totalBudget > 0
          ? budgetProvider.totalBudget
          : _monthlyIncome,
      'spent': budgetProvider.totalSpent,
      'daily_targets': _buildDailyTargets(budgetProvider),
      'week': budgetProvider.calendarData.isNotEmpty
          ? _convertCalendarToWeekData(budgetProvider.calendarData)
          : _generateWeekData(),
      'transactions': transactionProvider.transactions
          .take(5)
          .map((t) => {
                'action': t.description,
                'category': t.category,
                'amount': t.amount,
                'date': t.spentAt.toIso8601String(),
                'icon': _getCategoryIcon(t.category),
                'color': _getCategoryColor(t.category),
              })
          .toList(),
      'incomplete_profile': hasIncompleteProfile,
      'network_error': hasNetworkError,
      'data': {
        'goals': [],
        'goals_summary': {},
        'challenges': [],
        'challenges_summary': {},
      },
    };
  }

  /// Build daily targets from budget provider
  List<Map<String, dynamic>> _buildDailyTargets(BudgetProvider budgetProvider) {
    if (_monthlyIncome <= 0) {
      return [];
    }

    final dailyBudget = _monthlyIncome / 30;
    _incomeService.getDefaultBudgetWeights(_incomeTier ?? IncomeTier.middle);

    return [
      {
        'category': 'Food & Dining',
        'limit': dailyBudget * 0.35,
        'spent': 0.0,
        'icon': Icons.restaurant,
        'color': const Color(0xFF4CAF50),
      },
      {
        'category': 'Transportation',
        'limit': dailyBudget * 0.25,
        'spent': 0.0,
        'icon': Icons.directions_car,
        'color': const Color(0xFF2196F3),
      },
      {
        'category': 'Entertainment',
        'limit': dailyBudget * 0.20,
        'spent': 0.0,
        'icon': Icons.movie,
        'color': const Color(0xFF9C27B0),
      },
      {
        'category': 'Shopping',
        'limit': dailyBudget * 0.20,
        'spent': 0.0,
        'icon': Icons.shopping_bag,
        'color': const Color(0xFFFF9800),
      },
    ];
  }

  /// Convert calendar data to week data format
  List<Map<String, dynamic>> _convertCalendarToWeekData(
      List<dynamic> calendarData) {
    final days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
    final now = DateTime.now();
    final weekStart = now.subtract(Duration(days: now.weekday - 1));

    return List.generate(7, (index) {
      final dayDate = weekStart.add(Duration(days: index));
      final dayData = calendarData.firstWhere(
        (d) => d['day'] == dayDate.day,
        orElse: () => {'spent': 0, 'limit': 0},
      );

      final spent = (dayData['spent'] as num?)?.toDouble() ?? 0;
      final limit = (dayData['limit'] as num?)?.toDouble() ?? 0;

      String status = 'neutral';
      if (limit > 0) {
        final ratio = spent / limit;
        if (ratio > 1.0) {
          status = 'over';
        } else if (ratio > 0.8) {
          status = 'warning';
        } else {
          status = 'good';
        }
      }

      return {
        'day': days[index],
        'status': status,
      };
    });
  }

  /// Get category icon
  IconData _getCategoryIcon(String category) {
    switch (category.toLowerCase()) {
      case 'food':
      case 'food & dining':
        return Icons.restaurant;
      case 'transportation':
      case 'transport':
        return Icons.directions_car;
      case 'entertainment':
        return Icons.movie;
      case 'shopping':
        return Icons.shopping_bag;
      case 'utilities':
        return Icons.electrical_services;
      case 'health':
        return Icons.medical_services;
      default:
        return Icons.attach_money;
    }
  }

  /// Get category color
  Color _getCategoryColor(String category) {
    switch (category.toLowerCase()) {
      case 'food':
      case 'food & dining':
        return const Color(0xFF4CAF50);
      case 'transportation':
      case 'transport':
        return const Color(0xFF2196F3);
      case 'entertainment':
        return const Color(0xFF9C27B0);
      case 'shopping':
        return const Color(0xFFFF9800);
      case 'utilities':
        return const Color(0xFF607D8B);
      case 'health':
        return const Color(0xFFE91E63);
      default:
        return const Color(0xFF193C57);
    }
  }

  Widget _buildHeader(UserProvider userProvider) {
    final tierName = _incomeTier != null
        ? _incomeService.getIncomeTierName(_incomeTier!)
        : userProvider.userName;
    final primaryColor = _incomeTier != null
        ? _incomeService.getIncomeTierPrimaryColor(_incomeTier!)
        : const Color(0xFF193C57);
    final hasIncompleteProfile =
        userProvider.financialContext['incomplete_onboarding'] == true ||
            _monthlyIncome <= 0;
    final hasNetworkError = userProvider.financialContext['api_error'] == true;

    return Row(
      children: [
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Hello, $tierName!',
                style: TextStyle(
                  fontFamily: 'Sora',
                  fontWeight: FontWeight.bold,
                  fontSize: 24,
                  color: primaryColor,
                ),
              ),
              if (_monthlyIncome > 0)
                Text(
                  'Monthly income: \$${_monthlyIncome.toStringAsFixed(0)}',
                  style: TextStyle(
                    fontFamily: 'Manrope',
                    fontSize: 14,
                    color: Colors.grey[600],
                  ),
                )
              else if (hasIncompleteProfile)
                GestureDetector(
                  onTap: () =>
                      Navigator.pushNamed(context, '/onboarding_location'),
                  child: Row(
                    children: [
                      Icon(
                        Icons.info_outline,
                        size: 16,
                        color: Colors.orange[600],
                      ),
                      const SizedBox(width: 4),
                      Text(
                        'Complete your profile for personalized insights',
                        style: TextStyle(
                          fontFamily: 'Manrope',
                          fontSize: 14,
                          color: Colors.orange[600],
                          decoration: TextDecoration.underline,
                        ),
                      ),
                    ],
                  ),
                )
              else if (hasNetworkError)
                Row(
                  children: [
                    Icon(
                      Icons.cloud_off,
                      size: 16,
                      color: Colors.red[600],
                    ),
                    const SizedBox(width: 4),
                    Text(
                      'Connection issue - tap refresh to retry',
                      style: TextStyle(
                        fontFamily: 'Manrope',
                        fontSize: 14,
                        color: Colors.red[600],
                      ),
                    ),
                  ],
                )
              else
                GestureDetector(
                  onTap: () =>
                      Navigator.pushNamed(context, '/onboarding_location'),
                  child: Text(
                    'Tap to complete your profile',
                    style: TextStyle(
                      fontFamily: 'Manrope',
                      fontSize: 14,
                      color: Colors.blue[600],
                      decoration: TextDecoration.underline,
                    ),
                  ),
                ),
            ],
          ),
        ),

        // Profile and Settings buttons
        Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            // Profile button
            Container(
              decoration: BoxDecoration(
                color: primaryColor.withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(12),
              ),
              child: IconButton(
                onPressed: () => Navigator.pushNamed(context, '/profile'),
                icon: Icon(
                  Icons.person_outline,
                  color: primaryColor,
                  size: 24,
                ),
                tooltip: 'Profile',
              ),
            ),
            const SizedBox(width: 8),

            // Settings button
            Container(
              decoration: BoxDecoration(
                color: Colors.grey.withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(12),
              ),
              child: IconButton(
                onPressed: () => Navigator.pushNamed(context, '/settings'),
                icon: Icon(
                  Icons.settings_outlined,
                  color: Colors.grey[600],
                  size: 24,
                ),
                tooltip: 'Settings',
              ),
            ),
          ],
        ),
      ],
    );
  }

  Widget _buildBalanceCard(Map<String, dynamic> dashboardData) {
    final balance = dashboardData['balance'] ?? 0;
    final spent = dashboardData['spent'] ?? 0;
    final remaining =
        (balance is num && spent is num) ? balance - spent : balance;
    final primaryColor = _incomeTier != null
        ? _incomeService.getIncomeTierPrimaryColor(_incomeTier!)
        : const Color(0xFFFFD25F);

    return Card(
      color: primaryColor,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
      elevation: 4,
      child: Container(
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(20),
          gradient: LinearGradient(
            colors: [primaryColor, primaryColor.withValues(alpha: 0.8)],
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
          ),
        ),
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(
                    'Current Balance',
                    style: TextStyle(
                      fontFamily: 'Manrope',
                      fontSize: 16,
                      fontWeight: FontWeight.w500,
                      color: Colors.white,
                    ),
                  ),
                  Icon(Icons.account_balance_wallet, color: Colors.white),
                ],
              ),
              const SizedBox(height: 12),
              Text(
                '\$${balance.toStringAsFixed(2)}',
                style: const TextStyle(
                  fontFamily: 'Sora',
                  fontSize: 32,
                  fontWeight: FontWeight.bold,
                  color: Colors.white,
                ),
              ),
              const SizedBox(height: 12),
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Today Spent',
                        style: TextStyle(
                          fontFamily: 'Manrope',
                          fontSize: 12,
                          color: Colors.white.withValues(alpha: 0.8),
                        ),
                      ),
                      Text(
                        '\$${spent.toStringAsFixed(2)}',
                        style: const TextStyle(
                          fontFamily: 'Sora',
                          fontSize: 16,
                          fontWeight: FontWeight.bold,
                          color: Colors.white,
                        ),
                      ),
                    ],
                  ),
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.end,
                    children: [
                      Text(
                        'Remaining',
                        style: TextStyle(
                          fontFamily: 'Manrope',
                          fontSize: 12,
                          color: Colors.white.withValues(alpha: 0.8),
                        ),
                      ),
                      Text(
                        '\$${remaining.toStringAsFixed(2)}',
                        style: const TextStyle(
                          fontFamily: 'Sora',
                          fontSize: 16,
                          fontWeight: FontWeight.bold,
                          color: Colors.white,
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildBudgetTargets(Map<String, dynamic> dashboardData) {
    final targets = dashboardData['daily_targets'] ?? [];
    final primaryColor = _incomeTier != null
        ? _incomeService.getIncomeTierPrimaryColor(_incomeTier!)
        : const Color(0xFF193C57);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(
              "Today's Budget Targets",
              style: TextStyle(
                fontFamily: 'Sora',
                fontSize: 18,
                fontWeight: FontWeight.w600,
                color: primaryColor,
              ),
            ),
            GestureDetector(
              onTap: () => Navigator.pushNamed(context, '/daily_budget'),
              child: const Text(
                'View All',
                style: TextStyle(
                  fontFamily: 'Manrope',
                  fontSize: 14,
                  color: Color(0xFFFFD25F),
                  fontWeight: FontWeight.w600,
                ),
              ),
            ),
          ],
        ),
        const SizedBox(height: 12),
        if (targets.isEmpty)
          Card(
            shape:
                RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
            child: const Padding(
              padding: EdgeInsets.all(20),
              child: Center(
                child: Text(
                  'No budget targets set for today',
                  style: TextStyle(
                    fontFamily: 'Manrope',
                    color: Colors.grey,
                  ),
                ),
              ),
            ),
          )
        else
          ...targets.map<Widget>((target) {
            final limit =
                double.tryParse(target['limit']?.toString() ?? '0') ?? 0.0;
            final spent =
                double.tryParse(target['spent']?.toString() ?? '0') ?? 0.0;
            final progress = limit > 0 ? spent / limit : 0.0;
            final remaining = limit - spent;
            final categoryIcon = target['icon'] as IconData? ?? Icons.category;
            final categoryColor = target['color'] as Color? ?? primaryColor;

            Color progressColor;
            if (progress <= 0.7) {
              progressColor = const Color(0xFF4CAF50);
            } else if (progress <= 0.9) {
              progressColor = const Color(0xFFFF9800);
            } else {
              progressColor = const Color(0xFFFF5722);
            }

            return Card(
              margin: const EdgeInsets.only(bottom: 12),
              shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(16)),
              elevation: 3,
              child: Container(
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(16),
                  gradient: LinearGradient(
                    colors: [
                      Colors.white,
                      categoryColor.withValues(alpha: 0.02),
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
                        children: [
                          Container(
                            padding: const EdgeInsets.all(10),
                            decoration: BoxDecoration(
                              color: categoryColor.withValues(alpha: 0.1),
                              borderRadius: BorderRadius.circular(12),
                            ),
                            child: Icon(
                              categoryIcon,
                              color: categoryColor,
                              size: 24,
                            ),
                          ),
                          const SizedBox(width: 16),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  target['category'] ?? 'Category',
                                  style: TextStyle(
                                    fontFamily: 'Sora',
                                    fontWeight: FontWeight.w600,
                                    fontSize: 16,
                                    color: primaryColor,
                                  ),
                                ),
                                const SizedBox(height: 2),
                                Text(
                                  '\$${spent.toStringAsFixed(0)} of \$${limit.toStringAsFixed(0)}',
                                  style: TextStyle(
                                    fontFamily: 'Manrope',
                                    fontSize: 14,
                                    color: Colors.grey.shade600,
                                    fontWeight: FontWeight.w500,
                                  ),
                                ),
                              ],
                            ),
                          ),
                          Container(
                            padding: const EdgeInsets.symmetric(
                                horizontal: 12, vertical: 6),
                            decoration: BoxDecoration(
                              color: progressColor.withValues(alpha: 0.1),
                              borderRadius: BorderRadius.circular(20),
                              border: Border.all(
                                  color: progressColor.withValues(alpha: 0.3)),
                            ),
                            child: Text(
                              '${(progress * 100).toStringAsFixed(0)}%',
                              style: TextStyle(
                                fontFamily: 'Sora',
                                fontSize: 12,
                                color: progressColor,
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 16),
                      Container(
                        height: 8,
                        decoration: BoxDecoration(
                          borderRadius: BorderRadius.circular(4),
                          color: Colors.grey.shade200,
                        ),
                        child: FractionallySizedBox(
                          alignment: Alignment.centerLeft,
                          widthFactor: progress.clamp(0.0, 1.0),
                          child: Container(
                            decoration: BoxDecoration(
                              borderRadius: BorderRadius.circular(4),
                              color: progressColor,
                            ),
                          ),
                        ),
                      ),
                      const SizedBox(height: 12),
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Text(
                            remaining > 0
                                ? 'Remaining: \$${remaining.toStringAsFixed(0)}'
                                : 'Over budget: \$${(-remaining).toStringAsFixed(0)}',
                            style: TextStyle(
                              fontFamily: 'Manrope',
                              fontSize: 13,
                              color: remaining > 0
                                  ? Colors.grey[600]
                                  : Colors.red.shade600,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                          if (progress <= 0.7)
                            Icon(
                              Icons.check_circle,
                              color: progressColor,
                              size: 16,
                            )
                          else if (progress <= 0.9)
                            Icon(
                              Icons.warning,
                              color: progressColor,
                              size: 16,
                            )
                          else
                            Icon(
                              Icons.error,
                              color: progressColor,
                              size: 16,
                            ),
                        ],
                      ),
                    ],
                  ),
                ),
              ),
            );
          }).toList(),
      ],
    );
  }

  Widget _buildMiniCalendar(Map<String, dynamic> dashboardData) {
    final week = dashboardData['week'] ?? [];

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          'This Week',
          style: TextStyle(
            fontFamily: 'Sora',
            fontSize: 18,
            fontWeight: FontWeight.w600,
            color: Color(0xFF193C57),
          ),
        ),
        const SizedBox(height: 8),
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: week.map<Widget>((day) {
            Color color;
            switch (day['status']) {
              case 'over':
                color = const Color(0xFFFF5C5C);
                break;
              case 'warning':
                color = const Color(0xFFFFD25F);
                break;
              case 'good':
                color = const Color(0xFF84FAA1);
                break;
              default:
                color = Colors.grey.shade300;
            }

            return Container(
              width: 42,
              height: 50,
              decoration: BoxDecoration(
                color: color,
                borderRadius: BorderRadius.circular(12),
              ),
              alignment: Alignment.center,
              child: Text(day['day'],
                  style: const TextStyle(fontWeight: FontWeight.bold)),
            );
          }).toList(),
        ),
      ],
    );
  }

  /// MODULE 5: Build Active Goals Widget
  Widget _buildActiveGoals(Map<String, dynamic> dashboardData) {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;

    // Get goals data from dashboard
    final goalsData = dashboardData['data']?['goals'] as List<dynamic>? ?? [];
    final goalsSummary =
        dashboardData['data']?['goals_summary'] as Map<String, dynamic>? ?? {};

    final totalActive = goalsSummary['total_active'] ?? 0;
    final nearCompletion = goalsSummary['near_completion'] ?? 0;
    final overdue = goalsSummary['overdue'] ?? 0;

    // If no goals, show empty state
    if (goalsData.isEmpty && totalActive == 0) {
      return GestureDetector(
        onTap: () {
          Navigator.pushNamed(context, '/goals');
        },
        child: Container(
          padding: const EdgeInsets.all(20),
          decoration: BoxDecoration(
            color: colorScheme.surface,
            borderRadius: BorderRadius.circular(16),
            border: Border.all(
              color: colorScheme.outline.withValues(alpha: 0.2),
              width: 1,
            ),
          ),
          child: Column(
            children: [
              Icon(
                Icons.flag_outlined,
                size: 48,
                color: colorScheme.primary.withValues(alpha: 0.5),
              ),
              const SizedBox(height: 12),
              Text(
                'No Active Goals',
                style: textTheme.titleMedium?.copyWith(
                  color: colorScheme.onSurface,
                  fontWeight: FontWeight.w600,
                ),
              ),
              const SizedBox(height: 6),
              Text(
                'Start tracking your financial goals',
                style: textTheme.bodyMedium?.copyWith(
                  color: colorScheme.onSurface.withValues(alpha: 0.7),
                ),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 12),
              TextButton.icon(
                onPressed: () {
                  Navigator.pushNamed(context, '/goals');
                },
                icon: const Icon(Icons.add_circle_outline),
                label: const Text('Create Goal'),
              ),
            ],
          ),
        ),
      );
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // Header with summary
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Row(
              children: [
                Icon(
                  Icons.flag,
                  color: colorScheme.primary,
                  size: 20,
                ),
                const SizedBox(width: 8),
                Text(
                  'Active Goals',
                  style: textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.bold,
                    color: colorScheme.onSurface,
                  ),
                ),
                if (totalActive > 0) ...[
                  const SizedBox(width: 8),
                  Container(
                    padding:
                        const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                    decoration: BoxDecoration(
                      color: colorScheme.primaryContainer,
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Text(
                      '$totalActive',
                      style: textTheme.labelSmall?.copyWith(
                        color: colorScheme.onPrimaryContainer,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ),
                ],
              ],
            ),
            TextButton(
              onPressed: () {
                Navigator.pushNamed(context, '/goals');
              },
              child: const Text('View All'),
            ),
          ],
        ),

        // Warnings row (if any)
        if (nearCompletion > 0 || overdue > 0) ...[
          const SizedBox(height: 8),
          Row(
            children: [
              if (nearCompletion > 0) ...[
                Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                  decoration: BoxDecoration(
                    color: const Color(0xFFFFD25F).withValues(alpha: 0.2),
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(
                      color: const Color(0xFFFFD25F),
                      width: 1,
                    ),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const Icon(
                        Icons.star,
                        size: 14,
                        color: Color(0xFFFFD25F),
                      ),
                      const SizedBox(width: 4),
                      Text(
                        '$nearCompletion near completion',
                        style: textTheme.labelSmall?.copyWith(
                          color: colorScheme.onSurface,
                          fontWeight: FontWeight.w500,
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(width: 8),
              ],
              if (overdue > 0) ...[
                Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                  decoration: BoxDecoration(
                    color: Colors.red.withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(
                      color: Colors.red,
                      width: 1,
                    ),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const Icon(
                        Icons.warning_amber_rounded,
                        size: 14,
                        color: Colors.red,
                      ),
                      const SizedBox(width: 4),
                      Text(
                        '$overdue overdue',
                        style: textTheme.labelSmall?.copyWith(
                          color: Colors.red,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ],
          ),
        ],

        const SizedBox(height: 12),

        // Goals list
        ...goalsData.take(3).map((goalData) {
          final goal = goalData as Map<String, dynamic>;
          final title = goal['title'] ?? 'Untitled Goal';
          final progress = (goal['progress'] as num?)?.toDouble() ?? 0.0;
          final targetAmount =
              (goal['target_amount'] as num?)?.toDouble() ?? 0.0;
          final savedAmount = (goal['saved_amount'] as num?)?.toDouble() ?? 0.0;
          final isOverdue = goal['is_overdue'] as bool? ?? false;
          final priority = goal['priority'] ?? 'medium';
          final category = goal['category'] ?? 'Other';

          Color progressColor;
          if (isOverdue) {
            progressColor = Colors.red;
          } else if (progress >= 80) {
            progressColor = Colors.green;
          } else if (progress >= 50) {
            progressColor = const Color(0xFFFFD25F);
          } else {
            progressColor = const Color(0xFF193C57);
          }

          Color priorityColor;
          IconData priorityIcon;
          switch (priority) {
            case 'high':
              priorityColor = Colors.red;
              priorityIcon = Icons.priority_high;
              break;
            case 'low':
              priorityColor = Colors.blue;
              priorityIcon = Icons.low_priority;
              break;
            default:
              priorityColor = Colors.orange;
              priorityIcon = Icons.flag;
          }

          return Container(
            margin: const EdgeInsets.only(bottom: 12),
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              gradient: LinearGradient(
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
                colors: [
                  colorScheme.surface,
                  colorScheme.surfaceContainerHighest.withValues(alpha: 0.3),
                ],
              ),
              borderRadius: BorderRadius.circular(16),
              border: Border.all(
                color: isOverdue
                    ? Colors.red.withValues(alpha: 0.3)
                    : colorScheme.outline.withValues(alpha: 0.2),
                width: 1,
              ),
              boxShadow: [
                BoxShadow(
                  color: colorScheme.shadow.withValues(alpha: 0.05),
                  blurRadius: 8,
                  offset: const Offset(0, 2),
                ),
              ],
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Title and priority
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Expanded(
                      child: Row(
                        children: [
                          Icon(
                            priorityIcon,
                            size: 16,
                            color: priorityColor,
                          ),
                          const SizedBox(width: 8),
                          Expanded(
                            child: Text(
                              title,
                              style: textTheme.titleSmall?.copyWith(
                                fontWeight: FontWeight.bold,
                                color: colorScheme.onSurface,
                              ),
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                        ],
                      ),
                    ),
                    Container(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 8, vertical: 3),
                      decoration: BoxDecoration(
                        color: colorScheme.secondaryContainer,
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: Text(
                        category,
                        style: textTheme.labelSmall?.copyWith(
                          color: colorScheme.onSecondaryContainer,
                          fontSize: 10,
                        ),
                      ),
                    ),
                  ],
                ),

                const SizedBox(height: 12),

                // Progress bar
                ClipRRect(
                  borderRadius: BorderRadius.circular(8),
                  child: LinearProgressIndicator(
                    value: (progress / 100).clamp(0.0, 1.0),
                    backgroundColor: colorScheme.surfaceContainerHighest,
                    color: progressColor,
                    minHeight: 8,
                  ),
                ),

                const SizedBox(height: 8),

                // Amount and progress
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text(
                      '\$${savedAmount.toStringAsFixed(0)} / \$${targetAmount.toStringAsFixed(0)}',
                      style: textTheme.bodyMedium?.copyWith(
                        color: colorScheme.onSurface,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    Text(
                      '${progress.toStringAsFixed(0)}%',
                      style: textTheme.bodyMedium?.copyWith(
                        color: progressColor,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ],
                ),

                // Overdue warning
                if (isOverdue) ...[
                  const SizedBox(height: 8),
                  Container(
                    padding:
                        const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                    decoration: BoxDecoration(
                      color: Colors.red.withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(6),
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        const Icon(
                          Icons.schedule,
                          size: 12,
                          color: Colors.red,
                        ),
                        const SizedBox(width: 4),
                        Text(
                          'Overdue',
                          style: textTheme.labelSmall?.copyWith(
                            color: Colors.red,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ],
            ),
          );
        }),

        // Show more indicator if there are more goals
        if (goalsData.length > 3) ...[
          const SizedBox(height: 8),
          Center(
            child: TextButton.icon(
              onPressed: () {
                Navigator.pushNamed(context, '/goals');
              },
              icon: const Icon(Icons.expand_more),
              label: Text('+${goalsData.length - 3} more goals'),
            ),
          ),
        ],
      ],
    );
  }

  /// MODULE 5: Build Active Challenges Widget
  Widget _buildActiveChallenges(Map<String, dynamic> dashboardData) {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;

    // Get challenges data from dashboard
    final challengesData =
        dashboardData['data']?['challenges'] as List<dynamic>? ?? [];
    final challengesSummary =
        dashboardData['data']?['challenges_summary'] as Map<String, dynamic>? ??
            {};

    final activeChallenges = challengesSummary['active_challenges'] ?? 0;
    final completedThisMonth = challengesSummary['completed_this_month'] ?? 0;
    final currentStreak = challengesSummary['current_streak'] ?? 0;

    // If no challenges, show empty state
    if (challengesData.isEmpty && activeChallenges == 0) {
      return GestureDetector(
        onTap: () {
          Navigator.pushNamed(context, '/challenges');
        },
        child: Container(
          padding: const EdgeInsets.all(20),
          decoration: BoxDecoration(
            gradient: LinearGradient(
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
              colors: [
                const Color(0xFF6A5ACD).withValues(alpha: 0.1),
                const Color(0xFF9370DB).withValues(alpha: 0.05),
              ],
            ),
            borderRadius: BorderRadius.circular(16),
            border: Border.all(
              color: const Color(0xFF6A5ACD).withValues(alpha: 0.3),
              width: 1,
            ),
          ),
          child: Column(
            children: [
              Icon(
                Icons.emoji_events_outlined,
                size: 48,
                color: const Color(0xFF6A5ACD).withValues(alpha: 0.7),
              ),
              const SizedBox(height: 12),
              Text(
                'No Active Challenges',
                style: textTheme.titleMedium?.copyWith(
                  color: colorScheme.onSurface,
                  fontWeight: FontWeight.w600,
                ),
              ),
              const SizedBox(height: 6),
              Text(
                'Join challenges to earn rewards and build habits',
                style: textTheme.bodyMedium?.copyWith(
                  color: colorScheme.onSurface.withValues(alpha: 0.7),
                ),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 12),
              TextButton.icon(
                onPressed: () {
                  Navigator.pushNamed(context, '/challenges');
                },
                icon: const Icon(Icons.add_circle_outline),
                label: const Text('Browse Challenges'),
              ),
            ],
          ),
        ),
      );
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // Header with summary
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Row(
              children: [
                const Icon(
                  Icons.emoji_events,
                  color: Color(0xFF6A5ACD),
                  size: 20,
                ),
                const SizedBox(width: 8),
                Text(
                  'Active Challenges',
                  style: textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.bold,
                    color: colorScheme.onSurface,
                  ),
                ),
                if (activeChallenges > 0) ...[
                  const SizedBox(width: 8),
                  Container(
                    padding:
                        const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                    decoration: BoxDecoration(
                      color: const Color(0xFF6A5ACD).withValues(alpha: 0.2),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Text(
                      '$activeChallenges',
                      style: textTheme.labelSmall?.copyWith(
                        color: const Color(0xFF6A5ACD),
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ),
                ],
              ],
            ),
            TextButton(
              onPressed: () {
                Navigator.pushNamed(context, '/challenges');
              },
              child: const Text('View All'),
            ),
          ],
        ),

        // Stats row
        if (completedThisMonth > 0 || currentStreak > 0) ...[
          const SizedBox(height: 8),
          Row(
            children: [
              if (completedThisMonth > 0) ...[
                Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                  decoration: BoxDecoration(
                    color: Colors.green.withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(
                      color: Colors.green,
                      width: 1,
                    ),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const Icon(
                        Icons.check_circle,
                        size: 14,
                        color: Colors.green,
                      ),
                      const SizedBox(width: 4),
                      Text(
                        '$completedThisMonth completed',
                        style: textTheme.labelSmall?.copyWith(
                          color: Colors.green,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(width: 8),
              ],
              if (currentStreak > 0) ...[
                Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                  decoration: BoxDecoration(
                    color: const Color(0xFFFF5722).withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(
                      color: const Color(0xFFFF5722),
                      width: 1,
                    ),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const Icon(
                        Icons.local_fire_department,
                        size: 14,
                        color: Color(0xFFFF5722),
                      ),
                      const SizedBox(width: 4),
                      Text(
                        '$currentStreak day streak',
                        style: textTheme.labelSmall?.copyWith(
                          color: const Color(0xFFFF5722),
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ],
          ),
        ],

        const SizedBox(height: 12),

        // Challenges list
        ...challengesData.take(3).map((challengeData) {
          final challenge = challengeData as Map<String, dynamic>;
          final name = challenge['name'] ?? 'Challenge';
          final description = challenge['description'] ?? '';
          final difficulty = challenge['difficulty'] ?? 'medium';
          final progressPercentage =
              (challenge['progress_percentage'] as num?)?.toDouble() ?? 0.0;
          final daysCompleted = challenge['days_completed'] ?? 0;
          final durationDays = challenge['duration_days'] ?? 0;
          final rewardPoints = challenge['reward_points'] ?? 0;

          Color difficultyColor;
          IconData difficultyIcon;
          switch (difficulty.toLowerCase()) {
            case 'easy':
              difficultyColor = const Color(0xFF4CAF50);
              difficultyIcon = Icons.star_outline;
              break;
            case 'hard':
              difficultyColor = const Color(0xFFFF5722);
              difficultyIcon = Icons.star;
              break;
            default:
              difficultyColor = const Color(0xFFFF9800);
              difficultyIcon = Icons.star_half;
          }

          return Container(
            margin: const EdgeInsets.only(bottom: 12),
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              gradient: LinearGradient(
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
                colors: [
                  difficultyColor.withValues(alpha: 0.05),
                  difficultyColor.withValues(alpha: 0.02),
                ],
              ),
              borderRadius: BorderRadius.circular(16),
              border: Border.all(
                color: difficultyColor.withValues(alpha: 0.3),
                width: 1,
              ),
              boxShadow: [
                BoxShadow(
                  color: colorScheme.shadow.withValues(alpha: 0.05),
                  blurRadius: 8,
                  offset: const Offset(0, 2),
                ),
              ],
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Title and difficulty
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Expanded(
                      child: Row(
                        children: [
                          Icon(
                            Icons.emoji_events,
                            size: 16,
                            color: difficultyColor,
                          ),
                          const SizedBox(width: 8),
                          Expanded(
                            child: Text(
                              name,
                              style: textTheme.titleSmall?.copyWith(
                                fontWeight: FontWeight.bold,
                                color: colorScheme.onSurface,
                              ),
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                        ],
                      ),
                    ),
                    Container(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 8, vertical: 3),
                      decoration: BoxDecoration(
                        color: difficultyColor.withValues(alpha: 0.15),
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Icon(
                            difficultyIcon,
                            size: 12,
                            color: difficultyColor,
                          ),
                          const SizedBox(width: 4),
                          Text(
                            difficulty.toUpperCase(),
                            style: textTheme.labelSmall?.copyWith(
                              color: difficultyColor,
                              fontWeight: FontWeight.bold,
                              fontSize: 10,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),

                if (description.isNotEmpty) ...[
                  const SizedBox(height: 6),
                  Text(
                    description,
                    style: textTheme.bodySmall?.copyWith(
                      color: colorScheme.onSurface.withValues(alpha: 0.7),
                    ),
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                ],

                const SizedBox(height: 12),

                // Progress bar
                ClipRRect(
                  borderRadius: BorderRadius.circular(8),
                  child: LinearProgressIndicator(
                    value: (progressPercentage / 100).clamp(0.0, 1.0),
                    backgroundColor: colorScheme.surfaceContainerHighest,
                    color: difficultyColor,
                    minHeight: 8,
                  ),
                ),

                const SizedBox(height: 8),

                // Days and progress
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Row(
                      children: [
                        Icon(
                          Icons.calendar_today,
                          size: 14,
                          color: colorScheme.onSurface.withValues(alpha: 0.7),
                        ),
                        const SizedBox(width: 4),
                        Text(
                          '$daysCompleted / $durationDays days',
                          style: textTheme.bodyMedium?.copyWith(
                            color: colorScheme.onSurface,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ],
                    ),
                    Row(
                      children: [
                        const Icon(
                          Icons.stars,
                          size: 14,
                          color: Colors.amber,
                        ),
                        const SizedBox(width: 4),
                        Text(
                          '$rewardPoints pts',
                          style: textTheme.bodyMedium?.copyWith(
                            color: Colors.amber,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ],
            ),
          );
        }),

        // Show more indicator if there are more challenges
        if (challengesData.length > 3) ...[
          const SizedBox(height: 8),
          Center(
            child: TextButton.icon(
              onPressed: () {
                Navigator.pushNamed(context, '/challenges');
              },
              icon: const Icon(Icons.expand_more),
              label: Text('+${challengesData.length - 3} more challenges'),
            ),
          ),
        ],
      ],
    );
  }

  Widget _buildAIInsightsCard(Map<String, dynamic> dashboardData) {
    final hasIncompleteProfile = dashboardData['incomplete_profile'] == true;
    final hasNetworkError = dashboardData['network_error'] == true;

    return GestureDetector(
      onTap: () {
        final advice = latestAdvice ?? {};
        final action = advice['action'] as String?;

        if (action == 'complete_profile' && hasIncompleteProfile) {
          Navigator.pushNamed(context, '/onboarding_location');
        } else if (action == 'retry' && hasNetworkError) {
          refreshData();
        } else {
          Navigator.pushNamed(context, '/insights');
        }
      },
      child: Container(
        padding: const EdgeInsets.all(20),
        decoration: BoxDecoration(
          gradient: LinearGradient(
            colors: [
              const Color(0xFF193C57),
              const Color(0xFF193C57).withValues(alpha: 0.8),
            ],
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
          ),
          borderRadius: BorderRadius.circular(16),
          boxShadow: [
            BoxShadow(
              color: const Color(0xFF193C57).withValues(alpha: 0.3),
              blurRadius: 10,
              offset: const Offset(0, 4),
            ),
          ],
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(
                  Icons.psychology,
                  color: Colors.white,
                  size: 24,
                ),
                const SizedBox(width: 12),
                const Text(
                  'AI Insights',
                  style: TextStyle(
                    fontFamily: 'Sora',
                    fontWeight: FontWeight.bold,
                    fontSize: 18,
                    color: Colors.white,
                  ),
                ),
                const Spacer(),
                Icon(
                  Icons.arrow_forward_ios,
                  color: Colors.white.withValues(alpha: 0.7),
                  size: 16,
                ),
              ],
            ),
            const SizedBox(height: 16),
            if (aiSnapshot != null)
              _buildSnapshotPreview()
            else if (weeklyInsights != null)
              _buildWeeklyInsightsPreview()
            else if (financialHealthScore != null)
              _buildBudgetEngineInsightsPreview()
            else
              _buildAdviceContent(dashboardData),
            if (spendingAnomalies.isNotEmpty) ...[
              const SizedBox(height: 12),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                decoration: BoxDecoration(
                  color: Colors.orange.withValues(alpha: 0.2),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Icon(
                      Icons.warning_amber,
                      size: 16,
                      color: Colors.orange,
                    ),
                    const SizedBox(width: 4),
                    Text(
                      '${spendingAnomalies.length} anomaly detected',
                      style: const TextStyle(
                        fontFamily: 'Manrope',
                        fontSize: 12,
                        color: Colors.orange,
                        fontWeight: FontWeight.w500,
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

  Widget _buildSnapshotPreview() {
    final rating = aiSnapshot!['rating'] ?? 'B';
    final summary = aiSnapshot!['summary'] ?? '';

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
              decoration: BoxDecoration(
                color: Colors.white.withValues(alpha: 0.2),
                borderRadius: BorderRadius.circular(16),
              ),
              child: Text(
                'Rating: $rating',
                style: const TextStyle(
                  fontFamily: 'Sora',
                  fontWeight: FontWeight.w600,
                  fontSize: 12,
                  color: Colors.white,
                ),
              ),
            ),
          ],
        ),
        const SizedBox(height: 8),
        Text(
          summary.length > 100 ? '${summary.substring(0, 100)}...' : summary,
          style: TextStyle(
            fontFamily: 'Manrope',
            fontSize: 14,
            color: Colors.white.withValues(alpha: 0.9),
            height: 1.4,
          ),
        ),
      ],
    );
  }

  Widget _buildWeeklyInsightsPreview() {
    final insights = weeklyInsights!['insights'] ?? '';
    final trend = weeklyInsights!['trend'] ?? 'stable';

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Icon(
              _getTrendIcon(trend),
              color: _getTrendColor(trend),
              size: 16,
            ),
            const SizedBox(width: 6),
            Text(
              'Trend: ${trend.toUpperCase()}',
              style: TextStyle(
                fontFamily: 'Manrope',
                fontWeight: FontWeight.w600,
                fontSize: 12,
                color: _getTrendColor(trend),
              ),
            ),
          ],
        ),
        const SizedBox(height: 8),
        Text(
          insights.length > 100 ? '${insights.substring(0, 100)}...' : insights,
          style: TextStyle(
            fontFamily: 'Manrope',
            fontSize: 14,
            color: Colors.white.withValues(alpha: 0.9),
            height: 1.4,
          ),
        ),
      ],
    );
  }

  Widget _buildBudgetEngineInsightsPreview() {
    final score = financialHealthScore!['score'] ?? 75;
    final grade = financialHealthScore!['grade'] ?? 'B';

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
              decoration: BoxDecoration(
                color: Colors.white.withValues(alpha: 0.2),
                borderRadius: BorderRadius.circular(16),
              ),
              child: Text(
                'Budget Score: $grade',
                style: const TextStyle(
                  fontFamily: 'Sora',
                  fontWeight: FontWeight.w600,
                  fontSize: 12,
                  color: Colors.white,
                ),
              ),
            ),
          ],
        ),
        const SizedBox(height: 8),
        Text(
          'Your personalized budget is ${score >= 80 ? 'excellent' : score >= 70 ? 'good' : 'needs improvement'} and based on your real income, goals, and spending habits.',
          style: TextStyle(
            fontFamily: 'Manrope',
            fontSize: 14,
            color: Colors.white.withValues(alpha: 0.9),
            height: 1.4,
          ),
        ),
      ],
    );
  }

  Widget _buildAdviceContent(Map<String, dynamic> dashboardData) {
    final advice = latestAdvice ?? {};
    final action = advice['action'] as String?;
    final hasIncompleteProfile = dashboardData['incomplete_profile'] == true;
    final hasNetworkError = dashboardData['network_error'] == true;

    // Handle different advice types
    if (action == 'complete_profile' && hasIncompleteProfile) {
      return Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                decoration: BoxDecoration(
                  color: Colors.orange.withValues(alpha: 0.3),
                  borderRadius: BorderRadius.circular(16),
                ),
                child: const Text(
                  'PROFILE INCOMPLETE',
                  style: TextStyle(
                    fontFamily: 'Sora',
                    fontWeight: FontWeight.w600,
                    fontSize: 11,
                    color: Colors.white,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            advice['text'] ??
                'Complete your profile setup to get personalized financial insights and budget recommendations.',
            style: TextStyle(
              fontFamily: 'Manrope',
              fontSize: 14,
              color: Colors.white.withValues(alpha: 0.9),
              height: 1.4,
            ),
            maxLines: 3,
            overflow: TextOverflow.ellipsis,
          ),
        ],
      );
    } else if (action == 'retry' && hasNetworkError) {
      return Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                decoration: BoxDecoration(
                  color: Colors.red.withValues(alpha: 0.3),
                  borderRadius: BorderRadius.circular(16),
                ),
                child: const Text(
                  'CONNECTION ISSUE',
                  style: TextStyle(
                    fontFamily: 'Sora',
                    fontWeight: FontWeight.w600,
                    fontSize: 11,
                    color: Colors.white,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            advice['text'] ??
                'Unable to load your data. Please check your internet connection and try refreshing.',
            style: TextStyle(
              fontFamily: 'Manrope',
              fontSize: 14,
              color: Colors.white.withValues(alpha: 0.9),
              height: 1.4,
            ),
            maxLines: 3,
            overflow: TextOverflow.ellipsis,
          ),
        ],
      );
    } else {
      // Default advice content
      return Text(
        advice['text'] ??
            'Tap to view personalized AI insights based on your real financial data',
        style: TextStyle(
          fontFamily: 'Manrope',
          fontSize: 14,
          color: Colors.white.withValues(alpha: 0.9),
          height: 1.4,
        ),
        maxLines: 3,
        overflow: TextOverflow.ellipsis,
      );
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

  Widget _buildRecentTransactions(TransactionProvider transactionProvider) {
    final transactions = transactionProvider.transactions.take(5).toList();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            const Text(
              'Recent Transactions',
              style: TextStyle(
                fontFamily: 'Sora',
                fontSize: 18,
                fontWeight: FontWeight.w600,
                color: Color(0xFF193C57),
              ),
            ),
            GestureDetector(
              onTap: () => Navigator.pushNamed(context, '/transactions'),
              child: const Text(
                'View All',
                style: TextStyle(
                  fontFamily: 'Manrope',
                  fontSize: 14,
                  color: Color(0xFFFFD25F),
                  fontWeight: FontWeight.w600,
                ),
              ),
            ),
          ],
        ),
        const SizedBox(height: 16),
        if (transactions.isEmpty)
          Card(
            shape:
                RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
            child: const Padding(
              padding: EdgeInsets.all(20),
              child: Center(
                child: Column(
                  children: [
                    Icon(Icons.receipt_long, size: 48, color: Colors.grey),
                    SizedBox(height: 12),
                    Text(
                      'No recent transactions',
                      style: TextStyle(
                        fontFamily: 'Sora',
                        color: Colors.grey,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                  ],
                ),
              ),
            ),
          )
        else
          ...transactions.map((tx) {
            final txIcon = _getCategoryIcon(tx.category);
            final txColor = _getCategoryColor(tx.category);
            final timeAgo = _getTimeAgo(tx.spentAt.toIso8601String());

            return Card(
              margin: const EdgeInsets.only(bottom: 12),
              shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(16)),
              elevation: 2,
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Row(
                  children: [
                    Container(
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: txColor.withValues(alpha: 0.1),
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Icon(
                        txIcon,
                        color: txColor,
                        size: 24,
                      ),
                    ),
                    const SizedBox(width: 16),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            tx.description ?? '',
                            style: const TextStyle(
                              fontFamily: 'Sora',
                              fontWeight: FontWeight.w600,
                              fontSize: 15,
                              color: Color(0xFF193C57),
                            ),
                          ),
                          const SizedBox(height: 2),
                          Row(
                            children: [
                              Text(
                                tx.category,
                                style: TextStyle(
                                  fontFamily: 'Manrope',
                                  fontSize: 12,
                                  color: Colors.grey.shade600,
                                ),
                              ),
                              Text(
                                ' \u2022 $timeAgo',
                                style: TextStyle(
                                  fontFamily: 'Manrope',
                                  fontSize: 12,
                                  color: Colors.grey.shade500,
                                ),
                              ),
                            ],
                          ),
                        ],
                      ),
                    ),
                    Text(
                      '-\$${tx.amount.toStringAsFixed(2)}',
                      style: const TextStyle(
                        fontFamily: 'Sora',
                        fontWeight: FontWeight.bold,
                        fontSize: 16,
                        color: Color(0xFFFF5722),
                      ),
                    ),
                  ],
                ),
              ),
            );
          }),
      ],
    );
  }

  String _getTimeAgo(String? dateString) {
    if (dateString == null) return 'Unknown';

    try {
      final date = DateTime.parse(dateString);
      final now = DateTime.now();
      final difference = now.difference(date);

      if (difference.inMinutes < 60) {
        return '${difference.inMinutes}m ago';
      } else if (difference.inHours < 24) {
        return '${difference.inHours}h ago';
      } else if (difference.inDays < 7) {
        return '${difference.inDays}d ago';
      } else {
        return '${(difference.inDays / 7).floor()}w ago';
      }
    } catch (e) {
      return 'Unknown';
    }
  }

  /// Convert confidence score to letter grade
  String _getGradeFromConfidence(double confidence) {
    if (confidence >= 0.9) return 'A+';
    if (confidence >= 0.85) return 'A';
    if (confidence >= 0.8) return 'A-';
    if (confidence >= 0.75) return 'B+';
    if (confidence >= 0.7) return 'B';
    if (confidence >= 0.65) return 'B-';
    if (confidence >= 0.6) return 'C+';
    if (confidence >= 0.55) return 'C';
    if (confidence >= 0.5) return 'C-';
    return 'D';
  }
}
