/// Every user-reachable screen must lay out without overflow on a small phone,
/// with and without the keyboard up.
///
/// The emulator used for manual QA is 411x914dp, which is roomy enough to hide
/// this class of bug. At 360x640 with a 300px keyboard inset the pre-launch
/// pass found four real overflows, two of them mid-onboarding
/// (onboarding_goal 219px, onboarding_habits 104px) — and Flutter clips
/// overflow OUT OF HIT TESTING, so "Continue" was still painted but no longer
/// tappable. This suite fails on any overflow so that cannot come back.
library;

import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:mita/l10n/generated/app_localizations.dart';
import 'package:mita/providers/providers.dart';
import 'package:mita/theme/mita_theme.dart';

import 'package:mita/screens/add_expense_screen.dart';
import 'package:mita/screens/add_transaction_screen.dart';
import 'package:mita/screens/budget_settings_screen.dart';
import 'package:mita/screens/calendar_screen.dart';
import 'package:mita/screens/daily_budget_screen.dart';
import 'package:mita/screens/forgot_password_screen.dart';
import 'package:mita/screens/goals_screen.dart';
import 'package:mita/screens/habits_screen.dart';
import 'package:mita/screens/insights_screen.dart';
import 'package:mita/screens/login_screen.dart';
import 'package:mita/screens/main_screen.dart';
import 'package:mita/screens/onboarding_expenses_screen.dart';
import 'package:mita/screens/onboarding_goal_screen.dart';
import 'package:mita/screens/onboarding_habits_screen.dart';
import 'package:mita/screens/onboarding_income_screen.dart';
import 'package:mita/screens/onboarding_location_screen.dart';
import 'package:mita/screens/onboarding_spending_frequency_screen.dart';
import 'package:mita/screens/register_screen.dart';
import 'package:mita/screens/transactions_screen.dart';
import 'package:mita/screens/user_profile_screen.dart';
import 'package:mita/screens/user_settings_screen.dart';

/// The stock test font is a square-glyph placeholder that grossly overstates
/// text width, which would report overflows a real device never shows. Load the
/// shipped faces — including as "Roboto", the fallback unstyled Text resolves.
Future<void> _loadRealFonts() async {
  Future<void> load(String family, List<String> paths) async {
    final loader = FontLoader(family);
    for (final path in paths) {
      loader.addFont(File(path)
          .readAsBytes()
          .then((b) => ByteData.view(Uint8List.fromList(b).buffer)));
    }
    await loader.load();
  }

  const manrope = [
    'assets/fonts/Manrope/static/Manrope-Regular.ttf',
    'assets/fonts/Manrope/static/Manrope-Bold.ttf',
  ];
  await load('Manrope', manrope);
  await load('Sora', [
    'assets/fonts/Sora/static/Sora-Regular.ttf',
    'assets/fonts/Sora/static/Sora-Bold.ttf',
  ]);
  await load('Roboto', manrope);
}

Widget _hostApp(Widget home, {required double bottomInset}) => MultiProvider(
      providers: [
        ChangeNotifierProvider<SettingsProvider>(
            create: (_) => SettingsProvider()),
        ChangeNotifierProvider<BudgetProvider>(create: (_) => BudgetProvider()),
        ChangeNotifierProvider<TransactionProvider>(
            create: (_) => TransactionProvider()),
        ChangeNotifierProvider<GoalsProvider>(create: (_) => GoalsProvider()),
        ChangeNotifierProvider<ChallengesProvider>(
            create: (_) => ChallengesProvider()),
        ChangeNotifierProvider<HabitsProvider>(create: (_) => HabitsProvider()),
        ChangeNotifierProvider<BehavioralProvider>(
            create: (_) => BehavioralProvider()),
        ChangeNotifierProvider<MoodProvider>(create: (_) => MoodProvider()),
        ChangeNotifierProvider<NotificationsProvider>(
            create: (_) => NotificationsProvider()),
        ChangeNotifierProvider<AdviceProvider>(create: (_) => AdviceProvider()),
        ChangeNotifierProvider<InstallmentsProvider>(
            create: (_) => InstallmentsProvider()),
        ChangeNotifierProvider<LoadingProvider>(
            create: (_) => LoadingProvider()),
        ChangeNotifierProvider<UserProvider>(create: (_) => UserProvider()),
      ],
      child: MaterialApp(
        theme: MitaTheme.lightTheme,
        // Screens that call AppLocalizations.of(context) type-error without
        // these, and would never reach layout — so their overflow would go
        // unmeasured.
        localizationsDelegates: const [
          AppLocalizations.delegate,
          GlobalMaterialLocalizations.delegate,
          GlobalWidgetsLocalizations.delegate,
          GlobalCupertinoLocalizations.delegate,
        ],
        supportedLocales: AppLocalizations.supportedLocales,
        home: Builder(
          builder: (context) => MediaQuery(
            data: MediaQuery.of(context).copyWith(
              viewInsets: EdgeInsets.only(bottom: bottomInset),
              padding: const EdgeInsets.only(top: 24, bottom: 16),
            ),
            child: home,
          ),
        ),
      ),
    );

/// Screens a normal user can reach. Constructed with no arguments, so they
/// render their loading/empty state — which is exactly the fresh-account shape
/// a first user sees.
///
/// MoodScreen (and therefore BottomNavigation, which hosts it) are absent:
/// MoodScreen.initState calls ReminderService.scheduleDailyReminder, whose
/// notifications plugin has no implementation in a unit test and throws
/// asynchronously, which fails the test before layout is ever measured. Both
/// are covered on-device instead.
final Map<String, Widget Function()> _screens = {
  'LoginScreen': () => const LoginScreen(),
  'RegisterScreen': () => const RegisterScreen(),
  'ForgotPasswordScreen': () => const ForgotPasswordScreen(),
  'OnboardingLocation': () => const OnboardingLocationScreen(),
  'OnboardingIncome': () => const OnboardingIncomeScreen(),
  'OnboardingExpenses': () => const OnboardingExpensesScreen(),
  'OnboardingGoal': () => const OnboardingGoalScreen(),
  'OnboardingSpendingFrequency': () =>
      const OnboardingSpendingFrequencyScreen(),
  'OnboardingHabits': () => const OnboardingHabitsScreen(),
  'MainScreen': () => const MainScreen(),
  'CalendarScreen': () => const CalendarScreen(),
  'GoalsScreen': () => const GoalsScreen(),
  'InsightsScreen': () => const InsightsScreen(),
  'HabitsScreen': () => const HabitsScreen(),
  'TransactionsScreen': () => const TransactionsScreen(),
  'AddTransactionScreen': () => const AddTransactionScreen(),
  'AddExpenseScreen': () => const AddExpenseScreen(),
  'UserProfileScreen': () => const UserProfileScreen(),
  'UserSettingsScreen': () => const UserSettingsScreen(),
  'BudgetSettingsScreen': () => const BudgetSettingsScreen(),
  'DailyBudgetScreen': () => const DailyBudgetScreen(),
};

/// Refuses every socket, so a screen that fires a request on build cannot
/// reach the network from a unit test.
class _NoNetwork extends HttpOverrides {
  @override
  HttpClient createHttpClient(SecurityContext? context) =>
      throw const SocketException('network disabled in tests');
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  // Belt and braces on top of flutter_test's own override: no test in this
  // suite may reach a real host, least of all production.
  HttpOverrides.global = _NoNetwork();
  SharedPreferences.setMockInitialValues(<String, Object>{});
  setUpAll(_loadRealFonts);

  for (final entry in _screens.entries) {
    // inset 0 = keyboard down, 300 = keyboard up.
    for (final inset in const <double>[0, 300]) {
      testWidgets('${entry.key} does not overflow at 360x640 (inset $inset)',
          (tester) async {
        tester.view.physicalSize = const Size(360, 640);
        tester.view.devicePixelRatio = 1.0;
        addTearDown(tester.view.resetPhysicalSize);
        addTearDown(tester.view.resetDevicePixelRatio);

        final overflows = <String>{};
        final previousOnError = FlutterError.onError;
        // Restored in the tearDown below — leaving it swapped trips a binding
        // assertion in every later test.
        addTearDown(() => FlutterError.onError = previousOnError);
        // Only layout overflow is in scope. These screens are built bare —
        // no session, no backend — so they legitimately raise unrelated
        // runtime errors while rendering their loading/empty state; failing on
        // those would test the harness, not the layout.
        FlutterError.onError = (details) {
          final text = details.exceptionAsString();
          if (text.contains('overflowed by')) {
            overflows.add(text);
            return;
          }
          // Not in scope, but must still reach the binding: swallowing every
          // error leaves _pendingExceptionDetails unset and trips its
          // "overrode FlutterError.onError" assertion.
          previousOnError?.call(details);
        };

        await tester.pumpWidget(_hostApp(entry.value(), bottomInset: inset));
        await tester.pump();
        await tester.pump(const Duration(milliseconds: 1200));
        await tester.pump(const Duration(seconds: 2));

        expect(
          overflows,
          isEmpty,
          reason:
              '${entry.key} overflows at 360x640 with bottom inset $inset:\n'
              '${overflows.join("\n")}',
        );
      });
    }
  }
}
