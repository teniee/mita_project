import 'screens/daily_budget_screen.dart';
import 'screens/habits_screen.dart';
import 'screens/goals_screen.dart';
import 'screens/notifications_screen.dart';
import 'screens/transactions_screen.dart';
import 'screens/installments_screen.dart';
import 'screens/profile_screen.dart';
import 'screens/bottom_navigation.dart';
import 'screens/referral_screen.dart';
import 'screens/mood_screen.dart';
import 'screens/subscription_screen.dart';
import 'screens/add_expense_screen.dart';
import 'screens/calendar_screen.dart';
import 'screens/main_screen.dart';
import 'package:flutter/material.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'screens/advice_history_screen.dart';
import 'services/api_service.dart';
import 'services/push_notification_service.dart';
import 'package:sentry_flutter/sentry_flutter.dart';

import 'screens/welcome_screen.dart';
import 'screens/login_screen.dart';
import 'screens/onboarding_region_screen.dart';
import 'screens/onboarding_income_screen.dart';
import 'screens/onboarding_expenses_screen.dart';
import 'screens/onboarding_goal_screen.dart';
import 'screens/onboarding_habits_screen.dart';
import 'screens/onboarding_motivation_screen.dart';
import 'screens/onboarding_finish_screen.dart';

Future<void> _initFirebase() async {
  await Firebase.initializeApp();
  await FirebaseMessaging.instance.requestPermission();
  final token = await FirebaseMessaging.instance.getToken();
  if (token != null) {
    final api = ApiService();
    await api.registerPushToken(token);
  }
  await PushNotificationService.initialize(navigatorKey);
}

final GlobalKey<NavigatorState> navigatorKey = GlobalKey<NavigatorState>();

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await _initFirebase();
  await SentryFlutter.init(
    (o) => o.dsn = const String.fromEnvironment('SENTRY_DSN', defaultValue: ''),
    appRunner: () => runApp(const MITAApp()),
  );
}

class MITAApp extends StatelessWidget {
  const MITAApp({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      navigatorKey: navigatorKey,
      title: 'MITA',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        useMaterial3: true,
        primaryColor: const Color(0xFFFFD25F),
        scaffoldBackgroundColor: const Color(0xFFFFF9F0),
        fontFamily: 'Manrope',
      ),
      darkTheme: ThemeData.dark().copyWith(
        colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFFFFD25F)),
      ),
      themeMode: ThemeMode.system,
      initialRoute: '/',
      routes: {
        '/': (context) => const WelcomeScreen(),
        '/login': (context) => const LoginScreen(), // added login route
        '/main': (context) => const BottomNavigation(),
        '/onboarding_region': (context) => const OnboardingRegionScreen(),
        '/onboarding_income': (context) => const OnboardingIncomeScreen(),
        '/onboarding_expenses': (context) => const OnboardingExpensesScreen(),
        '/onboarding_goal': (context) => const OnboardingGoalScreen(),
        '/onboarding_habits': (context) => const OnboardingHabitsScreen(),
        '/onboarding_motivation': (context) => const OnboardingMotivationScreen(),
        '/onboarding_finish': (context) => const OnboardingFinishScreen(),
        '/referral': (context) => const ReferralScreen(),
        '/mood': (context) => const MoodScreen(),
        '/subscribe': (context) => const SubscriptionScreen(),
        '/notifications': (context) => const NotificationsScreen(),
      },
    );
  }
}
