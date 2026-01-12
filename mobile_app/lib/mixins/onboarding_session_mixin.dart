import 'package:flutter/material.dart';
import '../services/api_service.dart';
import '../services/logging_service.dart';

/// Mixin to handle session validation during onboarding
/// Prevents session expiration issues and provides consistent error handling
mixin OnboardingSessionMixin<T extends StatefulWidget> on State<T> {
  final ApiService _apiService = ApiService();
  final bool _sessionValidated = false;

  @override
  void initState() {
    super.initState();
    // DISABLED: No session validation during onboarding
    // User just logged in, token is fresh for 2 hours
    // Any validation would be redundant and potentially disruptive
  }

  /// Handle session expiration by clearing tokens and redirecting to login
  void _handleSessionExpired() {
    if (!mounted) return;

    showDialog<void>(
      context: context,
      barrierDismissible: false,
      builder: (context) => AlertDialog(
        title: const Text('Session Expired'),
        content: const Text(
          'Your session has expired. Please log in again to continue setting up your account.',
        ),
        actions: [
          TextButton(
            onPressed: () async {
              // Clear tokens and redirect to login
              await _apiService.clearTokens();
              if (mounted) {
                Navigator.pushNamedAndRemoveUntil(
                  context,
                  '/login',
                  (route) => false,
                );
              }
            },
            child: const Text('Back to Login'),
          ),
        ],
      ),
    );
  }

  /// Validate session before proceeding to next onboarding step
  Future<bool> validateSessionBeforeNavigation() async {
    // Just check if token exists - don't do aggressive validation during onboarding
    // User just logged in, token should be fresh for 2 hours
    final token = await _apiService.getToken();
    if (token == null) {
      logWarning('No token found - cannot proceed with onboarding',
          tag: 'ONBOARDING_SESSION');
      _handleSessionExpired();
      return false;
    }

    logDebug('Token exists, allowing navigation', tag: 'ONBOARDING_SESSION');
    return true;
  }

  /// Get whether session is currently validated
  bool get isSessionValidated => _sessionValidated;
}
