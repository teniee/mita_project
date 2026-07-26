import 'dart:async';

import 'package:flutter_test/flutter_test.dart';
import 'package:mita/models/transaction_model.dart';
import 'package:mita/providers/budget_provider.dart';
import 'package:mita/providers/transaction_provider.dart';
import 'package:mita/providers/user_provider.dart';
import 'package:mita/services/api_service.dart';
import 'package:mita/services/budget_adapter_service.dart';
import 'package:mita/services/iap_service.dart';
import 'package:mita/services/live_updates_service.dart';
import 'package:mita/services/transaction_service.dart';
import 'package:mita/services/user_data_manager.dart';
import 'package:mocktail/mocktail.dart';
import 'package:shared_preferences/shared_preferences.dart';

class _MockApiService extends Mock implements ApiService {}

class _MockBudgetAdapterService extends Mock implements BudgetAdapterService {}

class _MockIapService extends Mock implements IapService {}

class _MockLiveUpdatesService extends Mock implements LiveUpdatesService {}

class _MockTransactionService extends Mock implements TransactionService {}

class _MockUserDataManager extends Mock implements UserDataManager {}

TransactionModel _transaction(String id, double amount) {
  final timestamp = DateTime.utc(2026, 7, 24, 12);
  return TransactionModel(
    id: id,
    category: 'food',
    amount: amount,
    spentAt: timestamp,
    createdAt: timestamp,
  );
}

void _stubTransactionLoad(
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

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  SharedPreferences.setMockInitialValues(<String, Object>{});

  test('logout clears account state before remote revocation completes',
      () async {
    final api = _MockApiService();
    final manager = _MockUserDataManager();
    final iap = _MockIapService();
    final logoutCompleter = Completer<void>();
    var boundaryCalls = 0;

    when(api.getToken).thenAnswer((_) async => 'token');
    when(() => api.hasActiveSession).thenReturn(false);
    when(manager.beginSessionBoundary).thenReturn(1);
    when(manager.initialize).thenAnswer((_) async {});
    when(manager.getUserProfile).thenAnswer(
      (_) async => {'name': 'Account A', 'email': 'a@example.com'},
    );
    when(manager.hasCompletedOnboarding).thenAnswer((_) async => true);
    when(manager.getFinancialContext).thenAnswer(
      (_) async => {'income': 5000.0},
    );
    when(api.logout).thenAnswer((_) => logoutCompleter.future);
    when(manager.clearUserData).thenAnswer((_) async {});
    when(iap.resetSession).thenAnswer((_) async {});

    final provider = UserProvider(
      apiService: api,
      iapService: iap,
      userDataManager: manager,
      onSessionBoundary: () => boundaryCalls += 1,
    );
    await provider.initialize();
    expect(provider.state, UserState.authenticated);
    expect(provider.userName, 'Account A');

    boundaryCalls = 0;
    final logoutFuture = provider.logout();

    expect(boundaryCalls, 1);
    expect(provider.state, UserState.unauthenticated);
    expect(provider.userProfile, isEmpty);
    expect(provider.financialContext, isEmpty);

    logoutCompleter.complete();
    await logoutFuture;

    verify(api.logout).called(1);
    verify(manager.clearUserData).called(1);
    verify(iap.resetSession).called(1);
  });

  test('remote logout failure cannot restore local account state', () async {
    final api = _MockApiService();
    final manager = _MockUserDataManager();
    final iap = _MockIapService();
    var boundaryCalls = 0;

    when(api.logout).thenThrow(Exception('offline'));
    when(manager.clearUserData).thenAnswer((_) async {});
    when(iap.resetSession).thenAnswer((_) async {});

    final provider = UserProvider(
      apiService: api,
      iapService: iap,
      userDataManager: manager,
      onSessionBoundary: () => boundaryCalls += 1,
    );

    await provider.logout();

    expect(boundaryCalls, 1);
    expect(provider.state, UserState.unauthenticated);
    expect(provider.userProfile, isEmpty);
    expect(provider.isLoading, isFalse);
    verify(api.logout).called(1);
    verify(manager.clearUserData).called(1);
    verify(iap.resetSession).called(1);
  });

  test('a late account A logout cannot overwrite account B initialization',
      () async {
    final api = _MockApiService();
    final manager = _MockUserDataManager();
    final iap = _MockIapService();
    final accountALogout = Completer<void>();

    when(api.logout).thenAnswer((_) => accountALogout.future);
    when(() => api.hasActiveSession).thenReturn(true);
    when(api.getToken).thenAnswer((_) async => 'account-b-token');
    when(manager.beginSessionBoundary).thenReturn(1);
    when(manager.clearUserData).thenAnswer((_) async {});
    when(manager.initialize).thenAnswer((_) async {});
    when(manager.getUserProfile).thenAnswer(
      (_) async => {'name': 'Account B', 'email': 'b@example.com'},
    );
    when(manager.hasCompletedOnboarding).thenAnswer((_) async => true);
    when(manager.getFinancialContext).thenAnswer(
      (_) async => {'income': 7000.0},
    );
    when(iap.resetSession).thenAnswer((_) async {});

    final provider = UserProvider(
      apiService: api,
      iapService: iap,
      userDataManager: manager,
    );

    final oldLogout = provider.logout();
    await provider.initialize();
    expect(provider.state, UserState.authenticated);
    expect(provider.userName, 'Account B');

    accountALogout.complete();
    await oldLogout;

    expect(provider.state, UserState.authenticated);
    expect(provider.userName, 'Account B');
    expect(provider.isLoading, isFalse);
  });

  test('old live status cannot overwrite a new session', () async {
    final api = _MockApiService();
    final accountA = Completer<Map<String, dynamic>>();
    final accountB = Completer<Map<String, dynamic>>();
    var request = 0;

    when(api.getLiveBudgetStatus).thenAnswer((_) {
      request += 1;
      return request == 1 ? accountA.future : accountB.future;
    });

    final provider = BudgetProvider(
      apiService: api,
      budgetService: _MockBudgetAdapterService(),
      liveUpdates: _MockLiveUpdatesService(),
    );
    final oldLoad = provider.loadLiveBudgetStatus();
    provider.resetSession();
    final newLoad = provider.loadLiveBudgetStatus();

    accountB.complete({
      'monthly_budget': 2000.0,
      'monthly_spent': 20.0,
      'transaction_count': 2,
    });
    await newLoad;
    accountA.complete({
      'monthly_budget': 1000.0,
      'monthly_spent': 10.0,
      'transaction_count': 1,
    });
    await oldLoad;

    expect(provider.liveStatusFresh, isTrue);
    expect(provider.monthlyTransactionCount, 2);
    expect(provider.totalSpent, 20.0);
  });

  test('newest same-session live status wins and current failure is explicit',
      () async {
    final api = _MockApiService();
    final first = Completer<Map<String, dynamic>>();
    final second = Completer<Map<String, dynamic>>();
    var request = 0;

    when(api.getLiveBudgetStatus).thenAnswer((_) {
      request += 1;
      if (request == 1) return first.future;
      if (request == 2) return second.future;
      return Future<Map<String, dynamic>>.error(Exception('unavailable'));
    });

    final provider = BudgetProvider(
      apiService: api,
      budgetService: _MockBudgetAdapterService(),
      liveUpdates: _MockLiveUpdatesService(),
    );
    final firstLoad = provider.loadLiveBudgetStatus();
    final secondLoad = provider.loadLiveBudgetStatus();

    second.complete({
      'monthly_budget': 2000.0,
      'monthly_spent': 22.0,
      'transaction_count': 2,
    });
    await secondLoad;
    first.complete({
      'monthly_budget': 1000.0,
      'monthly_spent': 11.0,
      'transaction_count': 1,
    });
    await firstLoad;

    expect(provider.monthlyTransactionCount, 2);
    expect(provider.totalSpent, 22.0);

    await provider.loadLiveBudgetStatus();
    expect(provider.liveStatusFresh, isFalse);
    expect(provider.liveStatusError, isNotNull);
    expect(provider.monthlyTransactionCount, isNull);
    expect(provider.liveBudgetStatus, isEmpty);
  });

  test('transaction initialize restarts after reset and discards account A',
      () async {
    final api = _MockApiService();
    final service = _MockTransactionService();
    final accountA = Completer<List<TransactionModel>>();
    final accountB = Completer<List<TransactionModel>>();
    var request = 0;

    when(api.getToken).thenAnswer((_) async => 'token');
    _stubTransactionLoad(service, () {
      request += 1;
      return request == 1 ? accountA.future : accountB.future;
    });

    final provider = TransactionProvider(
      apiService: api,
      transactionService: service,
    );
    final oldInitialize = provider.initialize();
    await Future<void>.delayed(Duration.zero);

    provider.resetSession();
    final newInitialize = provider.initialize();
    await Future<void>.delayed(Duration.zero);

    accountB.complete([_transaction('account-b', 20.0)]);
    await newInitialize;
    accountA.complete([_transaction('account-a', 10.0)]);
    await oldInitialize;

    expect(provider.state, TransactionState.loaded);
    expect(provider.transactions.map((item) => item.id), ['account-b']);
    expect(provider.totalSpending, 20.0);
    expect(provider.spendingByCategory, {'food': 20.0});
  });

  test('transaction reset clears filters, totals, errors, and loading',
      () async {
    final api = _MockApiService();
    final service = _MockTransactionService();
    final pending = Completer<List<TransactionModel>>();

    _stubTransactionLoad(service, () => pending.future);
    final provider = TransactionProvider(
      apiService: api,
      transactionService: service,
    );

    final load = provider.loadTransactionsByDateRange(
      startDate: DateTime(2026, 7, 1),
      endDate: DateTime(2026, 7, 31),
      category: 'food',
    );
    expect(provider.isLoading, isTrue);
    expect(provider.selectedCategory, 'food');

    provider.resetSession();
    expect(provider.transactions, isEmpty);
    expect(provider.spendingByCategory, isEmpty);
    expect(provider.totalSpending, 0.0);
    expect(provider.selectedCategory, isNull);
    expect(provider.startDate, isNull);
    expect(provider.endDate, isNull);
    expect(provider.errorMessage, isNull);
    expect(provider.isLoading, isFalse);
    expect(provider.state, TransactionState.initial);

    pending.complete([_transaction('old', 99.0)]);
    await load;
    expect(provider.transactions, isEmpty);
  });
}
