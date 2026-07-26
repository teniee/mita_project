import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mita/models/transaction_model.dart';
import 'package:mita/providers/budget_provider.dart';
import 'package:mita/providers/loading_provider.dart';
import 'package:mita/providers/settings_provider.dart';
import 'package:mita/providers/transaction_provider.dart';
import 'package:mita/services/api_service.dart';
import 'package:mita/services/budget_adapter_service.dart';
import 'package:mita/services/income_service.dart';
import 'package:mita/services/live_updates_service.dart';
import 'package:mita/services/onboarding_state.dart';
import 'package:mita/services/transaction_service.dart';
import 'package:mocktail/mocktail.dart';
import 'package:shared_preferences/shared_preferences.dart';

class _MockApiService extends Mock implements ApiService {}

class _MockBudgetAdapterService extends Mock implements BudgetAdapterService {}

class _MockLiveUpdatesService extends Mock implements LiveUpdatesService {}

class _MockTransactionService extends Mock implements TransactionService {}

TransactionModel _transaction(String id, double amount) {
  final timestamp = DateTime.utc(2026, 7, 25, 12);
  return TransactionModel(
    id: id,
    category: 'food',
    amount: amount,
    spentAt: timestamp,
    createdAt: timestamp,
  );
}

void _stubTransactionLoads(
  _MockTransactionService service,
  Future<List<TransactionModel>> Function() response,
) {
  when(
    () => service.getTransactions(
      category: any(named: 'category'),
      startDate: any(named: 'startDate'),
      endDate: any(named: 'endDate'),
      limit: any(named: 'limit'),
    ),
  ).thenAnswer((_) => response());
}

List<String> _intelligenceMessages(Map<String, dynamic> result) {
  return (result['suggestions'] as List<dynamic>)
      .cast<Map<String, dynamic>>()
      .where((item) => item['type'] == 'intelligence')
      .map((item) => item['message'] as String)
      .toList();
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('budget session boundary', () {
    test('BudgetProvider propagates reset to its adapter', () {
      final adapter = _MockBudgetAdapterService();
      final provider = BudgetProvider(
        apiService: _MockApiService(),
        budgetService: adapter,
        liveUpdates: _MockLiveUpdatesService(),
      );

      provider.resetSession();

      verify(adapter.resetSession).called(1);
      expect(provider.state, BudgetState.initial);
      expect(provider.dailyBudgets, isEmpty);
      expect(provider.liveBudgetStatus, isEmpty);
    });

    test('provider reset drops the singleton adapter cache between accounts',
        () async {
      SharedPreferences.setMockInitialValues(<String, Object>{});
      final onboarding = OnboardingState.instance;
      final adapter = BudgetAdapterService();
      await onboarding.reset();
      adapter.resetSession();

      onboarding
        ..countryCode = 'US'
        ..stateCode = 'TX'
        ..income = 1000
        ..incomeTier = IncomeTier.low
        ..goals = <String>[]
        ..habits = <String>[]
        ..expenses = <Map<String, dynamic>>[];
      final accountA =
          _intelligenceMessages(await adapter.getEnhancedBudgetSuggestions());

      onboarding
        ..income = 20000
        ..incomeTier = IncomeTier.high;
      final cachedAccountA =
          _intelligenceMessages(await adapter.getEnhancedBudgetSuggestions());
      expect(cachedAccountA, accountA,
          reason: 'the one-hour adapter cache is active before reset');

      final provider = BudgetProvider(
        apiService: _MockApiService(),
        budgetService: adapter,
        liveUpdates: _MockLiveUpdatesService(),
      );
      provider.resetSession();

      final accountB =
          _intelligenceMessages(await adapter.getEnhancedBudgetSuggestions());
      expect(accountB, isNot(accountA),
          reason: 'account B must be recalculated after the provider reset');

      await onboarding.reset();
      adapter.resetSession();
    });

    test('newest same-session daily budget response wins', () async {
      final api = _MockApiService();
      final first = Completer<List<dynamic>>();
      final second = Completer<List<dynamic>>();
      var requestCount = 0;
      when(api.getDailyBudgets).thenAnswer((_) {
        requestCount += 1;
        return requestCount == 1 ? first.future : second.future;
      });
      final provider = BudgetProvider(
        apiService: api,
        budgetService: _MockBudgetAdapterService(),
        liveUpdates: _MockLiveUpdatesService(),
      );

      final oldLoad = provider.loadDailyBudgets();
      final newLoad = provider.loadDailyBudgets();
      second.complete(<Map<String, dynamic>>[
        <String, dynamic>{'date': '2026-07-25', 'spent': 20},
      ]);
      await newLoad;
      first.complete(<Map<String, dynamic>>[
        <String, dynamic>{'date': '2026-07-24', 'spent': 10},
      ]);
      await oldLoad;

      expect(provider.dailyBudgets.single['date'], '2026-07-25');
      expect(provider.dailyBudgets.single['spent'], 20);
    });
  });

  test(
      'SettingsProvider reset preserves device theme and locale while '
      'removing account preferences', () async {
    SharedPreferences.setMockInitialValues(<String, Object>{
      'theme_mode': 'dark',
      'locale': 'ru',
      'notifications_enabled': false,
      'biometrics_enabled': true,
      'default_currency': 'EUR',
      'budget_reminder_enabled': false,
      'weekly_report_enabled': false,
    });
    final provider = SettingsProvider();
    await provider.initialize();

    provider.resetSession();
    await Future<void>.delayed(Duration.zero);

    expect(provider.themeMode, ThemeMode.dark);
    expect(provider.locale, const Locale('ru'));
    expect(provider.notificationsEnabled, isTrue);
    expect(provider.biometricsEnabled, isFalse);
    expect(provider.defaultCurrency, 'USD');
    expect(provider.budgetReminderEnabled, isTrue);
    expect(provider.weeklyReportEnabled, isTrue);

    final prefs = await SharedPreferences.getInstance();
    expect(prefs.getString('theme_mode'), 'dark');
    expect(prefs.getString('locale'), 'ru');
    expect(prefs.containsKey('notifications_enabled'), isFalse);
    expect(prefs.containsKey('biometrics_enabled'), isFalse);
    expect(prefs.containsKey('default_currency'), isFalse);
    expect(prefs.containsKey('budget_reminder_enabled'), isFalse);
    expect(prefs.containsKey('weekly_report_enabled'), isFalse);
  });

  test('LoadingProvider ignores a stale finalizer after reset', () async {
    final provider = LoadingProvider();
    final accountA = Completer<void>();
    final accountB = Completer<void>();

    final oldOperation = provider.runWithLoading(() => accountA.future);
    expect(provider.isLoading, isTrue);

    provider.reset();
    final newOperation = provider.runWithLoading(() => accountB.future);
    expect(provider.isLoading, isTrue);

    accountA.complete();
    await oldOperation;
    expect(provider.isLoading, isTrue,
        reason: 'account A must not clear account B loading state');

    accountB.complete();
    await newOperation;
    expect(provider.isLoading, isFalse);
  });

  test('OnboardingState reset clears memory and persisted progress', () async {
    SharedPreferences.setMockInitialValues(<String, Object>{});
    final onboarding = OnboardingState.instance;
    await onboarding.reset();
    onboarding
      ..countryCode = 'BG'
      ..stateCode = 'VAR'
      ..income = 5000
      ..incomeTier = IncomeTier.middle
      ..expenses = <Map<String, dynamic>>[
        <String, dynamic>{'category': 'housing', 'amount': 1200},
      ]
      ..goals = <String>['save_more']
      ..savingsGoalAmount = 10000
      ..habits = <String>['track_spending']
      ..habitsComment = 'Account A'
      ..spendingFrequencies = <String, int>{'food': 4};
    await onboarding.save();

    final prefs = await SharedPreferences.getInstance();
    expect(
      jsonDecode(prefs.getString('onboarding_state')!) as Map<String, dynamic>,
      containsPair('countryCode', 'BG'),
    );

    final reset = onboarding.reset();
    expect(onboarding.countryCode, isNull);
    expect(onboarding.stateCode, isNull);
    expect(onboarding.income, isNull);
    expect(onboarding.incomeTier, isNull);
    expect(onboarding.expenses, isEmpty);
    expect(onboarding.goals, isEmpty);
    expect(onboarding.savingsGoalAmount, isNull);
    expect(onboarding.habits, isEmpty);
    expect(onboarding.habitsComment, isNull);
    expect(onboarding.spendingFrequencies, isNull);

    await reset;
    expect(prefs.containsKey('onboarding_state'), isFalse);
  });

  group('transaction mutation invalidates a pre-mutation list response', () {
    test('create keeps the newly created transaction', () async {
      final service = _MockTransactionService();
      final staleList = Completer<List<TransactionModel>>();
      _stubTransactionLoads(service, () => staleList.future);
      final input = TransactionInput(amount: 20, category: 'food');
      final created = _transaction('created', 20);
      when(() => service.createTransaction(input))
          .thenAnswer((_) async => created);
      final provider = TransactionProvider(
        apiService: _MockApiService(),
        transactionService: service,
      );

      final oldLoad = provider.loadTransactions();
      await provider.createTransaction(input);
      staleList.complete(<TransactionModel>[]);
      await oldLoad;

      expect(provider.transactions.map((item) => item.id), <String>['created']);
      expect(provider.totalSpending, 20);
    });

    test('update keeps the mutated amount', () async {
      final service = _MockTransactionService();
      final original = _transaction('transaction', 10);
      final updated = _transaction('transaction', 25);
      final staleList = Completer<List<TransactionModel>>();
      var loadCount = 0;
      _stubTransactionLoads(service, () {
        loadCount += 1;
        return loadCount == 1
            ? Future<List<TransactionModel>>.value(<TransactionModel>[original])
            : staleList.future;
      });
      final input = TransactionInput(amount: 25, category: 'food');
      when(() => service.updateTransaction('transaction', input))
          .thenAnswer((_) async => updated);
      final provider = TransactionProvider(
        apiService: _MockApiService(),
        transactionService: service,
      );
      await provider.loadTransactions();

      final oldLoad = provider.loadTransactions();
      await provider.updateTransaction('transaction', input);
      staleList.complete(<TransactionModel>[original]);
      await oldLoad;

      expect(provider.transactions.single.amount, 25);
      expect(provider.totalSpending, 25);
    });

    test('delete does not resurrect the removed transaction', () async {
      final service = _MockTransactionService();
      final original = _transaction('transaction', 10);
      final staleList = Completer<List<TransactionModel>>();
      var loadCount = 0;
      _stubTransactionLoads(service, () {
        loadCount += 1;
        return loadCount == 1
            ? Future<List<TransactionModel>>.value(<TransactionModel>[original])
            : staleList.future;
      });
      when(() => service.deleteTransaction('transaction'))
          .thenAnswer((_) async => true);
      final provider = TransactionProvider(
        apiService: _MockApiService(),
        transactionService: service,
      );
      await provider.loadTransactions();

      final oldLoad = provider.loadTransactions();
      await provider.deleteTransaction('transaction');
      staleList.complete(<TransactionModel>[original]);
      await oldLoad;

      expect(provider.transactions, isEmpty);
      expect(provider.totalSpending, 0);
    });
  });
}
