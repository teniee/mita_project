import 'package:flutter/foundation.dart';
import '../models/goal.dart';
import '../services/api_service.dart';
import '../services/logging_service.dart';

/// State enum for goals management
enum GoalsState {
  initial,
  loading,
  loaded,
  error,
}

/// Centralized goals state management provider
/// Manages goals list, statistics, filtering, and CRUD operations
class GoalsProvider extends ChangeNotifier {
  final ApiService _apiService = ApiService();

  // State
  GoalsState _state = GoalsState.initial;
  List<Goal> _goals = [];
  Map<String, dynamic> _statistics = {};
  String? _selectedStatus;
  String? _selectedCategory;
  String? _errorMessage;
  bool _isLoading = false;

  // Getters
  GoalsState get state => _state;
  List<Goal> get goals => _goals;
  Map<String, dynamic> get statistics => _statistics;
  String? get selectedStatus => _selectedStatus;
  String? get selectedCategory => _selectedCategory;
  String? get errorMessage => _errorMessage;
  bool get isLoading => _isLoading;
  bool get hasStatistics => _statistics.isNotEmpty;

  // Filtered goals based on current selection
  List<Goal> get filteredGoals {
    if (_selectedStatus == null) return _goals;
    return _goals.where((g) => g.status == _selectedStatus).toList();
  }

  // Statistics convenience getters
  int get totalGoals => _statistics['total_goals'] as int? ?? 0;
  int get activeGoals => _statistics['active_goals'] as int? ?? 0;
  int get completedGoals => _statistics['completed_goals'] as int? ?? 0;
  double get completionRate => (_statistics['completion_rate'] as num?)?.toDouble() ?? 0.0;
  double get averageProgress => (_statistics['average_progress'] as num?)?.toDouble() ?? 0.0;

  /// Initialize the provider and load initial data
  Future<void> initialize() async {
    if (_state != GoalsState.initial) return;

    _setLoading(true);
    _state = GoalsState.loading;
    notifyListeners();

    try {
      logInfo('Initializing GoalsProvider', tag: 'GOALS_PROVIDER');

      await Future.wait([
        loadGoals(),
        loadStatistics(),
      ]);

      _state = GoalsState.loaded;
      logInfo('GoalsProvider initialized successfully', tag: 'GOALS_PROVIDER');
    } catch (e) {
      logError('Failed to initialize GoalsProvider: $e', tag: 'GOALS_PROVIDER');
      _errorMessage = e.toString();
      _state = GoalsState.error;
    } finally {
      _setLoading(false);
    }
  }

  /// Load goals with current filters
  Future<void> loadGoals() async {
    try {
      _setLoading(true);

      final data = await _apiService.getGoals(
        status: _selectedStatus,
        category: _selectedCategory,
      );

      _goals = data.map((json) => Goal.fromJson(json)).toList();
      logInfo('Loaded ${_goals.length} goals', tag: 'GOALS_PROVIDER');
      notifyListeners();
    } catch (e) {
      logError('Failed to load goals: $e', tag: 'GOALS_PROVIDER');
      // Use sample data on error
      _goals = _getSampleGoals();
      notifyListeners();
    } finally {
      _setLoading(false);
    }
  }

  /// Load goal statistics
  Future<void> loadStatistics() async {
    try {
      final stats = await _apiService.getGoalStatistics();
      _statistics = stats;
      logInfo('Goal statistics loaded', tag: 'GOALS_PROVIDER');
      notifyListeners();
    } catch (e) {
      logError('Failed to load goal statistics: $e', tag: 'GOALS_PROVIDER');
    }
  }

  /// Set status filter
  void setStatusFilter(String? status) {
    if (_selectedStatus == status) return;
    _selectedStatus = status;
    notifyListeners();
    loadGoals();
  }

  /// Set category filter
  void setCategoryFilter(String? category) {
    if (_selectedCategory == category) return;
    _selectedCategory = category;
    notifyListeners();
    loadGoals();
  }

  /// Create a new goal
  Future<bool> createGoal(Map<String, dynamic> data) async {
    try {
      _setLoading(true);

      await _apiService.createGoal(data);

      // Refresh data
      await Future.wait([
        loadGoals(),
        loadStatistics(),
      ]);

      logInfo('Goal created successfully', tag: 'GOALS_PROVIDER');
      return true;
    } catch (e) {
      logError('Failed to create goal: $e', tag: 'GOALS_PROVIDER');
      _errorMessage = e.toString();
      return false;
    } finally {
      _setLoading(false);
    }
  }

  /// Update an existing goal
  Future<bool> updateGoal(String goalId, Map<String, dynamic> data) async {
    try {
      _setLoading(true);

      await _apiService.updateGoal(goalId, data);

      // Refresh data
      await Future.wait([
        loadGoals(),
        loadStatistics(),
      ]);

      logInfo('Goal $goalId updated successfully', tag: 'GOALS_PROVIDER');
      return true;
    } catch (e) {
      logError('Failed to update goal: $e', tag: 'GOALS_PROVIDER');
      _errorMessage = e.toString();
      return false;
    } finally {
      _setLoading(false);
    }
  }

  /// Delete a goal
  Future<bool> deleteGoal(String goalId) async {
    try {
      _setLoading(true);

      await _apiService.deleteGoal(goalId);

      // Refresh data
      await Future.wait([
        loadGoals(),
        loadStatistics(),
      ]);

      logInfo('Goal $goalId deleted successfully', tag: 'GOALS_PROVIDER');
      return true;
    } catch (e) {
      logError('Failed to delete goal: $e', tag: 'GOALS_PROVIDER');
      _errorMessage = e.toString();
      return false;
    } finally {
      _setLoading(false);
    }
  }

  /// Add savings to a goal
  Future<bool> addSavings(String goalId, double amount) async {
    try {
      _setLoading(true);

      await _apiService.addSavingsToGoal(goalId, amount);

      // Refresh data
      await Future.wait([
        loadGoals(),
        loadStatistics(),
      ]);

      logInfo('Added \$$amount to goal $goalId', tag: 'GOALS_PROVIDER');
      return true;
    } catch (e) {
      logError('Failed to add savings: $e', tag: 'GOALS_PROVIDER');
      _errorMessage = e.toString();
      return false;
    } finally {
      _setLoading(false);
    }
  }

  /// Pause a goal
  Future<bool> pauseGoal(String goalId) async {
    try {
      _setLoading(true);

      await _apiService.pauseGoal(goalId);

      // Refresh data
      await Future.wait([
        loadGoals(),
        loadStatistics(),
      ]);

      logInfo('Goal $goalId paused', tag: 'GOALS_PROVIDER');
      return true;
    } catch (e) {
      logError('Failed to pause goal: $e', tag: 'GOALS_PROVIDER');
      _errorMessage = e.toString();
      return false;
    } finally {
      _setLoading(false);
    }
  }

  /// Resume a paused goal
  Future<bool> resumeGoal(String goalId) async {
    try {
      _setLoading(true);

      await _apiService.resumeGoal(goalId);

      // Refresh data
      await Future.wait([
        loadGoals(),
        loadStatistics(),
      ]);

      logInfo('Goal $goalId resumed', tag: 'GOALS_PROVIDER');
      return true;
    } catch (e) {
      logError('Failed to resume goal: $e', tag: 'GOALS_PROVIDER');
      _errorMessage = e.toString();
      return false;
    } finally {
      _setLoading(false);
    }
  }

  /// Toggle goal status (pause/resume)
  Future<bool> toggleGoalStatus(Goal goal) async {
    if (goal.status == 'active') {
      return pauseGoal(goal.id);
    } else if (goal.status == 'paused') {
      return resumeGoal(goal.id);
    }
    return false;
  }

  /// Refresh all data
  Future<void> refresh() async {
    await Future.wait([
      loadGoals(),
      loadStatistics(),
    ]);
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

  /// Sample goals for fallback
  List<Goal> _getSampleGoals() {
    return [
      Goal(
        id: '1',
        title: 'Emergency Fund',
        description: 'Build a 3-month emergency fund',
        category: 'Emergency',
        targetAmount: 5000,
        savedAmount: 1250,
        status: 'active',
        progress: 25.0,
        createdAt: DateTime.now().subtract(const Duration(days: 30)),
        lastUpdated: DateTime.now(),
        priority: 'high',
      ),
    ];
  }
}
