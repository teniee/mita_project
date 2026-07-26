import 'package:flutter/foundation.dart';
import '../services/api_service.dart';
import '../services/logging_service.dart';

/// Habit data model for better type safety and data management
class Habit {
  // Backend habit ids are UUID strings; coercing through int.tryParse
  // collapsed every id to 0 and broke edit/delete/complete (422 on
  // /habits/0). Keep the id opaque.
  final String id;
  final String title;
  final String description;
  final String targetFrequency;
  final DateTime createdAt;
  final List<DateTime> completedDates;
  final int currentStreak;
  final int longestStreak;
  final double completionRate;

  Habit({
    required this.id,
    required this.title,
    required this.description,
    required this.targetFrequency,
    required this.createdAt,
    required this.completedDates,
    required this.currentStreak,
    required this.longestStreak,
    required this.completionRate,
  });

  factory Habit.fromJson(Map<String, dynamic> json) {
    final idData = json['id'];
    final id = idData?.toString() ?? '';

    final currentStreakData = json['current_streak'];
    final currentStreak = (currentStreakData == null)
        ? 0
        : (currentStreakData is num)
            ? currentStreakData.toInt()
            : (currentStreakData is String
                ? int.tryParse(currentStreakData) ?? 0
                : 0);

    final longestStreakData = json['longest_streak'];
    final longestStreak = (longestStreakData == null)
        ? 0
        : (longestStreakData is num)
            ? longestStreakData.toInt()
            : (longestStreakData is String
                ? int.tryParse(longestStreakData) ?? 0
                : 0);

    final completionRateData = json['completion_rate'];
    final completionRate = (completionRateData == null)
        ? 0.0
        : (completionRateData is num)
            ? completionRateData.toDouble()
            : (completionRateData is String
                ? double.tryParse(completionRateData) ?? 0.0
                : 0.0);

    return Habit(
      id: id,
      title: json['title'] as String? ?? '',
      description: json['description'] as String? ?? '',
      targetFrequency: json['target_frequency'] as String? ?? 'daily',
      createdAt: DateTime.tryParse(json['created_at'] as String? ?? '') ??
          DateTime.now(),
      completedDates: (json['completed_dates'] as List<dynamic>? ?? [])
          .map((date) => DateTime.tryParse(date.toString()) ?? DateTime.now())
          .toList(),
      currentStreak: currentStreak,
      longestStreak: longestStreak,
      completionRate: completionRate,
    );
  }

  bool get isCompletedToday {
    final today = DateTime.now();
    return completedDates.any((date) =>
        date.year == today.year &&
        date.month == today.month &&
        date.day == today.day);
  }
}

/// State enum for habits management
enum HabitsState {
  initial,
  loading,
  loaded,
  error,
}

/// Centralized habits state management provider
/// Manages habits list, progress tracking, and CRUD operations
class HabitsProvider extends ChangeNotifier {
  final ApiService _apiService;

  HabitsProvider({ApiService? apiService})
      : _apiService = apiService ?? ApiService();

  // State
  HabitsState _state = HabitsState.initial;
  List<Habit> _habits = [];
  final Map<String, Map<String, dynamic>> _habitProgress = {};
  String? _errorMessage;
  bool _isLoading = false;
  int _sessionGeneration = 0;
  int _habitsRequestId = 0;
  final Map<String, int> _progressRequestIds = {};

  // Getters
  HabitsState get state => _state;
  List<Habit> get habits => _habits;
  Map<String, Map<String, dynamic>> get habitProgress => _habitProgress;
  String? get errorMessage => _errorMessage;
  bool get isLoading => _isLoading;
  bool get hasHabits => _habits.isNotEmpty;
  int get habitCount => _habits.length;

  // Statistics convenience getters
  int get completedTodayCount =>
      _habits.where((h) => h.isCompletedToday).length;
  double get overallCompletionRate {
    if (_habits.isEmpty) return 0.0;
    return _habits.map((h) => h.completionRate).reduce((a, b) => a + b) /
        _habits.length;
  }

  int get totalCurrentStreak {
    if (_habits.isEmpty) return 0;
    return _habits.map((h) => h.currentStreak).reduce((a, b) => a > b ? a : b);
  }

  /// Initialize the provider and load initial data
  Future<void> initialize() async {
    if (_state != HabitsState.initial) return;
    final generation = _sessionGeneration;

    _setLoading(true, generation);
    _state = HabitsState.loading;
    notifyListeners();

    try {
      logInfo('Initializing HabitsProvider', tag: 'HABITS_PROVIDER');

      await loadHabits(sessionGeneration: generation);
      if (!_isCurrent(generation)) return;

      _state = HabitsState.loaded;
      logInfo('HabitsProvider initialized successfully',
          tag: 'HABITS_PROVIDER');
    } catch (e) {
      if (!_isCurrent(generation)) return;
      logError('Failed to initialize HabitsProvider: $e',
          tag: 'HABITS_PROVIDER');
      _errorMessage = e.toString();
      _state = HabitsState.error;
    } finally {
      _setLoading(false, generation);
    }
  }

  /// Load all habits
  Future<void> loadHabits({int? sessionGeneration}) async {
    final generation = sessionGeneration ?? _sessionGeneration;
    if (!_isCurrent(generation)) return;
    final requestId = ++_habitsRequestId;

    try {
      _setLoading(true, generation);
      _errorMessage = null;

      final data = await _apiService.getHabits();
      if (!_isCurrentHabitsRequest(generation, requestId)) return;
      _habits = data
          .map((json) => Habit.fromJson(json as Map<String, dynamic>))
          .toList();

      logInfo('Loaded ${_habits.length} habits', tag: 'HABITS_PROVIDER');

      // Load progress for each habit
      for (final habit in _habits) {
        _loadHabitProgress(
          habit.id,
          sessionGeneration: generation,
        );
      }

      notifyListeners();
    } catch (e) {
      if (!_isCurrentHabitsRequest(generation, requestId)) return;
      logError('Failed to load habits: $e', tag: 'HABITS_PROVIDER');
      _habits = [];
      _errorMessage = 'Failed to load habits. Please try again.';
      notifyListeners();
    } finally {
      if (_isCurrentHabitsRequest(generation, requestId)) {
        _setLoading(false, generation);
      }
    }
  }

  /// Load progress for a specific habit
  Future<void> _loadHabitProgress(
    String habitId, {
    required int sessionGeneration,
  }) async {
    if (!_isCurrent(sessionGeneration)) return;
    final requestId = _nextProgressRequestId(habitId);

    try {
      final progress = await _apiService.getHabitProgress(habitId);
      if (!_isCurrentProgressRequest(sessionGeneration, habitId, requestId)) {
        return;
      }
      _habitProgress[habitId] = progress;
      notifyListeners();
    } catch (e) {
      if (!_isCurrentProgressRequest(sessionGeneration, habitId, requestId)) {
        return;
      }
      // Silently fail - progress not critical for display
      logError('Failed to load habit progress for $habitId: $e',
          tag: 'HABITS_PROVIDER');
    }
  }

  /// Toggle habit completion for today
  Future<bool> toggleHabitCompletion(
    Habit habit, {
    int? sessionGeneration,
  }) async {
    final generation = sessionGeneration ?? _sessionGeneration;
    if (!_isCurrent(generation)) return false;
    final today = DateTime.now().toIso8601String().split('T')[0];

    try {
      _invalidateHabitSnapshots();
      if (habit.isCompletedToday) {
        await _apiService.uncompleteHabit(habit.id, today);
        if (!_isCurrent(generation)) return false;
        logInfo('Habit ${habit.id} unmarked for today', tag: 'HABITS_PROVIDER');
      } else {
        await _apiService.completeHabit(habit.id, today);
        if (!_isCurrent(generation)) return false;
        logInfo('Habit ${habit.id} completed for today',
            tag: 'HABITS_PROVIDER');
      }

      // Refresh habits list to get updated data
      await loadHabits(sessionGeneration: generation);
      if (!_isCurrent(generation)) return false;
      return true;
    } catch (e) {
      if (!_isCurrent(generation)) return false;
      logError('Failed to toggle habit completion: $e', tag: 'HABITS_PROVIDER');
      _errorMessage = 'Failed to update habit: $e';
      notifyListeners();
      return false;
    }
  }

  /// Create a new habit
  Future<bool> createHabit(
    Map<String, dynamic> data, {
    int? sessionGeneration,
  }) async {
    final generation = sessionGeneration ?? _sessionGeneration;
    if (!_isCurrent(generation)) return false;

    try {
      _invalidateHabitSnapshots();
      _setLoading(true, generation);

      await _apiService.createHabit(data);
      if (!_isCurrent(generation)) return false;

      // Refresh habits list
      await loadHabits(sessionGeneration: generation);
      if (!_isCurrent(generation)) return false;

      logInfo('Habit created successfully', tag: 'HABITS_PROVIDER');
      return true;
    } catch (e) {
      if (!_isCurrent(generation)) return false;
      logError('Failed to create habit: $e', tag: 'HABITS_PROVIDER');
      _errorMessage = e.toString();
      notifyListeners();
      return false;
    } finally {
      _setLoading(false, generation);
    }
  }

  /// Update an existing habit
  Future<bool> updateHabit(
    String habitId,
    Map<String, dynamic> data, {
    int? sessionGeneration,
  }) async {
    final generation = sessionGeneration ?? _sessionGeneration;
    if (!_isCurrent(generation)) return false;

    try {
      _invalidateHabitSnapshots();
      _setLoading(true, generation);

      await _apiService.updateHabit(habitId, data);
      if (!_isCurrent(generation)) return false;

      // Refresh habits list
      await loadHabits(sessionGeneration: generation);
      if (!_isCurrent(generation)) return false;

      logInfo('Habit $habitId updated successfully', tag: 'HABITS_PROVIDER');
      return true;
    } catch (e) {
      if (!_isCurrent(generation)) return false;
      logError('Failed to update habit: $e', tag: 'HABITS_PROVIDER');
      _errorMessage = e.toString();
      notifyListeners();
      return false;
    } finally {
      _setLoading(false, generation);
    }
  }

  /// Delete a habit
  Future<bool> deleteHabit(
    String habitId, {
    int? sessionGeneration,
  }) async {
    final generation = sessionGeneration ?? _sessionGeneration;
    if (!_isCurrent(generation)) return false;

    try {
      _invalidateHabitSnapshots();
      _invalidateHabitProgress(habitId);
      _setLoading(true, generation);

      await _apiService.deleteHabit(habitId);
      if (!_isCurrent(generation)) return false;

      // Remove from local state immediately
      _habits.removeWhere((h) => h.id == habitId);
      _habitProgress.remove(habitId);
      notifyListeners();

      logInfo('Habit $habitId deleted successfully', tag: 'HABITS_PROVIDER');
      return true;
    } catch (e) {
      if (!_isCurrent(generation)) return false;
      logError('Failed to delete habit: $e', tag: 'HABITS_PROVIDER');
      _errorMessage = e.toString();
      notifyListeners();
      return false;
    } finally {
      _setLoading(false, generation);
    }
  }

  /// Get progress for a specific habit
  Map<String, dynamic>? getProgressForHabit(String habitId) {
    return _habitProgress[habitId];
  }

  /// Refresh all data
  Future<void> refresh({int? sessionGeneration}) async {
    final generation = sessionGeneration ?? _sessionGeneration;
    if (!_isCurrent(generation)) return;

    _state = HabitsState.loading;
    notifyListeners();

    try {
      await loadHabits(sessionGeneration: generation);
      if (!_isCurrent(generation)) return;
      _state = HabitsState.loaded;
    } catch (e) {
      if (!_isCurrent(generation)) return;
      _state = HabitsState.error;
    }
    if (_isCurrent(generation)) {
      notifyListeners();
    }
  }

  /// Clear all account-owned state at an authentication boundary.
  void resetSession() {
    _sessionGeneration += 1;
    _habitsRequestId += 1;
    for (final habitId in _progressRequestIds.keys.toList()) {
      _progressRequestIds[habitId] = (_progressRequestIds[habitId] ?? 0) + 1;
    }
    _state = HabitsState.initial;
    _habits = [];
    _habitProgress.clear();
    _progressRequestIds.clear();
    _errorMessage = null;
    _isLoading = false;
    notifyListeners();
  }

  /// Clear error message
  void clearError() {
    _errorMessage = null;
    notifyListeners();
  }

  // Private helper
  void _setLoading(bool loading, int generation) {
    if (!_isCurrent(generation)) return;
    _isLoading = loading;
    notifyListeners();
  }

  bool _isCurrent(int generation) => generation == _sessionGeneration;

  bool _isCurrentHabitsRequest(int generation, int requestId) =>
      _isCurrent(generation) && requestId == _habitsRequestId;

  int _nextProgressRequestId(String habitId) {
    final requestId = (_progressRequestIds[habitId] ?? 0) + 1;
    _progressRequestIds[habitId] = requestId;
    return requestId;
  }

  bool _isCurrentProgressRequest(
          int generation, String habitId, int requestId) =>
      _isCurrent(generation) &&
      requestId == (_progressRequestIds[habitId] ?? 0);

  void _invalidateHabitSnapshots() {
    _habitsRequestId += 1;
    _isLoading = false;
  }

  void _invalidateHabitProgress(String habitId) {
    _progressRequestIds[habitId] = (_progressRequestIds[habitId] ?? 0) + 1;
  }
}
