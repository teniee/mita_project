import 'dart:async';
import 'dart:io';
import 'package:flutter/foundation.dart';
import 'dart:developer' as dev;
import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:firebase_crashlytics/firebase_crashlytics.dart';
import 'package:sentry_flutter/sentry_flutter.dart';
import 'package:provider/provider.dart';
import 'dart:ui';

import 'providers/providers.dart';

import 'firebase_options.dart';
import 'l10n/generated/app_localizations.dart';

import 'screens/notifications_screen.dart';
import 'screens/bottom_navigation.dart';
import 'screens/referral_screen.dart';
import 'screens/mood_screen.dart';
import 'screens/subscription_screen.dart';
import 'services/push_notification_service.dart';
import 'services/loading_service.dart';
import 'services/message_service.dart';
import 'services/logging_service.dart';
import 'services/localization_service.dart';
import 'services/app_version_service.dart';
import 'services/sentry_service.dart';
import 'services/ios_security_service.dart';
// Note: biometric_auth_service.dart available for future login flow integration
import 'core/app_error_handler.dart';
import 'core/error_handling.dart';
import 'theme/mita_theme.dart';

// DEBUG: Only import debug/test screens in debug mode
import 'screens/welcome_screen.dart';
import 'screens/login_screen.dart';
import 'screens/register_screen.dart';
import 'screens/forgot_password_screen.dart';
import 'screens/reset_password_screen.dart';
import 'screens/ai_assistant_screen.dart';
import 'screens/onboarding_location_screen.dart';
import 'screens/onboarding_income_screen.dart';
import 'screens/onboarding_expenses_screen.dart';
import 'screens/onboarding_goal_screen.dart';
import 'screens/onboarding_spending_frequency_screen.dart';
import 'screens/onboarding_habits_screen.dart';
import 'screens/onboarding_finish_screen.dart';
import 'screens/daily_budget_screen.dart';
import 'screens/add_expense_screen.dart';
import 'screens/insights_screen.dart';
import 'screens/budget_settings_screen.dart';
import 'screens/user_profile_screen.dart';
import 'screens/user_settings_screen.dart';
// DEBUG: auth_test_screen.dart removed from production (only for debug builds)
import 'screens/transactions_screen.dart';
import 'screens/goals_screen.dart';
import 'screens/challenges_screen.dart';
import 'screens/installment_calculator_screen.dart';
import 'screens/installments_screen.dart';

/// Initialise Firebase, Crashlytics and push notifications.
Future<void> _initFirebase() async {
  await Firebase.initializeApp(
    options: DefaultFirebaseOptions.currentPlatform,
  );
  await FirebaseCrashlytics.instance.setCrashlyticsCollectionEnabled(true);
  await FirebaseMessaging.instance.requestPermission();

  // SECURITY: Push token registration moved to post-authentication flow
  // Tokens are now only registered after successful user login via SecurePushTokenManager
  logInfo(
      'Firebase initialized - push token registration deferred to post-authentication',
      tag: 'MAIN');

  await PushNotificationService.initialize(navigatorKey);
}

final GlobalKey<NavigatorState> navigatorKey = GlobalKey<NavigatorState>();

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // Initialize logging service first (with PII masking enabled)
  LoggingService.instance.initialize(
    enableConsoleLogging: true,
    enablePIIMasking: true, // GDPR compliance
    minimumLevel: kDebugMode ? LogLevel.debug : LogLevel.info,
  );

  // SECURITY: iOS Jailbreak & Tampering Detection
  if (Platform.isIOS) {
    try {
      final securityService = IOSSecurityService();
      final isSecure = await securityService.performSecurityCheck();

      if (!isSecure && !kDebugMode) {
        // Get security recommendations
        final recommendations =
            await securityService.getSecurityRecommendations();
        logWarning(
          'iOS Security check failed: ${recommendations.join(", ")}',
          tag: 'MAIN_SECURITY',
        );
        // In production, consider blocking app launch or showing warning dialog
        // For now, we just log the issue
      } else {
        logInfo('iOS Security check passed', tag: 'MAIN_SECURITY');
      }

      // Log comprehensive security info for monitoring
      final securityInfo = await securityService.getComprehensiveSecurityInfo();
      logDebug('iOS Security Info: $securityInfo', tag: 'MAIN_SECURITY');
    } catch (e) {
      logError('iOS Security check error: $e', tag: 'MAIN_SECURITY', error: e);
      // Don't block app launch on security check errors
    }
  }

  // Initialize comprehensive error handling
  await AppErrorHandler.initialize();

  logInfo('=== PRODUCTION MODE - All services enabled ===', tag: 'MAIN');

  // Initialize app version service
  await AppVersionService.instance.initialize();

  // Initialize comprehensive Sentry monitoring for financial application
  const sentryDsn = String.fromEnvironment('SENTRY_DSN', defaultValue: '');
  const environment =
      String.fromEnvironment('ENVIRONMENT', defaultValue: 'development');
  const sentryRelease = String.fromEnvironment('SENTRY_RELEASE',
      defaultValue: 'mita-mobile@1.0.0');

  if (sentryDsn.isNotEmpty) {
    await sentryService.initialize(
      dsn: sentryDsn,
      environment: environment,
      release: sentryRelease,
      enableCrashReporting: true,
      enablePerformanceMonitoring:
          !kDebugMode, // Disable in debug for performance
      enableUserInteractionTracing: true,
      tracesSampleRate: environment == 'production' ? 0.1 : 1.0,
    );
    logInfo('Sentry initialized successfully', tag: 'MAIN');
  } else {
    if (kDebugMode) {
      dev.log('Sentry DSN not configured - advanced error monitoring disabled',
          name: 'MitaApp');
    }
  }

  // Initialize Firebase
  await _initFirebase();
  logInfo('Firebase initialized successfully', tag: 'MAIN');

  // Enhanced error handling that integrates with all monitoring systems
  FlutterError.onError = (FlutterErrorDetails details) {
    // Send to Firebase Crashlytics
    FirebaseCrashlytics.instance.recordFlutterFatalError(details);

    // Send to our custom error handler
    AppErrorHandler.reportError(
      details.exception,
      stackTrace: details.stack,
      severity: ErrorSeverity.critical,
      category: ErrorCategory.ui,
      context: {
        'library': details.library,
        'context': details.context?.toString(),
      },
    );

    // Send to enhanced Sentry service (only if initialized)
    if (sentryDsn.isNotEmpty) {
      sentryService.captureFinancialError(
        details.exception,
        category: FinancialErrorCategory.uiError,
        severity: FinancialSeverity.critical,
        stackTrace: details.stack.toString(),
        additionalContext: {
          'library': details.library,
          'context': details.context?.toString(),
          'error_source': 'flutter_error',
        },
        tags: {
          'error_source': 'flutter_error_handler',
          'ui_error': 'true',
        },
      );
    }
  };

  PlatformDispatcher.instance.onError = (error, stack) {
    // Send to Firebase Crashlytics
    FirebaseCrashlytics.instance.recordError(error, stack, fatal: true);

    // Send to our custom error handler
    AppErrorHandler.reportError(
      error,
      stackTrace: stack,
      severity: ErrorSeverity.critical,
      category: ErrorCategory.system,
      context: {'source': 'platform_dispatcher'},
    );

    // Send to enhanced Sentry service (only if initialized)
    if (sentryDsn.isNotEmpty) {
      sentryService.captureFinancialError(
        error,
        category: FinancialErrorCategory.systemError,
        severity: FinancialSeverity.critical,
        stackTrace: stack.toString(),
        additionalContext: {
          'source': 'platform_dispatcher',
          'error_source': 'platform',
        },
        tags: {
          'error_source': 'platform_dispatcher',
          'system_error': 'true',
          'fatal': 'true',
        },
      );
    }

    return true;
  };

  // FIXED: UserProvider Stream exposure caused MultiProvider assertion error
  // Root cause was premiumStatusStream getter exposing IapService stream
  // Solution: Disabled Stream getter in user_provider.dart:308-311
  final app = MultiProvider(
    providers: [
      ChangeNotifierProvider(create: (_) => SettingsProvider()),
      ChangeNotifierProvider(create: (_) => UserProvider()),
      // RE-ENABLED: All providers needed for internal screens
      ChangeNotifierProvider(create: (_) => BudgetProvider()),
      ChangeNotifierProvider(create: (_) => TransactionProvider()),
      ChangeNotifierProvider(create: (_) => GoalsProvider()),
      ChangeNotifierProvider(create: (_) => ChallengesProvider()),
      ChangeNotifierProvider(create: (_) => HabitsProvider()),
      ChangeNotifierProvider(create: (_) => BehavioralProvider()),
      ChangeNotifierProvider(create: (_) => MoodProvider()),
      ChangeNotifierProvider(create: (_) => NotificationsProvider()),
      ChangeNotifierProvider(create: (_) => AdviceProvider()),
      ChangeNotifierProvider(create: (_) => InstallmentsProvider()),
      ChangeNotifierProvider(create: (_) => LoadingProvider()),
    ],
    child: const MITAApp(),
  );

  logInfo('Running app with all providers initialized', tag: 'MAIN');

  // Run the app with comprehensive error monitoring
  if (sentryDsn.isNotEmpty) {
    // Use Sentry's runApp wrapper for additional error capture
    await SentryFlutter.init(
      (options) {
        // Sentry is already initialized by our service, this is just to use the runApp wrapper
        options.dsn = sentryDsn;
        options.environment = environment;
        options.release = sentryRelease;
        // Minimal configuration as our service handles the comprehensive setup
      },
      appRunner: () => runApp(app),
    );
  } else {
    runApp(app);
  }
}

class MITAApp extends StatefulWidget {
  const MITAApp({super.key});

  @override
  State<MITAApp> createState() => _MITAAppState();
}

class _MITAAppState extends State<MITAApp> {
  @override
  void initState() {
    super.initState();
    _initializeProviders();
  }

  Future<void> _initializeProviders() async {
    // Initialize providers after the first frame
    WidgetsBinding.instance.addPostFrameCallback((_) async {
      final settingsProvider = context.read<SettingsProvider>();
      final userProvider = context.read<UserProvider>();

      // Initialize settings first (for theme, locale, etc.)
      await settingsProvider.initialize();

      // Initialize user provider
      await userProvider.initialize();

      logInfo('All providers initialized', tag: 'MAIN');
    });
  }

  @override
  Widget build(BuildContext context) {
    // Get theme mode from SettingsProvider
    final themeMode = context.watch<SettingsProvider>().themeMode;

    final app = MaterialApp(
      navigatorKey: navigatorKey,
      scaffoldMessengerKey: MessageService.instance.messengerKey,
      title: 'MITA',
      debugShowCheckedModeBanner: false,
      theme: MitaTheme.lightTheme,
      darkTheme: MitaTheme.darkTheme,
      themeMode: themeMode,

      // Localization configuration
      localizationsDelegates: const [
        AppLocalizations.delegate,
        GlobalMaterialLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
      ],
      supportedLocales: AppLocalizations.supportedLocales,

      // Locale resolution for unsupported locales
      localeResolutionCallback: (locale, supportedLocales) {
        // Initialize localization service with resolved locale
        if (locale != null) {
          LocalizationService.instance.setLocale(locale);
        }

        // If the device locale is supported, use it
        if (locale != null) {
          for (final supportedLocale in supportedLocales) {
            if (supportedLocale.languageCode == locale.languageCode) {
              return supportedLocale;
            }
          }
        }

        // Default to English if device locale is not supported
        return const Locale('en');
      },

      initialRoute: '/', // Start at welcome screen
      onGenerateRoute: (settings) {
        logInfo('CRITICAL DEBUG: Navigation to route: ${settings.name}',
            tag: 'NAVIGATION');
        return null; // Let the routes table handle it
      },
      routes: {
        // DEBUG ROUTES REMOVED: /debug-test and /auth-test only available in debug builds
        // Use Flutter DevTools for debugging in production builds
        '/': (context) => const WelcomeScreen(),
        '/login': (context) => const LoginScreen(),
        '/register': (context) => const RegisterScreen(),
        '/forgot-password': (context) => const ForgotPasswordScreen(),
        '/reset-password': (context) => const ResetPasswordScreen(),
        '/ai-assistant': (context) => const AIAssistantScreen(),
        '/main': (context) => const BottomNavigation(),
        '/onboarding_location': (context) => const OnboardingLocationScreen(),
        '/onboarding_income': (context) => const OnboardingIncomeScreen(),
        '/onboarding_expenses': (context) => const OnboardingExpensesScreen(),
        '/onboarding_goal': (context) => const OnboardingGoalScreen(),
        '/onboarding_spending_frequency': (context) => const OnboardingSpendingFrequencyScreen(),
        '/onboarding_habits': (context) => const OnboardingHabitsScreen(),
        '/onboarding_finish': (context) => const OnboardingFinishScreen(),
        '/referral': (context) => const ReferralScreen(),
        '/mood': (context) => const MoodScreen(),
        '/subscribe': (context) => const SubscriptionScreen(),
        '/notifications': (context) => const NotificationsScreen(),
        '/daily_budget': (context) => const DailyBudgetScreen(),
        '/add_expense': (context) => const AddExpenseScreen(),
        '/insights': (context) => const InsightsScreen(),
        '/budget_settings': (context) => const BudgetSettingsScreen(),
        '/profile': (context) => const UserProfileScreen(),
        '/settings': (context) => const UserSettingsScreen(),
        '/transactions': (context) => const TransactionsScreen(),
        // DEBUG: /auth-test route removed for production compliance
        '/goals': (context) => const GoalsScreen(),
        '/challenges': (context) => const ChallengesScreen(),
        '/installment-calculator': (context) => const InstallmentCalculatorScreen(),
        '/installments': (context) => const InstallmentsScreen(),
      },
    );

    // Enhanced loading overlay with emergency dismiss
    return ValueListenableBuilder<bool>(
      valueListenable: LoadingService.instance.forceHiddenNotifier,
      builder: (context, forceHidden, child) {
        return ValueListenableBuilder<int>(
          valueListenable: LoadingService.instance.notifier,
          builder: (context, loadingCount, child) {
            final shouldShowLoading = loadingCount > 0 && !forceHidden;

            return Directionality(
              textDirection: TextDirection.ltr,
              child: Stack(
                children: [
                  child!,
                  if (shouldShowLoading) ...[
                    // Enhanced modal barrier with tap to dismiss after delay
                    _EnhancedModalBarrier(
                      onTap: () {
                        // Allow emergency dismiss after 10 seconds
                        final status = LoadingService.instance.getStatus();
                        if (status.globalLoadingDuration != null &&
                            status.globalLoadingDuration!.inSeconds >= 10) {
                          LoadingService.instance
                              .forceHide(reason: 'user_emergency_dismiss');
                        }
                      },
                    ),
                    // Enhanced loading indicator with timeout info
                    _EnhancedLoadingIndicator(),
                  ],
                ],
              ),
            );
          },
          child: child,
        );
      },
      child: app,
    );
  }
}

/// Enhanced modal barrier with tap-to-dismiss functionality
class _EnhancedModalBarrier extends StatelessWidget {
  final VoidCallback? onTap;

  const _EnhancedModalBarrier({this.onTap});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        color: Colors.black.withValues(alpha: 0.5),
        child: const SizedBox.expand(),
      ),
    );
  }
}

/// Enhanced loading indicator with status and timeout information
class _EnhancedLoadingIndicator extends StatefulWidget {
  @override
  State<_EnhancedLoadingIndicator> createState() =>
      _EnhancedLoadingIndicatorState();
}

class _EnhancedLoadingIndicatorState extends State<_EnhancedLoadingIndicator>
    with TickerProviderStateMixin {
  late AnimationController _controller;
  late Animation<double> _fadeAnimation;
  Timer? _statusTimer;
  LoadingStatus _status = LoadingService.instance.getStatus();

  @override
  void initState() {
    super.initState();

    _controller = AnimationController(
      duration: const Duration(milliseconds: 300),
      vsync: this,
    );

    _fadeAnimation = Tween<double>(
      begin: 0.0,
      end: 1.0,
    ).animate(CurvedAnimation(
      parent: _controller,
      curve: Curves.easeInOut,
    ));

    _controller.forward();

    // Update status periodically
    _statusTimer = Timer.periodic(const Duration(seconds: 1), (_) {
      if (mounted) {
        setState(() {
          _status = LoadingService.instance.getStatus();
        });
      }
    });
  }

  @override
  void dispose() {
    _controller.dispose();
    _statusTimer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;

    return FadeTransition(
      opacity: _fadeAnimation,
      child: Center(
        child: Container(
          padding: const EdgeInsets.all(24),
          margin: const EdgeInsets.all(32),
          decoration: BoxDecoration(
            color: colorScheme.surface,
            borderRadius: BorderRadius.circular(16),
            boxShadow: [
              BoxShadow(
                color: Colors.black.withValues(alpha: 0.2),
                blurRadius: 10,
                offset: const Offset(0, 4),
              ),
            ],
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              // Loading spinner
              SizedBox(
                width: 48,
                height: 48,
                child: CircularProgressIndicator(
                  color: colorScheme.primary,
                  strokeWidth: 3,
                ),
              ),

              const SizedBox(height: 16),

              // Loading message
              Text(
                _getLoadingMessage(),
                style: theme.textTheme.titleMedium?.copyWith(
                  color: colorScheme.onSurface,
                  fontWeight: FontWeight.w500,
                ),
                textAlign: TextAlign.center,
              ),

              if (_status.globalLoadingDuration != null) ...[
                const SizedBox(height: 8),
                Text(
                  _getDurationText(),
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: colorScheme.onSurfaceVariant,
                  ),
                ),
              ],

              // Emergency dismiss button after 10 seconds
              if (_status.globalLoadingDuration != null &&
                  _status.globalLoadingDuration!.inSeconds >= 10) ...[
                const SizedBox(height: 16),
                TextButton.icon(
                  onPressed: () {
                    LoadingService.instance
                        .forceHide(reason: 'user_emergency_dismiss');
                  },
                  icon: Icon(
                    Icons.close_rounded,
                    size: 18,
                    color: colorScheme.error,
                  ),
                  label: Text(
                    'Dismiss',
                    style: TextStyle(color: colorScheme.error),
                  ),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }

  String _getLoadingMessage() {
    if (_status.operations.isNotEmpty) {
      final operation = _status.operations.first;
      return operation.description;
    }

    return 'Loading...';
  }

  String _getDurationText() {
    final duration = _status.globalLoadingDuration;
    if (duration == null) return '';

    final seconds = duration.inSeconds;
    if (seconds < 60) {
      return '${seconds}s';
    } else {
      final minutes = duration.inMinutes;
      final remainingSeconds = seconds % 60;
      return '${minutes}m ${remainingSeconds}s';
    }
  }
}
