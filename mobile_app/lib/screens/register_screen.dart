import 'package:flutter/material.dart';
import '../theme/app_colors.dart';
import '../theme/app_typography.dart';
import 'package:dio/dio.dart';
import 'package:provider/provider.dart';
import '../services/api_service.dart';
import '../utils/json_utils.dart';
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

/// What the account actually requires. PasswordValidationService rejects
/// anything weaker, so the screen must not advertise a looser rule — the old
/// "at least 8 characters long" hint sent people round a loop of rejections
/// they could not explain.
const String _passwordRequirements =
    'Use at least 8 characters with upper- and lowercase letters, a number '
    'and a symbol.';

class _RegisterScreenState extends State<RegisterScreen> {
  final ApiService _api = ApiService();
  bool _loading = false;
  bool _obscurePassword = true;
  String? _error;

  /// Drop a stale rejection as soon as the user starts fixing it, so the red
  /// text always describes the values currently in the fields.
  void _clearError(String _) {
    if (_error != null) setState(() => _error = null);
  }

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
    final emailError =
        FormErrorHandler.validateEmail(email, reportError: false);
    if (emailError != null) {
      return emailError;
    }
    if (password.isEmpty) {
      return 'Please enter a password';
    }

    final passwordValidation = _validatePassword(password);
    if (!passwordValidation.isValid || !passwordValidation.isStrong) {
      // One concrete reason, not the whole list: the message renders inline
      // above the button and has to stay readable on a small phone.
      return passwordValidation.issues.isNotEmpty
          ? passwordValidation.issues.first
          : _passwordRequirements;
    }

    return null;
  }

  /// Turn a 400/409/422 registration rejection into a message that is true.
  ///
  /// Never surfaces the API's own prose: backend wording leaks internals and
  /// is not written for end users. We classify, then say it in our own words.
  String _messageForRegistrationRejection(DioException e) {
    final body = asStringKeyedMapOrNull(e.response?.data);
    final error = asStringKeyedMapOrNull(body?['error']) ?? const {};
    final code = asString(error['code']).toUpperCase();
    final apiMessage = asString(error['message']).toLowerCase();

    final looksDuplicate = code.startsWith('RESOURCE_3002') ||
        apiMessage.contains('already exists') ||
        apiMessage.contains('already registered');
    if (looksDuplicate) {
      return 'This email is already registered. Please try logging in instead.';
    }

    if (code.startsWith('VALIDATION') || e.response?.statusCode == 422) {
      // Point at the field the API rejected so the user knows what to change.
      final details = asStringKeyedMapOrNull(error['details']);
      final fields = (details?['validation_errors'] as List?)
              ?.map((v) => asString(asStringKeyedMapOrNull(v)?['field']))
              .join(' ')
              .toLowerCase() ??
          '';
      if (fields.contains('email')) {
        return 'Please enter a valid email address.';
      }
      if (fields.contains('password')) {
        return _passwordRequirements;
      }
      return 'Please check your email and password and try again.';
    }

    return 'We could not create your account. Please check your details and try again.';
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
      logInfo('Attempting FastAPI registration with stable backend',
          tag: 'REGISTER');

      final response = await _api.reliableRegister(
        _emailController.text.trim(),
        _passwordController.text,
      );

      // Extract tokens from standardized response structure
      final rawResponse = asStringKeyedMap(response.data);
      final responseData =
          asStringKeyedMapOrNull(rawResponse['data']) ?? rawResponse;
      final accessToken = asStringOrNull(responseData['access_token']);
      final refreshToken = asStringOrNull(responseData['refresh_token']);

      if (accessToken == null) {
        throw Exception('Registration response missing access token');
      }

      logInfo(
          'Tokens received - access length: ${accessToken.length}, refresh length: ${refreshToken?.length ?? 0}',
          tag: 'REGISTER');

      // Save tokens from FastAPI registration
      await _api.saveTokens(accessToken, refreshToken ?? '');

      if (!mounted) return;

      logInfo('FastAPI registration SUCCESS - initializing user state',
          tag: 'REGISTER');

      // Initialize user provider (will set authenticated state internally)
      final userProvider = context.read<UserProvider>();
      await userProvider.initialize();

      if (!mounted) return;

      // Check if user has completed onboarding (should be false for new registration)
      final hasOnboarded = userProvider.hasCompletedOnboarding;

      logInfo(
          'Registration complete - navigating to ${hasOnboarded ? "main" : "onboarding"}',
          tag: 'REGISTER');

      // Navigate based on onboarding status.
      // removeUntil, not replace: /login is still underneath this route, so a
      // pushReplacement left a freshly-registered (and authenticated) user one
      // Android Back press away from a blank login screen on onboarding step 1.
      Navigator.pushNamedAndRemoveUntil(
        context,
        hasOnboarded ? '/main' : '/onboarding_location',
        (route) => false,
      );
    } catch (e) {
      logError('FastAPI registration FAILED', tag: 'REGISTER', error: e);

      String errorMessage = 'Registration failed';

      // Extract more specific error message from DioException
      if (e is DioException) {
        final statusCode = e.response?.statusCode;

        // The API answers BOTH "this email already exists" (RESOURCE_3002) and
        // "this request is malformed" (VALIDATION_2002) with HTTP 422, so the
        // status code alone cannot tell them apart. Blanket-mapping 422 to
        // "already registered" told users with a typo'd address that they
        // already had an account and sent them to a login they could never
        // pass. Read the error envelope instead and only claim "duplicate"
        // when the API actually said duplicate.
        if (statusCode == 400 || statusCode == 409 || statusCode == 422) {
          errorMessage = _messageForRegistrationRejection(e);
        } else if (statusCode == 500) {
          errorMessage =
              'Server is experiencing issues. This is a temporary problem - please try again in a few minutes.';
        } else if (statusCode != null && statusCode >= 500) {
          errorMessage = 'Server error ($statusCode). Please try again later.';
        }

        // Handle timeout errors specifically
        switch (e.type) {
          case DioExceptionType.receiveTimeout:
          case DioExceptionType.sendTimeout:
          case DioExceptionType.connectionTimeout:
            errorMessage =
                'Registration is taking longer than expected. Our servers may be experiencing high load. Please try again.';
            _showTimeoutRetryDialog();
            return; // Don't show the generic error
          case DioExceptionType.connectionError:
            errorMessage =
                'Connection error. Please check your internet connection and try again.';
            break;
          default:
            break;
        }
      } else if (e is TimeoutException) {
        errorMessage =
            'Registration timeout. Our servers may be busy. Please try again in a moment.';
      } else if (e.toString().contains('SocketException') ||
          e.toString().contains('network') ||
          e.toString().contains('HandshakeException')) {
        errorMessage =
            'Network error. Check your internet connection and try again.';
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
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: const Text('Register'),
        backgroundColor: AppColors.background,
        foregroundColor: AppColors.textPrimary,
        elevation: 0,
      ),
      // The card is taller than the viewport once the keyboard opens, and an
      // overflowing child is clipped OUT OF HIT TESTING, not just out of
      // paint: the Register button stayed visible but stopped responding to
      // taps, so registration silently did nothing until the user happened to
      // dismiss the keyboard. Scrolling the card keeps every control reachable
      // at any viewport height, and minHeight keeps it centred when there is
      // room to spare.
      body: SafeArea(
        child: LayoutBuilder(
          builder: (context, constraints) => SingleChildScrollView(
            child: ConstrainedBox(
              constraints: BoxConstraints(minHeight: constraints.maxHeight),
              child: Center(
                child: Card(
                  elevation: 3,
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(28),
                  ),
                  color: Colors.white,
                  margin:
                      const EdgeInsets.symmetric(horizontal: 24, vertical: 60),
                  child: Padding(
                    padding: const EdgeInsets.symmetric(
                        vertical: 40, horizontal: 28),
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        // Compact logo and title
                        Column(
                          children: [
                            Container(
                              padding: const EdgeInsets.all(12),
                              decoration: BoxDecoration(
                                color: AppColors.textPrimary
                                    .withValues(alpha: 0.1),
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
                          onChanged: _clearError,
                          keyboardType: TextInputType.emailAddress,
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
                          obscureText: _obscurePassword,
                          onChanged: _clearError,
                          decoration: InputDecoration(
                            labelText: 'Password',
                            border: OutlineInputBorder(
                              borderRadius: BorderRadius.circular(16),
                            ),
                            suffixIcon: IconButton(
                              icon: Icon(_obscurePassword
                                  ? Icons.visibility_outlined
                                  : Icons.visibility_off_outlined),
                              tooltip: _obscurePassword
                                  ? 'Show password'
                                  : 'Hide password',
                              onPressed: () => setState(
                                  () => _obscurePassword = !_obscurePassword),
                            ),
                          ),
                        ),
                        const SizedBox(height: 8),
                        Text(
                          _passwordRequirements,
                          style: const TextStyle(
                            fontSize: 12,
                            color: Colors.grey,
                            fontFamily: AppTypography.fontBody,
                          ),
                        ),
                        // The error belongs HERE, immediately under the fields
                        // and above the button. It used to render after "Back
                        // to login" at the very bottom of the card, which with
                        // the keyboard open sits below the fold — so tapping
                        // Register on an invalid password looked like the
                        // button did nothing at all.
                        if (_error != null) ...[
                          const SizedBox(height: 12),
                          Row(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              const Icon(Icons.error_outline,
                                  color: Colors.red, size: 18),
                              const SizedBox(width: 8),
                              Expanded(
                                child: Text(
                                  _error!,
                                  style: const TextStyle(
                                    color: Colors.red,
                                    fontFamily: AppTypography.fontBody,
                                  ),
                                ),
                              ),
                            ],
                          ),
                        ],
                        const SizedBox(height: 16),
                        _loading
                            ? const CircularProgressIndicator()
                            : ElevatedButton(
                                style: ElevatedButton.styleFrom(
                                  backgroundColor: AppColors.secondary,
                                  foregroundColor: AppColors.textPrimary,
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
                          onPressed: () {
                            // FIX: Handle case where there's no previous route (black screen bug)
                            if (Navigator.canPop(context)) {
                              Navigator.pop(context);
                            } else {
                              // No previous route - navigate to login explicitly
                              Navigator.pushReplacementNamed(context, '/login');
                            }
                          },
                          child: const Text('Back to login'),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }

  void _showTimeoutRetryDialog() {
    showDialog<void>(
      context: context,
      builder: (BuildContext context) {
        return AlertDialog(
          shape:
              RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
          title: Row(
            children: [
              Icon(Icons.wifi_off,
                  color: Theme.of(context).colorScheme.primary),
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
