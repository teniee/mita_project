import 'dart:convert';
import 'package:shared_preferences/shared_preferences.dart';
import 'income_service.dart';

/// Onboarding state manager with persistence support
/// Saves progress to SharedPreferences to survive app crashes/restarts
class OnboardingState {
  OnboardingState._();
  static final instance = OnboardingState._();

  static const String _storageKey = 'onboarding_state';
  bool _isLoaded = false;
  int _sessionGeneration = 0;

  String? countryCode;
  String? stateCode;
  double? income;
  IncomeTier? incomeTier;
  List<Map<String, dynamic>> expenses = [];
  List<String> goals = [];
  double? savingsGoalAmount;
  List<String> habits = [];
  String? habitsComment;
  Map<String, int>? spendingFrequencies;

  /// Load saved onboarding state from persistent storage
  Future<void> load() async {
    if (_isLoaded) return; // Already loaded
    final generation = _sessionGeneration;

    try {
      final prefs = await SharedPreferences.getInstance();
      final jsonString = prefs.getString(_storageKey);
      if (generation != _sessionGeneration) return;

      if (jsonString != null) {
        final data = jsonDecode(jsonString) as Map<String, dynamic>;
        if (generation != _sessionGeneration) return;

        countryCode = data['countryCode'] as String?;
        stateCode = data['stateCode'] as String?;
        income = (data['income'] as num?)?.toDouble();

        // Restore income tier
        if (data['incomeTier'] != null) {
          final tierName = data['incomeTier'] as String;
          incomeTier = IncomeTier.values.firstWhere(
            (tier) => tier.name == tierName,
            orElse: () => IncomeTier.low,
          );
        }

        expenses =
            (data['expenses'] as List?)?.cast<Map<String, dynamic>>() ?? [];
        goals = (data['goals'] as List?)?.cast<String>() ?? [];
        savingsGoalAmount = (data['savingsGoalAmount'] as num?)?.toDouble();
        habits = (data['habits'] as List?)?.cast<String>() ?? [];
        habitsComment = data['habitsComment'] as String?;

        if (data['spendingFrequencies'] != null) {
          spendingFrequencies =
              (data['spendingFrequencies'] as Map<String, dynamic>)
                  .map((key, value) => MapEntry(key, value as int));
        }
      }

      if (generation == _sessionGeneration) {
        _isLoaded = true;
      }
    } catch (e) {
      // Failed to load - continue with empty state
      if (generation == _sessionGeneration) {
        _isLoaded = true;
      }
    }
  }

  /// Save current onboarding state to persistent storage
  Future<void> save() async {
    final generation = _sessionGeneration;
    try {
      final data = {
        'countryCode': countryCode,
        'stateCode': stateCode,
        'income': income,
        'incomeTier': incomeTier?.name,
        'expenses': expenses,
        'goals': goals,
        'savingsGoalAmount': savingsGoalAmount,
        'habits': habits,
        'habitsComment': habitsComment,
        'spendingFrequencies': spendingFrequencies,
        'savedAt': DateTime.now().toIso8601String(),
      };

      final prefs = await SharedPreferences.getInstance();
      if (generation != _sessionGeneration) return;
      await prefs.setString(_storageKey, jsonEncode(data));
    } catch (e) {
      // Failed to save - non-critical, continue
    }
  }

  /// Clear saved onboarding state from persistent storage
  Future<void> clear() async {
    final generation = _sessionGeneration;
    try {
      final prefs = await SharedPreferences.getInstance();
      if (generation != _sessionGeneration) return;
      await prefs.remove(_storageKey);
    } catch (e) {
      // Failed to clear - non-critical
    }
  }

  /// Check if there is saved onboarding progress
  Future<bool> hasSavedProgress() async {
    final generation = _sessionGeneration;
    try {
      final prefs = await SharedPreferences.getInstance();
      if (generation != _sessionGeneration) return false;
      return prefs.containsKey(_storageKey);
    } catch (e) {
      return false;
    }
  }

  /// Reset in-memory state and clear persistent storage
  Future<void> reset() async {
    final generation = beginSessionBoundary();
    try {
      final prefs = await SharedPreferences.getInstance();
      if (generation != _sessionGeneration) return;
      await prefs.remove(_storageKey);
    } catch (e) {
      // Failed to clear - non-critical
    }
  }

  /// Invalidate pending onboarding work and synchronously erase account data.
  int beginSessionBoundary() {
    _sessionGeneration += 1;
    _isLoaded = false;
    _clearMemory();
    return _sessionGeneration;
  }

  void _clearMemory() {
    countryCode = null;
    stateCode = null;
    income = null;
    incomeTier = null;
    expenses = [];
    goals = [];
    savingsGoalAmount = null;
    habits = [];
    habitsComment = null;
    spendingFrequencies = null;
  }

  /// Convert onboarding state to a Map for caching with UserProvider
  Map<String, dynamic> toMap() {
    return {
      'countryCode': countryCode,
      'stateCode': stateCode,
      'income': income,
      'incomeTier': incomeTier?.name,
      'expenses': expenses,
      'goals': goals,
      'savingsGoalAmount': savingsGoalAmount,
      'habits': habits,
      'habitsComment': habitsComment,
      'spendingFrequencies': spendingFrequencies,
    };
  }
}
