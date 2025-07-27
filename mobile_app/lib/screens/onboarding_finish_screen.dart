
import 'package:flutter/material.dart';
import '../services/api_service.dart';
import '../services/onboarding_state.dart';

class OnboardingFinishScreen extends StatefulWidget {
  const OnboardingFinishScreen({Key? key}) : super(key: key);

  @override
  State<OnboardingFinishScreen> createState() => _OnboardingFinishScreenState();
}

class _OnboardingFinishScreenState extends State<OnboardingFinishScreen> {
  final ApiService _api = ApiService();
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _submitOnboardingData();
  }

  Future<void> _submitOnboardingData() async {
    try {
      // Gather answers from the temporary onboarding state
      final state = OnboardingState.instance;
      final onboardingData = {
        "region": state.region,
        "income": state.income,
        "expenses": state.expenses,
        "goals": state.goals,
        "habits": state.habits,
        "motivation": state.motivation,
        if (state.habitsComment != null && state.habitsComment!.isNotEmpty)
          "habits_comment": state.habitsComment,
      };

      print('Submitting onboarding data: $onboardingData');

      try {
        await _api.submitOnboarding(onboardingData);
        print('Onboarding submitted successfully');
      } catch (e) {
        print('Onboarding submission failed (but continuing): $e');
        // Continue anyway since the backend endpoint might not be ready
      }

      OnboardingState.instance.reset();

      if (!mounted) return;
      setState(() {
        _loading = false;
      });

      // Always go to main screen after onboarding
      Navigator.pushReplacementNamed(context, '/main');
    } catch (e) {
      print('Critical error in onboarding: $e');
      setState(() {
        _loading = false;
        _error = "Unable to complete onboarding. Please try again.";
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFFFF9F0),
      body: Center(
        child: _loading
            ? const CircularProgressIndicator()
            : _error != null
                ? Padding(
                    padding: const EdgeInsets.all(24),
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Text(
                          _error!,
                          style: const TextStyle(
                            color: Colors.red,
                            fontFamily: 'Manrope',
                            fontSize: 16,
                          ),
                          textAlign: TextAlign.center,
                        ),
                        const SizedBox(height: 24),
                        ElevatedButton(
                          onPressed: () {
                            setState(() {
                              _loading = true;
                              _error = null;
                            });
                            _submitOnboardingData();
                          },
                          style: ElevatedButton.styleFrom(
                            backgroundColor: const Color(0xFF193C57),
                            foregroundColor: Colors.white,
                            padding: const EdgeInsets.symmetric(vertical: 16, horizontal: 24),
                            shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(18),
                            ),
                          ),
                          child: const Text('Retry'),
                        ),
                        const SizedBox(height: 12),
                        TextButton(
                          onPressed: () {
                            Navigator.pushReplacementNamed(context, '/main');
                          },
                          child: const Text(
                            'Skip for now',
                            style: TextStyle(color: Color(0xFF193C57)),
                          ),
                        ),
                      ],
                    ),
                  )
                : const Text(
                    'Welcome to MITA!',
                    style: TextStyle(
                      fontFamily: 'Sora',
                      fontWeight: FontWeight.bold,
                      fontSize: 24,
                      color: Color(0xFF193C57),
                    ),
                  ),
      ),
    );
  }
}
