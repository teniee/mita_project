
import 'package:flutter/material.dart';
import '../services/onboarding_state.dart';

class OnboardingGoalScreen extends StatefulWidget {
  const OnboardingGoalScreen({super.key});

  @override
  State<OnboardingGoalScreen> createState() => _OnboardingGoalScreenState();
}

class _OnboardingGoalScreenState extends State<OnboardingGoalScreen> {
  final List<Map<String, dynamic>> goals = [
    {'id': 'save_more', 'label': 'Build an emergency fund', 'icon': Icons.savings},
    {'id': 'pay_off_debt', 'label': 'Pay off debt', 'icon': Icons.credit_card},
    {'id': 'budgeting', 'label': 'Learn budgeting', 'icon': Icons.bar_chart},
    {'id': 'investing', 'label': 'Start investing', 'icon': Icons.show_chart},
  ];

  final Set<String> selectedGoals = {};

  void _toggleGoal(String id) {
    setState(() {
      if (selectedGoals.contains(id)) {
        selectedGoals.remove(id);
      } else {
        selectedGoals.add(id);
      }
    });
  }

  void _submitGoals() {
    if (selectedGoals.isEmpty) return;
    // Save selected goals for the final onboarding request
    OnboardingState.instance.goals = selectedGoals.toList();
    Navigator.pushNamed(context, '/onboarding_habits');
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFFFF9F0),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'What are your financial goals?',
                style: TextStyle(
                  fontFamily: 'Sora',
                  fontWeight: FontWeight.w700,
                  fontSize: 22,
                  color: Color(0xFF193C57),
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
                        color: isSelected ? const Color(0xFFFFD25F) : Colors.white,
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(20),
                          side: BorderSide(
                            color: isSelected ? const Color(0xFF193C57) : Colors.transparent,
                            width: 1.5,
                          ),
                        ),
                        child: Padding(
                          padding: const EdgeInsets.symmetric(vertical: 20, horizontal: 16),
                          child: Row(
                            children: [
                              Icon(goal['icon'], color: const Color(0xFF193C57)),
                              const SizedBox(width: 16),
                              Expanded(
                                child: Text(
                                  goal['label'],
                                  style: const TextStyle(
                                    fontFamily: 'Manrope',
                                    fontWeight: FontWeight.w600,
                                    fontSize: 16,
                                    color: Color(0xFF193C57),
                                  ),
                                ),
                              ),
                              if (isSelected)
                                const Icon(Icons.check_circle, color: Color(0xFF193C57)),
                            ],
                          ),
                        ),
                      ),
                    );
                  },
                ),
              ),
              const SizedBox(height: 12),
              SizedBox(
                width: double.infinity,
                child: ElevatedButton(
                  onPressed: selectedGoals.isNotEmpty ? _submitGoals : null,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: const Color(0xFF193C57),
                    foregroundColor: Colors.white,
                    padding: const EdgeInsets.symmetric(vertical: 16),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(18),
                    ),
                    textStyle: const TextStyle(
                      fontFamily: 'Sora',
                      fontWeight: FontWeight.w600,
                      fontSize: 16,
                    ),
                  ),
                  child: const Text("Continue"),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
