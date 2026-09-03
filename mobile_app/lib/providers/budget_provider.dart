import 'dart:async';
import 'package:flutter/foundation.dart';
import '../services/api_service.dart';
import '../services/budget_adapter_service.dart';
import '../services/live_updates_service.dart';
import '../services/logging_service.dart';
import '../utils/json_utils.dart';

/// Budget state enum for tracking loading states
enum BudgetState {
  initial,
  loading,
  loaded,
  error,
}

/// Merge one saved-calendar day (backend /calendar/saved/{year}/{month}
/// contract: date, day, limit, planned_budget) with real transaction
/// spending into the shape calendar_screen.dart renders.
///
/// Pure function so the traffic-light logic is unit-testable: a day only
/// turns 'over'/'warning' against a non-zero limit, which is why the
/// backend must never emit limit=0 for a planned day.
Map<String, dynamic> mergeSavedCalendarDay(
  Map<String, dynamic> d, {
  required DateTime today,
  required Map<int, double> spentByDay,
  required Map<int, Map<String, double>> spentByDayCategory,
}) {
  final day = d['day'] as int? ?? 0;
  final dateStr = d['date'] as String?;
  final dayDate = dateStr != null ? DateTime.tryParse(dateStr) : null;
  final dayOnly = dayDate != null
      ? DateTime(dayDate.year, dayDate.month, dayDate.day)
      : null;

  final isToday = dayOnly == today;
  final isPast = dayOnly != null && dayOnly.isBefore(today);
  final isFuture = dayOnly != null && !isToday && !isPast;

  final limit = (d['limit'] as num?)?.toDouble() ?? 0.0;

  // The backend already recomputes spent from the DailyPlan ledger on every
  // transaction mutation and returns it in the saved-calendar payload
  // (day 'spent' + per-category 'spent'). Trust it as the source of truth;
  // the local transactions overlay is only a fallback for a shell/preview
  // calendar that carries no spent. The old code IGNORED the backend spent
  // and recomputed from a separate /transactions/ fetch — when that fetch's
  // date filter missed the row, the whole calendar rendered spent $0 even
  // though every API value was correct.
  // Future days never carry attributed spend (the date picker blocks
  // future-dated transactions); force 0 regardless of source.
  final backendDaySpent = isFuture ? 0.0 : (d['spent'] as num?)?.toDouble();

  // Build per-category breakdown: planned + spent (backend, overlay fallback)
  final plannedCats = (d['planned_budget'] as Map?) ?? {};
  final mergedCats = <String, dynamic>{};

  for (final entry in plannedCats.entries) {
    final cat = entry.key as String;
    final val = entry.value;
    final double planned;
    double? backendCatSpent;
    if (val is Map) {
      planned = (val['planned'] as num?)?.toDouble() ?? 0.0;
      backendCatSpent = (val['spent'] as num?)?.toDouble();
    } else {
      planned = (val as num?)?.toDouble() ?? 0.0;
    }
    final spent = isFuture
        ? 0.0
        : (backendCatSpent ??
            ((isPast || isToday)
                ? (spentByDayCategory[day]?[cat] ?? 0.0)
                : 0.0));
    mergedCats[cat] = {'planned': planned, 'spent': spent};
  }

  // Include transactions whose category wasn't in the planned budget (only
  // relevant for the overlay fallback; the backend payload already carries
  // unplanned categories as plan rows with planned 0).
  if (backendDaySpent == null && (isPast || isToday)) {
    (spentByDayCategory[day] ?? {}).forEach((cat, amt) {
      if (!mergedCats.containsKey(cat)) {
        mergedCats[cat] = {'planned': 0.0, 'spent': amt};
      }
    });
  }

  final realSpent =
      isFuture ? 0.0 : (backendDaySpent ?? (spentByDay[day] ?? 0.0));

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
    // Persisted plan, not a preview — the saved calendar is backed by
    // daily_plan rows for this exact day.
    'is_preview': false,
    'limit': limit.round(), // int expected by calendar_screen.dart
    'status': status,
    'spent': realSpent.round(), // int expected by calendar_screen.dart
    'categories': mergedCats,
    'is_today': isToday,
    'is_weekend': dayDate != null && dayDate.weekday >= 6,
  };
}

/// What loadCalendarData should do with a fetched saved-calendar response,
/// given what the provider already holds. Extracted as a pure function so the
/// "saved data is source of truth; a transient empty must not downgrade to
/// shell preview" invariant is unit-testable without the network.
enum CalendarLoadAction { useSaved, keepExisting, useShell }

CalendarLoadAction calendarLoadAction({
  required bool savedIsEmpty,
  required bool hasSavedData,
  required bool sameMonth,
}) {
  if (!savedIsEmpty) return CalendarLoadAction.useSaved;
  // Empty/null response for the SAME month we already hold real saved data for
  // is a transient blip (e.g. right after a mutation) — keep the saved data.
  if (hasSavedData && sameMonth) return CalendarLoadAction.keepExisting;
  // Genuinely no saved data for this month → planning shell preview.
  return CalendarLoadAction.useShell;
}

/// Centralized budget state management provider
/// Manages daily budgets, live status, suggestions, and redistribution
class BudgetProvider extends ChangeNotifier {
  final ApiService _apiService;
  final BudgetAdapterService _budgetService;
  final LiveUpdatesService _liveUpdates;

  BudgetProvider({
    ApiService? apiService,
    BudgetAdapterService? budgetService,
    LiveUpdatesService? liveUpdates,
  })  : _apiService = apiService ?? ApiService(),
        _budgetService = budgetService ?? BudgetAdapterService(),
        _liveUpdates = liveUpdates ?? LiveUpdatesService();

  // State
  BudgetState _state = BudgetState.initial;
  bool _isLoading = false;
  bool _isRedistributing = false;
  String? _errorMessage;
  String? _liveStatusError;
  bool _liveStatusFresh = false;

  // Budget data
  List<Map<String, dynamic>> _dailyBudgets = [];
  Map<String, dynamic> _liveBudgetStatus = {};
  Map<String, dynamic> _budgetSuggestions = {};
  List<Map<String, dynamic>> _redistributionHistory = [];
  String _budgetMode = 'default';
  Map<String, dynamic>? _aiOptimization;
  Map<String, dynamic>? _budgetAdaptations;
  List<Map<String, dynamic>> _calendarData = [];
  // Provenance of _calendarData so a transient empty/error response (or an
  // AI/shell preview) can never downgrade real saved data for the same month.
  int? _calendarYear;
  int? _calendarMonth;
  bool _calendarHasSavedData = false;

  // Budget settings data
  Map<String, dynamic> _automationSettings = {};
  Map<String, dynamic>? _budgetRecommendations;
  Map<String, dynamic>? _budgetRemaining;
  Map<String, dynamic>? _behavioralAllocation;
  bool _isUpdatingMode = false;

  // Subscriptions
  StreamSubscription<void>? _budgetUpdateSubscription;
  int _sessionGeneration = 0;
  int _dailyBudgetsRequestId = 0;
  int _liveStatusRequestId = 0;
  int _calendarRequestId = 0;
  Future<void>? _initializeInFlight;
  int? _initializeGeneration;

  // Getters
  BudgetState get state => _state;
  bool get isLoading => _isLoading;
  bool get isRedistributing => _isRedistributing;
  String? get errorMessage => _errorMessage;
  String? get liveStatusError => _liveStatusError;
  bool get liveStatusFresh => _liveStatusFresh;
  List<Map<String, dynamic>> get dailyBudgets => _dailyBudgets;
  Map<String, dynamic> get liveBudgetStatus => _liveBudgetStatus;
  Map<String, dynamic> get budgetSuggestions => _budgetSuggestions;
  List<Map<String, dynamic>> get redistributionHistory =>
      _redistributionHistory;
  String get budgetMode => _budgetMode;
  Map<String, dynamic>? get aiOptimization => _aiOptimization;
  Map<String, dynamic>? get budgetAdaptations => _budgetAdaptations;
  List<Map<String, dynamic>> get calendarData => _calendarData;

  /// True when [calendarData] is a /calendar/shell PLANNING PREVIEW rather
  /// than the user's persisted plan. A preview is one monthly total spread
  /// evenly, so every day carries the same figure — it must be labelled, never
  /// presented as any day's actual budget.
  bool get calendarIsPreview =>
      _calendarData.isNotEmpty && !_calendarHasSavedData;
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

  int? get monthlyTransactionCount => _liveStatusFresh
      ? asIntOrNull(_liveBudgetStatus['transaction_count'])
      : null;

  double get remaining => totalBudget - totalSpent;
  double get spendingPercentage =>
      totalBudget > 0 ? (totalSpent / totalBudget) : 0.0;

  /// Initialize the provider and start listening for updates
  Future<void> initialize() {
    if (_state != BudgetState.initial) return Future.value();

    final generation = _sessionGeneration;
    final inFlight = _initializeInFlight;
    if (inFlight != null && _initializeGeneration == generation) {
      return inFlight;
    }

    final future = _doInitialize(generation);
    _initializeInFlight = future;
    _initializeGeneration = generation;
    future.whenComplete(() {
      if (identical(_initializeInFlight, future) &&
          _initializeGeneration == generation) {
        _initializeInFlight = null;
        _initializeGeneration = null;
      }
    });
    return future;
  }

  Future<void> _doInitialize(int generation) async {
    logInfo('Initializing BudgetProvider', tag: 'BUDGET_PROVIDER');

    // CRITICAL FIX: Check if user has a valid token before making API calls
    final token = await _apiService.getToken();
    if (!_isCurrent(generation)) return;
    if (token == null || token.isEmpty) {
      logWarning(
          'No authentication token found - skipping budget data initialization',
          tag: 'BUDGET_PROVIDER');
      _state = BudgetState.error;
      _errorMessage = 'Not authenticated';
      notifyListeners();
      return;
    }

    await loadAllBudgetData(sessionGeneration: generation);
    if (!_isCurrent(generation)) return;
    _subscribeToBudgetUpdates(generation);
  }

  void _clearSessionData() {
    _dailyBudgets = [];
    _liveBudgetStatus = {};
    _liveStatusError = null;
    _liveStatusFresh = false;
    _budgetSuggestions = {};
    _redistributionHistory = [];
    _budgetMode = 'default';
    _aiOptimization = null;
    _budgetAdaptations = null;
    _calendarData = [];
    _calendarYear = null;
    _calendarMonth = null;
    _calendarHasSavedData = false;
    _automationSettings = {};
    _budgetRecommendations = null;
    _budgetRemaining = null;
    _behavioralAllocation = null;
    _errorMessage = null;
    _state = BudgetState.initial;
    _isLoading = false;
    _isRedistributing = false;
    _isUpdatingMode = false;
  }

  /// Subscribe to live budget updates
  void _subscribeToBudgetUpdates(int generation) {
    _budgetUpdateSubscription?.cancel();
    _budgetUpdateSubscription = _liveUpdates.budgetUpdates.listen((budgetData) {
      if (!_isCurrent(generation)) return;
      logDebug('Received budget update from live service',
          tag: 'BUDGET_PROVIDER');
      loadLiveBudgetStatus(sessionGeneration: generation);
    });
  }

  /// Load all budget data at once
  Future<void> loadAllBudgetData({int? sessionGeneration}) async {
    final generation = sessionGeneration ?? _sessionGeneration;
    if (!_isCurrent(generation)) return;
    _setLoading(true);
    _state = BudgetState.loading;
    // Clear any stale error so a retry can recover; previously errorMessage
    // was never reset, so one failed load left the dashboard permanently on
    // the "Unable to load dashboard" screen even after the cause was fixed.
    _errorMessage = null;
    notifyListeners();

    // Run each load independently. A single non-critical widget's data
    // failing (AI optimization, suggestions, adaptations, redistribution)
    // must NOT blank the entire dashboard — only a genuine failure of the
    // core budget data should surface an error.
    Future<void> guard(String name, Future<void> Function() load,
        {bool critical = false}) async {
      try {
        await load();
      } catch (e) {
        logWarning('Budget sub-load "$name" failed: $e',
            tag: 'BUDGET_PROVIDER');
        if (critical) rethrow;
      }
    }

    try {
      await Future.wait([
        guard(
          'dailyBudgets',
          () => loadDailyBudgets(sessionGeneration: generation),
          critical: true,
        ),
        // The dashboard's "Today's Budget Targets" and week strip read
        // calendarData; without this load they always rendered the
        // income/30 default-weights fallback even though a real saved
        // calendar existed.
        guard('calendarData',
            () => loadCalendarData(sessionGeneration: generation)),
        guard('liveStatus',
            () => loadLiveBudgetStatus(sessionGeneration: generation)),
        guard('suggestions',
            () => loadBudgetSuggestions(sessionGeneration: generation)),
        guard('mode', () => loadBudgetMode(sessionGeneration: generation)),
        guard(
          'redistribution',
          () => loadRedistributionHistory(sessionGeneration: generation),
        ),
        guard('aiOptimization',
            () => loadAIOptimization(sessionGeneration: generation)),
        guard('adaptations',
            () => loadBudgetAdaptations(sessionGeneration: generation)),
      ]);
      if (!_isCurrent(generation)) return;

      _errorMessage = null;
      _state = BudgetState.loaded;
      logInfo('All budget data loaded successfully', tag: 'BUDGET_PROVIDER');
    } catch (e) {
      if (!_isCurrent(generation)) return;
      logError('Failed to load core budget data: $e', tag: 'BUDGET_PROVIDER');
      _errorMessage = e.toString();
      _state = BudgetState.error;
    } finally {
      if (_isCurrent(generation)) {
        _setLoading(false);
      }
    }
  }

  /// Load daily budgets
  Future<void> loadDailyBudgets({int? sessionGeneration}) async {
    final generation = sessionGeneration ?? _sessionGeneration;
    final requestId = ++_dailyBudgetsRequestId;
    try {
      final data = await _apiService.getDailyBudgets();
      if (!_isCurrent(generation) || requestId != _dailyBudgetsRequestId) {
        return;
      }
      _dailyBudgets = asMapList(data);
      logInfo('Daily budgets loaded: ${_dailyBudgets.length} items',
          tag: 'BUDGET_PROVIDER');
      notifyListeners();
    } catch (e) {
      if (!_isCurrent(generation) || requestId != _dailyBudgetsRequestId) {
        return;
      }
      logError('Error loading daily budgets: $e', tag: 'BUDGET_PROVIDER');
      _dailyBudgets = [];
    }
  }

  /// Load live budget status
  Future<void> loadLiveBudgetStatus({int? sessionGeneration}) async {
    final generation = sessionGeneration ?? _sessionGeneration;
    final requestId = ++_liveStatusRequestId;
    try {
      final status = await _apiService.getLiveBudgetStatus();
      if (!_isCurrent(generation) || requestId != _liveStatusRequestId) return;
      _liveBudgetStatus = status;
      _liveStatusFresh = true;
      _liveStatusError = null;
      logDebug('Live budget status loaded', tag: 'BUDGET_PROVIDER');
      notifyListeners();
    } catch (e) {
      if (!_isCurrent(generation) || requestId != _liveStatusRequestId) return;
      logError('Error loading live budget status: $e', tag: 'BUDGET_PROVIDER');
      // A failed refresh after a successful ledger mutation must not keep
      // presenting the previous count/spend as current.
      _liveBudgetStatus = {};
      _liveStatusFresh = false;
      _liveStatusError = 'Live budget status is unavailable';
      notifyListeners();
    }
  }

  /// Load budget suggestions (enhanced)
  Future<void> loadBudgetSuggestions({int? sessionGeneration}) async {
    final generation = sessionGeneration ?? _sessionGeneration;
    try {
      final enhancedSuggestions =
          await _budgetService.getEnhancedBudgetSuggestions();
      if (!_isCurrent(generation)) return;
      _budgetSuggestions = enhancedSuggestions;
      logInfo(
          'Enhanced budget suggestions loaded: ${enhancedSuggestions['total_count']} suggestions',
          tag: 'BUDGET_PROVIDER');
      notifyListeners();
    } catch (e) {
      if (!_isCurrent(generation)) return;
      logError('Error loading enhanced budget suggestions: $e',
          tag: 'BUDGET_PROVIDER');
      // Fallback to legacy API
      try {
        final legacySuggestions = await _apiService.getBudgetSuggestions();
        if (!_isCurrent(generation)) return;
        _budgetSuggestions = legacySuggestions;
        notifyListeners();
      } catch (fallbackError) {
        if (!_isCurrent(generation)) return;
        logError('Fallback budget suggestions also failed: $fallbackError',
            tag: 'BUDGET_PROVIDER');
      }
    }
  }

  /// Load budget mode
  Future<void> loadBudgetMode({int? sessionGeneration}) async {
    final generation = sessionGeneration ?? _sessionGeneration;
    try {
      final mode = await _apiService.getBudgetMode();
      if (!_isCurrent(generation)) return;
      _budgetMode = mode;
      logDebug('Budget mode loaded: $_budgetMode', tag: 'BUDGET_PROVIDER');
      notifyListeners();
    } catch (e) {
      if (!_isCurrent(generation)) return;
      logError('Error loading budget mode: $e', tag: 'BUDGET_PROVIDER');
    }
  }

  /// Set budget mode
  Future<bool> setBudgetMode(String newMode) async {
    if (_isUpdatingMode) return false;
    final generation = _sessionGeneration;

    _isUpdatingMode = true;
    notifyListeners();

    try {
      await _apiService.setBudgetMode(newMode);
      if (!_isCurrent(generation)) return false;
      _budgetMode = newMode;
      logInfo('Budget mode set to: $newMode', tag: 'BUDGET_PROVIDER');
      notifyListeners();
      return true;
    } catch (e) {
      if (!_isCurrent(generation)) return false;
      logError('Error setting budget mode: $e', tag: 'BUDGET_PROVIDER');
      _errorMessage = 'Failed to update budget mode';
      return false;
    } finally {
      if (_isCurrent(generation)) {
        _isUpdatingMode = false;
        notifyListeners();
      }
    }
  }

  /// Load automation settings
  Future<void> loadAutomationSettings({int? sessionGeneration}) async {
    final generation = sessionGeneration ?? _sessionGeneration;
    try {
      final settings = await _apiService.getBudgetAutomationSettings();
      if (!_isCurrent(generation)) return;
      _automationSettings = settings;
      logDebug('Automation settings loaded', tag: 'BUDGET_PROVIDER');
      notifyListeners();
    } catch (e) {
      if (!_isCurrent(generation)) return;
      logError('Error loading automation settings: $e', tag: 'BUDGET_PROVIDER');
    }
  }

  /// Update automation settings
  Future<bool> updateAutomationSettings(
      Map<String, dynamic> newSettings) async {
    final generation = _sessionGeneration;
    try {
      await _apiService.updateBudgetAutomationSettings(newSettings);
      if (!_isCurrent(generation)) return false;
      _automationSettings = {..._automationSettings, ...newSettings};
      logInfo('Automation settings updated', tag: 'BUDGET_PROVIDER');
      notifyListeners();
      return true;
    } catch (e) {
      if (!_isCurrent(generation)) return false;
      logError('Error updating automation settings: $e',
          tag: 'BUDGET_PROVIDER');
      return false;
    }
  }

  /// Load budget remaining for current month
  Future<void> loadBudgetRemaining({int? sessionGeneration}) async {
    final generation = sessionGeneration ?? _sessionGeneration;
    try {
      final now = DateTime.now();
      final remaining = await _apiService.getBudgetRemaining(
          year: now.year, month: now.month);
      if (!_isCurrent(generation)) return;
      _budgetRemaining = remaining;
      logDebug('Budget remaining loaded', tag: 'BUDGET_PROVIDER');
      notifyListeners();
    } catch (e) {
      if (!_isCurrent(generation)) return;
      logError('Error loading budget remaining: $e', tag: 'BUDGET_PROVIDER');
    }
  }

  /// Load income-based budget recommendations
  Future<void> loadBudgetRecommendations(
    double monthlyIncome, {
    int? sessionGeneration,
  }) async {
    final generation = sessionGeneration ?? _sessionGeneration;
    try {
      final recommendations =
          await _apiService.getIncomeBasedBudgetRecommendations(monthlyIncome);
      if (!_isCurrent(generation)) return;
      _budgetRecommendations = recommendations;
      logDebug('Budget recommendations loaded', tag: 'BUDGET_PROVIDER');
      notifyListeners();
    } catch (e) {
      if (!_isCurrent(generation)) return;
      logError('Error loading budget recommendations: $e',
          tag: 'BUDGET_PROVIDER');
    }
  }

  /// Load behavioral budget allocation
  Future<void> loadBehavioralAllocation(double monthlyIncome,
      {Map<String, dynamic>? profile, int? sessionGeneration}) async {
    final generation = sessionGeneration ?? _sessionGeneration;
    try {
      final allocation = await _apiService
          .getBehavioralBudgetAllocation(monthlyIncome, profile: profile);
      if (!_isCurrent(generation)) return;
      _behavioralAllocation = allocation;
      logDebug('Behavioral allocation loaded', tag: 'BUDGET_PROVIDER');
      notifyListeners();
    } catch (e) {
      if (!_isCurrent(generation)) return;
      logError('Error loading behavioral allocation: $e',
          tag: 'BUDGET_PROVIDER');
    }
  }

  /// Load all budget settings data (for BudgetSettingsScreen)
  Future<void> loadBudgetSettingsData(double monthlyIncome,
      {String? incomeTier}) async {
    final generation = _sessionGeneration;
    _setLoading(true);
    try {
      await Future.wait([
        loadBudgetMode(sessionGeneration: generation),
        loadAutomationSettings(sessionGeneration: generation),
        loadBudgetRemaining(sessionGeneration: generation),
        loadBudgetRecommendations(
          monthlyIncome,
          sessionGeneration: generation,
        ),
        loadBehavioralAllocation(monthlyIncome,
            profile: incomeTier != null ? {'income_tier': incomeTier} : null,
            sessionGeneration: generation),
      ]);
      if (!_isCurrent(generation)) return;
      logInfo('Budget settings data loaded successfully',
          tag: 'BUDGET_PROVIDER');
    } catch (e) {
      if (!_isCurrent(generation)) return;
      logError('Error loading budget settings data: $e',
          tag: 'BUDGET_PROVIDER');
      _errorMessage = e.toString();
    } finally {
      if (_isCurrent(generation)) {
        _setLoading(false);
      }
    }
  }

  /// Load redistribution history
  Future<void> loadRedistributionHistory({int? sessionGeneration}) async {
    final generation = sessionGeneration ?? _sessionGeneration;
    try {
      final history = await _apiService.getBudgetRedistributionHistory();
      if (!_isCurrent(generation)) return;
      _redistributionHistory = asMapList(history);
      logDebug(
          'Redistribution history loaded: ${_redistributionHistory.length} items',
          tag: 'BUDGET_PROVIDER');
      notifyListeners();
    } catch (e) {
      if (!_isCurrent(generation)) return;
      logError('Error loading redistribution history: $e',
          tag: 'BUDGET_PROVIDER');
    }
  }

  /// Load calendar data with fallbacks
  Future<void> loadCalendarData({
    int? year,
    int? month,
    int? sessionGeneration,
  }) async {
    final generation = sessionGeneration ?? _sessionGeneration;
    final requestId = ++_calendarRequestId;
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
      if (!_isCurrent(generation) || requestId != _calendarRequestId) return;

      // ── Step 2: Merge ──
      // The saved-calendar payload already carries backend-computed spent
      // (recalculated from the ledger on every mutation), so we no longer
      // fetch /transactions/ just to recompute it — that redundant request
      // was also the source of the "calendar shows spent $0" bug when its
      // date filter missed a row. The overlay maps stay empty; the merge
      // uses them only as a shell-calendar fallback.
      final spentByDayCategory = <int, Map<String, double>>{};
      final spentByDay = <int, double>{};

      // ── Step 3: Merge planned budget + real spending ──
      final action = calendarLoadAction(
        savedIsEmpty: savedCalendar == null || savedCalendar.isEmpty,
        hasSavedData: _calendarHasSavedData,
        sameMonth: _calendarYear == targetYear && _calendarMonth == targetMonth,
      );
      switch (action) {
        case CalendarLoadAction.useSaved:
          final today = DateTime(now.year, now.month, now.day);
          _calendarData = savedCalendar!
              .map<Map<String, dynamic>>((dynamic raw) => mergeSavedCalendarDay(
                    Map<String, dynamic>.from(raw as Map),
                    today: today,
                    spentByDay: spentByDay,
                    spentByDayCategory: spentByDayCategory,
                  ))
              .toList();
          _calendarYear = targetYear;
          _calendarMonth = targetMonth;
          _calendarHasSavedData = true;
          logInfo(
              'Calendar ready: ${_calendarData.length} days with real spending data',
              tag: 'BUDGET_PROVIDER');
          break;
        case CalendarLoadAction.keepExisting:
          // Real saved data already loaded for THIS month and the backend just
          // returned empty (a transient blip right after a mutation). Keep it —
          // a shell preview must never replace it (the post-delete "$5379
          // shell" bug).
          logWarning(
              'Empty saved calendar for $targetYear-$targetMonth — keeping '
              'existing saved data instead of shell preview',
              tag: 'BUDGET_PROVIDER');
          break;
        case CalendarLoadAction.useShell:
          // Genuinely no saved calendar for this month (new user / new month /
          // a month the user navigated to that was never onboarded).
          logWarning(
              'No saved calendar for $targetYear-$targetMonth — using shell preview',
              tag: 'BUDGET_PROVIDER');
          final shellCalendar = await _apiService.getCalendar();
          if (!_isCurrent(generation) || requestId != _calendarRequestId) {
            return;
          }
          _calendarData = asMapList(shellCalendar);
          _calendarYear = targetYear;
          _calendarMonth = targetMonth;
          _calendarHasSavedData = false;
          break;
      }

      _state = BudgetState.loaded;
      _errorMessage = null;
    } catch (e) {
      if (!_isCurrent(generation) || requestId != _calendarRequestId) return;
      logError('Calendar load failed: $e', tag: 'BUDGET_PROVIDER');
      _errorMessage = 'Failed to load calendar data';
      _state = BudgetState.error;
      // A transient load error must not wipe real saved data for the month the
      // user is viewing — the calendar would flash empty then shell-preview on
      // the next refresh. Only clear when we hold no saved data for this month.
      if (!(_calendarHasSavedData &&
          _calendarYear == targetYear &&
          _calendarMonth == targetMonth)) {
        _calendarData = [];
      }
    } finally {
      if (_isCurrent(generation) && requestId == _calendarRequestId) {
        _isLoading = false;
        notifyListeners();
      }
    }
  }

  /// Load AI budget optimization
  Future<void> loadAIOptimization({int? sessionGeneration}) async {
    final generation = sessionGeneration ?? _sessionGeneration;
    try {
      // AI context input: use the already-merged calendar when present.
      // This method used to fetch the shell preview and ASSIGN it to
      // _calendarData, racing loadCalendarData inside the same
      // Future.wait — the real saved+transactions merge got stomped by
      // the planning preview (or by [] whenever the shell call hit its
      // 10s watchdog), and the dashboard rendered fallback targets.
      var calendarData = List<Map<String, dynamic>>.from(_calendarData);
      if (calendarData.isEmpty) {
        calendarData = asMapList(await _apiService.getCalendar());
        if (!_isCurrent(generation)) return;
      }

      Map<String, dynamic> calendarDict = {};
      for (final day in asMapList(calendarData)) {
        final dayNum = asInt(day['day']).toString();
        calendarDict[dayNum] = {
          'spent': asDouble(day['spent']),
          'limit': asDouble(day['limit']),
        };
      }

      // Get user income
      final profile = await _apiService.getUserProfile();
      if (!_isCurrent(generation)) return;
      final incomeData = asStringKeyedMap(profile['data'])['income'];
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
      if (!_isCurrent(generation)) return;

      _aiOptimization = optimization;
      logInfo('AI budget optimization loaded successfully',
          tag: 'BUDGET_PROVIDER');
      notifyListeners();
    } catch (e) {
      if (!_isCurrent(generation)) return;
      logError('Error loading AI budget optimization: $e',
          tag: 'BUDGET_PROVIDER');
    }
  }

  /// Load budget adaptations
  Future<void> loadBudgetAdaptations({int? sessionGeneration}) async {
    final generation = sessionGeneration ?? _sessionGeneration;
    try {
      final adaptations = await _apiService.getBudgetAdaptations();
      if (!_isCurrent(generation)) return;
      _budgetAdaptations = adaptations;
      logInfo('Budget adaptations loaded successfully', tag: 'BUDGET_PROVIDER');
      notifyListeners();
    } catch (e) {
      if (!_isCurrent(generation)) return;
      logError('Error loading budget adaptations: $e', tag: 'BUDGET_PROVIDER');
    }
  }

  /// Trigger budget redistribution
  Future<bool> redistributeBudget() async {
    if (_isRedistributing) return false;
    final generation = _sessionGeneration;

    _isRedistributing = true;
    notifyListeners();

    try {
      logInfo('Starting budget redistribution', tag: 'BUDGET_PROVIDER');

      // Get current calendar data
      final calendarData = await _apiService.getCalendar();
      if (!_isCurrent(generation)) return false;
      if (calendarData.isEmpty) {
        throw Exception('No calendar data available for redistribution');
      }

      // Convert to expected format
      Map<String, Map<String, dynamic>> calendarDict = {};
      for (final day in asMapList(calendarData)) {
        final dayNum = asInt(day['day']).toString();
        calendarDict[dayNum] = {
          'total': asDouble(day['spent']),
          'limit': asDouble(day['limit']),
        };
      }

      // Trigger redistribution
      await _apiService.redistributeCalendarBudget(calendarDict);
      if (!_isCurrent(generation)) return false;

      // Refresh all data
      await loadAllBudgetData(sessionGeneration: generation);
      if (!_isCurrent(generation)) return false;

      logInfo('Budget redistribution completed successfully',
          tag: 'BUDGET_PROVIDER');
      return true;
    } catch (e) {
      if (!_isCurrent(generation)) return false;
      logError('Budget redistribution failed: $e', tag: 'BUDGET_PROVIDER');
      _errorMessage = 'Failed to redistribute budget: $e';
      return false;
    } finally {
      if (_isCurrent(generation)) {
        _isRedistributing = false;
        notifyListeners();
      }
    }
  }

  /// Trigger automatic budget adaptation
  Future<bool> triggerAutoAdaptation() async {
    final generation = _sessionGeneration;
    try {
      logInfo('Starting automatic budget adaptation', tag: 'BUDGET_PROVIDER');

      await _apiService.triggerBudgetAdaptation();
      if (!_isCurrent(generation)) return false;
      await loadAllBudgetData(sessionGeneration: generation);
      if (!_isCurrent(generation)) return false;

      logInfo('Budget adaptation completed successfully',
          tag: 'BUDGET_PROVIDER');
      return true;
    } catch (e) {
      if (!_isCurrent(generation)) return false;
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

  /// Called after a transaction is successfully created.
  /// If the transaction triggered a rebalance, refreshes redistribution history.
  Future<void> onTransactionCreated({bool rebalanced = false}) async {
    await onLedgerChanged(rebalanced: rebalanced);
  }

  /// Reload the budget data a ledger mutation (create/edit/delete)
  /// invalidates. The backend recalculates DailyPlan.spent and may
  /// auto-redistribute budget between days, so daily budgets, the merged
  /// calendar, and live status are all stale after any transaction write —
  /// previously only redistribution history was refreshed and the
  /// dashboard kept showing pre-mutation numbers until an app restart.
  Future<void> onLedgerChanged({bool rebalanced = false}) async {
    final generation = _sessionGeneration;
    await Future.wait([
      loadDailyBudgets(sessionGeneration: generation),
      loadCalendarData(sessionGeneration: generation),
      loadLiveBudgetStatus(sessionGeneration: generation),
      if (rebalanced) loadRedistributionHistory(sessionGeneration: generation),
    ]);
  }

  /// Clear account-scoped state synchronously at an authentication boundary.
  ///
  /// Incrementing the generation first invalidates every pending response from
  /// the previous account. Request sequence counters also prevent older
  /// same-session live/calendar responses from overwriting newer ones.
  void resetSession() {
    _sessionGeneration += 1;
    _dailyBudgetsRequestId += 1;
    _liveStatusRequestId += 1;
    _calendarRequestId += 1;
    _initializeInFlight = null;
    _initializeGeneration = null;
    _budgetUpdateSubscription?.cancel();
    _budgetUpdateSubscription = null;
    _liveUpdates.resetSession();
    _budgetService.resetSession();
    _clearSessionData();
    notifyListeners();
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

  bool _isCurrent(int generation) => generation == _sessionGeneration;
}
