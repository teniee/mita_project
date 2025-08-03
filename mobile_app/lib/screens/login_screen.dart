import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:google_sign_in/google_sign_in.dart';
import '../services/api_service.dart';
import '../theme/mita_theme.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({Key? key}) : super(key: key);

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> with TickerProviderStateMixin {
  final ApiService _api = ApiService();
  bool _loading = false;
  String? _error;
  
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
    
    _animationController = AnimationController(
      duration: const Duration(milliseconds: 800),
      vsync: this,
    );
    _errorAnimationController = AnimationController(
      duration: const Duration(milliseconds: 600),
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
    final isValid = password.length >= 6;
    if (_isPasswordValid != isValid) {
      setState(() {
        _isPasswordValid = isValid;
      });
    }
  }
  
  void _showError(String message) {
    setState(() {
      _error = message;
    });
    _errorAnimationController.forward().then((_) {
      _errorAnimationController.reverse();
    });
    
    // Provide haptic feedback for errors
    HapticFeedback.vibrate();
    
    // Show snackbar with retry option
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message),
        action: SnackBarAction(
          label: 'Dismiss',
          onPressed: () {
            ScaffoldMessenger.of(context).hideCurrentSnackBar();
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
      _error = null;
    });
    
    // Provide haptic feedback
    HapticFeedback.selectionClick();

    try {
      final googleUser = await GoogleSignIn().signIn();
      if (googleUser == null) {
        setState(() {
          _loading = false;
          _error = 'Sign-in cancelled';
        });
        return;
      }

      final googleAuth = await googleUser.authentication;
      final idToken = googleAuth.idToken;

      if (idToken == null) {
        setState(() {
          _loading = false;
          _error = 'Missing Google ID token';
        });
        return;
      }

      final response = await _api.loginWithGoogle(idToken);
      final accessToken = response.data['access_token'];
      final refreshToken = response.data['refresh_token'];
      
      if (_rememberMe) {
        await _api.saveTokens(accessToken, refreshToken);
      }

      if (!mounted) return;
      
      // Check if user has completed onboarding
      final hasOnboarded = await _api.hasCompletedOnboarding();
      if (hasOnboarded) {
        Navigator.pushReplacementNamed(context, '/main');
      } else {
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
    if (_loading || !_formKey.currentState!.validate()) return;
    
    setState(() {
      _loading = true;
      _error = null;
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
      
      // Check if user has completed onboarding
      final hasOnboarded = await _api.hasCompletedOnboarding();
      if (hasOnboarded) {
        Navigator.pushReplacementNamed(context, '/main');
      } else {
        Navigator.pushReplacementNamed(context, '/onboarding_region');
      }
    } catch (e) {
      setState(() {
        _loading = false;
      });
      _showError('Login failed. Please check your credentials and try again.');
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;
    
    return Scaffold(
      backgroundColor: colorScheme.background,
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
                      MitaTheme.createElevatedCard(
                        elevation: 2,
                        padding: const EdgeInsets.all(32),
                        child: Column(
                          children: [
                            // Logo container
                            Container(
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
                            const SizedBox(height: 24),
                            Text(
                              'Welcome back',
                              style: theme.textTheme.displaySmall?.copyWith(
                                fontWeight: FontWeight.w700,
                                color: colorScheme.onSurface,
                              ),
                            ),
                            const SizedBox(height: 8),
                            Text(
                              'Sign in to continue managing your finances',
                              textAlign: TextAlign.center,
                              style: theme.textTheme.bodyLarge?.copyWith(
                                color: colorScheme.onSurface.withOpacity(0.8),
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
                                TextFormField(
                                  controller: _emailController,
                                  focusNode: _emailFocusNode,
                                  keyboardType: TextInputType.emailAddress,
                                  textInputAction: TextInputAction.next,
                                  decoration: InputDecoration(
                                    labelText: 'Email address',
                                    hintText: 'Enter your email',
                                    prefixIcon: Icon(
                                      Icons.email_rounded,
                                      color: _isEmailValid 
                                        ? colorScheme.primary 
                                        : colorScheme.onSurface.withOpacity(0.6),
                                    ),
                                    suffixIcon: _isEmailValid
                                      ? Icon(
                                          Icons.check_circle,
                                          color: MitaTheme.statusColors['success'],
                                        )
                                      : null,
                                  ),
                                  validator: (value) {
                                    if (value == null || value.isEmpty) {
                                      return 'Please enter your email';
                                    }
                                    if (!value.contains('@') || !value.contains('.')) {
                                      return 'Please enter a valid email';
                                    }
                                    return null;
                                  },
                                  onFieldSubmitted: (_) {
                                    _passwordFocusNode.requestFocus();
                                  },
                                ),
                                
                                const SizedBox(height: 20),
                                
                                // Password field with show/hide toggle
                                TextFormField(
                                  controller: _passwordController,
                                  focusNode: _passwordFocusNode,
                                  obscureText: _obscurePassword,
                                  textInputAction: TextInputAction.done,
                                  decoration: InputDecoration(
                                    labelText: 'Password',
                                    hintText: 'Enter your password',
                                    prefixIcon: Icon(
                                      Icons.lock_rounded,
                                      color: _isPasswordValid 
                                        ? colorScheme.primary 
                                        : colorScheme.onSurface.withOpacity(0.6),
                                    ),
                                    suffixIcon: Row(
                                      mainAxisSize: MainAxisSize.min,
                                      children: [
                                        if (_isPasswordValid)
                                          Icon(
                                            Icons.check_circle,
                                            color: MitaTheme.statusColors['success'],
                                          ),
                                        IconButton(
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
                                          },
                                        ),
                                      ],
                                    ),
                                  ),
                                  validator: (value) {
                                    if (value == null || value.isEmpty) {
                                      return 'Please enter your password';
                                    }
                                    if (value.length < 6) {
                                      return 'Password must be at least 6 characters';
                                    }
                                    return null;
                                  },
                                  onFieldSubmitted: (_) {
                                    if (_formKey.currentState!.validate()) {
                                      _handleEmailLogin();
                                    }
                                  },
                                ),
                                
                                const SizedBox(height: 20),
                                
                                // Remember me and forgot password
                                Row(
                                  children: [
                                    Expanded(
                                      child: Row(
                                        children: [
                                          Transform.scale(
                                            scale: 1.1,
                                            child: Checkbox(
                                              value: _rememberMe,
                                              onChanged: (value) {
                                                setState(() {
                                                  _rememberMe = value ?? true;
                                                });
                                                HapticFeedback.selectionClick();
                                              },
                                            ),
                                          ),
                                          const SizedBox(width: 8),
                                          Expanded(
                                            child: Text(
                                              'Remember me',
                                              style: theme.textTheme.bodyMedium?.copyWith(
                                                fontWeight: FontWeight.w500,
                                              ),
                                            ),
                                          ),
                                        ],
                                      ),
                                    ),
                                    TextButton(
                                      onPressed: () {
                                        // TODO: Implement forgot password
                                        ScaffoldMessenger.of(context).showSnackBar(
                                          const SnackBar(
                                            content: Text('Forgot password feature coming soon'),
                                            behavior: SnackBarBehavior.floating,
                                          ),
                                        );
                                      },
                                      child: Text(
                                        'Forgot?',
                                        style: theme.textTheme.bodyMedium?.copyWith(
                                          color: colorScheme.primary,
                                          fontWeight: FontWeight.w600,
                                        ),
                                      ),
                                    ),
                                  ],
                                ),
                                
                                const SizedBox(height: 24),
                                
                                // Sign in button
                                AnimatedContainer(
                                  duration: const Duration(milliseconds: 200),
                                  child: _loading 
                                    ? Center(
                                        child: MitaTheme.createLoadingIndicator(
                                          message: 'Signing in...',
                                        ),
                                      )
                                    : FilledButton(
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
                                            const Text('Sign In'),
                                            const SizedBox(width: 8),
                                            Icon(
                                              Icons.arrow_forward_rounded,
                                              size: 20,
                                            ),
                                          ],
                                        ),
                                      ),
                                ),
                                
                                const SizedBox(height: 16),
                                
                                // Divider
                                Row(
                                  children: [
                                    Expanded(
                                      child: Divider(
                                        color: colorScheme.outline.withOpacity(0.5),
                                      ),
                                    ),
                                    Padding(
                                      padding: const EdgeInsets.symmetric(horizontal: 16),
                                      child: Text(
                                        'or',
                                        style: theme.textTheme.bodySmall?.copyWith(
                                          color: colorScheme.onSurface.withOpacity(0.6),
                                        ),
                                      ),
                                    ),
                                    Expanded(
                                      child: Divider(
                                        color: colorScheme.outline.withOpacity(0.5),
                                      ),
                                    ),
                                  ],
                                ),
                                
                                const SizedBox(height: 16),
                                
                                // Google sign-in button
                                OutlinedButton.icon(
                                  onPressed: _loading ? null : _handleGoogleSignIn,
                                  icon: Container(
                                    padding: const EdgeInsets.all(2),
                                    decoration: BoxDecoration(
                                      color: Colors.white,
                                      borderRadius: BorderRadius.circular(4),
                                    ),
                                    child: Image.asset(
                                      'assets/logo/mitalogo.png',
                                      width: 20,
                                      height: 20,
                                      errorBuilder: (context, error, stackTrace) {
                                        return Icon(
                                          Icons.g_mobiledata,
                                          size: 20,
                                          color: colorScheme.primary,
                                        );
                                      },
                                    ),
                                  ),
                                  label: const Text('Continue with Google'),
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
                                ),
                              ],
                            ),
                          ),
                        ),
                      ),
                      
                      const SizedBox(height: 24),
                      
                      // Sign up option
                      Row(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Text(
                            'Don\'t have an account? ',
                            style: theme.textTheme.bodyMedium?.copyWith(
                              color: colorScheme.onSurface.withOpacity(0.8),
                            ),
                          ),
                          TextButton(
                            onPressed: () => Navigator.pushNamed(context, '/register'),
                            child: Text(
                              'Sign up',
                              style: theme.textTheme.bodyMedium?.copyWith(
                                color: colorScheme.primary,
                                fontWeight: FontWeight.w700,
                              ),
                            ),
                          ),
                        ],
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