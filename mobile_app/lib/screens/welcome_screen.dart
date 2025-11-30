import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import '../theme/app_colors.dart';
import '../theme/app_typography.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';
import '../providers/settings_provider.dart';
import '../providers/user_provider.dart';
import '../services/api_service.dart';
import '../services/logging_service.dart';
import '../l10n/generated/app_localizations.dart';

/// Welcome screen with splash animation and auto-navigation
/// Provides a professional first impression with smooth Material 3 animations
///
/// State Management:
/// - Uses SettingsProvider for app settings initialization (theme, locale)
/// - Uses UserProvider for authentication state and user data
/// - Local setState is used only for transient UI state (animations, status text)
///
/// Provider Usage:
/// - context.read<T>() for one-time access in initialization methods
/// - No context.watch<T>() needed as this screen navigates away after initialization
class WelcomeScreen extends StatefulWidget {
  const WelcomeScreen({super.key});

  @override
  State<WelcomeScreen> createState() => _WelcomeScreenState();
}

class _WelcomeScreenState extends State<WelcomeScreen> with TickerProviderStateMixin {
  // Animation controllers for smooth transitions (local UI state)
  late AnimationController _logoController;
  late AnimationController _textController;
  late AnimationController _progressController;

  // Animations for coordinated entrance (local UI state)
  late Animation<double> _logoScale;
  late Animation<double> _logoOpacity;
  late Animation<Offset> _textSlide;
  late Animation<double> _textOpacity;
  late Animation<double> _progressValue;

  // Services
  final ApiService _api = ApiService();

  // Local UI state - kept as setState since these are transient splash screen states
  // that don't need to persist or be shared across the app
  String _statusText = 'Initializing...'; // Will be updated with localized text in initState
  bool _hasError = false;

  @override
  void initState() {
    super.initState();
    _initializeAnimations();

    // Set initial localized text and start sequence
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) {
        final l10n = AppLocalizations.of(context);
        setState(() => _statusText = l10n.initializing);
        _startWelcomeSequence();
      }
    });
  }

  void _initializeAnimations() {
    // Logo animation - scale and fade in
    _logoController = AnimationController(
      duration: const Duration(milliseconds: 1200),
      vsync: this,
    );

    _logoScale = Tween<double>(
      begin: 0.5,
      end: 1.0,
    ).animate(CurvedAnimation(
      parent: _logoController,
      curve: Curves.elasticOut,
    ));

    _logoOpacity = Tween<double>(
      begin: 0.0,
      end: 1.0,
    ).animate(CurvedAnimation(
      parent: _logoController,
      curve: const Interval(0.0, 0.6, curve: Curves.easeOut),
    ));

    // Text animation - slide up and fade in
    _textController = AnimationController(
      duration: const Duration(milliseconds: 800),
      vsync: this,
    );

    _textSlide = Tween<Offset>(
      begin: const Offset(0, 0.3),
      end: Offset.zero,
    ).animate(CurvedAnimation(
      parent: _textController,
      curve: Curves.easeOutCubic,
    ));

    _textOpacity = Tween<double>(
      begin: 0.0,
      end: 1.0,
    ).animate(CurvedAnimation(
      parent: _textController,
      curve: Curves.easeOut,
    ));

    // Progress animation for loading indication
    _progressController = AnimationController(
      duration: const Duration(milliseconds: 2000),
      vsync: this,
    );

    _progressValue = Tween<double>(
      begin: 0.0,
      end: 1.0,
    ).animate(CurvedAnimation(
      parent: _progressController,
      curve: Curves.easeInOut,
    ));
  }

  Future<void> _startWelcomeSequence() async {
    final l10n = AppLocalizations.of(context);

    try {
      // Start logo animation immediately
      _logoController.forward();

      // Start text animation after brief delay
      await Future.delayed(const Duration(milliseconds: 400));
      _textController.forward();

      // Start progress animation
      await Future.delayed(const Duration(milliseconds: 200));
      _progressController.forward();

      // Check authentication status
      await _checkAuthenticationStatus();
    } catch (e) {
      logError('Welcome screen initialization failed: $e', tag: 'WELCOME_SCREEN');

      setState(() {
        _hasError = true;
        _statusText = l10n.initializationFailed;
      });

      // Navigate to login after error delay
      await Future.delayed(const Duration(seconds: 2));
      if (mounted) {
        _navigateToLogin();
      }
    }
  }

  Future<void> _checkAuthenticationStatus() async {
    final l10n = AppLocalizations.of(context);
    // Use context.read for one-time access in methods (not reactive rebuilds)
    final userProvider = context.read<UserProvider>();
    final settingsProvider = context.read<SettingsProvider>();

    try {
      setState(() => _statusText = l10n.initializingMita);
      await Future.delayed(const Duration(milliseconds: 500));

      // Initialize SettingsProvider first for theme/locale preferences
      if (!settingsProvider.isInitialized) {
        await settingsProvider.initialize();
        logInfo('SettingsProvider initialized successfully', tag: 'WELCOME_SCREEN');
      }

      setState(() => _statusText = l10n.checkingAuthentication);
      await Future.delayed(const Duration(milliseconds: 300));

      // Check for existing token first
      final token = await _api.getToken();

      if (token == null) {
        // No token - new user, go to login
        logInfo('No authentication token found - redirecting to login', tag: 'WELCOME_SCREEN');
        setState(() => _statusText = l10n.welcomeToMita);
        await Future.delayed(const Duration(milliseconds: 800));
        if (mounted) _navigateToLogin();
        return;
      }

      // Initialize UserProvider for production-level data flow
      await userProvider.initialize();
      logInfo('UserProvider initialized successfully', tag: 'WELCOME_SCREEN');

      setState(() => _statusText = l10n.verifyingSession);
      await Future.delayed(const Duration(milliseconds: 300));

      // Check if user has completed onboarding using provider
      final hasOnboarded = userProvider.hasCompletedOnboarding;
      logInfo('Onboarding status from UserProvider: $hasOnboarded', tag: 'WELCOME_SCREEN');

      if (hasOnboarded) {
        setState(() => _statusText = l10n.loadingDashboard);
        await Future.delayed(const Duration(milliseconds: 500));

        setState(() => _statusText = l10n.welcomeBackExclamation);
        await Future.delayed(const Duration(milliseconds: 800));
        if (mounted) _navigateToMain();
      } else {
        setState(() => _statusText = l10n.continuingSetup);
        await Future.delayed(const Duration(milliseconds: 800));
        if (mounted) _navigateToOnboarding();
      }
    } catch (e) {
      logError('Authentication check failed: $e', tag: 'WELCOME_SCREEN');

      // Clear tokens and user data using provider
      await _api.clearTokens();
      await userProvider.logout();
      logInfo('User data cleared via UserProvider', tag: 'WELCOME_SCREEN');

      setState(() => _statusText = l10n.pleaseLoginToContinue);
      await Future.delayed(const Duration(milliseconds: 1000));
      if (mounted) _navigateToLogin();
    }
  }

  void _navigateToLogin() {
    HapticFeedback.lightImpact();
    Navigator.pushReplacementNamed(context, '/login');
  }

  void _navigateToMain() {
    HapticFeedback.lightImpact();
    Navigator.pushReplacementNamed(context, '/main');
  }

  void _navigateToOnboarding() {
    HapticFeedback.lightImpact();
    Navigator.pushReplacementNamed(context, '/onboarding_location');
  }

  @override
  void dispose() {
    _logoController.dispose();
    _textController.dispose();
    _progressController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final size = MediaQuery.of(context).size;
    final isLargeScreen = size.width > 600;

    return Scaffold(
      backgroundColor: theme.colorScheme.primary,
      // Add debug FAB for auth testing in debug mode only
      floatingActionButton: kDebugMode
          ? FloatingActionButton.small(
              onPressed: () {
                Navigator.pushNamed(context, '/auth-test');
              },
              backgroundColor: theme.colorScheme.secondary,
              child: Icon(
                Icons.bug_report,
                color: theme.colorScheme.onSecondary,
              ),
              tooltip: 'Auth Test Screen',
            )
          : null,
      body: SafeArea(
        child: Container(
          width: double.infinity,
          height: double.infinity,
          decoration: BoxDecoration(
            gradient: LinearGradient(
              begin: Alignment.topCenter,
              end: Alignment.bottomCenter,
              colors: [
                theme.colorScheme.primary,
                theme.colorScheme.primary.withValues(alpha: 0.8),
              ],
            ),
          ),
          child: Column(
            children: [
              Expanded(
                child: Center(
                  child: ConstrainedBox(
                    constraints: BoxConstraints(
                      maxWidth: isLargeScreen ? 400 : size.width * 0.8,
                    ),
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        // Animated Logo
                        AnimatedBuilder(
                          animation: _logoController,
                          builder: (context, child) {
                            return Transform.scale(
                              scale: _logoScale.value,
                              child: Opacity(
                                opacity: _logoOpacity.value,
                                child: Container(
                                  width: isLargeScreen ? 180 : 160,
                                  height: isLargeScreen ? 180 : 160,
                                  decoration: BoxDecoration(
                                    shape: BoxShape.circle,
                                    boxShadow: [
                                      BoxShadow(
                                        color: theme.colorScheme.secondary.withValues(alpha: 0.3),
                                        blurRadius: 20,
                                        spreadRadius: 5,
                                      ),
                                    ],
                                  ),
                                  child: ClipOval(
                                    child: Image.asset(
                                      'assets/logo/mitalogo.png',
                                      fit: BoxFit.cover,
                                      errorBuilder: (context, error, stackTrace) {
                                        return Container(
                                          decoration: BoxDecoration(
                                            color: theme.colorScheme.secondary,
                                            shape: BoxShape.circle,
                                          ),
                                          child: Icon(
                                            Icons.account_balance_wallet,
                                            size: isLargeScreen ? 80 : 60,
                                            color: theme.colorScheme.primary,
                                          ),
                                        );
                                      },
                                    ),
                                  ),
                                ),
                              ),
                            );
                          },
                        ),

                        SizedBox(height: isLargeScreen ? 40 : 32),

                        // Animated Text
                        AnimatedBuilder(
                          animation: _textController,
                          builder: (context, child) {
                            return SlideTransition(
                              position: _textSlide,
                              child: Opacity(
                                opacity: _textOpacity.value,
                                child: Column(
                                  children: [
                                    Text(
                                      'MITA',
                                      style: TextStyle(
                                        fontFamily: AppTypography.fontHeading,
                                        fontWeight: FontWeight.w800,
                                        fontSize: isLargeScreen ? 48 : 42,
                                        color: theme.colorScheme.secondary,
                                        letterSpacing: 3,
                                        height: 1.2,
                                      ),
                                      semanticsLabel: 'MITA - Money Intelligence Task Assistant',
                                    ),
                                    SizedBox(height: isLargeScreen ? 16 : 12),
                                    Text(
                                      'Money Intelligence Task Assistant',
                                      textAlign: TextAlign.center,
                                      style: TextStyle(
                                        fontFamily: AppTypography.fontBody,
                                        fontWeight: FontWeight.w400,
                                        fontSize: isLargeScreen ? 20 : 18,
                                        color: theme.colorScheme.onPrimary.withValues(alpha: 0.9),
                                        letterSpacing: 0.5,
                                        height: 1.4,
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                            );
                          },
                        ),
                      ],
                    ),
                  ),
                ),
              ),

              // Status and Progress Section
              Padding(
                padding: EdgeInsets.symmetric(
                  horizontal: 32,
                  vertical: isLargeScreen ? 40 : 32,
                ),
                child: Column(
                  children: [
                    // Status Text
                    AnimatedSwitcher(
                      duration: const Duration(milliseconds: 300),
                      child: Text(
                        _statusText,
                        key: ValueKey(_statusText),
                        style: TextStyle(
                          fontFamily: AppTypography.fontBody,
                          fontWeight: FontWeight.w500,
                          fontSize: 16,
                          color: _hasError
                              ? theme.colorScheme.error
                              : theme.colorScheme.onPrimary.withValues(alpha: 0.8),
                        ),
                        textAlign: TextAlign.center,
                      ),
                    ),

                    const SizedBox(height: 16),

                    // Progress Indicator
                    AnimatedBuilder(
                      animation: _progressController,
                      builder: (context, child) {
                        return SizedBox(
                          width: 200,
                          child: LinearProgressIndicator(
                            value: _hasError ? 1.0 : _progressValue.value,
                            backgroundColor: theme.colorScheme.onPrimary.withValues(alpha: 0.2),
                            valueColor: AlwaysStoppedAnimation<Color>(
                              _hasError ? theme.colorScheme.error : theme.colorScheme.secondary,
                            ),
                            borderRadius: BorderRadius.circular(2),
                          ),
                        );
                      },
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
