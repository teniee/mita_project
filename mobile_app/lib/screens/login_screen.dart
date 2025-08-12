import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:google_sign_in/google_sign_in.dart';
import '../services/api_service.dart';
import '../services/secure_push_token_manager.dart';
import '../services/password_validation_service.dart';
import '../services/accessibility_service.dart';
import '../theme/mita_theme.dart';
import '../l10n/generated/app_localizations.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> with TickerProviderStateMixin {
  final ApiService _api = ApiService();
  final AccessibilityService _accessibilityService = AccessibilityService.instance;
  bool _loading = false;
  
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

  Future<void> _handleGoogleSignIn() async {
    if (_loading) return;
    
    setState(() {
      _loading = true;
    });
    
    // Provide haptic feedback
    HapticFeedback.selectionClick();

    final l10n = AppLocalizations.of(context);

    try {
      final googleUser = await GoogleSignIn().signIn();
      if (googleUser == null) {
        setState(() {
          _loading = false;
        });
        _showError(l10n.signInCancelled);
        return;
      }

      final googleAuth = await googleUser.authentication;
      final idToken = googleAuth.idToken;

      if (idToken == null) {
        setState(() {
          _loading = false;
        });
        _showError(l10n.missingGoogleToken);
        return;
      }

      final response = await _api.loginWithGoogle(idToken);
      final accessToken = response.data['access_token'];
      final refreshToken = response.data['refresh_token'];
      
      if (_rememberMe) {
        await _api.saveTokens(accessToken, refreshToken);
      }

      if (!mounted) return;
      
      // SECURITY: Initialize push tokens AFTER successful authentication
      try {
        await SecurePushTokenManager.instance.initializePostAuthentication();
      } catch (e) {
        // Log but don't block login for push token issues
        // Using proper logging instead of print for production
        if (kDebugMode) {
          debugPrint('Warning: Push token initialization failed: $e');
        }
      }
      
      // Check if user has completed onboarding
      final hasOnboarded = await _api.hasCompletedOnboarding();
      if (!mounted) return;
      if (hasOnboarded) {
        _accessibilityService.announceToScreenReader(
          'Google sign-in successful. Navigating to dashboard.',
          isImportant: true,
        );
        Navigator.pushReplacementNamed(context, '/main');
      } else {
        _accessibilityService.announceToScreenReader(
          'Google sign-in successful. Navigating to onboarding.',
          isImportant: true,
        );
        Navigator.pushReplacementNamed(context, '/onboarding_region');
      }
    } catch (e) {
      setState(() {
        _loading = false;
      });
      _showError('Google sign-in failed. Please try again.');
    }
  }

  Future<void> _handleEmailLogin() async {
    if (_loading) return;
    
    final l10n = AppLocalizations.of(context);
    
    if (!_formKey.currentState!.validate()) {
      // Collect validation errors for accessibility announcement
      List<String> errors = [];
      if (_emailController.text.isEmpty) {
        errors.add('Email is required');
      } else if (!_emailController.text.contains('@') || !_emailController.text.contains('.')) {
        errors.add('Email format is invalid');
      }
      if (_passwordController.text.isEmpty) {
        errors.add('Password is required');
      }
      
      if (errors.isNotEmpty) {
        _accessibilityService.announceFormErrors(errors);
      }
      return;
    }
    
    setState(() {
      _loading = true;
    });
    
    // Provide haptic feedback
    HapticFeedback.selectionClick();

    try {
      final response = await _api.login(
        _emailController.text,
        _passwordController.text,
      );
      final accessToken = response.data['access_token'];
      final refreshToken = response.data['refresh_token'];
      
      if (_rememberMe) {
        await _api.saveTokens(accessToken, refreshToken);
      }

      if (!mounted) return;
      
      // SECURITY: Initialize push tokens AFTER successful authentication
      try {
        await SecurePushTokenManager.instance.initializePostAuthentication();
      } catch (e) {
        // Log but don't block login for push token issues
        // Using proper logging instead of print for production
        if (kDebugMode) {
          debugPrint('Warning: Push token initialization failed: $e');
        }
      }
      
      // Check if user has completed onboarding
      final hasOnboarded = await _api.hasCompletedOnboarding();
      if (!mounted) return;
      if (hasOnboarded) {
        _accessibilityService.announceToScreenReader(
          'Login successful. Navigating to dashboard.',
          isImportant: true,
        );
        Navigator.pushReplacementNamed(context, '/main');
      } else {
        _accessibilityService.announceToScreenReader(
          'Login successful. Navigating to onboarding.',
          isImportant: true,
        );
        Navigator.pushReplacementNamed(context, '/onboarding_region');
      }
    } catch (e) {
      setState(() {
        _loading = false;
      });
      _showError(l10n.loginFailed);
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;
    final l10n = AppLocalizations.of(context);
    
    return Scaffold(
      backgroundColor: colorScheme.surface,
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
                      
                      // App logo and welcome header
                      Semantics(
                        header: true,
                        label: 'MITA Login. Welcome back. Sign in to continue managing your finances',
                        child: MitaTheme.createElevatedCard(
                          elevation: 2,
                          padding: const EdgeInsets.all(32),
                          child: Column(
                            children: [
                              // Logo container
                              Semantics(
                                label: 'MITA app logo. Financial wallet icon',
                                child: Container(
                                  padding: const EdgeInsets.all(20),
                                  decoration: BoxDecoration(
                                    color: colorScheme.primaryContainer,
                                    borderRadius: BorderRadius.circular(24),
                                  ),
                                  child: Icon(
                                    Icons.account_balance_wallet_rounded,
                                    size: 48,
                                    color: colorScheme.onPrimaryContainer,
                                  ),
                                ),
                              ),
                              const SizedBox(height: 24),
                              Semantics(
                                header: true,
                                child: Text(
                                  l10n.welcomeBack,
                                  style: theme.textTheme.displaySmall?.copyWith(
                                    fontWeight: FontWeight.w700,
                                    color: colorScheme.onSurface,
                                  ),
                                ),
                              ),
                              const SizedBox(height: 8),
                              Text(
                                l10n.signInToContinue,
                                textAlign: TextAlign.center,
                                style: theme.textTheme.bodyLarge?.copyWith(
                                  color: colorScheme.onSurface.withValues(alpha: 0.8),
                                ),
                              ),
                            ],
                          ),
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
                                        label: 'Signing in to MITA. Please wait',
                                        liveRegion: true,
                                        child: Center(
                                          child: MitaTheme.createLoadingIndicator(
                                            message: l10n.signingIn,
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