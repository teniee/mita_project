import 'dart:async';
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
import 'core/app_error_handler.dart';
import 'core/error_handling.dart';
import 'theme/mita_theme.dart';

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
import 'screens/auth_test_screen.dart';
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
  logInfo('Firebase initialized - push token registration deferred to post-authentication', tag: 'MAIN');

  await PushNotificationService.initialize(navigatorKey);
}

final GlobalKey<NavigatorState> navigatorKey = GlobalKey<NavigatorState>();

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  
  // Initialize logging service first
  LoggingService.instance.initialize(
    enableConsoleLogging: true,
    minimumLevel: kDebugMode ? LogLevel.debug : LogLevel.info,
  );
  
  // Initialize comprehensive error handling
  await AppErrorHandler.initialize();
  
  // Initialize app version service
  await AppVersionService.instance.initialize();
  
  // Initialize comprehensive Sentry monitoring for financial application
  const sentryDsn = String.fromEnvironment('SENTRY_DSN', defaultValue: '');
  const environment = String.fromEnvironment('ENVIRONMENT', defaultValue: 'development');
  const sentryRelease = String.fromEnvironment('SENTRY_RELEASE', defaultValue: 'mita-mobile@1.0.0');
  
  if (sentryDsn.isNotEmpty) {
    await sentryService.initialize(
      dsn: sentryDsn,
      environment: environment,
      release: sentryRelease,
      enableCrashReporting: true,
      enablePerformanceMonitoring: !kDebugMode, // Disable in debug for performance
      enableUserInteractionTracing: true,
      tracesSampleRate: environment == 'production' ? 0.1 : 1.0,
    );
  } else {
    if (kDebugMode) dev.log('Sentry DSN not configured - advanced error monitoring disabled', name: 'MitaApp');
  }
  
  await _initFirebase();

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
    
    // Send to enhanced Sentry service
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
    
    // Send to enhanced Sentry service
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
    
    return true;
  };

  // Create the app with providers
  final app = MultiProvider(
    providers: [
      ChangeNotifierProvider(create: (_) => UserProvider()),
      ChangeNotifierProvider(create: (_) => BudgetProvider()),
      ChangeNotifierProvider(create: (_) => TransactionProvider()),
      ChangeNotifierProvider(create: (_) => SettingsProvider()),
      ChangeNotifierProvider(create: (_) => GoalsProvider()),
      ChangeNotifierProvider(create: (_) => ChallengesProvider()),
      ChangeNotifierProvider(create: (_) => HabitsProvider()),
      ChangeNotifierProvider(create: (_) => BehavioralProvider()),
    ],
    child: const MITAApp(),
  );

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
    // Get settings provider for theme mode
    final settingsProvider = context.watch<SettingsProvider>();

    final app = MaterialApp(
      navigatorKey: navigatorKey,
      scaffoldMessengerKey: MessageService.instance.messengerKey,
      title: 'MITA',
      debugShowCheckedModeBanner: false,
      theme: MitaTheme.lightTheme,
      darkTheme: MitaTheme.darkTheme,
      themeMode: settingsProvider.themeMode,
      
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
      
      initialRoute: '/',
      onGenerateRoute: (settings) {
        logInfo('CRITICAL DEBUG: Navigation to route: ${settings.name}', tag: 'NAVIGATION');
        return null; // Let the routes table handle it
      },
      routes: {
        '/': (context) => const AppErrorBoundary(
          screenName: 'Welcome',
          child: WelcomeScreen(),
        ),
        '/login': (context) => const AppErrorBoundary(
          screenName: 'Login',
          child: LoginScreen(),
        ),
        '/register': (context) => const AppErrorBoundary(
          screenName: 'Register', 
          child: RegisterScreen(),
        ),
        '/forgot-password': (context) => const AppErrorBoundary(
          screenName: 'ForgotPassword',
          child: ForgotPasswordScreen(),
        ),
        '/reset-password': (context) => const AppErrorBoundary(
          screenName: 'ResetPassword',
          child: ResetPasswordScreen(),
        ),
        '/ai-assistant': (context) => const AppErrorBoundary(
          screenName: 'AIAssistant',
          child: AIAssistantScreen(),
        ),
        '/main': (context) => const AppErrorBoundary(
          screenName: 'Main',
          child: BottomNavigation(),
        ),
        '/onboarding_location': (context) => const AppErrorBoundary(
          screenName: 'OnboardingLocation',
          child: OnboardingLocationScreen(),
        ),
        '/onboarding_income': (context) => const AppErrorBoundary(
          screenName: 'OnboardingIncome',
          child: OnboardingIncomeScreen(),
        ),
        '/onboarding_expenses': (context) => const AppErrorBoundary(
          screenName: 'OnboardingExpenses', 
          child: OnboardingExpensesScreen(),
        ),
        '/onboarding_goal': (context) => const AppErrorBoundary(
          screenName: 'OnboardingGoal',
          child: OnboardingGoalScreen(),
        ),
        '/onboarding_spending_frequency': (context) => const AppErrorBoundary(
          screenName: 'OnboardingSpendingFrequency',
          child: OnboardingSpendingFrequencyScreen(),
        ),
        '/onboarding_habits': (context) => const AppErrorBoundary(
          screenName: 'OnboardingHabits',
          child: OnboardingHabitsScreen(),
        ),
        '/onboarding_finish': (context) => const AppErrorBoundary(
          screenName: 'OnboardingFinish',
          child: OnboardingFinishScreen(),
        ),
        '/referral': (context) => const AppErrorBoundary(
          screenName: 'Referral',
          child: ReferralScreen(),
        ),
        '/mood': (context) => const AppErrorBoundary(
          screenName: 'Mood',
          child: MoodScreen(),
        ),
        '/subscribe': (context) => const AppErrorBoundary(
          screenName: 'Subscription',
          child: SubscriptionScreen(),
        ),
        '/notifications': (context) => const AppErrorBoundary(
          screenName: 'Notifications',
          child: NotificationsScreen(),
        ),
        '/daily_budget': (context) => const AppErrorBoundary(
          screenName: 'DailyBudget',  
          child: DailyBudgetScreen(),
        ),
        '/add_expense': (context) => const AppErrorBoundary(
          screenName: 'AddExpense',
          child: AddExpenseScreen(),
        ),
        '/insights': (context) => const AppErrorBoundary(
          screenName: 'Insights',
          child: InsightsScreen(),
        ),
        '/budget_settings': (context) => const AppErrorBoundary(
          screenName: 'BudgetSettings',
          child: BudgetSettingsScreen(),
        ),
        '/profile': (context) => const AppErrorBoundary(
          screenName: 'UserProfile',
          child: UserProfileScreen(),
        ),
        '/settings': (context) => const AppErrorBoundary(
          screenName: 'UserSettings',
          child: UserSettingsScreen(),
        ),
        '/transactions': (context) => const AppErrorBoundary(
          screenName: 'Transactions',
          child: TransactionsScreen(),
        ),
        '/auth-test': (context) => const AppErrorBoundary(
          screenName: 'AuthTest',
          child: AuthTestScreen(),
        ),
        '/goals': (context) => const AppErrorBoundary(
          screenName: 'Goals',
          child: GoalsScreen(),
        ),
        '/challenges': (context) => const AppErrorBoundary(
          screenName: 'Challenges',
          child: ChallengesScreen(),
        ),
        '/installment-calculator': (context) => const AppErrorBoundary(
          screenName: 'InstallmentCalculator',
          child: InstallmentCalculatorScreen(),
        ),
        '/installments': (context) => const AppErrorBoundary(
          screenName: 'Installments',
          child: InstallmentsScreen(),
        ),
      },
    );

    // Wrap the app with an enhanced loading overlay that auto-dismisses
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
                          LoadingService.instance.forceHide(reason: 'user_emergency_dismiss');
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
  State<_EnhancedLoadingIndicator> createState() => _EnhancedLoadingIndicatorState();
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
                    LoadingService.instance.forceHide(reason: 'user_emergency_dismiss');
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
