/// A user must never be shown synthetic financial or behavioural data as
/// though it were their own.
///
/// Found during the pre-launch pass, all on the day-one path:
///   * Insights invented an "AI Financial Analysis" — rating B+, risk
///     moderate, and a sentence asserting the user was "doing well with food
///     budgeting" — whenever the snapshot call failed.
///   * Insights generated fourteen days of daily spending from the user's
///     income when there were no transactions, and drew it as a trend.
///   * Insights defaulted a missing health score/grade to 75 / "B+".
///   * The Mood tab rendered a fixed week of moods (happy Mon, neutral Tue,
///     sad Wed …) that the user had never entered.
///   * Recommendations claimed hardcoded peer evidence — "71% adopt" badges
///     under "Based on successful Strategic Achiever patterns" and "Popular
///     goals among Strategic Achiever users" — while the cohort had no members
///     at all; the percentages are a fixed table in cohort_service.dart.
///   * Budget Optimization defaulted a missing overall_score to a green 100%.
///   * The dashboard synthesised "Today's Budget Targets" by splitting
///     income/30 across default weights whenever the calendar had not loaded
///     yet — rendering invented figures, in categories the planner does not
///     even use, in the same cards as the real plan.
///
/// This suite pumps Insights with every network call failing — the exact
/// condition that used to trigger the fabrications — and asserts the honest
/// empty states appear instead.
///
/// Mood is not covered here: MoodScreen.initState calls
/// ReminderService.scheduleDailyReminder, whose notifications plugin throws
/// asynchronously under flutter_test and fails the test before anything is
/// asserted. Its empty state is verified on-device instead.
library;

import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:mita/l10n/generated/app_localizations.dart';
import 'package:mita/providers/providers.dart';
import 'package:mita/screens/insights_screen.dart';
import 'package:mita/screens/main_screen.dart';
import 'package:mita/theme/mita_theme.dart';

class _NoNetwork extends HttpOverrides {
  @override
  HttpClient createHttpClient(SecurityContext? context) =>
      throw const SocketException('network disabled in tests');
}

Widget _host(Widget home) => MultiProvider(
      providers: [
        ChangeNotifierProvider<SettingsProvider>(
            create: (_) => SettingsProvider()),
        ChangeNotifierProvider<BudgetProvider>(create: (_) => BudgetProvider()),
        ChangeNotifierProvider<TransactionProvider>(
            create: (_) => TransactionProvider()),
        ChangeNotifierProvider<GoalsProvider>(create: (_) => GoalsProvider()),
        ChangeNotifierProvider<HabitsProvider>(create: (_) => HabitsProvider()),
        ChangeNotifierProvider<BehavioralProvider>(
            create: (_) => BehavioralProvider()),
        ChangeNotifierProvider<MoodProvider>(create: (_) => MoodProvider()),
        ChangeNotifierProvider<AdviceProvider>(create: (_) => AdviceProvider()),
        ChangeNotifierProvider<LoadingProvider>(
            create: (_) => LoadingProvider()),
        ChangeNotifierProvider<UserProvider>(create: (_) => UserProvider()),
      ],
      child: MaterialApp(
        theme: MitaTheme.lightTheme,
        localizationsDelegates: const [
          AppLocalizations.delegate,
          GlobalMaterialLocalizations.delegate,
          GlobalWidgetsLocalizations.delegate,
          GlobalCupertinoLocalizations.delegate,
        ],
        supportedLocales: AppLocalizations.supportedLocales,
        home: home,
      ),
    );

/// Render and let it settle. Errors are forwarded to the binding rather than
/// swallowed: swallowing leaves `_pendingExceptionDetails` unset and trips the
/// binding's "overrode FlutterError.onError" assertion.
Future<void> _settle(WidgetTester tester, Widget home) async {
  await tester.pumpWidget(_host(home));
  await tester.pump();
  await tester.pump(const Duration(milliseconds: 1200));
  await tester.pump(const Duration(seconds: 3));
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  HttpOverrides.global = _NoNetwork();
  SharedPreferences.setMockInitialValues(<String, Object>{});

  group('Dashboard invents no budget targets', () {
    testWidgets('no default-weight categories are rendered as targets',
        (tester) async {
      await _settle(tester, const MainScreen());

      // These four labels were produced *only* by the removed fallback; the
      // planner's own vocabulary is "groceries" / "transport public" /
      // "coffee". Their presence would mean invented targets are back.
      for (final invented in const [
        'Food & Dining',
        'Transportation',
        'Entertainment',
        'Shopping',
      ]) {
        expect(find.text(invented), findsNothing,
            reason: '"\$invented" is a default-weight invention, not a plan');
      }
    });

    testWidgets('shows loading or honest copy, never invented figures',
        (tester) async {
      await _settle(tester, const MainScreen());

      // Bare, with no session, the dashboard sits in its loading state. Either
      // that or the "no targets" copy is honest; inventing figures is not.
      final loading = find.byType(CircularProgressIndicator);
      final honest = find.text('No budget targets set for today');
      expect(
          loading.evaluate().isNotEmpty || honest.evaluate().isNotEmpty, isTrue,
          reason: 'the dashboard must load or say it has nothing, not invent');
    });
  });

  group('Recommendations claim no peer evidence it does not have', () {
    testWidgets('no adoption percentages are rendered', (tester) async {
      await _settle(tester, const InsightsScreen());

      // The hardcoded table in cohort_service.dart contains these exact
      // values; none of them may reach the screen as a peer statistic.
      expect(find.textContaining('% adopt'), findsNothing,
          reason: 'adoption rates are hardcoded, not measured');
      for (final pct in const ['78%', '65%', '82%', '73%', '68%', '81%']) {
        expect(find.textContaining('\$pct adopt'), findsNothing);
      }
    });

    testWidgets('no cohort-evidence language without a cohort', (tester) async {
      await _settle(tester, const InsightsScreen());

      expect(find.textContaining('Based on successful'), findsNothing,
          reason: 'implies measured peer outcomes that do not exist');
      expect(find.textContaining('Popular goals among'), findsNothing);
      expect(find.textContaining('users like you'), findsNothing);
    });

    testWidgets('no invented 100% optimization score', (tester) async {
      await _settle(tester, const InsightsScreen());
      expect(find.text('100%'), findsNothing,
          reason: 'a missing overall_score must not read as a perfect budget');
    });
  });

  group('Insights invents nothing when there is no data', () {
    testWidgets('no fabricated AI verdict', (tester) async {
      await _settle(tester, const InsightsScreen());

      // The exact sentence the old catch-block asserted about the user.
      expect(
          find.textContaining('doing well with food budgeting'), findsNothing,
          reason: 'a fabricated financial assessment must never render');
      expect(find.textContaining('good discipline'), findsNothing);
    });

    testWidgets('no invented health grade', (tester) async {
      await _settle(tester, const InsightsScreen());

      // 75 / "B+" was the old default for a score the server never sent.
      expect(find.text('75'), findsNothing,
          reason: 'a missing health score must not default to 75');
    });

    testWidgets('shows loading or honest empty copy, never an analysis',
        (tester) async {
      await _settle(tester, const InsightsScreen());

      // With every call failing the screen may still be loading. Either is
      // honest; what must never appear is a rendered verdict.
      final loading = find.byType(CircularProgressIndicator);
      final honestCopy = find.byWidgetPredicate((w) =>
          w is Text &&
          ((w.data ?? '').toLowerCase().contains('no insights') ||
              ((w.data ?? '').toLowerCase().contains('add') &&
                  (w.data ?? '').toLowerCase().contains('transaction')) ||
              (w.data ?? '').toLowerCase().contains('analyzing')));
      expect(
        loading.evaluate().isNotEmpty || honestCopy.evaluate().isNotEmpty,
        isTrue,
        reason: 'Insights must be loading or say plainly that there is no '
            'data — it must not render a verdict it does not have',
      );

      // And the verdict card itself must be absent.
      expect(find.textContaining('Rating:'), findsNothing);
    });
  });
}
