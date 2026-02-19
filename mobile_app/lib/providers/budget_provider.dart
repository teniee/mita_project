import 'dart:async';
import 'package:flutter/foundation.dart';
import '../services/api_service.dart';
import '../services/budget_adapter_service.dart';
import '../services/live_updates_service.dart';
import '../services/logging_service.dart';

/// Budget state enum for tracking loading states
enum BudgetState {
  initial,
  loading,
  loaded,
  error,
}

/// Centralized budget state management provider
/// Manages daily budgets, live status, suggestions, and redistribution
class BudgetProvider extends ChangeNotifier {
  final ApiService _apiService = ApiService();
  final BudgetAdapterService _budgetService = BudgetAdapterService();
  final LiveUpdatesService _liveUpdates = LiveUpdatesService();

  // State
  BudgetState _state = BudgetState.initial;
  bool _isLoading = false;
  bool _isRedistributing = false;
  String? _errorMessage;

  // Budget data
  List<dynamic> _dailyBudgets = [];
  Map<String, dynamic> _liveBudgetStatus = {};
  Map<String, dynamic> _budgetSuggestions = {};
  List<dynamic> _redistributionHistory = [];
  String _budgetMode = 'default';
  Map<String, dynamic>? _aiOptimization;
  Map<String, dynamic>? _budgetAdaptations;
  List<dynamic> _calendarData = [];

  // Budget settings data
  Map<String, dynamic> _automationSettings = {};
  Map<String, dynamic>? _budgetRecommendations;
  Map<String, dynamic>? _budgetRemaining;
  Map<String, dynamic>? _behavioralAllocation;
  bool _isUpdatingMode = false;

  // Subscriptions
  StreamSubscription<void>? _budgetUpdateSubscription;

  // Getters
  BudgetState get state => _state;
  bool get isLoading => _isLoading;
  bool get isRedistributing => _isRedistributing;
  String? get errorMessage => _errorMessage;
  List<dynamic> get dailyBudgets => _dailyBudgets;
  Map<String, dynamic> get liveBudgetStatus => _liveBudgetStatus;
  Map<String, dynamic> get budgetSuggestions => _budgetSuggestions;
  List<dynamic> get redistributionHistory => _redistributionHistory;
  String get budgetMode => _budgetMode;
  Map<String, dynamic>? get aiOptimization => _aiOptimization;
  Map<String, dynamic>? get budgetAdaptations => _budgetAdaptations;
  List<dynamic> get calendarData => _calendarData;
  Map<String, dynamic> get automationSettings => _automationSettings;
  Map<String, dynamic>? get budgetRecommendations => _budgetRecommendations;
  Map<String, dynamic>? get budgetRemaining => _budgetRemaining;
  Map<String, dynamic>? get behavioralAllocation => _behavioralAllocation;
  bool get isUpdatingMode => _isUpdatingMode;

  // Budget status convenience getters
  // FIX: Use correct field names from /budget/live_status endpoint
  // Backend returns 'monthly_budget' not 'total_budget'
  double get totalBudget {
    final valueData = _liveBudgetStatus['monthly_budget'];
    return (valueData == null)
        ? 0.0
        : (valueData is num)
            ? valueData.toDouble()
            : (valueData is String ? double.tryParse(valueData) ?? 0.0 : 0.0);
  }

  double get totalSpent {
    final valueData = _liveBudgetStatus['monthly_spent'];
    return (valueData == null)
        ? 0.0
        : (valueData is num)
            ? valueData.toDouble()
            : (valueData is String ? double.tryParse(valueData) ?? 0.0 : 0.0);
  }
  double get remaining => totalBudget - totalSpent;
  double get spendingPercentage =>
      totalBudget > 0 ? (totalSpent / totalBudget) : 0.0;

  /// Initialize the provider and start listening for updates
  Future<void> initialize() async {
    if (_state != BudgetState.initial) return;

    logInfo('Initializing BudgetProvider', tag: 'BUDGET_PROVIDER');

    // CRITICAL FIX: Check if user has a valid token before making API calls
    final token = await _apiService.getToken();
    if (token == null || token.isEmpty) {
      logWarning(
          'No authentication token found - skipping budget data initialization',
          tag: 'BUDGET_PROVIDER');
      _state = BudgetState.error;
      _errorMessage = 'Not authenticated';
      return;
    }

    await loadAllBudgetData();
    _subscribeToBudgetUpdates();
  }

  /// Subscribe to live budget updates
  void _subscribeToBudgetUpdates() {
    _budgetUpdateSubscription?.cancel();
    _budgetUpdateSubscription = _liveUpdates.budgetUpdates.listen((budgetData) {
      logDebug('Received budget update from live service',
          tag: 'BUDGET_PROVIDER');
      loadLiveBudgetStatus();
    });
  }

  /// Load all budget data at once
  Future<void> loadAllBudgetData() async {
    _setLoading(true);
    _state = BudgetState.loading;
    notifyListeners();

    try {
      await Future.wait([
        loadDailyBudgets(),
        loadLiveBudgetStatus(),
        loadBudgetSuggestions(),
        loadBudgetMode(),
        loadRedistributionHistory(),
        loadAIOptimization(),
        loadBudgetAdaptations(),
      ]);

      _state = BudgetState.loaded;
      logInfo('All budget data loaded successfully', tag: 'BUDGET_PROVIDER');
    } catch (e) {
      logError('Failed to load budget data: $e', tag: 'BUDGET_PROVIDER');
      _errorMessage = e.toString();
      _state = BudgetState.error;
    } finally {
      _setLoading(false);
    }
  }

  /// Load daily budgets
  Future<void> loadDailyBudgets() async {
    try {
      final data = await _apiService.getDailyBudgets();
      _dailyBudgets = data;
      logInfo('Daily budgets loaded: ${_dailyBudgets.length} items',
          tag: 'BUDGET_PROVIDER');
      notifyListeners();
    } catch (e) {
      logError('Error loading daily budgets: $e', tag: 'BUDGET_PROVIDER');
      _dailyBudgets = [];
    }
  }

  /// Load live budget status
  Future<void> loadLiveBudgetStatus() async {
    try {
      final status = await _apiService.getLiveBudgetStatus();
      _liveBudgetStatus = status;
      logDebug('Live budget status loaded', tag: 'BUDGET_PROVIDER');
      notifyListeners();
    } catch (e) {
      logError('Error loading live budget status: $e', tag: 'BUDGET_PROVIDER');
    }
  }

  /// Load budget suggestions (enhanced)
  Future<void> loadBudgetSuggestions() async {
    try {
      final enhancedSuggestions =
          await _budgetService.getEnhancedBudgetSuggestions();
      _budgetSuggestions = enhancedSuggestions;
      logInfo(
          'Enhanced budget suggestions loaded: ${enhancedSuggestions['total_count']} suggestions',
          tag: 'BUDGET_PROVIDER');
      notifyListeners();
    } catch (e) {
      logError('Error loading enhanced budget suggestions: $e',
          tag: 'BUDGET_PROVIDER');
      // Fallback to legacy API
      try {
        final legacySuggestions = await _apiService.getBudgetSuggestions();
        _budgetSuggestions = legacySuggestions;
        notifyListeners();
      } catch (fallbackError) {
        logError('Fallback budget suggestions also failed: $fallbackError',
            tag: 'BUDGET_PROVIDER');
      }
    }
  }

  /// Load budget mode
  Future<void> loadBudgetMode() async {
    try {
      final mode = await _apiService.getBudgetMode();
      _budgetMode = mode;
      logDebug('Budget mode loaded: $_budgetMode', tag: 'BUDGET_PROVIDER');
      notifyListeners();
    } catch (e) {
      logError('Error loading budget mode: $e', tag: 'BUDGET_PROVIDER');
    }
  }

  /// Set budget mode
  Future<bool> setBudgetMode(String newMode) async {
    if (_isUpdatingMode) return false;

    _isUpdatingMode = true;
    notifyListeners();

    try {
      await _apiService.setBudgetMode(newMode);
      _budgetMode = newMode;
      logInfo('Budget mode set to: $newMode', tag: 'BUDGET_PROVIDER');
      notifyListeners();
      return true;
    } catch (e) {
      logError('Error setting budget mode: $e', tag: 'BUDGET_PROVIDER');
      _errorMessage = 'Failed to update budget mode';
      return false;
    } finally {
      _isUpdatingMode = false;
      notifyListeners();
    }
  }

  /// Load automation settings
  Future<void> loadAutomationSettings() async {
    try {
      final settings = await _apiService.getBudgetAutomationSettings();
      _automationSettings = settings;
      logDebug('Automation settings loaded', tag: 'BUDGET_PROVIDER');
      notifyListeners();
    } catch (e) {
      logError('Error loading automation settings: $e', tag: 'BUDGET_PROVIDER');
    }
  }

  /// Update automation settings
  Future<bool> updateAutomationSettings(
      Map<String, dynamic> newSettings) async {
    try {
      await _apiService.updateBudgetAutomationSettings(newSettings);
      _automationSettings = {..._automationSettings, ...newSettings};
      logInfo('Automation settings updated', tag: 'BUDGET_PROVIDER');
      notifyListeners();
      return true;
    } catch (e) {
      logError('Error updating automation settings: $e',
          tag: 'BUDGET_PROVIDER');
      return false;
    }
  }

  /// Load budget remaining for current month
  Future<void> loadBudgetRemaining() async {
    try {
      final now = DateTime.now();
      final remaining = await _apiService.getBudgetRemaining(
          year: now.year, month: now.month);
      _budgetRemaining = remaining;
      logDebug('Budget remaining loaded', tag: 'BUDGET_PROVIDER');
      notifyListeners();
    } catch (e) {
      logError('Error loading budget remaining: $e', tag: 'BUDGET_PROVIDER');
    }
  }

  /// Load income-based budget recommendations
  Future<void> loadBudgetRecommendations(double monthlyIncome) async {
    try {
      final recommendations =
          await _apiService.getIncomeBasedBudgetRecommendations(monthlyIncome);
      _budgetRecommendations = recommendations;
      logDebug('Budget recommendations loaded', tag: 'BUDGET_PROVIDER');
      notifyListeners();
    } catch (e) {
      logError('Error loading budget recommendations: $e',
          tag: 'BUDGET_PROVIDER');
    }
  }

  /// Load behavioral budget allocation
  Future<void> loadBehavioralAllocation(double monthlyIncome,
      {Map<String, dynamic>? profile}) async {
    try {
      final allocation = await _apiService
          .getBehavioralBudgetAllocation(monthlyIncome, profile: profile);
      _behavioralAllocation = allocation;
      logDebug('Behavioral allocation loaded', tag: 'BUDGET_PROVIDER');
      notifyListeners();
    } catch (e) {
      logError('Error loading behavioral allocation: $e',
          tag: 'BUDGET_PROVIDER');
    }
  }

  /// Load all budget settings data (for BudgetSettingsScreen)
  Future<void> loadBudgetSettingsData(double monthlyIncome,
      {String? incomeTier}) async {
    _setLoading(true);
    try {
      await Future.wait([
        loadBudgetMode(),
        loadAutomationSettings(),
        loadBudgetRemaining(),
        loadBudgetRecommendations(monthlyIncome),
        loadBehavioralAllocation(monthlyIncome,
            profile: incomeTier != null ? {'income_tier': incomeTier} : null),
      ]);
      logInfo('Budget settings data loaded successfully',
          tag: 'BUDGET_PROVIDER');
    } catch (e) {
      logError('Error loading budget settings data: $e',
          tag: 'BUDGET_PROVIDER');
      _errorMessage = e.toString();
    } finally {
      _setLoading(false);
    }
  }

  /// Load redistribution history
  Future<void> loadRedistributionHistory() async {
    try {
      final history = await _apiService.getBudgetRedistributionHistory();
      _redistributionHistory = history;
      logDebug(
          'Redistribution history loaded: ${_redistributionHistory.length} items',
          tag: 'BUDGET_PROVIDER');
      notifyListeners();
    } catch (e) {
      logError('Error loading redistribution history: $e',
          tag: 'BUDGET_PROVIDER');
    }
  }

  /// Load calendar data with fallbacks
  Future<void> loadCalendarData({int? year, int? month}) async {
    final now = DateTime.now();
    final targetYear = year ?? now.year;
    final targetMonth = month ?? now.month;

    _isLoading = true;
    notifyListeners();

    try {
      // ── Step 1: Planned budgets from DailyPlan (created during onboarding) ──
      logInfo('Loading saved calendar for $targetYear-$targetMonth',
          tag: 'BUDGET_PROVIDER');
      final savedCalendar = await _apiService.getSavedCalendar(
        year: targetYear,
        month: targetMonth,
      );

      // ── Step 2: Real transactions for the month ──
      final spentByDayCategory = <int, Map<String, double>>{};
      final spentByDay = <int, double>{};
      try {
        final rawTx = await _apiService.getMonthlyTransactionsRaw(
          year: targetYear,
          month: targetMonth,
        );
        for (final tx in rawTx) {
          final spentAt =
              DateTime.tryParse(tx['spent_at'] as String? ?? '');
          if (spentAt == null) continue;
          final day = spentAt.day;
          final cat = (tx['category'] as String?) ?? 'other';
          final amount = (tx['amount'] as num?)?.toDouble() ?? 0.0;
          spentByDayCategory[day] ??= {};
          spentByDayCategory[day]![cat] =
              (spentByDayCategory[day]![cat] ?? 0.0) + amount;
          spentByDay[day] = (spentByDay[day] ?? 0.0) + amount;
        }
        logInfo('Loaded ${rawTx.length} transactions for calendar merge',
            tag: 'BUDGET_PROVIDER');
      } catch (txError) {
        logWarning('Could not load transactions for calendar: $txError',
            tag: 'BUDGET_PROVIDER');
      }

      // ── Step 3: Merge planned budget + real spending ──
      if (savedCalendar != null && savedCalendar.isNotEmpty) {
        final today =
            DateTime(now.year, now.month, now.day);

        _calendarData =
            savedCalendar.map<Map<String, dynamic>>((dynamic raw) {
          final d = Map<String, dynamic>.from(raw as Map);
          final day = d['day'] as int? ?? 0;
          final dateStr = d['date'] as String?;
          final dayDate = dateStr != null
              ? DateTime.tryParse(dateStr)
              : null;
          final dayOnly = dayDate != null
              ? DateTime(dayDate.year, dayDate.month, dayDate.day)
              : null;

          final isToday = dayOnly == today;
          final isPast =
              dayOnly != null && dayOnly.isBefore(today);

          final limit = (d['limit'] as num?)?.toDouble() ?? 0.0;
          final realSpent = spentByDay[day] ?? 0.0;

          // Build per-category breakdown: planned (from DailyPlan) + real
          final plannedCats =
              (d['planned_budget'] as Map?) ?? {};
          final mergedCats = <String, dynamic>{};

          for (final entry in plannedCats.entries) {
            final cat = entry.key as String;
            final val = entry.value;
            final planned = val is Map
                ? (val['planned'] as num?)?.toDouble() ?? 0.0
                : (val as num?)?.toDouble() ?? 0.0;
            final spent = (isPast || isToday)
                ? (spentByDayCategory[day]?[cat] ?? 0.0)
                : 0.0;
            mergedCats[cat] = {'planned': planned, 'spent': spent};
          }

          // Include transactions whose category wasn't in planned budget
          if (isPast || isToday) {
            (spentByDayCategory[day] ?? {}).forEach((cat, amt) {
              if (!mergedCats.containsKey(cat)) {
                mergedCats[cat] = {'planned': 0.0, 'spent': amt};
              }
            });
          }

          // Day status
          String status;
          if (!isPast && !isToday) {
            status = 'planned';
          } else if (limit > 0 && realSpent > limit) {
            status = 'over';
          } else if (limit > 0 && realSpent > limit * 0.85) {
            status = 'warning';
          } else {
            status = 'good';
          }

          return {
            'day': day,
            'date': dateStr,
            'limit': limit.round(), // int expected by calendar_screen.dart
            'status': status,
            'spent': realSpent.round(), // int expected by calendar_screen.dart
            'categories': mergedCats,
            'is_today': isToday,
            'is_weekend':
                dayDate != null && dayDate.weekday >= 6,
          };
        }).toList();

        logInfo(
            'Calendar ready: ${_calendarData.length} days with real spending data',
            tag: 'BUDGET_PROVIDER');
      } else {
        // No saved calendar yet (new user / new month before onboarding saves plan)
        // Fall back to shell preview — spent stays 0, it's a planning view
        logWarning(
            'No saved calendar for $targetYear-$targetMonth — using shell preview',
            tag: 'BUDGET_PROVIDER');
        _calendarData = await _apiService.getCalendar();
      }

      _state = BudgetState.loaded;
      _errorMessage = null;
    } catch (e) {
      logError('Calendar load failed: $e', tag: 'BUDGET_PROVIDER');
      _errorMessage = 'Failed to load calendar data';
      _state = BudgetState.error;
      _calendarData = [];
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  /// Load AI budget optimization
  Future<void> loadAIOptimization() async {
    try {
      // Get calendar data for AI context
      final calendarData = await _apiService.getCalendar();
      _calendarData = calendarData;

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
      final incomeData = profile['data']?['income'];
      final income = (incomeData == null)
          ? null
          : (incomeData is num)
              ? incomeData.toDouble()
              : (incomeData is String ? double.tryParse(incomeData) : null);

      // Fetch AI optimization
      final optimization = await _apiService.getAIBudgetOptimization(
        calendar: calendarDict,
        income: income,
      );

      _aiOptimization = optimization;
      logInfo('AI budget optimization loaded successfully',
          tag: 'BUDGET_PROVIDER');
      notifyListeners();
    } catch (e) {
      logError('Error loading AI budget optimization: $e',
          tag: 'BUDGET_PROVIDER');
    }
  }

  /// Load budget adaptations
  Future<void> loadBudgetAdaptations() async {
    try {
      final adaptations = await _apiService.getBudgetAdaptations();
      _budgetAdaptations = adaptations;
      logInfo('Budget adaptations loaded successfully', tag: 'BUDGET_PROVIDER');
      notifyListeners();
    } catch (e) {
      logError('Error loading budget adaptations: $e', tag: 'BUDGET_PROVIDER');
    }
  }

  /// Trigger budget redistribution
  Future<bool> redistributeBudget() async {
    if (_isRedistributing) return false;

    _isRedistributing = true;
    notifyListeners();

    try {
      logInfo('Starting budget redistribution', tag: 'BUDGET_PROVIDER');

      // Get current calendar data
      final calendarData = await _apiService.getCalendar();
      if (calendarData.isEmpty) {
        throw Exception('No calendar data available for redistribution');
      }

      // Convert to expected format
      Map<String, Map<String, dynamic>> calendarDict = {};
      for (var day in calendarData) {
        final dayNum = day['day'].toString();
        calendarDict[dayNum] = {
          'total': (day['spent'] ?? 0).toDouble(),
          'limit': (day['limit'] ?? 0).toDouble(),
        };
      }

      // Trigger redistribution
      await _apiService.redistributeCalendarBudget(calendarDict);

      // Refresh all data
      await loadAllBudgetData();

      logInfo('Budget redistribution completed successfully',
          tag: 'BUDGET_PROVIDER');
      return true;
    } catch (e) {
      logError('Budget redistribution failed: $e', tag: 'BUDGET_PROVIDER');
      _errorMessage = 'Failed to redistribute budget: $e';
      return false;
    } finally {
      _isRedistributing = false;
      notifyListeners();
    }
  }

  /// Trigger automatic budget adaptation
  Future<bool> triggerAutoAdaptation() async {
    try {
      logInfo('Starting automatic budget adaptation', tag: 'BUDGET_PROVIDER');

      await _apiService.triggerBudgetAdaptation();
      await loadAllBudgetData();

      logInfo('Budget adaptation completed successfully',
          tag: 'BUDGET_PROVIDER');
      return true;
    } catch (e) {
      logError('Auto adaptation failed: $e', tag: 'BUDGET_PROVIDER');
      _errorMessage = 'Failed to adapt budget: $e';
      return false;
    }
  }

  /// Get budget status color based on spending percentage
  String getBudgetStatus() {
    if (spendingPercentage > 0.8) return 'exceeded';
    if (spendingPercentage > 0.6) return 'warning';
    return 'normal';
  }

  /// Get budget mode display name
  String getBudgetModeDisplayName() {
    switch (_budgetMode) {
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

  /// Clear error message
  void clearError() {
    _errorMessage = null;
    notifyListeners();
  }

  /// Dispose subscriptions
  @override
  void dispose() {
    _budgetUpdateSubscription?.cancel();
    super.dispose();
  }

  // Private helper
  void _setLoading(bool loading) {
    _isLoading = loading;
    notifyListeners();
  }
}
