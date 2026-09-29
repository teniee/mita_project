/// Insights → Recommendations must not render the Budget Optimization card.
///
/// The card scored month-to-date spending against hard-coded income-tier
/// weights (CohortService.getCohortBudgetOptimization), not against the
/// user's saved plan. Those weights are keyed "housing" and "savings" — keys
/// no recordable expense category produces — so both always read $0. A user
/// whose only big expense was rent was scored around 50% and told they had
/// "room to increase housing spending". That is fabricated guidance shown as a
/// measured result, so the card is removed until it can be rebuilt from the
/// user's real budget.
///
/// The fakes below reproduce the exact production precondition: a profile
/// with income and at least one recorded expense this month. Every network
/// call fails, which is fine — the peer/cohort/tips calls degrade to their
/// fallbacks and the card was computed locally anyway.
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
import 'package:mita/screens/insights_screen.dart';
import 'package:mita/services/cohort_service.dart';
import 'package:mita/services/security_monitor.dart';
import 'package:mita/theme/mita_theme.dart';

class _NoNetwork extends HttpOverrides {
  @override
  HttpClient createHttpClient(SecurityContext? context) =>
      throw const SocketException('network disabled in tests');
}

const double _income = 5000.0;

/// Real recordable categories (add_transaction_screen.dart): a rent payment
/// and some food. Neither maps to the "housing" or "savings" weight keys.
const Map<String, double> _spending = {'rent': 1500.0, 'food': 300.0};

class _IncomeUserProvider extends UserProvider {
  @override
  UserState get state => UserState.authenticated;

  @override
  bool get isLoading => false;

  @override
  double get userIncome => _income;

  @override
  Future<void> initialize() async {}
}

class _SpendingTransactionProvider extends TransactionProvider {
  @override
  TransactionState get state => TransactionState.loaded;

  @override
  Map<String, double> get spendingByCategory => _spending;

  @override
  Future<void> initialize() async {}

  @override
  Future<void> loadMonthlyTransactions({
    required int year,
    required int month,
    String? category,
  }) async {}
}

class _LoadedBudgetProvider extends BudgetProvider {
  @override
  BudgetState get state => BudgetState.loaded;

  @override
  Future<void> initialize() async {}
}

Widget _host() => MultiProvider(
      providers: [
        ChangeNotifierProvider<SettingsProvider>(
            create: (_) => SettingsProvider()),
        ChangeNotifierProvider<BudgetProvider>(
            create: (_) => _LoadedBudgetProvider()),
        ChangeNotifierProvider<TransactionProvider>(
            create: (_) => _SpendingTransactionProvider()),
        ChangeNotifierProvider<GoalsProvider>(create: (_) => GoalsProvider()),
        ChangeNotifierProvider<HabitsProvider>(create: (_) => HabitsProvider()),
        ChangeNotifierProvider<BehavioralProvider>(
            create: (_) => BehavioralProvider()),
        ChangeNotifierProvider<MoodProvider>(create: (_) => MoodProvider()),
        ChangeNotifierProvider<AdviceProvider>(create: (_) => AdviceProvider()),
        ChangeNotifierProvider<LoadingProvider>(
            create: (_) => LoadingProvider()),
        ChangeNotifierProvider<UserProvider>(
            create: (_) => _IncomeUserProvider()),
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
        home: const InsightsScreen(),
      ),
    );

Future<void> _openRecommendations(WidgetTester tester) async {
  await tester.pumpWidget(_host());
  await tester.pump();
  await tester.pump(const Duration(milliseconds: 1200));
  await tester.pump(const Duration(seconds: 3));
  await tester.tap(find.text('Recommendations'));
  await tester.pump();
  await tester.pump(const Duration(seconds: 1));
}

/// Touching ApiService starts SecurityMonitor's 5-minute periodic timer,
/// which outlives the widget tree and trips the binding's "A Timer is still
/// pending" invariant on whichever test constructed the singleton. The
/// trailing pump drains the request timeout timers the failed calls armed.
Future<void> _drain(WidgetTester tester) async {
  await tester.pumpWidget(const SizedBox.shrink());
  await tester.pump(const Duration(minutes: 3));
  SecurityMonitor.instance.stopMonitoring();
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  HttpOverrides.global = _NoNetwork();
  SharedPreferences.setMockInitialValues(<String, Object>{});
  // getToken() blocks on the secure-storage platform channel, and
  // fetchAIInsights awaits it before leaving the loading state.
  TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
      .setMockMethodCallHandler(
    const MethodChannel('plugins.it_nomads.com/flutter_secure_storage'),
    (call) async => call.method == 'readAll' ? <String, String>{} : null,
  );

  testWidgets('Recommendations renders no Budget Optimization card',
      (tester) async {
    await _openRecommendations(tester);

    // Guard against a vacuous pass: the tab must actually be showing its
    // content (not the income-required or empty state).
    expect(find.text('Personalized Recommendations'), findsOneWidget,
        reason: 'the Recommendations tab must be rendered for this to mean '
            'anything');

    expect(find.text('Budget Optimization'), findsNothing,
        reason: 'the card scores spending against invented tier weights');
    expect(find.text('Optimization Suggestions:'), findsNothing);
    await _drain(tester);
  });

  testWidgets('no fabricated optimization score is rendered', (tester) async {
    // The score the removed card would have shown for this exact input.
    final fabricated =
        CohortService().getCohortBudgetOptimization(_income, Map.of(_spending));
    final score = '${(fabricated['overall_score'] as num).toStringAsFixed(0)}%';

    await _openRecommendations(tester);

    expect(find.text('Personalized Recommendations'), findsOneWidget);
    expect(find.text(score), findsNothing,
        reason: '$score is derived from hard-coded weights, not a measurement');
    await _drain(tester);
  });

  testWidgets('no fabricated category recommendations are rendered',
      (tester) async {
    await _openRecommendations(tester);

    expect(find.text('Personalized Recommendations'), findsOneWidget);

    // "housing" and "savings" can never be recorded, so the old card always
    // told this user to increase them despite a real rent payment.
    expect(find.textContaining('increase housing'), findsNothing,
        reason: 'rent was recorded; "increase housing" is fabricated');
    expect(find.textContaining('increase savings'), findsNothing);
    expect(find.textContaining('room to increase'), findsNothing);
    expect(find.textContaining('Consider reducing'), findsNothing);
    await _drain(tester);
  });
}
