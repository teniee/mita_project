// On-device proof that an EXPIRED/invalid access token is refreshed and the
// original request replayed transparently — the exact failure seen during
// the manual journey (a transaction edit 401'd and showed "Failed to update
// transaction" with no refresh).
//
// This drives the REAL shipped paths: ApiService (auth + the Dio 401
// refresh-retry interceptor) and TransactionService (now routed through that
// interceptor), against live production. It is NOT a curl substitute — it is
// the actual Flutter session.
//
//   flutter test integration_test/auth_refresh_on_device_test.dart -d <device>
//
// Skips (does not fail) if the backend is unreachable.

import 'dart:math';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:mita/config.dart';
import 'package:mita/models/transaction_model.dart';
import 'package:mita/services/api_service.dart';
import 'package:mita/services/transaction_service.dart';

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  var backendReachable = false;

  setUpAll(() async {
    try {
      final r = await Dio(BaseOptions(
        connectTimeout: const Duration(seconds: 8),
        receiveTimeout: const Duration(seconds: 8),
        validateStatus: (_) => true,
      )).get<dynamic>(AppConfig.fullHealthUrl);
      backendReachable = r.statusCode == 200;
    } catch (_) {
      backendReachable = false;
    }
  });

  testWidgets(
      'expired access token is refreshed and the transaction update replays '
      'transparently (no restart, no duplicate)', (tester) async {
    if (!backendReachable) {
      markTestSkipped('Backend not reachable at ${AppConfig.baseUrl}');
      return;
    }

    final api = ApiService();
    final txns = TransactionService();
    final email =
        'authrefresh_${DateTime.now().millisecondsSinceEpoch}_${Random().nextInt(9999)}@example.com';
    const password = 'Str0ng!Refresh#2026';

    // Register + login → valid access + refresh tokens on device.
    await api.registerWithDetails(email, password,
        country: 'US', annualIncome: 72000, timezone: 'America/New_York');
    final login = await api.login(email, password);
    final loginData = ((login.data as Map)['data'] ?? login.data) as Map;
    final validAccess = loginData['access_token'] as String;
    final validRefresh = loginData['refresh_token'] as String;
    await api.saveTokens(validAccess, validRefresh);

    await api.submitOnboarding({
      'region': 'US-NY',
      'income': {'monthly_income': 6000, 'additional_income': 0},
      'fixed_expenses': {'rent': 2000},
      'goals': {
        'savings_goal_amount_per_month': 500,
        'savings_goal_type': 'emergency_fund',
      },
      'spending_habits': {'dining_out_per_month': 8},
    });

    // Baseline transaction (created with a valid token).
    final created = await txns.createTransaction(TransactionInput(
      amount: 23.75,
      category: 'food',
      description: 'auth-refresh baseline',
      spentAt: DateTime.now().toUtc(),
    ));
    expect(created.id, isNotEmpty);

    // ── Corrupt the ACCESS token, keep the VALID refresh token ──────────
    // The backend will 401 the next request; the interceptor must refresh
    // using the still-valid refresh token and replay the update.
    await api.saveTokens('invalid.access.token.value', validRefresh);
    expect(await api.getToken(), 'invalid.access.token.value',
        reason: 'access token corrupted for the test');

    // ── The user action must succeed transparently ─────────────────────
    final updated = await txns.updateTransaction(
      created.id,
      TransactionInput(
        amount: 100.00,
        category: 'food',
        description: 'auth-refresh edited',
        spentAt: DateTime.now().toUtc(),
      ),
    );
    expect(updated.amount, 100.00,
        reason: 'edit succeeded after transparent token refresh');

    // The stored access token was rotated to a real one (not the bogus value).
    final refreshedAccess = await api.getToken();
    expect(refreshedAccess, isNotNull);
    expect(refreshedAccess, isNot('invalid.access.token.value'),
        reason: 'a new access token was stored by the refresh');

    // ── Idempotency: exactly one transaction, amount 100 (no duplicate) ─
    final list = await txns.getTransactions(limit: 100);
    final matching = list.where((t) => t.id == created.id).toList();
    expect(matching.length, 1, reason: 'no duplicate transaction');
    expect(matching.first.amount, 100.00);

    // Calendar accrual is 100 exactly (no double-count from a replay).
    final nowUtc = DateTime.now().toUtc();
    final saved = await api.getSavedCalendar(
        year: nowUtc.year, month: nowUtc.month);
    final todayKey = nowUtc.toIso8601String().substring(0, 10);
    final today = saved!
        .map((d) => Map<String, dynamic>.from(d as Map))
        .firstWhere((d) => d['date'] == todayKey);
    expect((today['spent'] as num).toDouble(), 100.00,
        reason: 'single accrual — the replay did not double-count');

    // Cleanup.
    await txns.deleteTransaction(created.id);
  }, timeout: const Timeout(Duration(minutes: 5)));
}
