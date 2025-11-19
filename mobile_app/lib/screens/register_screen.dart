import 'package:flutter/material.dart';
import '../theme/app_colors.dart';
import '../theme/app_typography.dart';
import 'package:dio/dio.dart';
import 'package:provider/provider.dart';
import '../services/api_service.dart';
import '../services/logging_service.dart';
import '../services/password_validation_service.dart';
import '../services/timeout_manager_service.dart';
import '../core/enhanced_error_handling.dart';
import '../providers/user_provider.dart';

class RegisterScreen extends StatefulWidget {
  const RegisterScreen({super.key});

  @override
  State<RegisterScreen> createState() => _RegisterScreenState();
}

class _RegisterScreenState extends State<RegisterScreen> {
  final ApiService _api = ApiService();
  bool _loading = false;
  String? _error;
  final TextEditingController _emailController = TextEditingController();
  final TextEditingController _passwordController = TextEditingController();

  PasswordValidationResult _validatePassword(String password) {
    return PasswordValidationService.validatePassword(password);
  }

  String? _validateInputs() {
    final email = _emailController.text.trim();
    final password = _passwordController.text;

    if (email.isEmpty) {
      return 'Please enter your email';
    }

    // Use centralized email validation
    final emailError = FormErrorHandler.validateEmail(email, reportError: false);
    if (emailError != null) {
      return emailError;
    }
    if (password.isEmpty) {
      return 'Please enter a password';
    }
    
    final passwordValidation = _validatePassword(password);
    if (!passwordValidation.isValid) {
      return passwordValidation.issues.first;
    }
    if (!passwordValidation.isStrong) {
      return 'Password does not meet security requirements. ${passwordValidation.issues.join('; ')}';
    }
    
    return null;
  }

  Future<void> _register() async {
    // Validate inputs first
    final validationError = _validateInputs();
    if (validationError != null) {
      setState(() {
        _error = validationError;
      });
      return;
    }
    setState(() {
      _loading = true;
      _error = null;
    });
    
    try {
      // Use reliable FastAPI registration with restored backend
      logInfo('Attempting FastAPI registration with stable backend', tag: 'REGISTER');
      
      final response = await _api.reliableRegister(
        _emailController.text.trim(),
        _passwordController.text,
      );

      // Extract tokens from standardized response structure
      final responseData = response.data['data'] ?? response.data;
      final accessToken = responseData['access_token'] as String;
      final refreshToken = responseData['refresh_token'] as String?;

      logInfo('Tokens received - access: ${accessToken.substring(0, 20)}..., refresh: ${refreshToken?.substring(0, 20) ?? 'null'}', tag: 'REGISTER');

      // Save tokens from FastAPI registration
      await _api.saveTokens(accessToken, refreshToken ?? '');

      if (!mounted) return;

      logInfo('FastAPI registration SUCCESS - initializing user state', tag: 'REGISTER');

      // Set authentication state using UserProvider
      final userProvider = context.read<UserProvider>();
      userProvider.setAuthenticated();
      await userProvider.initialize();

      if (!mounted) return;

      // Check if user has completed onboarding (should be false for new registration)
      final hasOnboarded = userProvider.hasCompletedOnboarding;

      logInfo('Registration complete - navigating to ${hasOnboarded ? "main" : "onboarding"}', tag: 'REGISTER');

      // Navigate based on onboarding status
      if (hasOnboarded) {
        Navigator.pushReplacementNamed(context, '/main');
      } else {
        Navigator.pushReplacementNamed(context, '/onboarding_location');
      }
      
    } catch (e) {
      logError('FastAPI registration FAILED', tag: 'REGISTER', error: e);
      
      String errorMessage = 'Registration failed';
      
      // Extract more specific error message from DioException
      if (e is DioException) {
        final statusCode = e.response?.statusCode;
        final errorData = e.response?.data?.toString() ?? '';
        
        if (statusCode == 400) {
          if (errorData.contains('already registered') || errorData.contains('Email already registered')) {
            errorMessage = 'This email is already registered. Please try logging in instead.';
          } else if (errorData.contains('Password too short')) {
            errorMessage = 'Password must be at least 8 characters long.';
          } else if (errorData.contains('Invalid email')) {
            errorMessage = 'Please enter a valid email address.';
          } else {
            errorMessage = 'Invalid email or password format.';
          }
        } else if (statusCode == 409 || statusCode == 422) {
          errorMessage = 'This email is already registered. Please try logging in instead.';
        } else if (statusCode == 500) {
          errorMessage = 'Server is experiencing issues. This is a temporary problem - please try again in a few minutes.';
        } else if (statusCode != null && statusCode >= 500) {
          errorMessage = 'Server error (${statusCode}). Please try again later.';
        }
        
        // Handle timeout errors specifically
        switch (e.type) {
          case DioExceptionType.receiveTimeout:
          case DioExceptionType.sendTimeout:
          case DioExceptionType.connectionTimeout:
            errorMessage = 'Registration is taking longer than expected. Our servers may be experiencing high load. Please try again.';
            _showTimeoutRetryDialog();
            return; // Don't show the generic error
          case DioExceptionType.connectionError:
            errorMessage = 'Connection error. Please check your internet connection and try again.';
            break;
          default:
            break;
        }
      } else if (e is TimeoutException) {
        errorMessage = 'Registration timeout. Our servers may be busy. Please try again in a moment.';
      } else if (e.toString().contains('SocketException') || 
                 e.toString().contains('network') ||
                 e.toString().contains('HandshakeException')) {
        errorMessage = 'Network error. Check your internet connection and try again.';
      }
      
      setState(() {
        _loading = false;
        _error = errorMessage;
      });
    } finally {
      if (mounted) {
        setState(() {
          _loading = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const AppColors.background,
      appBar: AppBar(
        title: const Text('Register'),
        backgroundColor: const AppColors.background,
        foregroundColor: const AppColors.textPrimary,
        elevation: 0,
      ),
      body: SafeArea(
        child: Center(
          child: Card(
            elevation: 3,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(28),
            ),
            color: Colors.white,
            margin: const EdgeInsets.symmetric(horizontal: 24, vertical: 60),
            child: Padding(
              padding: const EdgeInsets.symmetric(vertical: 40, horizontal: 28),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  // Compact logo and title
                  Column(
                    children: [
                      Container(
                        padding: const EdgeInsets.all(12),
                        decoration: BoxDecoration(
                          color: const AppColors.textPrimary.withValues(alpha: 0.1),
                          borderRadius: BorderRadius.circular(16),
                        ),
                        child: const Icon(
                          Icons.account_balance_wallet_rounded,
                          size: 24,
                          color: AppColors.textPrimary,
                        ),
                      ),
                      const SizedBox(height: 12),
                      const Text(
                        'Create account',
                        style: TextStyle(
                          fontFamily: AppTypography.fontHeading,
                          fontWeight: FontWeight.w700,
                          fontSize: 20,
                          color: AppColors.textPrimary,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 24),
                  TextField(
                    controller: _emailController,
                    decoration: InputDecoration(
                      labelText: 'Email',
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(16),
                      ),
                    ),
                  ),
                  const SizedBox(height: 12),
                  TextField(
                    controller: _passwordController,
                    obscureText: true,
                    decoration: InputDecoration(
                      labelText: 'Password',
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(16),
                      ),
                    ),
                  ),
                  const SizedBox(height: 8),
                  const Text(
                    'Password must be at least 8 characters long',
                    style: TextStyle(
                      fontSize: 12,
                      color: Colors.grey,
                      fontFamily: AppTypography.fontBody,
                    ),
                  ),
                  const SizedBox(height: 16),
                  _loading
                      ? const CircularProgressIndicator()
                      : ElevatedButton(
                          style: ElevatedButton.styleFrom(
                            backgroundColor: const AppColors.secondary,
                            foregroundColor: const AppColors.textPrimary,
                            shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(18),
                            ),
                            padding: const EdgeInsets.symmetric(
                                vertical: 16, horizontal: 24),
                            textStyle: const TextStyle(
                              fontFamily: AppTypography.fontHeading,
                              fontWeight: FontWeight.w600,
                              fontSize: 16,
                            ),
                          ),
                          onPressed: _register,
                          child: const Text('Register'),
                        ),
                  TextButton(
                    onPressed: () => Navigator.pop(context),
                    child: const Text('Back to login'),
                  ),
                  if (_error != null) ...[
                    const SizedBox(height: 16),
                    Text(
                      _error!,
                      style: const TextStyle(
                        color: Colors.red,
                        fontFamily: AppTypography.fontBody,
                      ),
                    ),
                  ]
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  void _showTimeoutRetryDialog() {
    showDialog(
      context: context,
      builder: (BuildContext context) {
        return AlertDialog(
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
          title: Row(
            children: [
              Icon(Icons.wifi_off, color: Theme.of(context).colorScheme.primary),
              const SizedBox(width: 8),
              const Text('Connection Timeout'),
            ],
          ),
          content: const Text(
            'The registration request is taking longer than expected. This might be due to server load or network conditions.\n\nWe\'ve increased the timeout limit. Would you like to try again?',
          ),
          actions: [
            TextButton(
              onPressed: () {
                Navigator.of(context).pop();
                setState(() {
                  _loading = false;
                });
              },
              child: const Text('Cancel'),
            ),
            FilledButton(
              onPressed: () {
                Navigator.of(context).pop();
                // Retry the registration with the same credentials
                _register();
              },
              child: const Text('Try Again'),
            ),
          ],
        );
      },
    );
  }
}

