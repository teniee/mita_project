import 'screens/daily_budget_screen.dart';
import 'screens/habits_screen.dart';
import 'screens/goals_screen.dart';
import 'screens/notifications_screen.dart';
import 'screens/transactions_screen.dart';
import 'screens/installments_screen.dart';
import 'screens/profile_screen.dart';
import 'screens/bottom_navigation.dart';
import 'screens/add_expense_screen.dart';
import 'screens/calendar_screen.dart';
import 'screens/main_screen.dart';
import 'package:flutter/material.dart';

import 'screens/welcome_screen.dart';
import 'screens/login_screen.dart';
import 'screens/onboarding_region_screen.dart';
import 'screens/onboarding_income_screen.dart';
import 'screens/onboarding_expenses_screen.dart';
import 'screens/onboarding_goal_screen.dart';
import 'screens/onboarding_habits_screen.dart';
import 'screens/onboarding_motivation_screen.dart';
import 'screens/onboarding_finish_screen.dart';

void main() {
  runApp(const MITAApp());
}

class MITAApp extends StatelessWidget {
  const MITAApp({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'MITA',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        useMaterial3: true,
        primaryColor: const Color(0xFFFFD25F),
        scaffoldBackgroundColor: const Color(0xFFFFF9F0),
        fontFamily: 'Manrope',
      ),
      initialRoute: '/home',
      routes: {
        '/': (context) => const WelcomeScreen(),
        '/login': (context) => const LoginScreen(), // 👈 добавлен логин
        '/main': (context) => const BottomNavigation(),
        '/onboarding_region': (context) => const OnboardingRegionScreen(),
        '/onboarding_income': (context) => const OnboardingIncomeScreen(),
        '/onboarding_expenses': (context) => const OnboardingExpensesScreen(),
        '/onboarding_goal': (context) => const OnboardingGoalScreen(),
        '/onboarding_habits': (context) => const OnboardingHabitsScreen(),
        '/onboarding_motivation': (context) => const OnboardingMotivationScreen(),
        '/onboarding_finish': (context) => const OnboardingFinishScreen(),
      },
    );
  }
}
