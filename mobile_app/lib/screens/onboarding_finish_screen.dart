
import 'package:flutter/material.dart';
import '../services/api_service.dart';
import '../services/onboarding_state.dart';
import '../services/logging_service.dart';
import '../services/user_data_manager.dart';

class OnboardingFinishScreen extends StatefulWidget {
  const OnboardingFinishScreen({super.key});

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
        "countryCode": state.countryCode,
        "stateCode": state.stateCode,
        "income": state.income,
        "incomeTier": state.incomeTier?.name,
        "expenses": state.expenses,
        "goals": state.goals,
        "habits": state.habits,
        if (state.habitsComment != null && state.habitsComment!.isNotEmpty)
          "habits_comment": state.habitsComment,
      };

      logInfo('Submitting onboarding data: $onboardingData', tag: 'ONBOARDING_FINISH');

      // Cache onboarding data immediately for main app use
      await UserDataManager.instance.cacheOnboardingData(onboardingData);
      logInfo('Onboarding data cached for immediate use', tag: 'ONBOARDING_FINISH');

      // Try to submit to backend
      try {
        await _api.submitOnboarding(onboardingData);
        logInfo('Onboarding submitted to backend successfully', tag: 'ONBOARDING_FINISH');
        
        // Force refresh user data from API to get latest state
        await UserDataManager.instance.refreshUserData();
        
      } catch (e) {
        logWarning('Backend submission failed (but continuing with cached data): $e', tag: 'ONBOARDING_FINISH');
        // Continue with cached data - user can still use the app
      }

      // Clear temporary onboarding state only after successful caching
      OnboardingState.instance.reset();

      if (!mounted) return;
      setState(() {
        _loading = false;
      });

      // Navigate to main screen with user data ready
      Navigator.pushReplacementNamed(context, '/main');
      
    } catch (e) {
      logError('Critical error in onboarding: $e', tag: 'ONBOARDING_FINISH');
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
                          style: const const TextStyle(
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
                            style: const TextStyle(color: Color(0xFF193C57)),
                          ),
                        ),
                      ],
                    ),
                  )
                : const Text(
                    'Welcome to MITA!',
                    style: const TextStyle(
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
