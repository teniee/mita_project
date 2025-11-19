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
  final ApiService _apiService = ApiService();

  // State
  AdviceState _state = AdviceState.initial;
  bool _isLoading = false;
  String? _errorMessage;

  // Advice data
  List<dynamic> _adviceHistory = [];
  Map<String, dynamic>? _latestAdvice;

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

    logInfo('Initializing AdviceProvider', tag: 'ADVICE_PROVIDER');
    await loadAdviceData();
  }

  /// Load all advice data from API
  Future<void> loadAdviceData() async {
    _setLoading(true);
    _state = AdviceState.loading;
    notifyListeners();

    try {
      final results = await Future.wait([
        _apiService.getAdviceHistory(),
        _apiService.getLatestAdvice(),
      ]);

      _adviceHistory = results[0] as List<dynamic>;
      _latestAdvice = results[1] as Map<String, dynamic>?;

      _state = AdviceState.loaded;
      logInfo('Advice data loaded successfully', tag: 'ADVICE_PROVIDER');
    } catch (e) {
      logError('Error loading advice data: $e', tag: 'ADVICE_PROVIDER');
      _errorMessage = e.toString();
      _adviceHistory = [];
      _latestAdvice = null;
      _state = AdviceState.error;
    } finally {
      _setLoading(false);
    }
  }

  /// Refresh advice data
  Future<void> refresh() async {
    await loadAdviceData();
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
  void _setLoading(bool loading) {
    _isLoading = loading;
    notifyListeners();
  }
}
