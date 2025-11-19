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

    try {
      final prefs = await SharedPreferences.getInstance();
      final jsonString = prefs.getString(_storageKey);

      if (jsonString != null) {
        final data = jsonDecode(jsonString) as Map<String, dynamic>;

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

        expenses = (data['expenses'] as List?)?.cast<Map<String, dynamic>>() ?? [];
        goals = (data['goals'] as List?)?.cast<String>() ?? [];
        savingsGoalAmount = (data['savingsGoalAmount'] as num?)?.toDouble();
        habits = (data['habits'] as List?)?.cast<String>() ?? [];
        habitsComment = data['habitsComment'] as String?;

        if (data['spendingFrequencies'] != null) {
          spendingFrequencies = (data['spendingFrequencies'] as Map<String, dynamic>)
              .map((key, value) => MapEntry(key, value as int));
        }
      }

      _isLoaded = true;
    } catch (e) {
      // Failed to load - continue with empty state
      _isLoaded = true;
    }
  }

  /// Save current onboarding state to persistent storage
  Future<void> save() async {
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
      await prefs.setString(_storageKey, jsonEncode(data));
    } catch (e) {
      // Failed to save - non-critical, continue
    }
  }

  /// Clear saved onboarding state from persistent storage
  Future<void> clear() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.remove(_storageKey);
    } catch (e) {
      // Failed to clear - non-critical
    }
  }

  /// Check if there is saved onboarding progress
  Future<bool> hasSavedProgress() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      return prefs.containsKey(_storageKey);
    } catch (e) {
      return false;
    }
  }

  /// Reset in-memory state and clear persistent storage
  Future<void> reset() async {
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

    await clear();
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
