import 'package:flutter/foundation.dart';
import '../services/api_service.dart';
import '../services/logging_service.dart';

/// Habit data model for better type safety and data management
class Habit {
  final int id;
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
    return Habit(
      id: json['id'] as int? ?? 0,
      title: json['title'] as String? ?? '',
      description: json['description'] as String? ?? '',
      targetFrequency: json['target_frequency'] as String? ?? 'daily',
      createdAt: DateTime.tryParse(json['created_at'] as String? ?? '') ??
          DateTime.now(),
      completedDates: (json['completed_dates'] as List<dynamic>? ?? [])
          .map((date) => DateTime.tryParse(date.toString()) ?? DateTime.now())
          .toList(),
      currentStreak: json['current_streak'] as int? ?? 0,
      longestStreak: json['longest_streak'] as int? ?? 0,
      completionRate: (json['completion_rate'] as num? ?? 0.0).toDouble(),
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
  final ApiService _apiService = ApiService();

  // State
  HabitsState _state = HabitsState.initial;
  List<Habit> _habits = [];
  Map<int, Map<String, dynamic>> _habitProgress = {};
  String? _errorMessage;
  bool _isLoading = false;

  // Getters
  HabitsState get state => _state;
  List<Habit> get habits => _habits;
  Map<int, Map<String, dynamic>> get habitProgress => _habitProgress;
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

    _setLoading(true);
    _state = HabitsState.loading;
    notifyListeners();

    try {
      logInfo('Initializing HabitsProvider', tag: 'HABITS_PROVIDER');

      await loadHabits();

      _state = HabitsState.loaded;
      logInfo('HabitsProvider initialized successfully',
          tag: 'HABITS_PROVIDER');
    } catch (e) {
      logError('Failed to initialize HabitsProvider: $e',
          tag: 'HABITS_PROVIDER');
      _errorMessage = e.toString();
      _state = HabitsState.error;
    } finally {
      _setLoading(false);
    }
  }

  /// Load all habits
  Future<void> loadHabits() async {
    try {
      _setLoading(true);
      _errorMessage = null;

      final data = await _apiService.getHabits();
      _habits = data
          .map((json) => Habit.fromJson(json as Map<String, dynamic>))
          .toList();

      logInfo('Loaded ${_habits.length} habits', tag: 'HABITS_PROVIDER');

      // Load progress for each habit
      for (final habit in _habits) {
        _loadHabitProgress(habit.id);
      }

      notifyListeners();
    } catch (e) {
      logError('Failed to load habits: $e', tag: 'HABITS_PROVIDER');
      _habits = [];
      _errorMessage = 'Failed to load habits. Please try again.';
      notifyListeners();
    } finally {
      _setLoading(false);
    }
  }

  /// Load progress for a specific habit
  Future<void> _loadHabitProgress(int habitId) async {
    try {
      final progress = await _apiService.getHabitProgress(habitId);
      _habitProgress[habitId] = progress;
      notifyListeners();
    } catch (e) {
      // Silently fail - progress not critical for display
      logError('Failed to load habit progress for $habitId: $e',
          tag: 'HABITS_PROVIDER');
    }
  }

  /// Toggle habit completion for today
  Future<bool> toggleHabitCompletion(Habit habit) async {
    final today = DateTime.now().toIso8601String().split('T')[0];

    try {
      if (habit.isCompletedToday) {
        await _apiService.uncompleteHabit(habit.id, today);
        logInfo('Habit ${habit.id} unmarked for today', tag: 'HABITS_PROVIDER');
      } else {
        await _apiService.completeHabit(habit.id, today);
        logInfo('Habit ${habit.id} completed for today',
            tag: 'HABITS_PROVIDER');
      }

      // Refresh habits list to get updated data
      await loadHabits();
      return true;
    } catch (e) {
      logError('Failed to toggle habit completion: $e', tag: 'HABITS_PROVIDER');
      _errorMessage = 'Failed to update habit: $e';
      notifyListeners();
      return false;
    }
  }

  /// Create a new habit
  Future<bool> createHabit(Map<String, dynamic> data) async {
    try {
      _setLoading(true);

      await _apiService.createHabit(data);

      // Refresh habits list
      await loadHabits();

      logInfo('Habit created successfully', tag: 'HABITS_PROVIDER');
      return true;
    } catch (e) {
      logError('Failed to create habit: $e', tag: 'HABITS_PROVIDER');
      _errorMessage = e.toString();
      notifyListeners();
      return false;
    } finally {
      _setLoading(false);
    }
  }

  /// Update an existing habit
  Future<bool> updateHabit(int habitId, Map<String, dynamic> data) async {
    try {
      _setLoading(true);

      await _apiService.updateHabit(habitId, data);

      // Refresh habits list
      await loadHabits();

      logInfo('Habit $habitId updated successfully', tag: 'HABITS_PROVIDER');
      return true;
    } catch (e) {
      logError('Failed to update habit: $e', tag: 'HABITS_PROVIDER');
      _errorMessage = e.toString();
      notifyListeners();
      return false;
    } finally {
      _setLoading(false);
    }
  }

  /// Delete a habit
  Future<bool> deleteHabit(int habitId) async {
    try {
      _setLoading(true);

      await _apiService.deleteHabit(habitId);

      // Remove from local state immediately
      _habits.removeWhere((h) => h.id == habitId);
      _habitProgress.remove(habitId);
      notifyListeners();

      logInfo('Habit $habitId deleted successfully', tag: 'HABITS_PROVIDER');
      return true;
    } catch (e) {
      logError('Failed to delete habit: $e', tag: 'HABITS_PROVIDER');
      _errorMessage = e.toString();
      notifyListeners();
      return false;
    } finally {
      _setLoading(false);
    }
  }

  /// Get progress for a specific habit
  Map<String, dynamic>? getProgressForHabit(int habitId) {
    return _habitProgress[habitId];
  }

  /// Refresh all data
  Future<void> refresh() async {
    _state = HabitsState.loading;
    notifyListeners();

    try {
      await loadHabits();
      _state = HabitsState.loaded;
    } catch (e) {
      _state = HabitsState.error;
    }
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
}
