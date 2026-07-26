import '../utils/json_utils.dart';
import 'package:flutter/foundation.dart';
import '../services/api_service.dart';
import '../services/logging_service.dart';

/// Behavioral state enum for tracking loading states
enum BehavioralState {
  initial,
  loading,
  loaded,
  error,
}

/// Centralized behavioral insights state management provider
/// Manages spending patterns, predictions, anomalies, and behavioral analysis
class BehavioralProvider extends ChangeNotifier {
  BehavioralProvider({ApiService? apiService})
      : _apiService = apiService ?? ApiService();

  final ApiService _apiService;
  int _sessionGeneration = 0;
  int _behavioralDataRequestId = 0;
  final Map<String, int> _resourceRequestIds = {};

  static const _patternsResource = 'patterns';
  static const _predictionsResource = 'predictions';
  static const _anomaliesResource = 'anomalies';
  static const _insightsResource = 'insights';
  static const _behavioralPredictionsResource = 'behavioral_predictions';
  static const _adaptiveRecommendationsResource = 'adaptive_recommendations';
  static const _behavioralClusterResource = 'behavioral_cluster';
  static const _behavioralProgressResource = 'behavioral_progress';
  static const _behavioralAnomaliesResource = 'behavioral_anomalies';
  static const _spendingTriggersResource = 'spending_triggers';
  static const _behavioralWarningsResource = 'behavioral_warnings';
  static const _behavioralPreferencesResource = 'behavioral_preferences';
  static const _behavioralCalendarResource = 'behavioral_calendar';
  static const _expenseSuggestionsResource = 'expense_suggestions';
  static const _notificationSettingsResource = 'notification_settings';

  // State
  BehavioralState _state = BehavioralState.initial;
  bool _isLoading = false;
  String? _errorMessage;

  // Behavioral data
  Map<String, dynamic> _patterns = {};
  Map<String, dynamic> _predictions = {};
  List<Map<String, dynamic>> _anomalies = [];
  Map<String, dynamic> _insights = {};
  Map<String, dynamic> _behavioralPredictions = {};
  Map<String, dynamic> _adaptiveRecommendations = {};
  Map<String, dynamic> _behavioralCluster = {};
  Map<String, dynamic> _behavioralProgress = {};
  Map<String, dynamic> _behavioralAnomalies = {};
  Map<String, dynamic> _spendingTriggers = {};
  Map<String, dynamic> _behavioralWarnings = {};
  Map<String, dynamic> _behavioralPreferences = {};
  Map<String, dynamic> _behavioralCalendar = {};
  List<Map<String, dynamic>> _behavioralExpenseSuggestions = [];
  Map<String, dynamic> _behavioralNotificationSettings = {};

  // Getters
  BehavioralState get state => _state;
  bool get isLoading => _isLoading;
  String? get errorMessage => _errorMessage;

  // Data getters
  Map<String, dynamic> get patterns => _patterns;
  Map<String, dynamic> get predictions => _predictions;
  List<Map<String, dynamic>> get anomalies => _anomalies;
  Map<String, dynamic> get insights => _insights;
  Map<String, dynamic> get behavioralPredictions => _behavioralPredictions;
  Map<String, dynamic> get adaptiveRecommendations => _adaptiveRecommendations;
  Map<String, dynamic> get behavioralCluster => _behavioralCluster;
  Map<String, dynamic> get behavioralProgress => _behavioralProgress;
  Map<String, dynamic> get behavioralAnomalies => _behavioralAnomalies;
  Map<String, dynamic> get spendingTriggers => _spendingTriggers;
  Map<String, dynamic> get behavioralWarnings => _behavioralWarnings;
  Map<String, dynamic> get behavioralPreferences => _behavioralPreferences;
  Map<String, dynamic> get behavioralCalendar => _behavioralCalendar;
  List<Map<String, dynamic>> get behavioralExpenseSuggestions =>
      _behavioralExpenseSuggestions;
  Map<String, dynamic> get behavioralNotificationSettings =>
      _behavioralNotificationSettings;

  /// Initialize the provider and load all behavioral data
  Future<void> initialize() async {
    if (_state != BehavioralState.initial) return;

    logInfo('Initializing BehavioralProvider', tag: 'BEHAVIORAL_PROVIDER');
    await loadBehavioralData();
  }

  /// Load all behavioral data from API
  Future<void> loadBehavioralData() async {
    final generation = _sessionGeneration;
    final aggregateRequestId = ++_behavioralDataRequestId;
    final requestIds = _claimAllResourceRequests();
    _setLoading(true);
    _state = BehavioralState.loading;
    notifyListeners();

    try {
      final results = await Future.wait([
        _apiService.getSpendingPatterns(),
        _apiService.getBehaviorPredictions(),
        _apiService.getBehaviorAnomalies(),
        _apiService.getBehaviorInsights(),
        _apiService.getBehavioralPredictions(),
        _apiService.getAdaptiveBehaviorRecommendations(),
        _apiService.getBehavioralCluster(),
        _apiService.getBehavioralProgress(months: 6),
        _apiService.getBehavioralAnomalies(),
        _apiService.getSpendingTriggers(),
        _apiService.getBehavioralWarnings(),
        _apiService.getBehavioralPreferences(),
        _apiService.getBehaviorCalendar(),
        _apiService.getBehavioralExpenseSuggestions(),
        _apiService.getBehavioralNotificationSettings(),
      ]);

      if (!_isCurrentSession(generation)) return;

      if (_isCurrentResourceRequest(
          generation, _patternsResource, requestIds[_patternsResource]!)) {
        _patterns = Map<String, dynamic>.from(results[0] as Map);
      }
      if (_isCurrentResourceRequest(generation, _predictionsResource,
          requestIds[_predictionsResource]!)) {
        _predictions = Map<String, dynamic>.from(results[1] as Map);
      }
      if (_isCurrentResourceRequest(
          generation, _anomaliesResource, requestIds[_anomaliesResource]!)) {
        _anomalies = asMapList(results[2]);
      }
      if (_isCurrentResourceRequest(
          generation, _insightsResource, requestIds[_insightsResource]!)) {
        _insights = Map<String, dynamic>.from(results[3] as Map);
      }
      if (_isCurrentResourceRequest(
        generation,
        _behavioralPredictionsResource,
        requestIds[_behavioralPredictionsResource]!,
      )) {
        _behavioralPredictions = Map<String, dynamic>.from(results[4] as Map);
      }
      if (_isCurrentResourceRequest(
        generation,
        _adaptiveRecommendationsResource,
        requestIds[_adaptiveRecommendationsResource]!,
      )) {
        _adaptiveRecommendations = Map<String, dynamic>.from(results[5] as Map);
      }
      if (_isCurrentResourceRequest(
        generation,
        _behavioralClusterResource,
        requestIds[_behavioralClusterResource]!,
      )) {
        _behavioralCluster = Map<String, dynamic>.from(results[6] as Map);
      }
      if (_isCurrentResourceRequest(
        generation,
        _behavioralProgressResource,
        requestIds[_behavioralProgressResource]!,
      )) {
        _behavioralProgress = Map<String, dynamic>.from(results[7] as Map);
      }
      if (_isCurrentResourceRequest(
        generation,
        _behavioralAnomaliesResource,
        requestIds[_behavioralAnomaliesResource]!,
      )) {
        _behavioralAnomalies = Map<String, dynamic>.from(results[8] as Map);
      }
      if (_isCurrentResourceRequest(
        generation,
        _spendingTriggersResource,
        requestIds[_spendingTriggersResource]!,
      )) {
        _spendingTriggers = Map<String, dynamic>.from(results[9] as Map);
      }
      if (_isCurrentResourceRequest(
        generation,
        _behavioralWarningsResource,
        requestIds[_behavioralWarningsResource]!,
      )) {
        _behavioralWarnings = Map<String, dynamic>.from(results[10] as Map);
      }
      if (_isCurrentResourceRequest(
        generation,
        _behavioralPreferencesResource,
        requestIds[_behavioralPreferencesResource]!,
      )) {
        _behavioralPreferences = Map<String, dynamic>.from(results[11] as Map);
      }
      if (_isCurrentResourceRequest(
        generation,
        _behavioralCalendarResource,
        requestIds[_behavioralCalendarResource]!,
      )) {
        _behavioralCalendar = Map<String, dynamic>.from(results[12] as Map);
      }
      if (_isCurrentResourceRequest(
        generation,
        _expenseSuggestionsResource,
        requestIds[_expenseSuggestionsResource]!,
      )) {
        _behavioralExpenseSuggestions =
            List<Map<String, dynamic>>.from(results[13] as List? ?? []);
      }
      if (_isCurrentResourceRequest(
        generation,
        _notificationSettingsResource,
        requestIds[_notificationSettingsResource]!,
      )) {
        _behavioralNotificationSettings =
            Map<String, dynamic>.from(results[14] as Map);
      }

      if (_isCurrentAggregateRequest(generation, aggregateRequestId)) {
        _state = BehavioralState.loaded;
      }
      logInfo('Behavioral data loaded successfully',
          tag: 'BEHAVIORAL_PROVIDER');
    } catch (e) {
      logError('Error loading behavioral data: $e', tag: 'BEHAVIORAL_PROVIDER');
      if (!_isCurrentAggregateRequest(generation, aggregateRequestId)) return;
      _errorMessage = e.toString();
      _state = BehavioralState.error;
    } finally {
      if (_isCurrentAggregateRequest(generation, aggregateRequestId)) {
        _setLoading(false);
      }
    }
  }

  /// Refresh all behavioral data
  Future<void> refresh() async {
    await loadBehavioralData();
  }

  /// Load spending patterns
  Future<void> loadSpendingPatterns({int? year, int? month}) async {
    final generation = _sessionGeneration;
    final requestId = _nextResourceRequestId(_patternsResource);
    try {
      _setLoading(true);
      final patterns =
          await _apiService.getSpendingPatterns(year: year, month: month);
      if (!_isCurrentResourceRequest(
          generation, _patternsResource, requestId)) {
        return;
      }
      _patterns = patterns;
      logInfo('Spending patterns loaded', tag: 'BEHAVIORAL_PROVIDER');
      notifyListeners();
    } catch (e) {
      logError('Error loading spending patterns: $e',
          tag: 'BEHAVIORAL_PROVIDER');
      if (!_isCurrentResourceRequest(
          generation, _patternsResource, requestId)) {
        return;
      }
      _errorMessage = 'Failed to load spending patterns';
    } finally {
      if (_isCurrentResourceRequest(generation, _patternsResource, requestId)) {
        _setLoading(false);
      }
    }
  }

  /// Load behavioral predictions
  Future<void> loadBehavioralPredictions() async {
    final generation = _sessionGeneration;
    final requestId = _nextResourceRequestId(_behavioralPredictionsResource);
    try {
      _setLoading(true);
      final predictions = await _apiService.getBehavioralPredictions();
      if (!_isCurrentResourceRequest(
          generation, _behavioralPredictionsResource, requestId)) {
        return;
      }
      _behavioralPredictions = predictions;
      logInfo('Behavioral predictions loaded', tag: 'BEHAVIORAL_PROVIDER');
      notifyListeners();
    } catch (e) {
      logError('Error loading behavioral predictions: $e',
          tag: 'BEHAVIORAL_PROVIDER');
      if (!_isCurrentResourceRequest(
          generation, _behavioralPredictionsResource, requestId)) {
        return;
      }
      _errorMessage = 'Failed to load behavioral predictions';
    } finally {
      if (_isCurrentResourceRequest(
          generation, _behavioralPredictionsResource, requestId)) {
        _setLoading(false);
      }
    }
  }

  /// Load behavioral progress
  Future<void> loadBehavioralProgress({int months = 6}) async {
    final generation = _sessionGeneration;
    final requestId = _nextResourceRequestId(_behavioralProgressResource);
    try {
      _setLoading(true);
      final progress = await _apiService.getBehavioralProgress(months: months);
      if (!_isCurrentResourceRequest(
          generation, _behavioralProgressResource, requestId)) {
        return;
      }
      _behavioralProgress = progress;
      logInfo('Behavioral progress loaded', tag: 'BEHAVIORAL_PROVIDER');
      notifyListeners();
    } catch (e) {
      logError('Error loading behavioral progress: $e',
          tag: 'BEHAVIORAL_PROVIDER');
      if (!_isCurrentResourceRequest(
          generation, _behavioralProgressResource, requestId)) {
        return;
      }
      _errorMessage = 'Failed to load behavioral progress';
    } finally {
      if (_isCurrentResourceRequest(
          generation, _behavioralProgressResource, requestId)) {
        _setLoading(false);
      }
    }
  }

  /// Load behavioral cluster
  Future<void> loadBehavioralCluster() async {
    final generation = _sessionGeneration;
    final requestId = _nextResourceRequestId(_behavioralClusterResource);
    try {
      _setLoading(true);
      final cluster = await _apiService.getBehavioralCluster();
      if (!_isCurrentResourceRequest(
          generation, _behavioralClusterResource, requestId)) {
        return;
      }
      _behavioralCluster = cluster;
      logInfo('Behavioral cluster loaded', tag: 'BEHAVIORAL_PROVIDER');
      notifyListeners();
    } catch (e) {
      logError('Error loading behavioral cluster: $e',
          tag: 'BEHAVIORAL_PROVIDER');
      if (!_isCurrentResourceRequest(
          generation, _behavioralClusterResource, requestId)) {
        return;
      }
      _errorMessage = 'Failed to load behavioral cluster';
    } finally {
      if (_isCurrentResourceRequest(
          generation, _behavioralClusterResource, requestId)) {
        _setLoading(false);
      }
    }
  }

  /// Load spending triggers
  Future<void> loadSpendingTriggers({int? year, int? month}) async {
    final generation = _sessionGeneration;
    final requestId = _nextResourceRequestId(_spendingTriggersResource);
    try {
      _setLoading(true);
      final triggers =
          await _apiService.getSpendingTriggers(year: year, month: month);
      if (!_isCurrentResourceRequest(
          generation, _spendingTriggersResource, requestId)) {
        return;
      }
      _spendingTriggers = triggers;
      logInfo('Spending triggers loaded', tag: 'BEHAVIORAL_PROVIDER');
      notifyListeners();
    } catch (e) {
      logError('Error loading spending triggers: $e',
          tag: 'BEHAVIORAL_PROVIDER');
      if (!_isCurrentResourceRequest(
          generation, _spendingTriggersResource, requestId)) {
        return;
      }
      _errorMessage = 'Failed to load spending triggers';
    } finally {
      if (_isCurrentResourceRequest(
          generation, _spendingTriggersResource, requestId)) {
        _setLoading(false);
      }
    }
  }

  /// Load adaptive recommendations
  Future<void> loadAdaptiveRecommendations() async {
    final generation = _sessionGeneration;
    final requestId = _nextResourceRequestId(_adaptiveRecommendationsResource);
    try {
      _setLoading(true);
      final recommendations =
          await _apiService.getAdaptiveBehaviorRecommendations();
      if (!_isCurrentResourceRequest(
          generation, _adaptiveRecommendationsResource, requestId)) {
        return;
      }
      _adaptiveRecommendations = recommendations;
      logInfo('Adaptive recommendations loaded', tag: 'BEHAVIORAL_PROVIDER');
      notifyListeners();
    } catch (e) {
      logError('Error loading adaptive recommendations: $e',
          tag: 'BEHAVIORAL_PROVIDER');
      if (!_isCurrentResourceRequest(
          generation, _adaptiveRecommendationsResource, requestId)) {
        return;
      }
      _errorMessage = 'Failed to load adaptive recommendations';
    } finally {
      if (_isCurrentResourceRequest(
          generation, _adaptiveRecommendationsResource, requestId)) {
        _setLoading(false);
      }
    }
  }

  /// Load behavioral warnings
  Future<void> loadBehavioralWarnings({int? year, int? month}) async {
    final generation = _sessionGeneration;
    final requestId = _nextResourceRequestId(_behavioralWarningsResource);
    try {
      _setLoading(true);
      final warnings =
          await _apiService.getBehavioralWarnings(year: year, month: month);
      if (!_isCurrentResourceRequest(
          generation, _behavioralWarningsResource, requestId)) {
        return;
      }
      _behavioralWarnings = warnings;
      logInfo('Behavioral warnings loaded', tag: 'BEHAVIORAL_PROVIDER');
      notifyListeners();
    } catch (e) {
      logError('Error loading behavioral warnings: $e',
          tag: 'BEHAVIORAL_PROVIDER');
      if (!_isCurrentResourceRequest(
          generation, _behavioralWarningsResource, requestId)) {
        return;
      }
      _errorMessage = 'Failed to load behavioral warnings';
    } finally {
      if (_isCurrentResourceRequest(
          generation, _behavioralWarningsResource, requestId)) {
        _setLoading(false);
      }
    }
  }

  /// Load behavioral expense suggestions
  Future<void> loadBehavioralExpenseSuggestions({
    String? category,
    double? amount,
    String? description,
    String? date,
  }) async {
    final generation = _sessionGeneration;
    final requestId = _nextResourceRequestId(_expenseSuggestionsResource);
    try {
      _setLoading(true);
      final result = await _apiService.getBehavioralExpenseSuggestions(
        category: category,
        amount: amount,
        description: description,
        date: date,
      );
      if (!_isCurrentResourceRequest(
          generation, _expenseSuggestionsResource, requestId)) {
        return;
      }
      _behavioralExpenseSuggestions =
          List<Map<String, dynamic>>.from(result as List? ?? []);
      logInfo('Behavioral expense suggestions loaded',
          tag: 'BEHAVIORAL_PROVIDER');
      notifyListeners();
    } catch (e) {
      logError('Error loading behavioral expense suggestions: $e',
          tag: 'BEHAVIORAL_PROVIDER');
      if (!_isCurrentResourceRequest(
          generation, _expenseSuggestionsResource, requestId)) {
        return;
      }
      _errorMessage = 'Failed to load behavioral expense suggestions';
    } finally {
      if (_isCurrentResourceRequest(
          generation, _expenseSuggestionsResource, requestId)) {
        _setLoading(false);
      }
    }
  }

  /// Load behavioral notification settings
  Future<void> loadBehavioralNotificationSettings() async {
    final generation = _sessionGeneration;
    final requestId = _nextResourceRequestId(_notificationSettingsResource);
    try {
      _setLoading(true);
      final settings = await _apiService.getBehavioralNotificationSettings();
      if (!_isCurrentResourceRequest(
          generation, _notificationSettingsResource, requestId)) {
        return;
      }
      _behavioralNotificationSettings = settings;
      logInfo('Behavioral notification settings loaded',
          tag: 'BEHAVIORAL_PROVIDER');
      notifyListeners();
    } catch (e) {
      logError('Error loading behavioral notification settings: $e',
          tag: 'BEHAVIORAL_PROVIDER');
      if (!_isCurrentResourceRequest(
          generation, _notificationSettingsResource, requestId)) {
        return;
      }
      _errorMessage = 'Failed to load behavioral notification settings';
    } finally {
      if (_isCurrentResourceRequest(
          generation, _notificationSettingsResource, requestId)) {
        _setLoading(false);
      }
    }
  }

  /// Discard all state owned by the previous authenticated account.
  void resetSession() {
    _sessionGeneration++;
    _behavioralDataRequestId++;
    for (final resource in _resourceRequestIds.keys.toList()) {
      _resourceRequestIds[resource] = (_resourceRequestIds[resource] ?? 0) + 1;
    }
    _state = BehavioralState.initial;
    _isLoading = false;
    _errorMessage = null;
    _patterns = {};
    _predictions = {};
    _anomalies = [];
    _insights = {};
    _behavioralPredictions = {};
    _adaptiveRecommendations = {};
    _behavioralCluster = {};
    _behavioralProgress = {};
    _behavioralAnomalies = {};
    _spendingTriggers = {};
    _behavioralWarnings = {};
    _behavioralPreferences = {};
    _behavioralCalendar = {};
    _behavioralExpenseSuggestions = [];
    _behavioralNotificationSettings = {};
    _resourceRequestIds.clear();
    notifyListeners();
  }

  /// Clear error message
  void clearError() {
    _errorMessage = null;
    notifyListeners();
  }

  // Private helper
  void _setLoading(bool loading) {
    _isLoading = loading;
    notifyListeners();
  }

  bool _isCurrentSession(int generation) => generation == _sessionGeneration;

  int _nextResourceRequestId(String resource) {
    final requestId = (_resourceRequestIds[resource] ?? 0) + 1;
    _resourceRequestIds[resource] = requestId;
    return requestId;
  }

  Map<String, int> _claimAllResourceRequests() {
    return {
      for (final resource in const [
        _patternsResource,
        _predictionsResource,
        _anomaliesResource,
        _insightsResource,
        _behavioralPredictionsResource,
        _adaptiveRecommendationsResource,
        _behavioralClusterResource,
        _behavioralProgressResource,
        _behavioralAnomaliesResource,
        _spendingTriggersResource,
        _behavioralWarningsResource,
        _behavioralPreferencesResource,
        _behavioralCalendarResource,
        _expenseSuggestionsResource,
        _notificationSettingsResource,
      ])
        resource: _nextResourceRequestId(resource),
    };
  }

  bool _isCurrentAggregateRequest(int generation, int requestId) =>
      _isCurrentSession(generation) && requestId == _behavioralDataRequestId;

  bool _isCurrentResourceRequest(
          int generation, String resource, int requestId) =>
      _isCurrentSession(generation) &&
      requestId == (_resourceRequestIds[resource] ?? 0);
}
