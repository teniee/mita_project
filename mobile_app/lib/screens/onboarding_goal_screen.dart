import 'package:flutter/material.dart';
import '../theme/app_colors.dart';
import '../theme/app_typography.dart';
import '../services/onboarding_state.dart';
import '../widgets/onboarding_progress_indicator.dart';

class OnboardingGoalScreen extends StatefulWidget {
  const OnboardingGoalScreen({super.key});

  @override
  State<OnboardingGoalScreen> createState() => _OnboardingGoalScreenState();
}

class _OnboardingGoalScreenState extends State<OnboardingGoalScreen> {
  final List<Map<String, dynamic>> goals = [
    {
      'id': 'save_more',
      'label': 'Build an emergency fund',
      'icon': Icons.savings
    },
    {'id': 'pay_off_debt', 'label': 'Pay off debt', 'icon': Icons.credit_card},
    {'id': 'budgeting', 'label': 'Learn budgeting', 'icon': Icons.bar_chart},
    {'id': 'investing', 'label': 'Start investing', 'icon': Icons.show_chart},
  ];

  final Set<String> selectedGoals = {};
  final _savingsAmountController = TextEditingController();

  @override
  void dispose() {
    _savingsAmountController.dispose();
    super.dispose();
  }

  void _toggleGoal(String id) {
    setState(() {
      if (selectedGoals.contains(id)) {
        selectedGoals.remove(id);
      } else {
        selectedGoals.add(id);
      }
    });
  }

  Future<void> _submitGoals() async {
    if (selectedGoals.isEmpty) return;

    // Save selected goals
    OnboardingState.instance.goals = selectedGoals.toList();

    // Save savings goal amount (if provided)
    final savingsAmount = double.tryParse(_savingsAmountController.text);
    OnboardingState.instance.savingsGoalAmount = savingsAmount ?? 0.0;
    await OnboardingState.instance.save();

    Navigator.pushNamed(context, '/onboarding_spending_frequency');
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        backgroundColor: AppColors.background,
        elevation: 0,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back, color: AppColors.textPrimary),
          onPressed: () => Navigator.pop(context),
        ),
      ),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const SizedBox(height: 8),
              const OnboardingProgressIndicator(
                currentStep: 4,
                totalSteps: 7,
              ),
              const SizedBox(height: 24),
              const Text(
                'What are your financial goals?',
                style: TextStyle(
                  fontFamily: AppTypography.fontHeading,
                  fontWeight: FontWeight.w700,
                  fontSize: 22,
                  color: AppColors.textPrimary,
                ),
              ),
              const SizedBox(height: 24),
              Expanded(
                child: ListView.separated(
                  itemCount: goals.length,
                  separatorBuilder: (_, __) => const SizedBox(height: 16),
                  itemBuilder: (context, index) {
                    final goal = goals[index];
                    final isSelected = selectedGoals.contains(goal['id']);
                    return GestureDetector(
                      onTap: () => _toggleGoal(goal['id']),
                      child: Card(
                        elevation: isSelected ? 4 : 1,
                        color: isSelected ? AppColors.secondary : Colors.white,
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(20),
                          side: BorderSide(
                            color: isSelected
                                ? AppColors.textPrimary
                                : Colors.transparent,
                            width: 1.5,
                          ),
                        ),
                        child: Padding(
                          padding: const EdgeInsets.symmetric(
                              vertical: 20, horizontal: 16),
                          child: Row(
                            children: [
                              Icon(goal['icon'], color: AppColors.textPrimary),
                              const SizedBox(width: 16),
                              Expanded(
                                child: Text(
                                  goal['label'],
                                  style: const TextStyle(
                                    fontFamily: AppTypography.fontBody,
                                    fontWeight: FontWeight.w600,
                                    fontSize: 16,
                                    color: AppColors.textPrimary,
                                  ),
                                ),
                              ),
                              if (isSelected)
                                const Icon(Icons.check_circle,
                                    color: AppColors.textPrimary),
                            ],
                          ),
                        ),
                      ),
                    );
                  },
                ),
              ),
              const SizedBox(height: 20),
              const Text(
                'Monthly savings goal (optional)',
                style: TextStyle(
                  fontFamily: AppTypography.fontBody,
                  fontWeight: FontWeight.w600,
                  fontSize: 16,
                  color: AppColors.textPrimary,
                ),
              ),
              const SizedBox(height: 8),
              TextFormField(
                controller: _savingsAmountController,
                keyboardType:
                    const TextInputType.numberWithOptions(decimal: true),
                decoration: InputDecoration(
                  hintText: 'How much do you want to save per month?',
                  prefixText: '\$ ',
                  filled: true,
                  fillColor: Colors.white,
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(16),
                    borderSide: const BorderSide(color: AppColors.textPrimary),
                  ),
                  contentPadding:
                      const EdgeInsets.symmetric(vertical: 16, horizontal: 16),
                ),
              ),
              const SizedBox(height: 20),
              SizedBox(
                width: double.infinity,
                child: ElevatedButton(
                  onPressed: selectedGoals.isNotEmpty ? _submitGoals : null,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: AppColors.textPrimary,
                    foregroundColor: Colors.white,
                    padding: const EdgeInsets.symmetric(vertical: 16),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(18),
                    ),
                    textStyle: const TextStyle(
                      fontFamily: AppTypography.fontHeading,
                      fontWeight: FontWeight.w600,
                      fontSize: 16,
                    ),
                  ),
                  child: const Text("Continue"),
                ),
              ),
              const SizedBox(height: 12),
              SizedBox(
                width: double.infinity,
                child: TextButton(
                  onPressed: () {
                    // Skip goals - set empty list
                    OnboardingState.instance.goals = [];
                    OnboardingState.instance.savingsGoalAmount = 0.0;
                    Navigator.pushNamed(
                        context, '/onboarding_spending_frequency');
                  },
                  child: const Text(
                    "Skip for now",
                    style: TextStyle(
                        fontFamily: AppTypography.fontHeading,
                        color: Colors.grey),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
