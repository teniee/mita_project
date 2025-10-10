
import 'package:flutter/material.dart';
import '../services/api_service.dart';
import '../services/accessibility_service.dart';
import '../services/budget_adapter_service.dart';
import '../services/live_updates_service.dart';
import 'package:intl/intl.dart';
import 'dart:async';
import '../services/logging_service.dart';
import '../core/enhanced_error_handling.dart';
import '../core/app_error_handler.dart';
import '../core/error_handling.dart';

class DailyBudgetScreen extends StatefulWidget {
  const DailyBudgetScreen({super.key});

  @override
  State<DailyBudgetScreen> createState() => _DailyBudgetScreenState();
}

class _DailyBudgetScreenState extends State<DailyBudgetScreen>
    with RobustErrorHandlingMixin {
  final ApiService _apiService = ApiService();
  final AccessibilityService _accessibilityService = AccessibilityService.instance;
  final BudgetAdapterService _budgetService = BudgetAdapterService();
  final LiveUpdatesService _liveUpdates = LiveUpdatesService();
  bool _isLoading = true;
  bool _isRedistributing = false;
  List<dynamic> _budgets = [];
  Map<String, dynamic> _liveBudgetStatus = {};
  Map<String, dynamic> _budgetSuggestions = {};
  List<dynamic> _redistributionHistory = [];
  String _budgetMode = 'default';
  StreamSubscription? _budgetUpdateSubscription;
  Map<String, dynamic>? _aiOptimization; // NEW: AI budget optimization
  Map<String, dynamic>? _budgetAdaptations; // NEW: Real-time budget adaptations

  @override
  void initState() {
    super.initState();
    _accessibilityService.initialize().then((_) {
      _accessibilityService.announceNavigation(
        'Daily Budget Dashboard',
        description: 'Smart budget tracking and financial insights',
      );
    });
    _initializeData();
    _subscribeToBudgetUpdates();
  }

  @override
  void dispose() {
    _budgetUpdateSubscription?.cancel();
    super.dispose();
  }

  Future<void> _initializeData() async {
    await fetchBudgets();
    await _fetchLiveBudgetStatus();
    await _fetchBudgetSuggestions();
    await _fetchBudgetMode();
    await _fetchRedistributionHistory();
    await _fetchAIBudgetOptimization(); // NEW: Fetch AI optimization
    await _fetchBudgetAdaptations(); // NEW: Fetch budget adaptations
  }

  void _subscribeToBudgetUpdates() {
    // Subscribe to centralized live updates instead of creating duplicate timer
    logInfo('Subscribing to centralized budget updates', tag: 'DAILY_BUDGET_SCREEN');

    _budgetUpdateSubscription = _liveUpdates.budgetUpdates.listen((budgetData) {
      if (mounted) {
        logDebug('Received budget update, refreshing status', tag: 'DAILY_BUDGET_SCREEN');
        _fetchLiveBudgetStatus();
      }
    });
  }

  Future<void> fetchBudgets() async {
    await executeRobustly<List<dynamic>>(
      () async {
        final data = await _apiService.getDailyBudgets().executeSafely(
          operationName: 'Fetch Daily Budgets',
          maxRetries: 2,
          category: ErrorCategory.network,
          fallbackValue: [],
        );
        
        if (mounted) {
          setState(() {
            _budgets = data ?? [];
            _isLoading = false;
          });
        }
        
        logInfo('Daily budgets loaded successfully: ${_budgets.length} items', tag: 'DAILY_BUDGET');
        return _budgets;
      },
      operationName: 'Daily Budget Data Loading',
      showLoadingState: true,
      onError: () {
        if (mounted) {
          setState(() {
            _budgets = [];
            _isLoading = false;
          });
          
          // Show error snackbar with retry option
          context.showErrorSnack(
            'Failed to load budget data',
            onRetry: fetchBudgets,
          );
        }
      },
    );
  }

  Future<void> _fetchLiveBudgetStatus() async {
    try {
      final status = await _apiService.getLiveBudgetStatus();
      if (mounted) {
        setState(() {
          _liveBudgetStatus = status;
        });
      }
    } catch (e) {
      logError('Error loading live budget status: $e');
    }
  }

  Future<void> _fetchBudgetSuggestions() async {
    try {
      // Use enhanced budget suggestions instead of legacy API
      final enhancedSuggestions = await _budgetService.getEnhancedBudgetSuggestions();
      if (mounted) {
        setState(() {
          _budgetSuggestions = enhancedSuggestions;
        });
      }
      logInfo('Enhanced budget suggestions loaded: ${enhancedSuggestions['total_count']} suggestions', tag: 'DAILY_BUDGET');
    } catch (e) {
      logError('Error loading enhanced budget suggestions: $e', tag: 'DAILY_BUDGET');
      // Fallback to legacy API if enhanced fails
      try {
        final legacySuggestions = await _apiService.getBudgetSuggestions();
        if (mounted) {
          setState(() {
            _budgetSuggestions = legacySuggestions;
          });
        }
      } catch (fallbackError) {
        logError('Fallback budget suggestions also failed: $fallbackError');
      }
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

  /// NEW: Fetch AI budget optimization suggestions
  Future<void> _fetchAIBudgetOptimization() async {
    try {
      // Get calendar data to provide context for AI optimization
      final calendarData = await _apiService.getCalendar();

      // Convert to map format expected by AI
      Map<String, dynamic> calendarDict = {};
      for (var day in calendarData) {
        final dayNum = day['day'].toString();
        calendarDict[dayNum] = {
          'spent': (day['spent'] ?? 0).toDouble(),
          'limit': (day['limit'] ?? 0).toDouble(),
        };
      }

      // Get user income
      final profile = await _apiService.getUserProfile();
      final income = (profile['data']?['income'] as num?)?.toDouble();

      // Fetch AI optimization
      final optimization = await _apiService.getAIBudgetOptimization(
        calendar: calendarDict,
        income: income,
      );

      if (mounted) {
        setState(() {
          _aiOptimization = optimization;
        });
      }
      logInfo('AI budget optimization loaded successfully', tag: 'DAILY_BUDGET');
    } catch (e) {
      logError('Error loading AI budget optimization: $e', tag: 'DAILY_BUDGET');
    }
  }

  Future<void> _triggerBudgetRedistribution() async {
    if (_isRedistributing) return;

    _accessibilityService.announceToScreenReader(
      'Starting budget redistribution',
      financialContext: 'Budget Management',
      isImportant: true,
    );

    await executeRobustly<void>(
      () async {
        setState(() {
          _isRedistributing = true;
        });

        // Get current calendar data for redistribution with enhanced error handling
        final calendarData = await _apiService.getCalendar().executeSafely(
          operationName: 'Get Calendar Data for Redistribution',
          maxRetries: 2,
          category: ErrorCategory.network,
          fallbackValue: [],
        );
        
        if (calendarData == null || calendarData.isEmpty) {
          throw ValidationException('No calendar data available for redistribution');
        }
        
        // Convert to the format expected by redistribution algorithm
        Map<String, Map<String, dynamic>> calendarDict = {};
        for (var day in calendarData) {
          final dayNum = day['day'].toString();
          calendarDict[dayNum] = {
            'total': (day['spent'] ?? 0).toDouble(),
            'limit': (day['limit'] ?? 0).toDouble(),
          };
        }

        // Trigger redistribution with enhanced error handling
        await _apiService.redistributeCalendarBudget(calendarDict).executeSafely(
          operationName: 'Budget Redistribution',
          maxRetries: 1, // Only retry once for financial operations
          category: ErrorCategory.system,
        );
        
        // Refresh all data after redistribution
        await _initializeData();
        
        if (mounted) {
          _accessibilityService.announceToScreenReader(
            'Budget successfully redistributed. Budget amounts have been updated.',
            financialContext: 'Budget Management',
            isImportant: true,
          );
          
          context.showSuccessSnack(
            'Budget successfully redistributed!'
          );
        }
      },
      operationName: 'Budget Redistribution Process',
      showLoadingState: false, // We handle loading state manually
      onSuccess: () {
        logInfo('Budget redistribution completed successfully', tag: 'BUDGET_REDISTRIBUTION');
      },
      onError: () {
        if (mounted) {
          _accessibilityService.announceToScreenReader(
            'Failed to redistribute budget. Please try again.',
            financialContext: 'Budget Management Error',
            isImportant: true,
          );
          
          showEnhancedErrorDialog(
            'Budget Redistribution Failed',
            errorMessage ?? 'Unable to redistribute your budget at this time. This could be due to network issues or temporary server problems.',
            onRetry: _triggerBudgetRedistribution,
            canRetry: true,
          );
        }
      },
    ).whenComplete(() {
      if (mounted) {
        setState(() {
          _isRedistributing = false;
        });
      }
    });
  }

  Future<void> _triggerAutoBudgetAdaptation() async {
    try {
      _accessibilityService.announceToScreenReader(
        'Starting automatic budget adaptation',
        financialContext: 'Budget Management',
        isImportant: true,
      );
      
      await _apiService.triggerBudgetAdaptation();
      await _initializeData();
      
      if (mounted) {
        _accessibilityService.announceToScreenReader(
          'Budget adapted based on your spending patterns. Budget amounts have been updated.',
          financialContext: 'Budget Management',
          isImportant: true,
        );
        
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Semantics(
              liveRegion: true,
              label: 'Success: Budget adapted based on spending patterns',
              child: const Text('Budget adapted based on your spending patterns!'),
            ),
            duration: const Duration(seconds: 3),
            backgroundColor: const Color(0xFF84FAA1),
          ),
        );
      }
    } catch (e) {
      logError('Error during auto adaptation: $e');
      if (mounted) {
        _accessibilityService.announceToScreenReader(
          'Failed to adapt budget automatically. Please try again.',
          financialContext: 'Budget Management Error',
          isImportant: true,
        );
      }
    }
  }

  Color getStatusColor(String status) {
    switch (status.toLowerCase()) {
      case 'normal':
      case 'good':
        return const Color(0xFF84FAA1);
      case 'warning':
        return const Color(0xFFFFD25F);
      case 'exceeded':
      case 'over':
        return const Color(0xFFFF5C5C);
      default:
        return Colors.grey;
    }
  }

  IconData getStatusIcon(String status) {
    switch (status.toLowerCase()) {
      case 'normal':
      case 'good':
        return Icons.check_circle;
      case 'warning':
        return Icons.warning;
      case 'exceeded':
      case 'over':
        return Icons.error;
      default:
        return Icons.info;
    }
  }

  String _getBudgetModeDisplayName(String mode) {
    switch (mode) {
      case 'strict':
        return 'Strict Budget';
      case 'flexible':
        return 'Flexible Budget';
      case 'behavioral':
        return 'Behavioral Adaptive';
      case 'goal':
        return 'Goal-Oriented';
      default:
        return 'Standard Budget';
    }
  }


  Widget _buildLiveBudgetCard() {
    if (_liveBudgetStatus.isEmpty) return const SizedBox.shrink();
    
    final totalBudget = _liveBudgetStatus['total_budget']?.toDouble() ?? 0.0;
    final totalSpent = _liveBudgetStatus['total_spent']?.toDouble() ?? 0.0;
    final remaining = totalBudget - totalSpent;
    final percentage = totalBudget > 0 ? (totalSpent / totalBudget) : 0.0;
    
    String statusDescription;
    if (percentage > 0.8) {
      statusDescription = 'Warning: Over 80% of budget used';
    } else if (percentage > 0.6) {
      statusDescription = 'Caution: Over 60% of budget used';
    } else {
      statusDescription = 'Good: Budget within safe limits';
    }
    
    return Semantics(
      label: _accessibilityService.createProgressSemanticLabel(
        category: 'Total Budget',
        spent: totalSpent,
        limit: totalBudget,
        status: statusDescription,
      ),
      child: Card(
        margin: const EdgeInsets.only(bottom: 16),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        elevation: 4,
        child: Container(
          padding: const EdgeInsets.all(20),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(16),
            gradient: LinearGradient(
              colors: percentage > 0.8 
                ? [const Color(0xFFFF5C5C), const Color(0xFFFF8A65)]
                : percentage > 0.6 
                  ? [const Color(0xFFFFD25F), const Color(0xFFFFE082)]
                  : [const Color(0xFF84FAA1), const Color(0xFFA8E6A0)],
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
            ),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Semantics(
                    header: true,
                    label: 'Live Budget Status',
                    child: const Text(
                      'Live Budget Status',
                      style: TextStyle(
                        fontSize: 18,
                        fontWeight: FontWeight.bold,
                        color: Colors.white,
                        fontFamily: 'Sora',
                      ),
                    ),
                  ),
                  Semantics(
                    label: 'Budget Mode: ${_getBudgetModeDisplayName(_budgetMode)}',
                    child: Container(
                      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                      decoration: BoxDecoration(
                        color: Colors.white.withValues(alpha: 0.2),
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Text(
                        _getBudgetModeDisplayName(_budgetMode),
                        style: const TextStyle(
                          color: Colors.white,
                          fontWeight: FontWeight.w500,
                          fontSize: 12,
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            const SizedBox(height: 16),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Semantics(
                  label: _accessibilityService.createFinancialSemanticLabel(
                    label: 'Total Budget',
                    amount: totalBudget,
                    isBalance: true,
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        'Total Budget',
                        style: TextStyle(color: Colors.white70, fontSize: 14),
                      ),
                      Text(
                        '\$${totalBudget.toStringAsFixed(2)}',
                        style: const TextStyle(
                          color: Colors.white,
                          fontSize: 20,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ],
                  ),
                ),
                Semantics(
                  label: _accessibilityService.createFinancialSemanticLabel(
                    label: 'Total Spent',
                    amount: totalSpent,
                    isBalance: false,
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        'Spent',
                        style: TextStyle(color: Colors.white70, fontSize: 14),
                      ),
                      Text(
                        '\$${totalSpent.toStringAsFixed(2)}',
                        style: const TextStyle(
                          color: Colors.white,
                          fontSize: 20,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ],
                  ),
                ),
                Semantics(
                  label: _accessibilityService.createFinancialSemanticLabel(
                    label: 'Remaining Budget',
                    amount: remaining,
                    status: remaining >= 0 ? 'Available' : 'Over budget',
                    isBalance: true,
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        'Remaining',
                        style: TextStyle(color: Colors.white70, fontSize: 14),
                      ),
                      Text(
                        '\$${remaining.toStringAsFixed(2)}',
                        style: const TextStyle(
                          color: Colors.white,
                          fontSize: 20,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),
            Semantics(
              label: 'Budget progress bar. ${(percentage * 100).toStringAsFixed(1)} percent of budget used',
              child: ClipRRect(
                borderRadius: BorderRadius.circular(8),
                child: LinearProgressIndicator(
                  value: percentage.clamp(0.0, 1.0),
                  backgroundColor: Colors.white.withValues(alpha: 0.3),
                  valueColor: const AlwaysStoppedAnimation<Color>(Colors.white),
                  minHeight: 8,
                ),
              ),
            ),
            const SizedBox(height: 8),
            Text(
              '${(percentage * 100).toStringAsFixed(1)}% of budget used',
              style: const TextStyle(color: Colors.white70, fontSize: 12),
            ),
          ],
        ),
      ),
    ),
    );
  }

  Widget _buildActionButtons() {
    return Card(
      margin: const EdgeInsets.only(bottom: 16),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      elevation: 3,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Semantics(
              header: true,
              child: const Text(
                'Smart Budget Actions',
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.bold,
                  fontFamily: 'Sora',
                  color: Color(0xFF193C57),
                ),
              ),
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: Semantics(
                    label: _accessibilityService.createButtonSemanticLabel(
                      action: _isRedistributing ? 'Redistributing budget' : 'Redistribute Budget',
                      context: _isRedistributing 
                        ? 'Budget redistribution in progress, please wait'
                        : 'Reallocate budget between days based on spending patterns',
                      isDisabled: _isRedistributing,
                    ),
                    button: true,
                    child: ElevatedButton.icon(
                      onPressed: _isRedistributing ? null : _triggerBudgetRedistribution,
                      icon: _isRedistributing 
                        ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2))
                        : const Icon(Icons.balance, size: 18),
                      label: Text(_isRedistributing ? 'Redistributing...' : 'Redistribute'),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: const Color(0xFF6B73FF),
                        foregroundColor: Colors.white,
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                        padding: const EdgeInsets.symmetric(vertical: 12),
                      ),
                    ).withMinimumTouchTarget(),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Semantics(
                    label: _accessibilityService.createButtonSemanticLabel(
                      action: 'Auto Adapt Budget',
                      context: 'Automatically adjust budget based on your spending patterns and behavior',
                    ),
                    button: true,
                    child: ElevatedButton.icon(
                      onPressed: _triggerAutoBudgetAdaptation,
                      icon: const Icon(Icons.auto_fix_high, size: 18),
                      label: const Text('Auto Adapt'),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: const Color(0xFF84FAA1),
                        foregroundColor: Colors.white,
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                        padding: const EdgeInsets.symmetric(vertical: 12),
                      ),
                    ).withMinimumTouchTarget(),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildSuggestionsCard() {
    if (_budgetSuggestions.isEmpty) return const SizedBox.shrink();

    final suggestions = _budgetSuggestions['suggestions'] as List<dynamic>? ?? [];
    if (suggestions.isEmpty) return const SizedBox.shrink();

    return Card(
      margin: const EdgeInsets.only(bottom: 16),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      elevation: 3,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Row(
              children: [
                Icon(Icons.lightbulb, color: Color(0xFFFFD25F)),
                SizedBox(width: 8),
                Text(
                  'AI Budget Suggestions',
                  style: TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.bold,
                    fontFamily: 'Sora',
                    color: Color(0xFF193C57),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            ...suggestions.take(3).map<Widget>((suggestion) => 
              Container(
                margin: const EdgeInsets.only(bottom: 8),
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: const Color(0xFFFFF9F0),
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: const Color(0xFFFFD25F), width: 1),
                ),
                child: Row(
                  children: [
                    const Icon(Icons.arrow_forward, size: 16, color: Color(0xFFFFD25F)),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        suggestion['message'] ?? suggestion.toString(),
                        style: const TextStyle(fontSize: 14, color: Color(0xFF193C57)),
                      ),
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

  Widget _buildRedistributionHistory() {
    if (_redistributionHistory.isEmpty) return const SizedBox.shrink();

    return Card(
      margin: const EdgeInsets.only(bottom: 16),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      elevation: 3,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Row(
              children: [
                Icon(Icons.history, color: Color(0xFF6B73FF)),
                SizedBox(width: 8),
                Text(
                  'Recent Redistribution',
                  style: TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.bold,
                    fontFamily: 'Sora',
                    color: Color(0xFF193C57),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            ..._redistributionHistory.take(3).map<Widget>((transfer) =>
              Container(
                margin: const EdgeInsets.only(bottom: 8),
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: const Color(0xFFF0F4FF),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text(
                      'Day ${transfer['from']} → Day ${transfer['to']}',
                      style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w500),
                    ),
                    Text(
                      '\$${(transfer['amount'] ?? 0).toStringAsFixed(2)}',
                      style: const TextStyle(
                        fontSize: 14,
                        fontWeight: FontWeight.bold,
                        color: Color(0xFF6B73FF),
                      ),
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

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFFFF9F0),
      appBar: AppBar(
        title: Semantics(
          header: true,
          label: 'Smart Daily Budget Dashboard',
          child: const Text(
            'Smart Daily Budget',
            style: TextStyle(
              fontFamily: 'Sora',
              fontWeight: FontWeight.bold,
              color: Color(0xFF193C57),
            ),
          ),
        ),
        backgroundColor: const Color(0xFFFFF9F0),
        elevation: 0,
        iconTheme: const IconThemeData(color: Color(0xFF193C57)),
        centerTitle: true,
        actions: [
          Semantics(
            label: _accessibilityService.createButtonSemanticLabel(
              action: 'Budget Settings',
              context: 'Configure budget modes and preferences',
            ),
            button: true,
            child: IconButton(
              icon: const Icon(Icons.settings),
              onPressed: () {
                Navigator.pushNamed(context, '/budget_settings');
                _accessibilityService.announceNavigation(
                  'Budget Settings',
                  description: 'Configure your budget preferences',
                );
              },
            ).withMinimumTouchTarget(),
          ),
        ],
      ),
      body: _isLoading
          ? Semantics(
              label: 'Loading budget data. Please wait.',
              liveRegion: true,
              child: const Center(child: CircularProgressIndicator()),
            )
          : RefreshIndicator(
              onRefresh: _initializeData,
              child: SingleChildScrollView(
                padding: const EdgeInsets.all(16),
                physics: const AlwaysScrollableScrollPhysics(),
                child: Column(
                  children: [
                    _buildLiveBudgetCard(),
                    _buildActionButtons(),
                    _buildSuggestionsCard(),
                    _buildRedistributionHistory(),
                    
                    // Original budget list
                    if (_budgets.isEmpty)
                      Semantics(
                        label: 'No budget data available. Your intelligent budget tracking will appear here when data is loaded.',
                        child: Card(
                          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                          elevation: 3,
                          child: const Padding(
                            padding: EdgeInsets.all(32),
                            child: Column(
                              children: [
                                Icon(Icons.account_balance_wallet, size: 64, color: Colors.grey),
                                SizedBox(height: 16),
                                Text(
                                  'No budget data available',
                                  style: TextStyle(
                                    fontSize: 18,
                                    color: Colors.grey,
                                    fontWeight: FontWeight.w500,
                                  ),
                                ),
                                SizedBox(height: 8),
                                Text(
                                  'Your intelligent budget tracking will appear here',
                                  style: TextStyle(color: Colors.grey),
                                  textAlign: TextAlign.center,
                                ),
                              ],
                            ),
                          ),
                        ),
                      )
                    else
                      ...(_budgets.map<Widget>((budget) {
                        final date = DateFormat('MMMM d, yyyy').format(DateTime.parse(budget['date']));
                        final status = budget['status'] ?? 'unknown';
                        final spent = (budget['spent'] ?? 0).toDouble();
                        final limit = (budget['limit'] ?? 1).toDouble();
                        final percentage = ((spent / limit) * 100).round();
                        
                        return Semantics(
                          label: _accessibilityService.createProgressSemanticLabel(
                            category: 'Budget for $date',
                            spent: spent,
                            limit: limit,
                            status: status,
                          ),
                          child: Card(
                            margin: const EdgeInsets.only(bottom: 16),
                            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
                            elevation: 3,
                            child: ListTile(
                              contentPadding: const EdgeInsets.all(16),
                              leading: Semantics(
                                label: 'Status icon: $status',
                                child: Icon(getStatusIcon(status), color: getStatusColor(status), size: 32),
                              ),
                              title: Semantics(
                                label: 'Date: $date',
                                child: Text(
                                  date,
                                  style: const TextStyle(
                                    fontFamily: 'Sora',
                                    fontWeight: FontWeight.bold,
                                  ),
                                ),
                              ),
                              subtitle: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  const SizedBox(height: 4),
                                  Semantics(
                                    label: _accessibilityService.createFinancialSemanticLabel(
                                      label: 'Spending summary',
                                      amount: spent,
                                      category: 'out of ${_accessibilityService.formatCurrency(limit)} limit',
                                    ),
                                    child: Text(
                                      'Spent: \$${budget['spent']} / Limit: \$${budget['limit']}',
                                      style: const TextStyle(fontFamily: 'Manrope'),
                                    ),
                                  ),
                                  const SizedBox(height: 4),
                                  Semantics(
                                    label: 'Progress indicator: $percentage percent of budget used',
                                    child: LinearProgressIndicator(
                                      value: ((budget['spent'] ?? 0) / (budget['limit'] ?? 1)).clamp(0.0, 1.0),
                                      backgroundColor: Colors.grey[300],
                                      valueColor: AlwaysStoppedAnimation<Color>(getStatusColor(status)),
                                    ),
                                  ),
                                ],
                              ),
                              trailing: Semantics(
                                label: 'Budget status: $status',
                                child: Container(
                                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                                  decoration: BoxDecoration(
                                    color: getStatusColor(status).withValues(alpha: 0.1),
                                    borderRadius: BorderRadius.circular(8),
                                  ),
                                  child: Text(
                                    status.toUpperCase(),
                                    style: TextStyle(
                                      fontWeight: FontWeight.bold,
                                      color: getStatusColor(status),
                                      fontSize: 12,
                                    ),
                                  ),
                                ),
                              ),
                            ),
                          ),
                        );
                      }).toList()),
                  ],
                ),
              ),
            ),
    );
  }
}
