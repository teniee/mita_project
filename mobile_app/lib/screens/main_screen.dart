
import 'package:flutter/material.dart';
import 'dart:async';
import '../services/offline_first_provider.dart';
import '../services/live_updates_service.dart';
import '../services/logging_service.dart';
import '../services/income_service.dart';
import '../services/budget_adapter_service.dart';
import '../services/user_data_manager.dart';

class MainScreen extends StatefulWidget {
  const MainScreen({super.key});

  @override
  State<MainScreen> createState() => _MainScreenState();
}

class _MainScreenState extends State<MainScreen> {
  final OfflineFirstProvider _offlineProvider = OfflineFirstProvider();
  final LiveUpdatesService _liveUpdates = LiveUpdatesService();
  final IncomeService _incomeService = IncomeService();
  final BudgetAdapterService _budgetService = BudgetAdapterService();
  
  Map<String, dynamic>? dashboardData;
  Map<String, dynamic>? latestAdvice;
  Map<String, dynamic>? userProfile;
  
  // Income-based data
  Map<String, dynamic>? incomeClassification;
  Map<String, dynamic>? peerComparison;
  Map<String, dynamic>? cohortInsights;
  
  // AI Insights Data
  Map<String, dynamic>? aiSnapshot;
  Map<String, dynamic>? financialHealthScore;
  Map<String, dynamic>? weeklyInsights;
  List<Map<String, dynamic>> spendingAnomalies = [];
  
  bool isLoading = false; // Start as false - we'll show cached data immediately
  String? error;
  
  // Income tier info
  IncomeTier? _incomeTier;
  double _monthlyIncome = 0.0;

  @override
  void initState() {
    super.initState();
    print('CRITICAL DEBUG: MainScreen initState called');
    _initializeOfflineFirst();
    print('CRITICAL DEBUG: MainScreen initState completed');
  }

  /// Initialize offline-first loading - instant UI with cached data
  Future<void> _initializeOfflineFirst() async {
    try {
      print('CRITICAL DEBUG: MainScreen _initializeOfflineFirst started');

      // Initialize offline provider (this is very fast)
      await _offlineProvider.initialize();
      print('CRITICAL DEBUG: MainScreen _offlineProvider.initialize() completed');

      // Load data immediately from cache/fallback
      _loadCachedDataToUI();
      print('CRITICAL DEBUG: MainScreen _loadCachedDataToUI() completed');

      // Set up listener for background sync status
      _offlineProvider.isBackgroundSyncing.addListener(_onBackgroundSyncChanged);
      print('CRITICAL DEBUG: MainScreen background sync listener set up');

      // Initialize live updates
      await _initializeLiveUpdates();
      print('CRITICAL DEBUG: MainScreen _initializeLiveUpdates() completed');

      logDebug('Offline-first initialization completed', tag: 'MAIN_SCREEN');
    } catch (e) {
      print('CRITICAL DEBUG: ERROR in MainScreen _initializeOfflineFirst: $e');
      logError('Error in offline-first initialization: $e', tag: 'MAIN_SCREEN');
      // Still show fallback data
      _loadFallbackData();
    }
  }

  /// Initialize live updates and set up listeners
  Future<void> _initializeLiveUpdates() async {
    try {
      logInfo('Initializing live updates service', tag: 'MAIN_SCREEN');
      
      // Enable live updates with 2-minute intervals
      await _liveUpdates.enableLiveUpdates(const Duration(minutes: 2));
      
      // Set up listeners for real-time data updates
      _liveUpdates.dashboardUpdates.listen((updatedDashboard) {
        if (mounted) {
          setState(() {
            dashboardData = updatedDashboard;
          });
          logDebug('Dashboard updated via live updates', tag: 'MAIN_SCREEN');
        }
      });
      
      _liveUpdates.profileUpdates.listen((updatedProfile) {
        if (mounted) {
          setState(() {
            userProfile = updatedProfile;
          });
          logDebug('Profile updated via live updates', tag: 'MAIN_SCREEN');
        }
      });
      
      _liveUpdates.transactionUpdates.listen((transactionUpdate) {
        if (mounted && transactionUpdate['hasNewTransactions'] == true) {
          // Show notification about new transactions
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: const Row(
                children: [
                  Icon(Icons.account_balance_wallet, color: Colors.white),
                  SizedBox(width: 8),
                  Text('New transaction detected'),
                ],
              ),
              backgroundColor: Theme.of(context).colorScheme.primary,
              behavior: SnackBarBehavior.floating,
              duration: const Duration(seconds: 3),
            ),
          );
          logDebug('New transaction detected via live updates', tag: 'MAIN_SCREEN');
        }
      });
      
      logInfo('Live updates service initialized successfully', tag: 'MAIN_SCREEN');
    } catch (e) {
      logError('Error initializing live updates: $e', tag: 'MAIN_SCREEN');
    }
  }

  /// Load cached data to UI immediately (no loading state)
  void _loadCachedDataToUI() {
    try {
      print('CRITICAL DEBUG: MainScreen _loadCachedDataToUI() started');
      // Load data using new production budget engine
      _loadProductionBudgetData();
      print('CRITICAL DEBUG: MainScreen _loadProductionBudgetData() completed');

      logDebug('Production budget data loaded to UI instantly', tag: 'MAIN_SCREEN');
    } catch (e) {
      print('CRITICAL DEBUG: ERROR in MainScreen _loadCachedDataToUI(): $e');
      logWarning('Error loading production budget data, using fallback', tag: 'MAIN_SCREEN');
      _loadFallbackData();
    }
  }

  /// Load data using production budget engine with real user data
  Future<void> _loadProductionBudgetData() async {
    try {
      print('CRITICAL DEBUG: MainScreen _loadProductionBudgetData() started');
      // Get real user financial context from onboarding/profile data
      final financialContext = await UserDataManager.instance.getFinancialContext();
      print('CRITICAL DEBUG: MainScreen got financial context: $financialContext');
      logInfo('CRITICAL DEBUG: MainScreen got financial context: $financialContext', tag: 'MAIN_SCREEN');

      // Check if onboarding is incomplete
      if (financialContext['incomplete_onboarding'] == true) {
        logWarning('CRITICAL DEBUG: Incomplete onboarding detected - using fallback data', tag: 'MAIN_SCREEN');
        _loadCachedDataFromProvider(); // Use fallback approach
        return;
      }

      // Extract actual user income (not hardcoded)
      _monthlyIncome = financialContext['income'] as double;
      _incomeTier = _incomeService.classifyIncome(_monthlyIncome);
      
      // Get personalized dashboard data using real user data
      final productionDashboard = await _budgetService.getDashboardData();
      final budgetInsights = await _budgetService.getBudgetInsights();
      
      // Set up data using production calculations
      dashboardData = productionDashboard;
      userProfile = {'data': {'income': _monthlyIncome}};
      latestAdvice = _getDefaultAdvice();
      
      // Set up income-based data
      incomeClassification = _getDefaultIncomeClassification();
      peerComparison = _getDefaultPeerComparison();
      cohortInsights = _getDefaultCohortInsights();
      
      // Initialize AI data from production insights
      aiSnapshot = null;
      financialHealthScore = budgetInsights['confidence'] != null ? {
        'score': (budgetInsights['confidence'] * 100).round(),
        'grade': _getGradeFromConfidence(budgetInsights['confidence']),
      } : null;
      weeklyInsights = null;
      spendingAnomalies = [];
      
      // Update UI immediately
      if (mounted) {
        setState(() {
          isLoading = false;
          error = null;
        });
      }
      
      logDebug('Production budget data loaded successfully', tag: 'MAIN_SCREEN');
    } catch (e) {
      print('CRITICAL DEBUG: ERROR in MainScreen _loadProductionBudgetData(): $e');
      logError('Error loading production budget data: $e', tag: 'MAIN_SCREEN', error: e);
      // Fall back to cached data approach
      _loadCachedDataFromProvider();
    }
  }

  /// Fallback to original cached data approach with user data
  Future<void> _loadCachedDataFromProvider() async {
    try {
      // Try to get real user data first
      final financialContext = await UserDataManager.instance.getFinancialContext().timeout(
        const Duration(seconds: 2),
        onTimeout: () => <String, dynamic>{},
      );
      
      // Get cached data from offline provider as backup
      final cachedDashboard = _offlineProvider.getDashboardData();
      final cachedProfile = _offlineProvider.getUserProfile();
      
      // Extract income - require valid user data
      final userIncome = financialContext['income'] as double? ?? 
                        (cachedProfile['data']?['income'] as num?)?.toDouble();
      
      if (userIncome == null || userIncome <= 0) {
        // Redirect to onboarding if no valid income data
        if (mounted) {
          Navigator.pushReplacementNamed(context, '/onboarding_region');
          return;
        }
      }
      
      _monthlyIncome = userIncome!;
      _incomeTier = _incomeService.classifyIncome(_monthlyIncome);
      
      // Process the dashboard data
      dashboardData = _processCachedDashboardData(cachedDashboard);
      userProfile = cachedProfile;
      latestAdvice = _getDefaultAdvice();
      
      // Set up income-based data
      incomeClassification = _getDefaultIncomeClassification();
      peerComparison = _getDefaultPeerComparison();
      cohortInsights = _getDefaultCohortInsights();
      
      // Initialize other data as empty for now
      aiSnapshot = null;
      financialHealthScore = null;
      weeklyInsights = null;
      spendingAnomalies = [];
      
      // Update UI immediately
      if (mounted) {
        setState(() {
          isLoading = false;
          error = null;
        });
      }
      
      logDebug('Cached data loaded to UI instantly', tag: 'MAIN_SCREEN');
    } catch (e) {
      logWarning('Error loading cached data, using fallback', tag: 'MAIN_SCREEN');
      _loadFallbackData();
    }
  }

  /// Load fallback data when cached data is not available
  void _loadFallbackData() {
    // No fallback data - redirect to onboarding
    if (mounted) {
      Navigator.pushReplacementNamed(context, '/onboarding_region');
      return;
    }
    latestAdvice = _getDefaultAdvice();
    incomeClassification = _getDefaultIncomeClassification();
    peerComparison = _getDefaultPeerComparison();
    cohortInsights = _getDefaultCohortInsights();
    
    aiSnapshot = null;
    financialHealthScore = null;
    weeklyInsights = null;
    spendingAnomalies = [];

    if (mounted) {
      setState(() {
        isLoading = false;
        error = null;
      });
    }
    
    logDebug('Fallback data loaded to UI', tag: 'MAIN_SCREEN');
  }

  /// Process cached dashboard data for UI display
  Map<String, dynamic> _processCachedDashboardData(Map<String, dynamic> cachedData) {
    if (cachedData.isEmpty) {
      return _getDefaultDashboard();
    }

    // Use cached data directly if it has the right structure
    if (cachedData.containsKey('daily_targets') && cachedData.containsKey('transactions')) {
      return cachedData;
    }

    // Transform cached data to expected format
    return {
      'balance': cachedData['balance'] ?? (_monthlyIncome * 0.85),
      'spent': cachedData['today_spent'] ?? ((_monthlyIncome / 30) * 0.45),
      'daily_targets': cachedData['daily_targets'] ?? _getDefaultDailyTargets(),
      'week': cachedData['week'] ?? _generateWeekData(),
      'transactions': cachedData['transactions'] ?? _getDefaultTransactions(),
    };
  }

  /// Handle background sync status changes
  void _onBackgroundSyncChanged() {
    // Optionally show a subtle indicator that data is being synced
    // For now, we'll just log it
    if (_offlineProvider.isBackgroundSyncing.value) {
      logDebug('Background sync started', tag: 'MAIN_SCREEN');
    } else {
      logDebug('Background sync completed', tag: 'MAIN_SCREEN');
      // Refresh UI with potentially updated data
      _refreshFromCache();
    }
  }

  /// Refresh UI with updated cached data after background sync
  void _refreshFromCache() {
    try {
      final updatedDashboard = _offlineProvider.getDashboardData();
      final updatedProfile = _offlineProvider.getUserProfile();
      
      if (updatedDashboard.isNotEmpty && mounted) {
        setState(() {
          dashboardData = _processCachedDashboardData(updatedDashboard);
          userProfile = updatedProfile;
          
          // Update income if it changed
          final newIncome = (updatedProfile['data']?['income'] as num?)?.toDouble() ?? _monthlyIncome;
          if (newIncome != _monthlyIncome) {
            _monthlyIncome = newIncome;
            _incomeTier = _incomeService.classifyIncome(_monthlyIncome);
            incomeClassification = _getDefaultIncomeClassification();
            peerComparison = _getDefaultPeerComparison();
            cohortInsights = _getDefaultCohortInsights();
          }
        });
      }
    } catch (e) {
      logWarning('Error refreshing from cache: $e', tag: 'MAIN_SCREEN');
    }
  }

  /// User-initiated refresh
  Future<void> refreshData() async {
    try {
      // Refresh using production budget data first
      await _refreshProductionBudgetData();
      
      // Fallback to offline provider refresh
      await _offlineProvider.refreshData();
      
      // Update UI with refreshed data
      _refreshFromCache();
      
      // Show brief success message
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Budget data refreshed'),
            duration: Duration(seconds: 1),
            behavior: SnackBarBehavior.floating,
          ),
        );
      }
    } catch (e) {
      logWarning('Manual refresh failed: $e', tag: 'MAIN_SCREEN');
    }
  }

  /// Refresh production budget data
  Future<void> _refreshProductionBudgetData() async {
    try {
      logDebug('Refreshing production budget data', tag: 'MAIN_SCREEN');
      
      // Get fresh data from budget adapter
      final refreshedDashboard = await _budgetService.getDashboardData();
      final refreshedInsights = await _budgetService.getBudgetInsights();
      
      if (mounted) {
        setState(() {
          dashboardData = refreshedDashboard;
          
          // Update financial health score from insights
          financialHealthScore = refreshedInsights['confidence'] != null ? {
            'score': (refreshedInsights['confidence'] * 100).round(),
            'grade': _getGradeFromConfidence(refreshedInsights['confidence']),
          } : financialHealthScore;
        });
      }
      
      logDebug('Production budget data refreshed successfully', tag: 'MAIN_SCREEN');
    } catch (e) {
      logWarning('Failed to refresh production budget data: $e', tag: 'MAIN_SCREEN');
    }
  }

  @override
  void dispose() {
    _offlineProvider.isBackgroundSyncing.removeListener(_onBackgroundSyncChanged);
    _liveUpdates.disableLiveUpdates();
    super.dispose();
  }

  Map<String, dynamic> _getDefaultDashboard() => {
    'balance': _monthlyIncome * 0.85, // Higher balance for better UX
    'spent': (_monthlyIncome / 30) * 0.45, // 45% of daily budget spent
    'daily_targets': _getDefaultDailyTargets(),
    'week': _generateWeekData(),
    'transactions': _getDefaultTransactions(),
  };
  
  List<Map<String, dynamic>> _getDefaultDailyTargets() {
    _incomeService.getDefaultBudgetWeights(_incomeTier ?? IncomeTier.middle);
    final dailyBudget = _monthlyIncome / 30;
    
    return [
      {
        'category': 'Food & Dining',
        'limit': dailyBudget * 0.35, // More realistic food budget
        'spent': dailyBudget * 0.35 * 0.60, // 60% spent
        'icon': Icons.restaurant,
        'color': const Color(0xFF4CAF50),
      },
      {
        'category': 'Transportation',
        'limit': dailyBudget * 0.25,
        'spent': dailyBudget * 0.25 * 0.40, // 40% spent
        'icon': Icons.directions_car,
        'color': const Color(0xFF2196F3),
      },
      {
        'category': 'Entertainment',
        'limit': dailyBudget * 0.20,
        'spent': dailyBudget * 0.20 * 0.30, // 30% spent
        'icon': Icons.movie,
        'color': const Color(0xFF9C27B0),
      },
      {
        'category': 'Shopping',
        'limit': dailyBudget * 0.20,
        'spent': dailyBudget * 0.20 * 0.25, // 25% spent
        'icon': Icons.shopping_bag,
        'color': const Color(0xFFFF9800),
      },
    ];
  }
  
  Map<String, dynamic> _getDefaultIncomeClassification() => {
    'monthly_income': _monthlyIncome,
    'tier': _incomeTier.toString().split('.').last,
    'tier_name': _incomeService.getIncomeTierName(_incomeTier ?? IncomeTier.middle),
    'range': _incomeService.getIncomeRangeString(_incomeTier ?? IncomeTier.middle),
  };
  
  Map<String, dynamic> _getDefaultPeerComparison() => {
    'your_spending': _monthlyIncome * 0.65,
    'peer_average': _monthlyIncome * 0.72,
    'peer_median': _monthlyIncome * 0.68,
    'percentile': 35,
    'categories': {
      'food': {'your_amount': _monthlyIncome * 0.12, 'peer_average': _monthlyIncome * 0.15},
      'transportation': {'your_amount': _monthlyIncome * 0.10, 'peer_average': _monthlyIncome * 0.15},
      'entertainment': {'your_amount': _monthlyIncome * 0.06, 'peer_average': _monthlyIncome * 0.08},
    },
    'insights': [
      'You spend 15% less than peers in your income group',
      'Your food spending is well-controlled',
      'Transportation costs are below average',
    ],
  };
  
  Map<String, dynamic> _getDefaultCohortInsights() => {
    'cohort_size': 2847,
    'your_rank': 842,
    'percentile': 70,
    'top_insights': [
      'Users in your income group typically save 18% of income',
      'Most peers allocate 15% to food expenses',
      'Transportation costs vary widely in your group',
    ],
  };

  Map<String, dynamic> _getDefaultAdvice() => {
    'text': 'Great job staying within your budget this week! Consider setting aside the extra savings for your emergency fund.',
    'title': 'Weekly Budget Update',
  };

  List<Map<String, dynamic>> _getDefaultTransactions() {
    final now = DateTime.now();
    
    return [
      {
        'action': 'Morning Coffee',
        'amount': (12.50).toStringAsFixed(2),
        'date': now.subtract(const Duration(hours: 2)).toIso8601String(),
        'category': 'Food',
        'icon': Icons.local_cafe,
        'color': const Color(0xFF8D6E63),
      },
      {
        'action': 'Grocery Shopping',
        'amount': (89.32).toStringAsFixed(2),
        'date': now.subtract(const Duration(days: 1)).toIso8601String(),
        'category': 'Food',
        'icon': Icons.local_grocery_store,
        'color': const Color(0xFF4CAF50),
      },
      {
        'action': 'Uber Ride',
        'amount': (24.75).toStringAsFixed(2),
        'date': now.subtract(const Duration(hours: 6)).toIso8601String(),
        'category': 'Transportation',
        'icon': Icons.local_taxi,
        'color': const Color(0xFF2196F3),
      },
      {
        'action': 'Lunch at Work',
        'amount': (15.80).toStringAsFixed(2),
        'date': now.subtract(const Duration(days: 1, hours: 5)).toIso8601String(),
        'category': 'Food',
        'icon': Icons.restaurant,
        'color': const Color(0xFF4CAF50),
      },
      {
        'action': 'Netflix Subscription',
        'amount': (15.99).toStringAsFixed(2),
        'date': now.subtract(const Duration(days: 2)).toIso8601String(),
        'category': 'Entertainment',
        'icon': Icons.movie,
        'color': const Color(0xFF9C27B0),
      },
    ];
  }

  List<Map<String, dynamic>> _generateWeekData() {
    final days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
    final statuses = ['good', 'good', 'warning', 'good', 'good', 'over', 'good'];
    return List.generate(7, (index) => {
      'day': days[index],
      'status': statuses[index],
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
    
    return Scaffold(
      backgroundColor: colorScheme.surface,
      body: SafeArea(
        child: isLoading
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
            : error != null
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
                                horizontal: MediaQuery.of(context).size.width > 600 ? 32.0 : 16.0,
                                vertical: 12.0,
                              ),
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  // Header
                                  _buildHeader(),
                                  const SizedBox(height: 16),
                                  
                                  // Balance Card
                                  _buildBalanceCard(),
                                  const SizedBox(height: 16),
                                  
                                  // Budget Targets
                                  _buildBudgetTargets(),
                                  const SizedBox(height: 16),
                                  
                                  // Mini Calendar
                                  _buildMiniCalendar(),
                                  const SizedBox(height: 16),
                                  
                                  // AI Insights
                                  _buildAIInsightsCard(),
                                  const SizedBox(height: 16),
                                  
                                  // Recent Transactions
                                  _buildRecentTransactions(),
                                  
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
      floatingActionButton: error == null && !isLoading ? Semantics(
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
      ) : null,
    );
  }

  Widget _buildHeader() {
    final tierName = _incomeTier != null ? _incomeService.getIncomeTierName(_incomeTier!) : 'User';
    final primaryColor = _incomeTier != null ? _incomeService.getIncomeTierPrimaryColor(_incomeTier!) : const Color(0xFF193C57);
    
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

  
  Widget _buildBalanceCard() {
    final balance = dashboardData?['balance'] ?? 0;
    final spent = dashboardData?['spent'] ?? 0;
    final remaining = (balance is num && spent is num) ? balance - spent : balance;
    final primaryColor = _incomeTier != null ? _incomeService.getIncomeTierPrimaryColor(_incomeTier!) : const Color(0xFFFFD25F);

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


  Widget _buildBudgetTargets() {
    final targets = dashboardData?['daily_targets'] ?? [];
    final primaryColor = _incomeTier != null ? _incomeService.getIncomeTierPrimaryColor(_incomeTier!) : const Color(0xFF193C57);

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
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
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
            final limit = double.tryParse(target['limit']?.toString() ?? '0') ?? 0.0;
            final spent = double.tryParse(target['spent']?.toString() ?? '0') ?? 0.0;
            final progress = limit > 0 ? spent / limit : 0.0;
            final remaining = limit - spent;
            final categoryIcon = target['icon'] as IconData? ?? Icons.category;
            final categoryColor = target['color'] as Color? ?? primaryColor;
            
            Color progressColor;
            if (progress <= 0.7) {
              progressColor = const Color(0xFF4CAF50); // Green
            } else if (progress <= 0.9) {
              progressColor = const Color(0xFFFF9800); // Orange
            } else {
              progressColor = const Color(0xFFFF5722); // Red
            }

            return Card(
              margin: const EdgeInsets.only(bottom: 12),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
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
                            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                            decoration: BoxDecoration(
                              color: progressColor.withValues(alpha: 0.1),
                              borderRadius: BorderRadius.circular(20),
                              border: Border.all(color: progressColor.withValues(alpha: 0.3)),
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
                            remaining > 0 ? 'Remaining: \$${remaining.toStringAsFixed(0)}' : 'Over budget: \$${(-remaining).toStringAsFixed(0)}',
                            style: TextStyle(
                              fontFamily: 'Manrope',
                              fontSize: 13,
                              color: remaining > 0 ? Colors.grey[600] : Colors.red.shade600,
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

  Widget _buildMiniCalendar() {
    final week = dashboardData?['week'] ?? [];

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
              case 'over': color = const Color(0xFFFF5C5C); break;
              case 'warning': color = const Color(0xFFFFD25F); break;
              default: color = const Color(0xFF84FAA1);
            }

            return Container(
              width: 42,
              height: 50,
              decoration: BoxDecoration(
                color: color,
                borderRadius: BorderRadius.circular(12),
              ),
              alignment: Alignment.center,
              child: Text(day['day'], style: const TextStyle(fontWeight: FontWeight.bold)),
            );
          }).toList(),
        ),
      ],
    );
  }

  Widget _buildAIInsightsCard() {
    return GestureDetector(
      onTap: () => Navigator.pushNamed(context, '/insights'),
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
              Text(
                latestAdvice?['text'] ?? 'Tap to view personalized AI insights based on your real financial data',
                style: TextStyle(
                  fontFamily: 'Manrope',
                  fontSize: 14,
                  color: Colors.white.withValues(alpha: 0.9),
                  height: 1.4,
                ),
                maxLines: 3,
                overflow: TextOverflow.ellipsis,
              ),
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


  Widget _buildRecentTransactions() {
    final transactions = dashboardData?['transactions'] ?? [];

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
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
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
          ...transactions.map<Widget>((tx) {
            final txIcon = tx['icon'] as IconData? ?? Icons.attach_money;
            final txColor = tx['color'] as Color? ?? const Color(0xFF193C57);
            final amount = double.tryParse(tx['amount']?.toString() ?? '0') ?? 0.0;
            final timeAgo = _getTimeAgo(tx['date']);
            
            return Card(
              margin: const EdgeInsets.only(bottom: 12),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
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
                            tx['action'] ?? 'Transaction',
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
                                tx['category'] ?? 'Other',
                                style: TextStyle(
                                  fontFamily: 'Manrope',
                                  fontSize: 12,
                                  color: Colors.grey.shade600,
                                ),
                              ),
                              Text(
                                ' • $timeAgo',
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
                      '-\$${amount.toStringAsFixed(2)}',
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
          }).toList(),
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
