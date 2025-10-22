import 'income_service.dart';

class OnboardingState {
  OnboardingState._();
  static final instance = OnboardingState._();

  String? region;
  String? countryCode;
  String? stateCode;
  double? income;
  IncomeTier? incomeTier;
  List<Map<String, dynamic>> expenses = [];
  List<String> goals = [];
  double? savingsGoalAmount;  // NEW: Actual savings goal dollar amount
  List<String> habits = [];
  String? habitsComment;
  Map<String, int>? spendingFrequencies;  // NEW: Real user spending frequencies

  void reset() {
    region = null;
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
}
