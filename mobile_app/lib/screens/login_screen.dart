import 'dart:async';
import 'dart:developer' as dev;

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import '../theme/app_colors.dart';
import '../theme/app_typography.dart';
import 'package:flutter/services.dart';
import 'package:dio/dio.dart';
import 'package:google_sign_in/google_sign_in.dart';
import 'package:provider/provider.dart';
import '../services/api_service.dart';
import '../providers/user_provider.dart';
import '../services/secure_push_token_manager.dart';
import '../services/password_validation_service.dart';
import '../services/accessibility_service.dart';
import '../services/timeout_manager_service.dart';
import '../theme/mita_theme.dart';
import '../l10n/generated/app_localizations.dart';
import '../core/enhanced_error_handling.dart';
import '../core/app_error_handler.dart';
import '../core/error_handling.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> 
    with TickerProviderStateMixin, RobustErrorHandlingMixin {
  final ApiService _api = ApiService();
  final AccessibilityService _accessibilityService = AccessibilityService.instance;
  bool _loading = false;
  bool _slowConnectionDetected = false;
  Timer? _slowConnectionTimer;
  
  // Form controllers and validation
  final GlobalKey<FormState> _formKey = GlobalKey<FormState>();
  final TextEditingController _emailController = TextEditingController();
  final TextEditingController _passwordController = TextEditingController();
  
  // UI state
  bool _rememberMe = true;
  bool _obscurePassword = true;
  bool _isEmailValid = false;
  bool _isPasswordValid = false;
  
  // Focus nodes for better UX
  final FocusNode _emailFocusNode = FocusNode();
  final FocusNode _passwordFocusNode = FocusNode();
  final FocusNode _signInButtonFocusNode = FocusNode();
  
  // Animations
  late AnimationController _animationController;
  late AnimationController _errorAnimationController;
  late Animation<double> _fadeAnimation;
  late Animation<Offset> _slideAnimation;
  late Animation<double> _errorShakeAnimation;

  @override
  void initState() {
    super.initState();
    
    // Initialize accessibility service
    _accessibilityService.initialize().then((_) {
      _accessibilityService.announceNavigation(
        'Login Screen',
        description: 'Sign in to MITA financial app',
      );
    });
    
    _animationController = AnimationController(
      duration: _accessibilityService.getAnimationDuration(
        const Duration(milliseconds: 800),
      ),
      vsync: this,
    );
    _errorAnimationController = AnimationController(
      duration: _accessibilityService.getAnimationDuration(
        const Duration(milliseconds: 600),
      ),
      vsync: this,
    );
    
    _fadeAnimation = Tween<double>(begin: 0.0, end: 1.0).animate(
      CurvedAnimation(parent: _animationController, curve: Curves.easeInOut),
    );
    _slideAnimation = Tween<Offset>(
      begin: const Offset(0, 0.3),
      end: Offset.zero,
    ).animate(CurvedAnimation(parent: _animationController, curve: Curves.easeOutCubic));
    _errorShakeAnimation = Tween<double>(begin: 0, end: 1).animate(
      CurvedAnimation(parent: _errorAnimationController, curve: Curves.elasticOut),
    );
    
    // Add listeners for real-time validation
    _emailController.addListener(_validateEmail);
    _passwordController.addListener(_validatePassword);
    
    _animationController.forward();
  }
  
  @override
  void dispose() {
    _animationController.dispose();
    _errorAnimationController.dispose();
    _emailController.dispose();
    _passwordController.dispose();
    _emailFocusNode.dispose();
    _passwordFocusNode.dispose();
    _signInButtonFocusNode.dispose();
    _slowConnectionTimer?.cancel();
    super.dispose();
  }
  
  void _validateEmail() {
    final email = _emailController.text;
    final isValid = email.isNotEmpty && email.contains('@') && email.contains('.');
    if (_isEmailValid != isValid) {
      setState(() {
        _isEmailValid = isValid;
      });
    }
  }
  
  void _validatePassword() {
    final password = _passwordController.text;
    final validation = PasswordValidationService.validatePassword(password);
    final isValid = validation.isValid && password.isNotEmpty;
    if (_isPasswordValid != isValid) {
      setState(() {
        _isPasswordValid = isValid;
      });
    }
  }
  
  void _showError(String message) {
    _errorAnimationController.forward().then((_) {
      _errorAnimationController.reverse();
    });
    
    // Provide haptic feedback for errors
    HapticFeedback.vibrate();
    
    // Announce error to screen readers
    _accessibilityService.announceToScreenReader(
      'Login error: $message',
      financialContext: 'Authentication Error',
      isImportant: true,
    );
    
    // Show snackbar with retry option
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Semantics(
          liveRegion: true,
          label: 'Error message: $message',
          child: Text(message),
        ),
        action: SnackBarAction(
          label: AppLocalizations.of(context).dismiss,
          onPressed: () {
            ScaffoldMessenger.of(context).hideCurrentSnackBar();
            _accessibilityService.announceToScreenReader('Error message dismissed');
          },
        ),
        behavior: SnackBarBehavior.floating,
        margin: const EdgeInsets.all(16),
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
            'The login request is taking longer than expected. This might be due to server load or network conditions.\n\nWe\'ve increased the timeout limit. Would you like to try again?',
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
                // Retry the login with the same credentials
                _handleEmailLogin();
              },
              child: const Text('Try Again'),
            ),
          ],
        );
      },
    );
  }

  Future<void> _handleGoogleSignIn() async {
    if (isLoading) return;
    
    // Provide haptic feedback
    HapticFeedback.selectionClick();
    final l10n = AppLocalizations.of(context);

    // Set loading state immediately and start slow connection detection
    setState(() {
      _loading = true;
      _slowConnectionDetected = false;
    });
    
    // Detect slow connection after 15 seconds
    _slowConnectionTimer = Timer(const Duration(seconds: 15), () {
      if (_loading && mounted) {
        setState(() {
          _slowConnectionDetected = true;
        });
        _accessibilityService.announceToScreenReader(
          'Google sign-in is taking longer than usual. Please wait while we connect to the server.',
          isImportant: true,
        );
      }
    });

    try {
      if (kDebugMode) dev.log('Starting Google sign-in process', name: 'LoginScreen');
      
      final googleUser = await GoogleSignIn().signIn();
        
      if (googleUser == null) {
        _slowConnectionTimer?.cancel();
        setState(() {
          _loading = false;
          _slowConnectionDetected = false;
        });
        if (kDebugMode) dev.log('Google sign-in cancelled by user', name: 'LoginScreen');
        return;
      }

      if (kDebugMode) dev.log('Google user obtained, getting authentication', name: 'LoginScreen');
      final googleAuth = await googleUser.authentication;
      final idToken = googleAuth.idToken;

      if (idToken == null) {
        _slowConnectionTimer?.cancel();
        setState(() {
          _loading = false;
          _slowConnectionDetected = false;
        });
        throw AuthenticationException('Missing Google authentication token');
      }

      if (kDebugMode) dev.log('Google ID token obtained, calling backend', name: 'LoginScreen');
      final response = await _api.loginWithGoogle(idToken);
        
      if (kDebugMode) dev.log('Google login API response received: ${response.statusCode}', name: 'LoginScreen');
      if (kDebugMode) dev.log('Google login response data keys: ${response.data?.keys?.toList()}', name: 'LoginScreen');

      if (response.statusCode != 200) {
        throw AuthenticationException('Google login failed with status: ${response.statusCode}');
      }

      // Enhanced token extraction with multiple fallback patterns (same as email login)
      String? accessToken;
      String? refreshToken;
      
      final responseData = response.data;
      if (responseData is Map<String, dynamic>) {
        // Pattern 1: Direct access
        accessToken = responseData['access_token'];
        refreshToken = responseData['refresh_token'];
        
        // Pattern 2: Nested in 'data' object
        if (accessToken == null && responseData['data'] != null) {
          final data = responseData['data'] as Map<String, dynamic>?;
          accessToken = data?['access_token'];
          refreshToken = data?['refresh_token'];
        }
        
        // Pattern 3: Different key names
        if (accessToken == null) {
          accessToken = responseData['accessToken'] ?? responseData['access_token'] ?? responseData['token'];
          refreshToken = responseData['refreshToken'] ?? responseData['refresh_token'];
        }
        
        if (kDebugMode) dev.log('Google login extracted tokens - Access: ${accessToken != null ? "YES" : "NO"}, Refresh: ${refreshToken != null ? "YES" : "NO"}', name: 'LoginScreen');
      }

      if (accessToken == null) {
        if (kDebugMode) dev.log('No access token found in Google login response: $responseData', name: 'LoginScreen');
        throw AuthenticationException('Google login successful but no access token received');
      }

      // ALWAYS save tokens - they're required for API calls
      if (kDebugMode) dev.log('Saving Google login tokens to storage', name: 'LoginScreen');
      await _api.saveTokens(accessToken, refreshToken ?? '');

      // Verify token storage
      final storedToken = await _api.getToken();
      if (kDebugMode) dev.log('Google login token storage verification: ${storedToken != null ? "SUCCESS" : "FAILED"}', name: 'LoginScreen');

      if (!mounted) {
        if (kDebugMode) dev.log('Widget unmounted during Google login process', name: 'LoginScreen');
        return;
      }

      // SECURITY: Initialize push tokens AFTER successful authentication
      try {
        await SecurePushTokenManager.instance.initializePostAuthentication();
      } catch (e) {
        if (kDebugMode) dev.log('Google login push token initialization failed: $e', name: 'LoginScreen');
        AppErrorHandler.reportError(
          e,
          severity: ErrorSeverity.low,
          category: ErrorCategory.system,
          context: {'operation': 'push_token_init_google'},
        );
      }

      // Set authentication state using UserProvider
      if (kDebugMode) dev.log('Setting authentication state in UserProvider', name: 'LoginScreen');
      final userProvider = context.read<UserProvider>();
      userProvider.setAuthenticated();
      await userProvider.initialize();

      // Check if user has completed onboarding
      if (kDebugMode) dev.log('Checking onboarding status after Google login', name: 'LoginScreen');
      final hasOnboarded = userProvider.hasCompletedOnboarding;
      
      if (!mounted) {
        if (kDebugMode) dev.log('Widget unmounted during Google login onboarding check', name: 'LoginScreen');
        return;
      }

      _slowConnectionTimer?.cancel();
      setState(() {
        _loading = false;
        _slowConnectionDetected = false;
      });
        
      if (kDebugMode) dev.log('Google login successful, navigating to ${hasOnboarded ? "main" : "onboarding"}', name: 'LoginScreen');
      
      // Force navigation with explicit error handling
      try {
        if (hasOnboarded) {
          _accessibilityService.announceToScreenReader(
            'Google sign-in successful. Navigating to dashboard.',
            isImportant: true,
          );
          await Navigator.pushReplacementNamed(context, '/main');
        } else {
          _accessibilityService.announceToScreenReader(
            'Google sign-in successful. Navigating to onboarding.',
            isImportant: true,
          );
          await Navigator.pushReplacementNamed(context, '/onboarding_location');
        }
        if (kDebugMode) dev.log('Google login navigation completed successfully', name: 'LoginScreen');
      } catch (navigationError) {
        if (kDebugMode) dev.log('Google login navigation failed: $navigationError', name: 'LoginScreen');
        
        // Fallback navigation mechanism for Google login
        try {
          if (kDebugMode) dev.log('Attempting fallback navigation for Google login', name: 'LoginScreen');
          await Future.delayed(const Duration(milliseconds: 100));
          
          if (mounted) {
            if (hasOnboarded) {
              Navigator.of(context).pushNamedAndRemoveUntil('/main', (route) => false);
            } else {
              Navigator.of(context).pushNamedAndRemoveUntil('/onboarding_location', (route) => false);
            }
            if (kDebugMode) dev.log('Google login fallback navigation successful', name: 'LoginScreen');
          }
        } catch (fallbackError) {
          if (kDebugMode) dev.log('Google login fallback navigation also failed: $fallbackError', name: 'LoginScreen');
          // Show manual navigation instruction
          if (mounted) {
            showDialog(
              context: context,
              builder: (context) => AlertDialog(
                title: const Text('Google Sign-In Successful'),
                content: const Text(
                  'You have successfully signed in with Google, but there was a navigation issue. '
                  'Please restart the app to continue.',
                ),
                actions: [
                  TextButton(
                    onPressed: () => Navigator.of(context).pop(),
                    child: const Text('OK'),
                  ),
                ],
              ),
            );
          }
        }
      }
      
    } catch (e, stackTrace) {
      if (kDebugMode) dev.log('Google sign-in process failed: $e', name: 'LoginScreen', error: e);
      
      _slowConnectionTimer?.cancel();
      setState(() {
        _loading = false;
        _slowConnectionDetected = false;
      });
      
      if (mounted) {
        String errorMsg = 'Google sign-in failed. Please try again or use email login.';
        
        if (e.toString().contains('cancelled')) {
          errorMsg = 'Sign-in was cancelled. Please try again when ready.';
        } else if (e is DioException) {
          final statusCode = e.response?.statusCode;
          if (statusCode != null) {
            errorMsg = 'Google sign-in failed (${statusCode}). Please try again.';
          }
        }
            
        showEnhancedErrorDialog(
          'Google Sign-In Failed',
          errorMsg,
          onRetry: _handleGoogleSignIn,
          canRetry: !errorMsg.contains('cancelled'),
          additionalContext: {
            'provider': 'google',
            'error_type': e.runtimeType.toString(),
            'status_code': e is DioException ? e.response?.statusCode : null,
          },
        );
      }
    }
  }

  Future<void> _handleEmailLogin() async {
    if (isLoading) return;
    
    final l10n = AppLocalizations.of(context);
    
    // Enhanced form validation using FormErrorHandler
    FormErrorHandler.clearAllErrors();
    
    final emailError = FormErrorHandler.validateEmail(_emailController.text);
    final passwordError = FormErrorHandler.validatePassword(_passwordController.text);
    
    if (emailError != null || passwordError != null) {
      List<String> errors = [];
      if (emailError != null) errors.add(emailError);
      if (passwordError != null) errors.add(passwordError);
      
      _accessibilityService.announceFormErrors(errors);
      return;
    }
    
    // Provide haptic feedback
    HapticFeedback.selectionClick();

    // Set loading state immediately and start slow connection detection
    setState(() {
      _loading = true;
      _slowConnectionDetected = false;
    });
    
    // Detect slow connection after 15 seconds
    _slowConnectionTimer = Timer(const Duration(seconds: 15), () {
      if (_loading && mounted) {
        setState(() {
          _slowConnectionDetected = true;
        });
        _accessibilityService.announceToScreenReader(
          'Login is taking longer than usual. The server may be under heavy load. Please wait.',
          isImportant: true,
        );
      }
    });

    try {
      if (kDebugMode) dev.log('Starting login process for ${_emailController.text.substring(0, 3)}***', name: 'LoginScreen');
      
      final response = await _api.reliableLogin(
        _emailController.text.trim(),
        _passwordController.text,
      );

      if (kDebugMode) dev.log('Login API response received: ${response.statusCode}', name: 'LoginScreen');
      if (kDebugMode) dev.log('Login response data keys: ${response.data?.keys?.toList()}', name: 'LoginScreen');

      if (response.statusCode != 200) {
        throw AuthenticationException('Login failed with status: ${response.statusCode}');
      }

      // Enhanced token extraction with multiple fallback patterns
      String? accessToken;
      String? refreshToken;
      
      // Try different response data structures
      final responseData = response.data;
      if (responseData is Map<String, dynamic>) {
        // Pattern 1: Direct access
        accessToken = responseData['access_token'];
        refreshToken = responseData['refresh_token'];
        
        // Pattern 2: Nested in 'data' object
        if (accessToken == null && responseData['data'] != null) {
          final data = responseData['data'] as Map<String, dynamic>?;
          accessToken = data?['access_token'];
          refreshToken = data?['refresh_token'];
        }
        
        // Pattern 3: Different key names
        if (accessToken == null) {
          accessToken = responseData['accessToken'] ?? responseData['access_token'] ?? responseData['token'];
          refreshToken = responseData['refreshToken'] ?? responseData['refresh_token'];
        }
        
        if (kDebugMode) dev.log('Extracted tokens - Access: ${accessToken != null ? "YES" : "NO"}, Refresh: ${refreshToken != null ? "YES" : "NO"}', name: 'LoginScreen');
      }

      if (accessToken == null) {
        if (kDebugMode) dev.log('No access token found in response: $responseData', name: 'LoginScreen');
        throw AuthenticationException('Login successful but no access token received');
      }

      // ALWAYS save tokens - they're required for API calls
      if (kDebugMode) dev.log('Saving tokens to storage', name: 'LoginScreen');
      await _api.saveTokens(accessToken, refreshToken ?? '');

      // Verify token storage
      final storedToken = await _api.getToken();
      if (kDebugMode) dev.log('Token storage verification: ${storedToken != null ? "SUCCESS" : "FAILED"}', name: 'LoginScreen');

      if (!mounted) {
        if (kDebugMode) dev.log('Widget unmounted during login process', name: 'LoginScreen');
        return;
      }

      // SECURITY: Initialize push tokens AFTER successful authentication
      try {
        await SecurePushTokenManager.instance.initializePostAuthentication();
      } catch (e) {
        // Log but don't block login for push token issues
        if (kDebugMode) dev.log('Push token initialization failed: $e', name: 'LoginScreen');
        AppErrorHandler.reportError(
          e,
          severity: ErrorSeverity.low,
          category: ErrorCategory.system,
          context: {'operation': 'push_token_init'},
        );
      }

      // Set authentication state using UserProvider
      if (kDebugMode) dev.log('Setting authentication state in UserProvider', name: 'LoginScreen');
      final userProvider = context.read<UserProvider>();
      userProvider.setAuthenticated();
      await userProvider.initialize();

      // Check if user has completed onboarding
      if (kDebugMode) dev.log('Checking onboarding status', name: 'LoginScreen');
      final hasOnboarded = userProvider.hasCompletedOnboarding;
      
      if (!mounted) {
        if (kDebugMode) dev.log('Widget unmounted during onboarding check', name: 'LoginScreen');
        return;
      }

      _slowConnectionTimer?.cancel();
      setState(() {
        _loading = false;
        _slowConnectionDetected = false;
      });
        
      if (kDebugMode) dev.log('Login successful, navigating to ${hasOnboarded ? "main" : "onboarding"}', name: 'LoginScreen');
      
      // Force navigation with explicit error handling
      try {
        if (hasOnboarded) {
          _accessibilityService.announceToScreenReader(
            'Login successful. Navigating to dashboard.',
            isImportant: true,
          );
          await Navigator.pushReplacementNamed(context, '/main');
        } else {
          _accessibilityService.announceToScreenReader(
            'Login successful. Navigating to onboarding.',
            isImportant: true,
          );
          await Navigator.pushReplacementNamed(context, '/onboarding_location');
        }
        if (kDebugMode) dev.log('Navigation completed successfully', name: 'LoginScreen');
      } catch (navigationError) {
        if (kDebugMode) dev.log('Navigation failed: $navigationError', name: 'LoginScreen');
        
        // Fallback navigation mechanism
        try {
          if (kDebugMode) dev.log('Attempting fallback navigation', name: 'LoginScreen');
          await Future.delayed(const Duration(milliseconds: 100));
          
          if (mounted) {
            if (hasOnboarded) {
              Navigator.of(context).pushNamedAndRemoveUntil('/main', (route) => false);
            } else {
              Navigator.of(context).pushNamedAndRemoveUntil('/onboarding_location', (route) => false);
            }
            if (kDebugMode) dev.log('Fallback navigation successful', name: 'LoginScreen');
          }
        } catch (fallbackError) {
          if (kDebugMode) dev.log('Fallback navigation also failed: $fallbackError', name: 'LoginScreen');
          // Show manual navigation instruction
          if (mounted) {
            showDialog(
              context: context,
              builder: (context) => AlertDialog(
                title: const Text('Login Successful'),
                content: const Text(
                  'You have successfully logged in, but there was a navigation issue. '
                  'Please restart the app to continue.',
                ),
                actions: [
                  TextButton(
                    onPressed: () => Navigator.of(context).pop(),
                    child: const Text('OK'),
                  ),
                ],
              ),
            );
          }
        }
      }
      
    } catch (e, stackTrace) {
      if (kDebugMode) dev.log('Login process failed: $e', name: 'LoginScreen', error: e);
      
      _slowConnectionTimer?.cancel();
      setState(() {
        _loading = false;
        _slowConnectionDetected = false;
      });
      
      if (mounted) {
        String errorMsg = 'Unable to sign in. Please check your credentials and try again.';
        
        if (e is DioException) {
          final statusCode = e.response?.statusCode;
          if (statusCode == 401) {
            errorMsg = 'Invalid email or password. Please try again.';
          } else if (statusCode == 422) {
            errorMsg = 'Invalid credentials format. Please check your input.';
          } else if (statusCode == 429) {
            errorMsg = 'Too many login attempts. Please try again in a few minutes.';
          } else if (statusCode != null) {
            errorMsg = 'Login failed (${statusCode}). Please try again.';
          }
        } else if (e.toString().contains('timeout') || e.toString().contains('TimeoutException')) {
          errorMsg = 'Login request timed out. Please check your connection and try again.';
        }
        
        showEnhancedErrorDialog(
          'Login Failed',
          errorMsg,
          onRetry: _handleEmailLogin,
          canRetry: true,
          additionalContext: {
            'email': _emailController.text,
            'error_type': e.runtimeType.toString(),
            'status_code': e is DioException ? e.response?.statusCode : null,
          },
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;
    final l10n = AppLocalizations.of(context);
    
    return Scaffold(
      backgroundColor: colorScheme.surface,
      // Add debug FAB for auth testing in debug mode only
      floatingActionButton: kDebugMode ? FloatingActionButton.small(
        onPressed: () {
          Navigator.pushNamed(context, '/auth-test');
        },
        backgroundColor: colorScheme.secondary,
        child: Icon(
          Icons.bug_report,
          color: colorScheme.onSecondary,
        ),
        tooltip: 'Auth Test Screen',
      ) : null,
      body: SafeArea(
        child: FadeTransition(
          opacity: _fadeAnimation,
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: SlideTransition(
              position: _slideAnimation,
              child: Center(
                child: ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: 400),
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      const SizedBox(height: 60),
                      
                      // Compact app logo and welcome header
                      Semantics(
                        header: true,
                        label: 'MITA Login. Welcome back. Sign in to continue managing your finances',
                        child: Column(
                          children: [
                            // Compact logo container
                            Semantics(
                              label: 'MITA app logo. Financial wallet icon',
                              child: Container(
                                padding: const EdgeInsets.all(16),
                                decoration: BoxDecoration(
                                  color: colorScheme.primaryContainer,
                                  borderRadius: BorderRadius.circular(20),
                                ),
                                child: Icon(
                                  Icons.account_balance_wallet_rounded,
                                  size: 32,
                                  color: colorScheme.onPrimaryContainer,
                                ),
                              ),
                            ),
                            const SizedBox(height: 16),
                            Semantics(
                              header: true,
                              child: Text(
                                l10n.welcomeBack,
                                style: theme.textTheme.headlineMedium?.copyWith(
                                  fontWeight: FontWeight.w700,
                                  color: colorScheme.onSurface,
                                ),
                              ),
                            ),
                            const SizedBox(height: 4),
                            Text(
                              l10n.signInToContinue,
                              textAlign: TextAlign.center,
                              style: theme.textTheme.bodyMedium?.copyWith(
                                color: colorScheme.onSurface.withValues(alpha: 0.7),
                              ),
                            ),
                          ],
                        ),
                      ),
                      
                      const SizedBox(height: 32),
                      
                      // Login form
                      AnimatedBuilder(
                        animation: _errorShakeAnimation,
                        builder: (context, child) {
                          return Transform.translate(
                            offset: Offset(
                              _errorShakeAnimation.value * 10.0 * (0.5 - _errorShakeAnimation.value).abs(),
                              0,
                            ),
                            child: child,
                          );
                        },
                        child: MitaTheme.createElevatedCard(
                          elevation: 1,
                          padding: const EdgeInsets.all(24),
                          child: Form(
                            key: _formKey,
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.stretch,
                              children: [
                                // Email field with validation
                                Semantics(
                                  label: _accessibilityService.createTextFieldSemanticLabel(
                                    label: 'Email address',
                                    isRequired: true,
                                    helperText: 'Enter your email to sign in to MITA',
                                  ),
                                  child: TextFormField(
                                    controller: _emailController,
                                    focusNode: _emailFocusNode,
                                    keyboardType: TextInputType.emailAddress,
                                    textInputAction: TextInputAction.next,
                                    decoration: InputDecoration(
                                      labelText: l10n.emailAddress,
                                      hintText: l10n.enterYourEmail,
                                      prefixIcon: Semantics(
                                        label: 'Email icon',
                                        child: Icon(
                                          Icons.email_rounded,
                                          color: _isEmailValid 
                                            ? colorScheme.primary 
                                            : colorScheme.onSurface.withValues(alpha: 0.6),
                                        ),
                                      ),
                                      suffixIcon: _isEmailValid
                                        ? Semantics(
                                            label: 'Valid email address entered',
                                            child: Icon(
                                              Icons.check_circle,
                                              color: MitaTheme.statusColors['success'],
                                            ),
                                          )
                                        : null,
                                    ),
                                    validator: (value) {
                                      if (value == null || value.isEmpty) {
                                        return l10n.pleaseEnterEmail;
                                      }
                                      if (!value.contains('@') || !value.contains('.')) {
                                        return l10n.pleaseEnterValidEmail;
                                      }
                                      return null;
                                    },
                                    onFieldSubmitted: (_) {
                                      _passwordFocusNode.requestFocus();
                                    },
                                  ),
                                ).withMinimumTouchTarget(),
                                
                                const SizedBox(height: 20),
                                
                                // Password field with show/hide toggle
                                Semantics(
                                  label: _accessibilityService.createTextFieldSemanticLabel(
                                    label: 'Password',
                                    isRequired: true,
                                    helperText: 'Enter your password to sign in',
                                  ),
                                  child: TextFormField(
                                    controller: _passwordController,
                                    focusNode: _passwordFocusNode,
                                    obscureText: _obscurePassword,
                                    textInputAction: TextInputAction.done,
                                    decoration: InputDecoration(
                                      labelText: l10n.password,
                                      hintText: l10n.enterYourPassword,
                                      prefixIcon: Semantics(
                                        label: 'Password icon',
                                        child: Icon(
                                          Icons.lock_rounded,
                                          color: _isPasswordValid 
                                            ? colorScheme.primary 
                                            : colorScheme.onSurface.withValues(alpha: 0.6),
                                        ),
                                      ),
                                      suffixIcon: Row(
                                        mainAxisSize: MainAxisSize.min,
                                        children: [
                                          if (_isPasswordValid)
                                            Semantics(
                                              label: 'Valid password entered',
                                              child: Icon(
                                                Icons.check_circle,
                                                color: MitaTheme.statusColors['success'],
                                              ),
                                            ),
                                          Semantics(
                                            label: _obscurePassword 
                                              ? l10n.showPassword 
                                              : l10n.hidePassword,
                                            button: true,
                                            child: IconButton(
                                              icon: Icon(
                                                _obscurePassword 
                                                  ? Icons.visibility_rounded 
                                                  : Icons.visibility_off_rounded,
                                              ),
                                              onPressed: () {
                                                setState(() {
                                                  _obscurePassword = !_obscurePassword;
                                                });
                                                HapticFeedback.selectionClick();
                                                _accessibilityService.announceToScreenReader(
                                                  _obscurePassword 
                                                    ? l10n.passwordHidden 
                                                    : l10n.passwordShown,
                                                );
                                              },
                                            ).withMinimumTouchTarget(),
                                          ),
                                        ],
                                      ),
                                    ),
                                    validator: (value) {
                                      if (value == null || value.isEmpty) {
                                        return l10n.pleaseEnterPassword;
                                      }
                                      
                                      final validation = PasswordValidationService.validatePassword(value);
                                      if (!validation.isValid && validation.issues.isNotEmpty) {
                                        // Return first critical issue for login screen
                                        return validation.issues.first;
                                      }
                                      
                                      return null;
                                    },
                                    onFieldSubmitted: (_) {
                                      if (_formKey.currentState!.validate()) {
                                        _handleEmailLogin();
                                      }
                                    },
                                  ),
                                ).withMinimumTouchTarget(),
                                
                                const SizedBox(height: 20),
                                
                                // Remember me and forgot password
                                Row(
                                  children: [
                                    Expanded(
                                      child: Row(
                                        children: [
                                          Semantics(
                                            label: _rememberMe 
                                              ? 'Remember me, checked checkbox' 
                                              : 'Remember me, unchecked checkbox',
                                            child: Transform.scale(
                                              scale: 1.1,
                                              child: Checkbox(
                                                value: _rememberMe,
                                                onChanged: (value) {
                                                  setState(() {
                                                    _rememberMe = value ?? true;
                                                  });
                                                  HapticFeedback.selectionClick();
                                                  _accessibilityService.announceToScreenReader(
                                                    _rememberMe 
                                                      ? l10n.rememberMeEnabled 
                                                      : l10n.rememberMeDisabled,
                                                  );
                                                },
                                              ),
                                            ).withMinimumTouchTarget(),
                                          ),
                                          const SizedBox(width: 8),
                                          Expanded(
                                            child: GestureDetector(
                                              onTap: () {
                                                setState(() {
                                                  _rememberMe = !_rememberMe;
                                                });
                                                HapticFeedback.selectionClick();
                                                _accessibilityService.announceToScreenReader(
                                                  _rememberMe 
                                                    ? l10n.rememberMeEnabled 
                                                    : l10n.rememberMeDisabled,
                                                );
                                              },
                                              child: Semantics(
                                                label: 'Remember me checkbox label. Tap to toggle',
                                                button: true,
                                                child: Text(
                                                  l10n.rememberMe,
                                                  style: theme.textTheme.bodyMedium?.copyWith(
                                                    fontWeight: FontWeight.w500,
                                                  ),
                                                ),
                                              ),
                                            ),
                                          ),
                                        ],
                                      ),
                                    ),
                                    Semantics(
                                      label: 'Forgot password. Navigate to password reset',
                                      button: true,
                                      child: TextButton(
                                        onPressed: () {
                                          Navigator.of(context).pushNamed('/forgot-password');
                                          _accessibilityService.announceNavigation(
                                            'Forgot Password',
                                            description: 'Reset your password screen',
                                          );
                                        },
                                        child: Text(
                                          l10n.forgot,
                                          style: theme.textTheme.bodyMedium?.copyWith(
                                            color: colorScheme.primary,
                                            fontWeight: FontWeight.w600,
                                          ),
                                        ),
                                      ).withMinimumTouchTarget(),
                                    ),
                                  ],
                                ),
                                
                                const SizedBox(height: 24),
                                
                                // Sign in button
                                AnimatedContainer(
                                  duration: _accessibilityService.getAnimationDuration(
                                    const Duration(milliseconds: 200),
                                  ),
                                  child: _loading 
                                    ? Semantics(
                                        label: _slowConnectionDetected 
                                          ? 'Signing in to MITA. Connection is slow, please wait'
                                          : 'Signing in to MITA. Please wait',
                                        liveRegion: true,
                                        child: Center(
                                          child: Column(
                                            mainAxisSize: MainAxisSize.min,
                                            children: [
                                              MitaTheme.createLoadingIndicator(
                                                message: l10n.signingIn,
                                              ),
                                              if (_slowConnectionDetected) ...[
                                                const SizedBox(height: 16),
                                                Container(
                                                  padding: const EdgeInsets.all(12),
                                                  decoration: BoxDecoration(
                                                    color: colorScheme.surfaceContainerHighest,
                                                    borderRadius: BorderRadius.circular(8),
                                                  ),
                                                  child: Row(
                                                    mainAxisSize: MainAxisSize.min,
                                                    children: [
                                                      Icon(
                                                        Icons.info_outline,
                                                        size: 16,
                                                        color: colorScheme.primary,
                                                      ),
                                                      const SizedBox(width: 8),
                                                      Flexible(
                                                        child: Text(
                                                          'Server is responding slowly. Please wait...',
                                                          style: theme.textTheme.bodySmall?.copyWith(
                                                            color: colorScheme.onSurface,
                                                          ),
                                                          textAlign: TextAlign.center,
                                                        ),
                                                      ),
                                                    ],
                                                  ),
                                                ),
                                              ],
                                            ],
                                          ),
                                        ),
                                      )
                                    : Semantics(
                                        label: _accessibilityService.createButtonSemanticLabel(
                                          action: 'Sign in to MITA',
                                          context: (_isEmailValid && _isPasswordValid) 
                                            ? 'Ready to sign in with email and password'
                                            : 'Enter valid email and password to enable',
                                          isDisabled: !(_isEmailValid && _isPasswordValid),
                                        ),
                                        button: true,
                                        child: FilledButton(
                                          focusNode: _signInButtonFocusNode,
                                          onPressed: (_isEmailValid && _isPasswordValid) 
                                            ? _handleEmailLogin 
                                            : null,
                                          style: FilledButton.styleFrom(
                                            padding: const EdgeInsets.symmetric(vertical: 20),
                                            textStyle: theme.textTheme.titleLarge?.copyWith(
                                              fontWeight: FontWeight.w700,
                                            ),
                                          ),
                                          child: Row(
                                            mainAxisAlignment: MainAxisAlignment.center,
                                            children: [
                                              Text(l10n.signIn),
                                              const SizedBox(width: 8),
                                              const Icon(
                                                Icons.arrow_forward_rounded,
                                                size: 20,
                                              ),
                                            ],
                                          ),
                                        ).withMinimumTouchTarget(),
                                      ),
                                ),
                                
                                const SizedBox(height: 16),
                                
                                // Divider
                                Row(
                                  children: [
                                    Expanded(
                                      child: Divider(
                                        color: colorScheme.outline.withValues(alpha: 0.5),
                                      ),
                                    ),
                                    Padding(
                                      padding: const EdgeInsets.symmetric(horizontal: 16),
                                      child: Text(
                                        l10n.or,
                                        style: theme.textTheme.bodySmall?.copyWith(
                                          color: colorScheme.onSurface.withValues(alpha: 0.6),
                                        ),
                                      ),
                                    ),
                                    Expanded(
                                      child: Divider(
                                        color: colorScheme.outline.withValues(alpha: 0.5),
                                      ),
                                    ),
                                  ],
                                ),
                                
                                const SizedBox(height: 16),
                                
                                // Google sign-in button
                                Semantics(
                                  label: _accessibilityService.createButtonSemanticLabel(
                                    action: 'Continue with Google',
                                    context: 'Alternative sign in method using your Google account',
                                    isDisabled: _loading,
                                  ),
                                  button: true,
                                  child: OutlinedButton.icon(
                                    onPressed: _loading ? null : _handleGoogleSignIn,
                                    icon: Semantics(
                                      label: 'Google logo',
                                      child: Container(
                                        padding: const EdgeInsets.all(2),
                                        decoration: BoxDecoration(
                                          color: Colors.white,
                                          borderRadius: BorderRadius.circular(4),
                                        ),
                                        child: Image.asset(
                                          'assets/logo/mitalogo.png',
                                          width: 20,
                                          height: 20,
                                          semanticLabel: 'Google logo',
                                          errorBuilder: (context, error, stackTrace) {
                                            return Icon(
                                              Icons.g_mobiledata,
                                              size: 20,
                                              color: colorScheme.primary,
                                            );
                                          },
                                        ),
                                      ),
                                    ),
                                    label: Text(l10n.continueWithGoogle),
                                    style: OutlinedButton.styleFrom(
                                      padding: const EdgeInsets.symmetric(vertical: 16),
                                      side: BorderSide(
                                        color: colorScheme.outline,
                                        width: 1,
                                      ),
                                      textStyle: theme.textTheme.titleMedium?.copyWith(
                                        fontWeight: FontWeight.w600,
                                      ),
                                    ),
                                  ).withMinimumTouchTarget(),
                                ),
                              ],
                            ),
                          ),
                        ),
                      ),
                      
                      const SizedBox(height: 24),
                      
                      // Sign up option
                      Semantics(
                        label: 'Don\'t have an account? Sign up for MITA',
                        child: Row(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            Text(
                              l10n.dontHaveAccountQuestion,
                              style: theme.textTheme.bodyMedium?.copyWith(
                                color: colorScheme.onSurface.withValues(alpha: 0.8),
                              ),
                            ),
                            Semantics(
                              label: 'Sign up for new MITA account',
                              button: true,
                              child: TextButton(
                                onPressed: () {
                                  Navigator.pushNamed(context, '/register');
                                  _accessibilityService.announceNavigation(
                                    'Registration',
                                    description: 'Create new MITA account',
                                  );
                                },
                                child: Text(
                                  l10n.signUp,
                                  style: theme.textTheme.bodyMedium?.copyWith(
                                    color: colorScheme.primary,
                                    fontWeight: FontWeight.w700,
                                  ),
                                ),
                              ).withMinimumTouchTarget(),
                            ),
                          ],
                        ),
                      ),
                      
                      const SizedBox(height: 40),
                    ],
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}