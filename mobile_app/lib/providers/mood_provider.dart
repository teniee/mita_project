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
  final ApiService _apiService = ApiService();

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
    try {
      _setLoading(true);
      _state = MoodState.submitting;
      notifyListeners();

      await _apiService.logMood(_selectedMood.round());

      _hasSubmittedToday = true;
      _lastSubmissionDate = DateTime.now();
      _state = MoodState.loaded;

      logInfo('Mood logged successfully: ${_selectedMood.round()}',
          tag: 'MOOD_PROVIDER');
      notifyListeners();
      return true;
    } catch (e) {
      logError('Error logging mood: $e', tag: 'MOOD_PROVIDER');
      _errorMessage = e.toString();
      _state = MoodState.error;
      notifyListeners();
      return false;
    } finally {
      _setLoading(false);
    }
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
}
