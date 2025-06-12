class OnboardingState {
  OnboardingState._();
  static final instance = OnboardingState._();

  String? region;
  double? income;
  List<Map<String, dynamic>> expenses = [];
  List<String> goals = [];
  List<String> habits = [];
  String? habitsComment;
  String? motivation;

  void reset() {
    region = null;
    income = null;
    expenses = [];
    goals = [];
    habits = [];
    habitsComment = null;
    motivation = null;
  }
}
