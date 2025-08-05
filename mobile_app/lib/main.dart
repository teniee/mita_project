import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:firebase_crashlytics/firebase_crashlytics.dart';
import 'package:sentry_flutter/sentry_flutter.dart';
import 'dart:ui';

import 'firebase_options.dart';

import 'screens/notifications_screen.dart';
import 'screens/bottom_navigation.dart';
import 'screens/referral_screen.dart';
import 'screens/mood_screen.dart';
import 'screens/subscription_screen.dart';
import 'services/push_notification_service.dart';
import 'services/loading_service.dart';
import 'services/message_service.dart';
import 'services/logging_service.dart';
import 'core/app_error_handler.dart';
import 'core/error_handling.dart';
import 'theme/mita_theme.dart';

import 'screens/welcome_screen.dart';
import 'screens/login_screen.dart';
import 'screens/register_screen.dart';
import 'screens/onboarding_region_screen.dart';
import 'screens/onboarding_location_screen.dart';
import 'screens/onboarding_income_screen.dart';
import 'screens/onboarding_expenses_screen.dart';
import 'screens/onboarding_goal_screen.dart';
import 'screens/onboarding_habits_screen.dart';
import 'screens/onboarding_motivation_screen.dart';
import 'screens/onboarding_finish_screen.dart';
import 'screens/daily_budget_screen.dart';
import 'screens/add_expense_screen.dart';
import 'screens/insights_screen.dart';
import 'screens/budget_settings_screen.dart';

/// Initialise Firebase, Crashlytics and push notifications.
Future<void> _initFirebase() async {
  await Firebase.initializeApp(
    options: DefaultFirebaseOptions.currentPlatform,
  );
  await FirebaseCrashlytics.instance.setCrashlyticsCollectionEnabled(true);
  await FirebaseMessaging.instance.requestPermission();

  // Register device push-token (optional)
  final token = await FirebaseMessaging.instance.getToken();
  if (token != null) {
    // TODO: Register push token when backend is ready
    // final api = ApiService();
    // await api.registerPushToken(token);
  }

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
  
  await _initFirebase();

  // Enhanced error handling that integrates with our custom system
  FlutterError.onError = (FlutterErrorDetails details) {
    // Send to Firebase Crashlytics
    FirebaseCrashlytics.instance.recordFlutterFatalError(details);
    
    // Also send to our custom error handler
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
  };
  
  PlatformDispatcher.instance.onError = (error, stack) {
    // Send to Firebase Crashlytics
    FirebaseCrashlytics.instance.recordError(error, stack, fatal: true);
    
    // Also send to our custom error handler
    AppErrorHandler.reportError(
      error,
      stackTrace: stack,
      severity: ErrorSeverity.critical,
      category: ErrorCategory.system,
      context: {'source': 'platform_dispatcher'},
    );
    
    return true;
  };

  await SentryFlutter.init(
    (o) =>
        o.dsn = const String.fromEnvironment('SENTRY_DSN', defaultValue: ''),
    appRunner: () => runApp(const MITAApp()),
  );
}

class MITAApp extends StatelessWidget {
  const MITAApp({super.key});

  @override
  Widget build(BuildContext context) {
    final app = MaterialApp(
      navigatorKey: navigatorKey,
      scaffoldMessengerKey: MessageService.instance.messengerKey,
      title: 'MITA',
      debugShowCheckedModeBanner: false,
      theme: MitaTheme.lightTheme,
      darkTheme: MitaTheme.darkTheme,
      themeMode: ThemeMode.system,
      initialRoute: '/',
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
        '/main': (context) => const AppErrorBoundary(
          screenName: 'Main',
          child: BottomNavigation(),
        ),
        '/onboarding_region': (context) => const AppErrorBoundary(
          screenName: 'OnboardingRegion',
          child: OnboardingRegionScreen(),
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
        '/onboarding_habits': (context) => const AppErrorBoundary(
          screenName: 'OnboardingHabits',
          child: OnboardingHabitsScreen(),
        ),
        '/onboarding_motivation': (context) => const AppErrorBoundary(
          screenName: 'OnboardingMotivation',
          child: OnboardingMotivationScreen(),
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
      },
    );

    // Wrap the app with a global loading overlay
    return ValueListenableBuilder<int>(
      valueListenable: LoadingService.instance.notifier,
      builder: (context, value, child) {
        return Directionality(
          textDirection: TextDirection.ltr,
          child: Stack(
            children: [
              child!,
              if (value > 0) ...[
                const ModalBarrier(dismissible: false, color: Colors.black45),
                const Center(child: CircularProgressIndicator()),
              ],
            ],
          ),
        );
      },
      child: app,
    );
  }
}
