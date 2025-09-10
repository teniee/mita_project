
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
  bool _success = false;
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

      // Validate that we have essential data
      if (state.income == null || state.region == null) {
        throw Exception('Missing essential onboarding data. Please go back and complete all steps.');
      }

      // Check if user is still authenticated before proceeding
      final currentToken = await _api.getToken();
      if (currentToken == null) {
        throw Exception('Session expired. Please log in again.');
      }

      // Cache onboarding data immediately for main app use
      await UserDataManager.instance.cacheOnboardingData(onboardingData);
      logInfo('Onboarding data cached for immediate use', tag: 'ONBOARDING_FINISH');

      // Try to submit to backend with proper error handling
      try {
        await _api.submitOnboarding(onboardingData);
        logInfo('Onboarding submitted to backend successfully', tag: 'ONBOARDING_FINISH');
        
        // Force refresh user data from API to get latest state
        await UserDataManager.instance.refreshUserData();
        
      } catch (e) {
        logWarning('Backend submission failed (but continuing with cached data): $e', tag: 'ONBOARDING_FINISH');
        
        // Check if it's an authentication error
        if (e.toString().contains('401') || e.toString().toLowerCase().contains('unauthorized')) {
          // Try to refresh token and retry once
          try {
            final refreshed = await _api.refreshAccessToken();
            if (refreshed != null) {
              await _api.submitOnboarding(onboardingData);
              logInfo('Onboarding submitted after token refresh', tag: 'ONBOARDING_FINISH');
            } else {
              throw Exception('Session expired. Please log in again.');
            }
          } catch (refreshError) {
            logError('Token refresh failed during onboarding: $refreshError', tag: 'ONBOARDING_FINISH');
            throw Exception('Session expired. Please log in again.');
          }
        }
        // For other errors, continue with cached data - user can still use the app
      }

      if (!mounted) return;
      
      // Show success message briefly before navigating
      setState(() {
        _loading = false;
        _success = true;
      });

      // Brief success display
      await Future.delayed(const Duration(milliseconds: 1500));
      
      if (!mounted) return;

      // Clear temporary onboarding state only after successful completion
      OnboardingState.instance.reset();

      // Navigate to main screen with proper replacement to prevent back navigation
      if (mounted) {
        Navigator.pushNamedAndRemoveUntil(
          context, 
          '/main', 
          (route) => false, // Remove all previous routes
        );
      }
      
    } catch (e) {
      logError('Critical error in onboarding: $e', tag: 'ONBOARDING_FINISH');
      
      if (!mounted) return;
      
      setState(() {
        _loading = false;
        _error = _getErrorMessage(e);
      });
    }
  }

  String _getErrorMessage(dynamic error) {
    final errorMsg = error.toString();
    
    if (errorMsg.contains('Session expired') || errorMsg.contains('log in again')) {
      return "Your session has expired. Please log in again to continue.";
    } else if (errorMsg.contains('Missing essential')) {
      return "Please complete all onboarding steps before continuing.";
    } else if (errorMsg.contains('network') || errorMsg.contains('connection')) {
      return "Network connection issue. Please check your internet and try again.";
    } else {
      return "Unable to complete setup. Please try again or skip for now.";
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFFFF9F0),
      body: Center(
        child: _loading
            ? Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  const CircularProgressIndicator(),
                  const SizedBox(height: 16),
                  Text(
                    'Setting up your MITA account...',
                    style: TextStyle(
                      fontFamily: 'Manrope',
                      fontSize: 16,
                      color: Colors.grey[600],
                    ),
                  ),
                ],
              )
            : _success
                ? Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Container(
                        width: 80,
                        height: 80,
                        decoration: const BoxDecoration(
                          color: Colors.green,
                          shape: BoxShape.circle,
                        ),
                        child: const Icon(
                          Icons.check,
                          color: Colors.white,
                          size: 48,
                        ),
                      ),
                      const SizedBox(height: 24),
                      const Text(
                        'Setup Complete!',
                        style: TextStyle(
                          fontFamily: 'Sora',
                          fontWeight: FontWeight.bold,
                          fontSize: 24,
                          color: Color(0xFF193C57),
                        ),
                      ),
                      const SizedBox(height: 8),
                      Text(
                        'Welcome to MITA!',
                        style: TextStyle(
                          fontFamily: 'Manrope',
                          fontSize: 16,
                          color: Colors.grey[600],
                        ),
                      ),
                    ],
                  )
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
                            // Clear the error state and navigate
                            OnboardingState.instance.reset();
                            Navigator.pushNamedAndRemoveUntil(
                              context, 
                              '/main', 
                              (route) => false,
                            );
                          },
                          child: const Text(
                            'Skip for now',
                            style: TextStyle(color: Color(0xFF193C57)),
                          ),
                        ),
                        const SizedBox(height: 12),
                        // Add logout option for session expired errors
                        if (_error?.contains('session has expired') == true ||
                            _error?.contains('log in again') == true)
                          TextButton(
                            onPressed: () async {
                              // Clear all user data and return to login
                              await _api.clearTokens();
                              OnboardingState.instance.reset();
                              if (mounted) {
                                Navigator.pushNamedAndRemoveUntil(
                                  context, 
                                  '/login', 
                                  (route) => false,
                                );
                              }
                            },
                            child: const Text(
                              'Back to Login',
                              style: TextStyle(
                                color: Color(0xFFD32F2F),
                                fontWeight: FontWeight.w600,
                              ),
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
