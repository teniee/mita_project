
import 'package:flutter/material.dart';
import '../services/onboarding_state.dart';
import '../mixins/onboarding_session_mixin.dart';

class OnboardingHabitsScreen extends StatefulWidget {
  const OnboardingHabitsScreen({super.key});

  @override
  State<OnboardingHabitsScreen> createState() => _OnboardingHabitsScreenState();
}

class _OnboardingHabitsScreenState extends State<OnboardingHabitsScreen>
    with OnboardingSessionMixin {
  final List<Map<String, dynamic>> habits = [
    {'id': 'impulse_buying', 'label': 'Impulse purchases', 'icon': Icons.shopping_cart},
    {'id': 'no_budgeting', 'label': 'No budgeting', 'icon': Icons.money_off},
    {'id': 'forgot_subscriptions', 'label': 'Forget about subscriptions', 'icon': Icons.subscriptions},
    {'id': 'credit_dependency', 'label': 'Frequent loans', 'icon': Icons.credit_card},
  ];

  final Set<String> selectedHabits = {};
  final TextEditingController commentController = TextEditingController();

  void _toggleHabit(String id) {
    setState(() {
      if (selectedHabits.contains(id)) {
        selectedHabits.remove(id);
      } else {
        selectedHabits.add(id);
      }
    });
  }

  void _submitHabits() async {
    if (selectedHabits.isEmpty) return;
    
    // Validate session before proceeding to final step
    final isValid = await validateSessionBeforeNavigation();
    if (!isValid) return;
    
    // Save habits and optional comment
    OnboardingState.instance.habits = selectedHabits.toList();
    OnboardingState.instance.habitsComment = commentController.text.trim();
    Navigator.pushNamed(context, '/onboarding_finish');
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
                'Which financial habits are hurting you?',
                style: TextStyle(
                  fontFamily: 'Sora',
                  fontWeight: FontWeight.w700,
                  fontSize: 22,
                  color: Color(0xFF193C57),
                ),
              ),
              const SizedBox(height: 24),
              Expanded(
                child: ListView(
                  children: [
                    ...habits.map((habit) {
                      final isSelected = selectedHabits.contains(habit['id']);
                      return Padding(
                        padding: const EdgeInsets.only(bottom: 16),
                        child: GestureDetector(
                          onTap: () => _toggleHabit(habit['id']),
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
                                  Icon(habit['icon'], color: const Color(0xFF193C57)),
                                  const SizedBox(width: 16),
                                  Expanded(
                                    child: Text(
                                      habit['label'],
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
                        ),
                      );
                    }),
                    const SizedBox(height: 12),
                    const Text(
                      "Anything else?",
                      style: TextStyle(
                        fontFamily: 'Manrope',
                        fontSize: 16,
                        color: Color(0xFF193C57),
                      ),
                    ),
                    const SizedBox(height: 8),
                    TextFormField(
                      controller: commentController,
                      decoration: InputDecoration(
                        hintText: 'Describe your situation...',
                        filled: true,
                        fillColor: Colors.white,
                        contentPadding: const EdgeInsets.symmetric(vertical: 14, horizontal: 16),
                        border: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(16),
                          borderSide: BorderSide.none,
                        ),
                      ),
                      maxLines: 3,
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 12),
              SizedBox(
                width: double.infinity,
                child: ElevatedButton(
                  onPressed: selectedHabits.isNotEmpty ? _submitHabits : null,
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
                  child: const Text("Finish onboarding"),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
