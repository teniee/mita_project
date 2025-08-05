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
  List<String> habits = [];
  String? habitsComment;

  void reset() {
    region = null;
    countryCode = null;
    stateCode = null;
    income = null;
    incomeTier = null;
    expenses = [];
    goals = [];
    habits = [];
    habitsComment = null;
  }
}
