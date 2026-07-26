import 'package:flutter/foundation.dart';
import '../services/api_service.dart';
import '../services/logging_service.dart';

/// Mood state enum for tracking loading states
enum MoodState {
  initial,
  loading,
  loaded,
  submitting,
  error,
}

/// Centralized mood tracking state management provider
/// Manages mood logging, submission state, and mood history
class MoodProvider extends ChangeNotifier {
  MoodProvider({ApiService? apiService})
      : _apiService = apiService ?? ApiService();

  final ApiService _apiService;
  int _sessionGeneration = 0;

  // State
  MoodState _state = MoodState.initial;
  bool _isLoading = false;
  String? _errorMessage;

  // Mood data
  double _selectedMood = 3;
  bool _hasSubmittedToday = false;
  final List<Map<String, dynamic>> _moodHistory = [];
  DateTime? _lastSubmissionDate;

  // Getters
  MoodState get state => _state;
  bool get isLoading => _isLoading;
  String? get errorMessage => _errorMessage;

  // Data getters
  double get selectedMood => _selectedMood;
  bool get hasSubmittedToday => _hasSubmittedToday;
  List<Map<String, dynamic>> get moodHistory => _moodHistory;
  DateTime? get lastSubmissionDate => _lastSubmissionDate;

  /// Initialize the provider
  Future<void> initialize() async {
    if (_state != MoodState.initial) return;

    logInfo('Initializing MoodProvider', tag: 'MOOD_PROVIDER');
    _state = MoodState.loaded;
    notifyListeners();
  }

  /// Update selected mood value
  void setSelectedMood(double mood) {
    _selectedMood = mood;
    notifyListeners();
  }

  /// Log mood to API
  Future<bool> logMood() async {
    final generation = _sessionGeneration;
    final mood = _selectedMood.round();
    try {
      _setLoading(true);
      _state = MoodState.submitting;
      notifyListeners();

      await _apiService.logMood(mood);
      if (!_isCurrentSession(generation)) return false;

      _hasSubmittedToday = true;
      _lastSubmissionDate = DateTime.now();
      _state = MoodState.loaded;

      logInfo('Mood logged successfully: $mood', tag: 'MOOD_PROVIDER');
      notifyListeners();
      return true;
    } catch (e) {
      logError('Error logging mood: $e', tag: 'MOOD_PROVIDER');
      if (!_isCurrentSession(generation)) return false;
      _errorMessage = e.toString();
      _state = MoodState.error;
      notifyListeners();
      return false;
    } finally {
      if (_isCurrentSession(generation)) {
        _setLoading(false);
      }
    }
  }

  /// Discard all state owned by the previous authenticated account.
  void resetSession() {
    _sessionGeneration++;
    _state = MoodState.initial;
    _isLoading = false;
    _errorMessage = null;
    _selectedMood = 3;
    _hasSubmittedToday = false;
    _moodHistory.clear();
    _lastSubmissionDate = null;
    notifyListeners();
  }

  /// Reset submission state (e.g., for new day)
  void resetSubmissionState() {
    _hasSubmittedToday = false;
    _state = MoodState.loaded;
    notifyListeners();
  }

  /// Clear error message
  void clearError() {
    _errorMessage = null;
    if (_state == MoodState.error) {
      _state = MoodState.loaded;
    }
    notifyListeners();
  }

  // Private helper
  void _setLoading(bool loading) {
    _isLoading = loading;
    notifyListeners();
  }

  bool _isCurrentSession(int generation) => generation == _sessionGeneration;
}
