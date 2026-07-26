import 'package:flutter/foundation.dart';
import '../services/api_service.dart';
import '../services/logging_service.dart';

/// Advice state enum for tracking loading states
enum AdviceState {
  initial,
  loading,
  loaded,
  error,
}

/// Centralized advice state management provider
/// Manages advice history and latest advice data
class AdviceProvider extends ChangeNotifier {
  final ApiService _apiService;

  AdviceProvider({ApiService? apiService})
      : _apiService = apiService ?? ApiService();

  // State
  AdviceState _state = AdviceState.initial;
  bool _isLoading = false;
  String? _errorMessage;

  // Advice data
  List<dynamic> _adviceHistory = [];
  Map<String, dynamic>? _latestAdvice;
  int _sessionGeneration = 0;
  int _adviceRequestId = 0;

  // Getters
  AdviceState get state => _state;
  bool get isLoading => _isLoading;
  String? get errorMessage => _errorMessage;

  // Data getters
  List<dynamic> get adviceHistory => _adviceHistory;
  Map<String, dynamic>? get latestAdvice => _latestAdvice;

  /// Initialize the provider and load advice data
  Future<void> initialize() async {
    if (_state != AdviceState.initial) return;
    final generation = _sessionGeneration;

    logInfo('Initializing AdviceProvider', tag: 'ADVICE_PROVIDER');
    await loadAdviceData(sessionGeneration: generation);
  }

  /// Load all advice data from API
  Future<void> loadAdviceData({int? sessionGeneration}) async {
    final generation = sessionGeneration ?? _sessionGeneration;
    if (!_isCurrent(generation)) return;
    final requestId = ++_adviceRequestId;

    _setLoading(true, generation);
    _state = AdviceState.loading;
    notifyListeners();

    try {
      final results = await Future.wait([
        _apiService.getAdviceHistory(),
        _apiService.getLatestAdvice(),
      ]);
      if (!_isCurrentRequest(generation, requestId)) return;

      _adviceHistory = results[0] as List<dynamic>;
      _latestAdvice = results[1] as Map<String, dynamic>?;

      _state = AdviceState.loaded;
      logInfo('Advice data loaded successfully', tag: 'ADVICE_PROVIDER');
    } catch (e) {
      if (!_isCurrentRequest(generation, requestId)) return;
      logError('Error loading advice data: $e', tag: 'ADVICE_PROVIDER');
      _errorMessage = e.toString();
      _adviceHistory = [];
      _latestAdvice = null;
      _state = AdviceState.error;
    } finally {
      if (_isCurrentRequest(generation, requestId)) {
        _setLoading(false, generation);
      }
    }
  }

  /// Refresh advice data
  Future<void> refresh({int? sessionGeneration}) async {
    final generation = sessionGeneration ?? _sessionGeneration;
    if (!_isCurrent(generation)) return;
    await loadAdviceData(sessionGeneration: generation);
  }

  /// Clear all account-owned state at an authentication boundary.
  void resetSession() {
    _sessionGeneration += 1;
    _adviceRequestId += 1;
    _state = AdviceState.initial;
    _isLoading = false;
    _errorMessage = null;
    _adviceHistory = [];
    _latestAdvice = null;
    notifyListeners();
  }

  /// Clear error message
  void clearError() {
    _errorMessage = null;
    if (_state == AdviceState.error) {
      _state = AdviceState.loaded;
    }
    notifyListeners();
  }

  // Private helper
  void _setLoading(bool loading, int generation) {
    if (!_isCurrent(generation)) return;
    _isLoading = loading;
    notifyListeners();
  }

  bool _isCurrent(int generation) => generation == _sessionGeneration;

  bool _isCurrentRequest(int generation, int requestId) =>
      _isCurrent(generation) && requestId == _adviceRequestId;
}
