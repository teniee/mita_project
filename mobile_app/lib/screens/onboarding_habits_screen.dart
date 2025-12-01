import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../theme/app_colors.dart';
import '../theme/app_typography.dart';
import '../services/onboarding_state.dart';
import '../providers/user_provider.dart';
import '../widgets/onboarding_progress_indicator.dart';
import '../mixins/onboarding_session_mixin.dart';

class OnboardingHabitsScreen extends StatefulWidget {
  const OnboardingHabitsScreen({super.key});

  @override
  State<OnboardingHabitsScreen> createState() => _OnboardingHabitsScreenState();
}

class _OnboardingHabitsScreenState extends State<OnboardingHabitsScreen>
    with OnboardingSessionMixin {
  final List<Map<String, dynamic>> habits = [
    {
      'id': 'impulse_buying',
      'label': 'Impulse purchases',
      'icon': Icons.shopping_cart
    },
    {'id': 'no_budgeting', 'label': 'No budgeting', 'icon': Icons.money_off},
    {
      'id': 'forgot_subscriptions',
      'label': 'Forget about subscriptions',
      'icon': Icons.subscriptions
    },
    {
      'id': 'credit_dependency',
      'label': 'Frequent loans',
      'icon': Icons.credit_card
    },
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
    await OnboardingState.instance.save();

    // Cache onboarding data using UserProvider for centralized state management
    if (mounted) {
      final userProvider = Provider.of<UserProvider>(context, listen: false);
      final onboardingData = OnboardingState.instance.toMap();
      await userProvider.cacheOnboardingData(onboardingData);
    }

    if (!mounted) return;
    Navigator.pushNamed(context, '/onboarding_finish');
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
                currentStep: 6,
                totalSteps: 7,
              ),
              const SizedBox(height: 24),
              const Text(
                'Which financial habits are hurting you?',
                style: TextStyle(
                  fontFamily: AppTypography.fontHeading,
                  fontWeight: FontWeight.w700,
                  fontSize: 22,
                  color: AppColors.textPrimary,
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
                            color:
                                isSelected ? AppColors.secondary : Colors.white,
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
                                  Icon(habit['icon'],
                                      color: AppColors.textPrimary),
                                  const SizedBox(width: 16),
                                  Expanded(
                                    child: Text(
                                      habit['label'],
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
                        ),
                      );
                    }),
                    const SizedBox(height: 12),
                    const Text(
                      "Anything else?",
                      style: TextStyle(
                        fontFamily: AppTypography.fontBody,
                        fontSize: 16,
                        color: AppColors.textPrimary,
                      ),
                    ),
                    const SizedBox(height: 8),
                    TextFormField(
                      controller: commentController,
                      decoration: InputDecoration(
                        hintText: 'Describe your situation...',
                        filled: true,
                        fillColor: Colors.white,
                        contentPadding: const EdgeInsets.symmetric(
                            vertical: 14, horizontal: 16),
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
                  onPressed: () async {
                    // Skip habits - set empty list
                    final isValid = await validateSessionBeforeNavigation();
                    if (!isValid) return;

                    OnboardingState.instance.habits = [];
                    OnboardingState.instance.habitsComment = null;
                    await OnboardingState.instance.save();

                    // Cache onboarding data using UserProvider for centralized state management
                    if (mounted) {
                      final userProvider =
                          Provider.of<UserProvider>(context, listen: false);
                      final onboardingData = OnboardingState.instance.toMap();
                      await userProvider.cacheOnboardingData(onboardingData);
                    }

                    if (!mounted) return;
                    Navigator.pushNamed(context, '/onboarding_finish');
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
