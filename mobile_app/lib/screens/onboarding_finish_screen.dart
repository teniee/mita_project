import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../theme/app_colors.dart';
import '../theme/app_typography.dart';
import '../providers/user_provider.dart';
import '../services/api_service.dart';
import '../services/onboarding_state.dart';
import '../services/logging_service.dart';

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

  // Retry rate limiting
  int _retryCount = 0;
  static const int _maxRetries = 3;
  DateTime? _lastRetryTime;
  static const Duration _retryDelay = Duration(seconds: 5);

  @override
  void initState() {
    super.initState();
    _checkAuthAndSubmit();
  }

  Future<void> _checkAuthAndSubmit() async {
    // First, check if user has a valid token BEFORE attempting submission
    final currentToken = await _api.getToken();

    if (currentToken == null) {
      // No token at all - prompt for registration/login
      if (!mounted) return;
      setState(() {
        _loading = false;
        _error =
            'To save your budget and preferences, please create an account or log in. Your setup will be saved after authentication.';
      });
      return;
    }

    // Token exists, try to submit (will handle token expiration during submission)
    _submitOnboardingData();
  }

  bool _canRetry() {
    // Check max retries
    if (_retryCount >= _maxRetries) {
      return false;
    }

    // Check time-based rate limit
    if (_lastRetryTime != null) {
      final timeSinceLastRetry = DateTime.now().difference(_lastRetryTime!);
      if (timeSinceLastRetry < _retryDelay) {
        return false;
      }
    }

    return true;
  }

  String _getRetryMessage() {
    if (_retryCount >= _maxRetries) {
      return 'Maximum retry attempts reached. Please contact support or try again later.';
    }

    if (_lastRetryTime != null) {
      final timeSinceLastRetry = DateTime.now().difference(_lastRetryTime!);
      if (timeSinceLastRetry < _retryDelay) {
        final remaining = _retryDelay.inSeconds - timeSinceLastRetry.inSeconds;
        return 'Please wait $remaining seconds before retrying.';
      }
    }

    return '';
  }

  Future<void> _submitOnboardingData() async {
    try {
      // Gather answers from the temporary onboarding state
      final state = OnboardingState.instance;

      // Transform expenses from array to dict format expected by backend
      final Map<String, double> fixedExpenses = {};
      for (var expense in state.expenses) {
        final category = (expense['category'] as String)
            .toLowerCase()
            .replaceAll(' ', '_')
            .replaceAll('/', '_or_');
        final amount = double.tryParse(expense['amount'].toString()) ?? 0.0;
        fixedExpenses[category] = amount;
      }

      // Transform goals from list to dict format expected by backend
      // Priority order for primary goal: emergency fund > debt > investing > budgeting
      String primaryGoal = "general";
      if (state.goals.contains("save_more")) {
        primaryGoal = "save_more";
      } else if (state.goals.contains("pay_off_debt")) {
        primaryGoal = "pay_off_debt";
      } else if (state.goals.contains("investing")) {
        primaryGoal = "investing";
      } else if (state.goals.contains("budgeting")) {
        primaryGoal = "budgeting";
      } else if (state.goals.isNotEmpty) {
        primaryGoal = state.goals.first;
      }

      final goalsData = {
        "savings_goal_amount_per_month": state.savingsGoalAmount ?? 0.0,
        "savings_goal_type": primaryGoal,
        "has_emergency_fund": state.goals.contains("save_more"),
        "all_goals": state.goals, // Include all selected goals
      };

      // Use REAL spending frequencies from user input (not hardcoded!)
      final spendingHabits = state.spendingFrequencies ??
          {
            // Fallback to defaults only if user didn't provide input
            "dining_out_per_month":
                state.habits.contains("Impulse purchases") ? 15 : 8,
            "entertainment_per_month": 4,
            "clothing_per_month": 2,
            "travel_per_year": 2,
            "coffee_per_week": 5,
            "transport_per_month": 20,
          };

      // Format data to match backend expectations
      final onboardingData = {
        "region": state.countryCode ?? "US",
        "income": {
          "monthly_income": state.income ?? 0,
          "additional_income": 0,
        },
        "fixed_expenses": fixedExpenses,
        "spending_habits": spendingHabits,
        "goals": goalsData,
        // Also include original format for backward compatibility
        "_meta": {
          "countryCode": state.countryCode,
          "stateCode": state.stateCode,
          "incomeTier": state.incomeTier?.name,
          "goals_list": state.goals,
          "habits_list": state.habits,
          if (state.habitsComment != null && state.habitsComment!.isNotEmpty)
            "habits_comment": state.habitsComment,
        },
      };

      logInfo('Submitting onboarding data: $onboardingData',
          tag: 'ONBOARDING_FINISH');

      // Validate that we have essential data
      if (state.income == null || state.countryCode == null) {
        throw Exception(
            'Missing essential onboarding data. Please go back and complete all steps.');
      }

      // Check if user is still authenticated before proceeding
      final currentToken = await _api.getToken();
      if (currentToken == null) {
        throw Exception('Session expired. Please log in again.');
      }

      // Cache onboarding data using UserProvider for centralized state management
      final userProvider = context.read<UserProvider>();
      await userProvider.cacheOnboardingData(onboardingData);
      logInfo('Onboarding data cached for immediate use',
          tag: 'ONBOARDING_FINISH');

      // CRITICAL DEBUG: Verify cache was actually saved
      final cachedCheck = userProvider.hasCompletedOnboarding;
      logInfo('CRITICAL DEBUG: Cache verification after save: $cachedCheck',
          tag: 'ONBOARDING_FINISH');

      // Try to submit to backend with proper error handling
      try {
        await _api.submitOnboarding(onboardingData);
        logInfo('Onboarding submitted to backend successfully',
            tag: 'ONBOARDING_FINISH');
        // Note: User data refresh is already handled by UserProvider.cacheOnboardingData()
      } catch (e) {
        logWarning(
            'Backend submission failed (but continuing with cached data): $e',
            tag: 'ONBOARDING_FINISH');

        // Check if it's an authentication error
        if (e.toString().contains('401') ||
            e.toString().toLowerCase().contains('unauthorized')) {
          // Try to refresh token and retry once
          try {
            final refreshed = await _api.refreshAccessToken();
            if (refreshed != null) {
              await _api.submitOnboarding(onboardingData);
              logInfo('Onboarding submitted after token refresh',
                  tag: 'ONBOARDING_FINISH');
            } else {
              throw Exception('Session expired. Please log in again.');
            }
          } catch (refreshError) {
            logError('Token refresh failed during onboarding: $refreshError',
                tag: 'ONBOARDING_FINISH');
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

      // CRITICAL DEBUG: Final verification before navigation
      final finalCacheCheck = userProvider.hasCompletedOnboarding;
      logInfo(
          'CRITICAL DEBUG: Final cache check before navigation: $finalCacheCheck',
          tag: 'ONBOARDING_FINISH');

      // Clear temporary onboarding state only after successful completion
      OnboardingState.instance.reset();
      logInfo('CRITICAL DEBUG: OnboardingState reset completed',
          tag: 'ONBOARDING_FINISH');

      // Navigate to main screen with proper replacement to prevent back navigation
      if (mounted) {
        logInfo('CRITICAL DEBUG: Navigating to /main screen',
            tag: 'ONBOARDING_FINISH');
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

    if (errorMsg.contains('Session expired') ||
        errorMsg.contains('log in again')) {
      return "Your session has expired. Please log in again to continue.";
    } else if (errorMsg.contains('Missing essential')) {
      return "Please complete all onboarding steps before continuing.";
    } else if (errorMsg.contains('network') ||
        errorMsg.contains('connection')) {
      return "Network connection issue. Please check your internet and try again.";
    } else {
      return "Unable to complete setup. Please try again or skip for now.";
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
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
                      fontFamily: AppTypography.fontBody,
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
                          fontFamily: AppTypography.fontHeading,
                          fontWeight: FontWeight.bold,
                          fontSize: 24,
                          color: AppColors.textPrimary,
                        ),
                      ),
                      const SizedBox(height: 8),
                      Text(
                        'Welcome to MITA!',
                        style: TextStyle(
                          fontFamily: AppTypography.fontBody,
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
                                fontFamily: AppTypography.fontBody,
                                fontSize: 16,
                              ),
                              textAlign: TextAlign.center,
                            ),
                            const SizedBox(height: 12),
                            // Retry count indicator
                            if (_retryCount > 0)
                              Text(
                                'Retry attempts: $_retryCount/$_maxRetries',
                                style: TextStyle(
                                  fontFamily: AppTypography.fontBody,
                                  fontSize: 13,
                                  color: Colors.grey.shade600,
                                ),
                              ),
                            // Rate limit message
                            if (!_canRetry() &&
                                _getRetryMessage().isNotEmpty) ...[
                              const SizedBox(height: 8),
                              Container(
                                padding: const EdgeInsets.all(12),
                                decoration: BoxDecoration(
                                  color: Colors.orange.shade50,
                                  borderRadius: BorderRadius.circular(8),
                                  border:
                                      Border.all(color: Colors.orange.shade200),
                                ),
                                child: Text(
                                  _getRetryMessage(),
                                  style: TextStyle(
                                    fontFamily: AppTypography.fontBody,
                                    fontSize: 13,
                                    color: Colors.orange.shade800,
                                  ),
                                  textAlign: TextAlign.center,
                                ),
                              ),
                            ],
                            const SizedBox(height: 24),
                            ElevatedButton(
                              onPressed: _canRetry()
                                  ? () {
                                      setState(() {
                                        _loading = true;
                                        _error = null;
                                        _retryCount++;
                                        _lastRetryTime = DateTime.now();
                                      });
                                      _submitOnboardingData();
                                    }
                                  : null, // Disabled when rate limited
                              style: ElevatedButton.styleFrom(
                                backgroundColor: AppColors.textPrimary,
                                foregroundColor: Colors.white,
                                disabledBackgroundColor: Colors.grey.shade300,
                                disabledForegroundColor: Colors.grey.shade600,
                                padding: const EdgeInsets.symmetric(
                                    vertical: 16, horizontal: 24),
                                shape: RoundedRectangleBorder(
                                  borderRadius: BorderRadius.circular(18),
                                ),
                              ),
                              child: Text(
                                  _canRetry() ? 'Retry' : 'Retry Disabled'),
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
                                style: TextStyle(color: AppColors.textPrimary),
                              ),
                            ),
                            const SizedBox(height: 12),
                            // Add login/registration options for auth-related errors
                            if (_error?.contains('session has expired') == true ||
                                _error?.contains('log in') == true ||
                                _error?.contains('create an account') == true)
                              Column(
                                children: [
                                  // Primary action: Create Account (for new users)
                                  SizedBox(
                                    width: double.infinity,
                                    child: ElevatedButton(
                                      onPressed: () async {
                                        // Clear temporary data before registration
                                        await _api.clearTokens();
                                        if (mounted) {
                                          Navigator.pushNamedAndRemoveUntil(
                                            context,
                                            '/register',
                                            (route) => false,
                                          );
                                        }
                                      },
                                      style: ElevatedButton.styleFrom(
                                        backgroundColor: AppColors.textPrimary,
                                        foregroundColor: Colors.white,
                                        padding: const EdgeInsets.symmetric(
                                            vertical: 16, horizontal: 24),
                                        shape: RoundedRectangleBorder(
                                          borderRadius: BorderRadius.circular(18),
                                        ),
                                      ),
                                      child: const Text(
                                        'Create Account',
                                        style: TextStyle(
                                          fontWeight: FontWeight.w600,
                                          fontSize: 16,
                                        ),
                                      ),
                                    ),
                                  ),
                                  const SizedBox(height: 12),
                                  // Secondary action: Login (for existing users)
                                  TextButton(
                                    onPressed: () async {
                                      // Clear tokens and go to login
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
                                      'Already have an account? Log In',
                                      style: TextStyle(
                                        color: AppColors.textPrimary,
                                        fontWeight: FontWeight.w600,
                                      ),
                                    ),
                                  ),
                                ],
                              ),
                          ],
                        ),
                      )
                    : const Text(
                        'Welcome to MITA!',
                        style: TextStyle(
                          fontFamily: AppTypography.fontHeading,
                          fontWeight: FontWeight.bold,
                          fontSize: 24,
                          color: AppColors.textPrimary,
                        ),
                      ),
      ),
    );
  }
}
