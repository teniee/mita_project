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
  final ApiService _apiService = ApiService();

  // State
  BehavioralState _state = BehavioralState.initial;
  bool _isLoading = false;
  String? _errorMessage;

  // Behavioral data
  Map<String, dynamic> _patterns = {};
  Map<String, dynamic> _predictions = {};
  List<dynamic> _anomalies = [];
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
  List<dynamic> get anomalies => _anomalies;
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
  List<Map<String, dynamic>> get behavioralExpenseSuggestions => _behavioralExpenseSuggestions;
  Map<String, dynamic> get behavioralNotificationSettings => _behavioralNotificationSettings;

  /// Initialize the provider and load all behavioral data
  Future<void> initialize() async {
    if (_state != BehavioralState.initial) return;

    logInfo('Initializing BehavioralProvider', tag: 'BEHAVIORAL_PROVIDER');
    await loadBehavioralData();
  }

  /// Load all behavioral data from API
  Future<void> loadBehavioralData() async {
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

      _patterns = Map<String, dynamic>.from(results[0] as Map);
      _predictions = Map<String, dynamic>.from(results[1] as Map);
      _anomalies = List<dynamic>.from(results[2] as List);
      _insights = Map<String, dynamic>.from(results[3] as Map);
      _behavioralPredictions = Map<String, dynamic>.from(results[4] as Map);
      _adaptiveRecommendations = Map<String, dynamic>.from(results[5] as Map);
      _behavioralCluster = Map<String, dynamic>.from(results[6] as Map);
      _behavioralProgress = Map<String, dynamic>.from(results[7] as Map);
      _behavioralAnomalies = Map<String, dynamic>.from(results[8] as Map);
      _spendingTriggers = Map<String, dynamic>.from(results[9] as Map);
      _behavioralWarnings = Map<String, dynamic>.from(results[10] as Map);
      _behavioralPreferences = Map<String, dynamic>.from(results[11] as Map);
      _behavioralCalendar = Map<String, dynamic>.from(results[12] as Map);
      _behavioralExpenseSuggestions = List<Map<String, dynamic>>.from(results[13] as List? ?? []);
      _behavioralNotificationSettings = Map<String, dynamic>.from(results[14] as Map);

      _state = BehavioralState.loaded;
      logInfo('Behavioral data loaded successfully', tag: 'BEHAVIORAL_PROVIDER');
    } catch (e) {
      logError('Error loading behavioral data: $e', tag: 'BEHAVIORAL_PROVIDER');
      _errorMessage = e.toString();
      _state = BehavioralState.error;
    } finally {
      _setLoading(false);
    }
  }

  /// Refresh all behavioral data
  Future<void> refresh() async {
    await loadBehavioralData();
  }

  /// Load spending patterns
  Future<void> loadSpendingPatterns({int? year, int? month}) async {
    try {
      _setLoading(true);
      _patterns = await _apiService.getSpendingPatterns(year: year, month: month);
      logInfo('Spending patterns loaded', tag: 'BEHAVIORAL_PROVIDER');
      notifyListeners();
    } catch (e) {
      logError('Error loading spending patterns: $e', tag: 'BEHAVIORAL_PROVIDER');
      _errorMessage = 'Failed to load spending patterns';
    } finally {
      _setLoading(false);
    }
  }

  /// Load behavioral predictions
  Future<void> loadBehavioralPredictions() async {
    try {
      _setLoading(true);
      _behavioralPredictions = await _apiService.getBehavioralPredictions();
      logInfo('Behavioral predictions loaded', tag: 'BEHAVIORAL_PROVIDER');
      notifyListeners();
    } catch (e) {
      logError('Error loading behavioral predictions: $e', tag: 'BEHAVIORAL_PROVIDER');
      _errorMessage = 'Failed to load behavioral predictions';
    } finally {
      _setLoading(false);
    }
  }

  /// Load behavioral progress
  Future<void> loadBehavioralProgress({int months = 6}) async {
    try {
      _setLoading(true);
      _behavioralProgress = await _apiService.getBehavioralProgress(months: months);
      logInfo('Behavioral progress loaded', tag: 'BEHAVIORAL_PROVIDER');
      notifyListeners();
    } catch (e) {
      logError('Error loading behavioral progress: $e', tag: 'BEHAVIORAL_PROVIDER');
      _errorMessage = 'Failed to load behavioral progress';
    } finally {
      _setLoading(false);
    }
  }

  /// Load behavioral cluster
  Future<void> loadBehavioralCluster() async {
    try {
      _setLoading(true);
      _behavioralCluster = await _apiService.getBehavioralCluster();
      logInfo('Behavioral cluster loaded', tag: 'BEHAVIORAL_PROVIDER');
      notifyListeners();
    } catch (e) {
      logError('Error loading behavioral cluster: $e', tag: 'BEHAVIORAL_PROVIDER');
      _errorMessage = 'Failed to load behavioral cluster';
    } finally {
      _setLoading(false);
    }
  }

  /// Load spending triggers
  Future<void> loadSpendingTriggers({int? year, int? month}) async {
    try {
      _setLoading(true);
      _spendingTriggers = await _apiService.getSpendingTriggers(year: year, month: month);
      logInfo('Spending triggers loaded', tag: 'BEHAVIORAL_PROVIDER');
      notifyListeners();
    } catch (e) {
      logError('Error loading spending triggers: $e', tag: 'BEHAVIORAL_PROVIDER');
      _errorMessage = 'Failed to load spending triggers';
    } finally {
      _setLoading(false);
    }
  }

  /// Load adaptive recommendations
  Future<void> loadAdaptiveRecommendations() async {
    try {
      _setLoading(true);
      _adaptiveRecommendations = await _apiService.getAdaptiveBehaviorRecommendations();
      logInfo('Adaptive recommendations loaded', tag: 'BEHAVIORAL_PROVIDER');
      notifyListeners();
    } catch (e) {
      logError('Error loading adaptive recommendations: $e', tag: 'BEHAVIORAL_PROVIDER');
      _errorMessage = 'Failed to load adaptive recommendations';
    } finally {
      _setLoading(false);
    }
  }

  /// Load behavioral warnings
  Future<void> loadBehavioralWarnings({int? year, int? month}) async {
    try {
      _setLoading(true);
      _behavioralWarnings = await _apiService.getBehavioralWarnings(year: year, month: month);
      logInfo('Behavioral warnings loaded', tag: 'BEHAVIORAL_PROVIDER');
      notifyListeners();
    } catch (e) {
      logError('Error loading behavioral warnings: $e', tag: 'BEHAVIORAL_PROVIDER');
      _errorMessage = 'Failed to load behavioral warnings';
    } finally {
      _setLoading(false);
    }
  }

  /// Load behavioral expense suggestions
  Future<void> loadBehavioralExpenseSuggestions({
    String? category,
    double? amount,
    String? description,
    String? date,
  }) async {
    try {
      _setLoading(true);
      final result = await _apiService.getBehavioralExpenseSuggestions(
        category: category,
        amount: amount,
        description: description,
        date: date,
      );
      _behavioralExpenseSuggestions = List<Map<String, dynamic>>.from(result as List? ?? []);
      logInfo('Behavioral expense suggestions loaded', tag: 'BEHAVIORAL_PROVIDER');
      notifyListeners();
    } catch (e) {
      logError('Error loading behavioral expense suggestions: $e', tag: 'BEHAVIORAL_PROVIDER');
      _errorMessage = 'Failed to load behavioral expense suggestions';
    } finally {
      _setLoading(false);
    }
  }

  /// Load behavioral notification settings
  Future<void> loadBehavioralNotificationSettings() async {
    try {
      _setLoading(true);
      _behavioralNotificationSettings = await _apiService.getBehavioralNotificationSettings();
      logInfo('Behavioral notification settings loaded', tag: 'BEHAVIORAL_PROVIDER');
      notifyListeners();
    } catch (e) {
      logError('Error loading behavioral notification settings: $e', tag: 'BEHAVIORAL_PROVIDER');
      _errorMessage = 'Failed to load behavioral notification settings';
    } finally {
      _setLoading(false);
    }
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
}
