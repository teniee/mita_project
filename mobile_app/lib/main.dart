import 'package:flutter/material.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:firebase_crashlytics/firebase_crashlytics.dart';
import 'package:sentry_flutter/sentry_flutter.dart';
import 'dart:ui';

import 'screens/notifications_screen.dart';
import 'screens/bottom_navigation.dart';
import 'screens/referral_screen.dart';
import 'screens/mood_screen.dart';
import 'screens/subscription_screen.dart';
import 'services/api_service.dart';
import 'services/push_notification_service.dart';
import 'services/loading_service.dart';
import 'services/message_service.dart';

import 'screens/welcome_screen.dart';
import 'screens/login_screen.dart';
import 'screens/register_screen.dart';
import 'screens/onboarding_region_screen.dart';
import 'screens/onboarding_income_screen.dart';
import 'screens/onboarding_expenses_screen.dart';
import 'screens/onboarding_goal_screen.dart';
import 'screens/onboarding_habits_screen.dart';
import 'screens/onboarding_motivation_screen.dart';
import 'screens/onboarding_finish_screen.dart';

Future<void> _initFirebase() async {
  await Firebase.initializeApp();
  await FirebaseCrashlytics.instance.setCrashlyticsCollectionEnabled(true);
  await FirebaseMessaging.instance.requestPermission();

  final token = await FirebaseMessaging.instance.getToken();
  if (token != null) {
    final api = ApiService();
    print('⚠️ Using API base: ${api.baseUrl}');
    //await api.registerPushToken(token);
  }

  await PushNotificationService.initialize(navigatorKey);
}

final GlobalKey<NavigatorState> navigatorKey = GlobalKey<NavigatorState>();

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await _initFirebase();
  FlutterError.onError = FirebaseCrashlytics.instance.recordFlutterFatalError;
  PlatformDispatcher.instance.onError = (error, stack) {
    FirebaseCrashlytics.instance.recordError(error, stack, fatal: true);
    return true;
  };
  await SentryFlutter.init(
    (o) => o.dsn = const String.fromEnvironment('SENTRY_DSN', defaultValue: ''),
    appRunner: () => runApp(const MITAApp()),
  );
}

class MITAApp extends StatelessWidget {
  const MITAApp({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    final app = MaterialApp(
      navigatorKey: navigatorKey,
      scaffoldMessengerKey: MessageService.instance.messengerKey,
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
        '/login': (context) => const LoginScreen(),
        '/register': (context) => const RegisterScreen(),
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
    return ValueListenableBuilder<int>(
      valueListenable: LoadingService.instance.notifier,
      builder: (context, value, child) {
        return Stack(
          children: [
            child!,
            if (value > 0) ...[
              const ModalBarrier(dismissible: false, color: Colors.black45),
              const Center(child: CircularProgressIndicator()),
            ],
          ],
        );
      },
      child: app,
    );
  }
}
