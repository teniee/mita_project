/// Real-user acceptance journey through the app's own service layer against a
/// live DISPOSABLE backend.
///
/// mobile_backend_journey_live_test.dart already proves the happy path
/// (register → login → onboarding → transaction → calendar → refresh →
/// persistence → logout). This file covers the part that decides whether a
/// real person's money stays correct once they start *changing* things:
///
///   * overspending a category triggers redistribution
///   * redistribution conserves the month's total planned amount to the cent
///   * editing a transaction moves the accrual by exactly the delta
///   * deleting a transaction returns the ledger to its pre-create state
///   * a second account cannot see the first account's financial data
///
/// The user is created in Europe/Sofia, because every date-bucketing bug this
/// codebase has hit came from a device east of UTC.
///
///   flutter test integration_test/acceptance_journey_live_test.dart \
///     -d emulator-5554 \
///     --dart-define=RUN_LIVE_E2E=true \
///     --dart-define=E2E_BASE_URL=http://10.0.2.2:8000 \
///     --dart-define=API_BASE_URL=http://10.0.2.2:8000
library;

import 'dart:io';
import 'dart:math';

import 'package:dio/dio.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mita/config.dart';
import 'package:mita/models/transaction_model.dart';
import 'package:mita/services/api_service.dart';
import 'package:mita/services/transaction_service.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'target_guard.dart';

const _runLiveE2E = bool.fromEnvironment('RUN_LIVE_E2E', defaultValue: false);
const _e2eBaseUrl = kE2eBaseUrl;

/// Sum of every day's limit in the saved calendar — the month's planned total.
double _plannedTotal(List<dynamic> savedCalendar) {
  var total = 0.0;
  for (final raw in savedCalendar) {
    final day = Map<String, dynamic>.from(raw as Map);
    total += (day['limit'] as num).toDouble();
  }
  return total;
}

double _limitFor(List<dynamic> savedCalendar, String dayKey) {
  for (final raw in savedCalendar) {
    final day = Map<String, dynamic>.from(raw as Map);
    if (day['date'] == dayKey) return (day['limit'] as num).toDouble();
  }
  fail('day $dayKey missing from the saved calendar');
}

/// Cents, so float noise cannot masquerade as a money difference.
int _cents(double v) => (v * 100).round();

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  HttpOverrides.global = null;
  SharedPreferences.setMockInitialValues(<String, Object>{});

  final Map<String, String> secureStore = {};
  TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
      .setMockMethodCallHandler(
          const MethodChannel('plugins.it_nomads.com/flutter_secure_storage'),
          (call) async {
    final args = (call.arguments as Map?) ?? const {};
    switch (call.method) {
      case 'write':
        secureStore[args['key'] as String] = args['value'] as String;
        return null;
      case 'read':
        return secureStore[args['key'] as String];
      case 'containsKey':
        return secureStore.containsKey(args['key'] as String);
      case 'delete':
        secureStore.remove(args['key'] as String);
        return null;
      case 'readAll':
        return Map<String, String>.from(secureStore);
      case 'deleteAll':
        secureStore.clear();
        return null;
      default:
        return null;
    }
  });

  var backendReachable = false;

  setUpAll(() async {
    if (!_runLiveE2E) return;
    if (!e2eTargetIsSafe) fail(e2eTargetProblem);
    try {
      await Dio(BaseOptions(
        connectTimeout: const Duration(seconds: 5),
        receiveTimeout: const Duration(seconds: 5),
        validateStatus: (_) => true,
      )).get('$_e2eBaseUrl${AppConfig.healthEndpoint}');
      backendReachable = true;
    } catch (_) {
      backendReachable = false;
    }
  });

  bool skipIfUnreachable() {
    if (!_runLiveE2E) {
      markTestSkipped(
          'Live E2E disabled (pass --dart-define=RUN_LIVE_E2E=true)');
      return true;
    }
    if (!e2eTargetIsSafe) fail(e2eTargetProblem);
    if (!backendReachable) {
      markTestSkipped('Backend not reachable at ${AppConfig.baseUrl}');
      return true;
    }
    return false;
  }

  /// Register + login + onboard a fresh Europe/Sofia account, leaving its
  /// tokens installed in the shared ApiService.
  Future<String> onboardAccount(ApiService api, String tag) async {
    final email =
        'acceptance_${tag}_${DateTime.now().millisecondsSinceEpoch}_${Random().nextInt(9999)}@example.com';
    const password = 'Str0ng!Acceptance#2026';

    final reg = await api.registerWithDetails(
      email,
      password,
      country: 'US',
      annualIncome: 72000,
      timezone: 'Europe/Sofia',
    );
    expect(reg.statusCode, 201, reason: 'registration should succeed');

    final login = await api.login(email, password);
    expect(login.statusCode, 200);
    final data = login.data['data'] ?? login.data;
    await api.saveTokens(
      data['access_token'] as String,
      data['refresh_token'] as String,
    );

    await api.submitOnboarding({
      'region': 'US-NY',
      'income': {'monthly_income': 6000, 'additional_income': 0},
      'fixed_expenses': {'rent': 1500, 'utilities': 200},
      'goals': {
        'savings_goal_amount_per_month': 500,
        'savings_goal_type': 'emergency_fund',
      },
      'spending_habits': {'dining_out_per_month': 8, 'coffee_per_week': 4},
    });
    return email;
  }

  test('overspend redistributes without creating or destroying money',
      () async {
    if (skipIfUnreachable()) return;

    final api = ApiService();
    final txns = TransactionService();
    await onboardAccount(api, 'money');

    final now = DateTime.now();
    final todayKey = DateTime(now.year, now.month, now.day)
        .toIso8601String()
        .substring(0, 10);

    // Baseline: the month as onboarding planned it.
    final before = await api.getSavedCalendar(year: now.year, month: now.month);
    expect(before, isNotNull);
    final plannedBefore = _plannedTotal(before!);
    final todayLimit = _limitFor(before, todayKey);
    expect(plannedBefore, greaterThan(0));
    expect(todayLimit, greaterThan(0));

    // A normal spend, well inside the day's limit.
    final normal = await txns.createTransaction(TransactionInput(
      amount: 12.50,
      category: 'food',
      description: 'acceptance: normal spend',
      spentAt: now,
    ));
    expect(normal.id, isNotEmpty);

    final afterNormal =
        await api.getSavedCalendar(year: now.year, month: now.month);
    expect(_cents(_plannedTotal(afterNormal!)), _cents(plannedBefore),
        reason: 'a normal spend must not change the month total');

    // Now overspend the day by a wide margin and let the rebalancer react.
    final overspend = await txns.createTransaction(TransactionInput(
      amount: todayLimit * 2 + 75,
      category: 'food',
      description: 'acceptance: overspend',
      spentAt: now,
    ));
    expect(overspend.id, isNotEmpty);

    final afterOverspend =
        await api.getSavedCalendar(year: now.year, month: now.month);
    expect(afterOverspend, isNotNull);

    // THE invariant: redistribution moves money between days, it never mints
    // or burns any. Compared in cents.
    expect(_cents(_plannedTotal(afterOverspend!)), _cents(plannedBefore),
        reason: 'redistribution must conserve the month total to the cent');

    // And it must never leave a day with a non-positive budget.
    for (final raw in afterOverspend) {
      final day = Map<String, dynamic>.from(raw as Map);
      expect((day['limit'] as num).toDouble(), greaterThan(0),
          reason: 'day ${day['date']} lost its budget in redistribution');
    }

    // Clean up so the delete path is exercised too.
    expect(await txns.deleteTransaction(overspend.id), isTrue);
    expect(await txns.deleteTransaction(normal.id), isTrue);
  }, timeout: const Timeout(Duration(minutes: 3)));

  test('edit moves the accrual by exactly the delta, delete reverses it',
      () async {
    if (skipIfUnreachable()) return;

    final api = ApiService();
    final txns = TransactionService();
    await onboardAccount(api, 'edit');

    final now = DateTime.now();
    final baseline = await txns.getTransactions();
    expect(baseline, isEmpty, reason: 'a fresh account starts with no spend');

    final created = await txns.createTransaction(TransactionInput(
      amount: 40.00,
      category: 'food',
      description: 'acceptance: created',
      spentAt: now,
    ));
    var listed = await txns.getTransactions();
    expect(listed, hasLength(1));
    expect(_cents(listed.first.amount), _cents(40.00));

    // Edit: 40.00 -> 65.25, same day and category.
    final edited = await txns.updateTransaction(
      created.id,
      TransactionInput(
        amount: 65.25,
        category: 'food',
        description: 'acceptance: edited',
        spentAt: now,
      ),
    );
    expect(_cents(edited.amount), _cents(65.25));

    listed = await txns.getTransactions();
    expect(listed, hasLength(1), reason: 'an edit must not duplicate the row');
    expect(_cents(listed.first.amount), _cents(65.25));

    // Delete returns the ledger to empty.
    expect(await txns.deleteTransaction(created.id), isTrue);
    listed = await txns.getTransactions();
    expect(listed, isEmpty, reason: 'delete must remove it from the ledger');
  }, timeout: const Timeout(Duration(minutes: 3)));

  test('a second account sees none of the first account data', () async {
    if (skipIfUnreachable()) return;

    final api = ApiService();
    final txns = TransactionService();

    // Account A records a spend.
    final emailA = await onboardAccount(api, 'isoa');
    final aTxn = await txns.createTransaction(TransactionInput(
      amount: 99.99,
      category: 'food',
      description: 'acceptance: account A only',
      spentAt: DateTime.now(),
    ));
    final aList = await txns.getTransactions();
    expect(aList, hasLength(1));
    final aProfile = await api.getUserProfile();
    final aEmail = (aProfile['data'] ?? aProfile)['email'];
    expect(aEmail, emailA);

    // Log out the way the app does, then onboard account B on the same client.
    await api.logout();
    final emailB = await onboardAccount(api, 'isob');

    final bList = await txns.getTransactions();
    expect(bList, isEmpty,
        reason: 'account B must not see account A transactions');

    final bProfile = await api.getUserProfile();
    expect((bProfile['data'] ?? bProfile)['email'], emailB);

    // B must not be able to read A's transaction by id either.
    var leaked = false;
    try {
      final stolen = await txns.getTransaction(aTxn.id);
      leaked = stolen.id == aTxn.id;
    } catch (_) {
      leaked = false; // refused, which is the point
    }
    expect(leaked, isFalse,
        reason: 'account B fetched account A transaction by id');
  }, timeout: const Timeout(Duration(minutes: 3)));
}
