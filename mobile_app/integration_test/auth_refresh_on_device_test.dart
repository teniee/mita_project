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

// Live-backend gate: this test creates a throwaway account against
// production, so it is OFF unless explicitly enabled. `flutter test` (CI)
// only runs test/ and never reaches integration_test/, but even a manual
// `flutter test integration_test/` skips this without the flag:
//
//   flutter test integration_test/auth_refresh_on_device_test.dart \
//     -d <device> --dart-define=RUN_LIVE_E2E=true \
//     --dart-define=E2E_TEST_PASSWORD=<throwaway-password>
const _runLiveE2E =
    bool.fromEnvironment('RUN_LIVE_E2E', defaultValue: false);
// Never a committed credential — the account is synthesized per run; the
// password comes from the environment with a per-run random fallback.
const _passwordFromEnv = String.fromEnvironment('E2E_TEST_PASSWORD');

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  var backendReachable = false;

  setUpAll(() async {
    if (!_runLiveE2E) return;
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
    if (!_runLiveE2E) {
      markTestSkipped('Live E2E disabled (pass --dart-define=RUN_LIVE_E2E=true)');
      return;
    }
    if (!backendReachable) {
      markTestSkipped('Backend not reachable at ${AppConfig.baseUrl}');
      return;
    }

    final api = ApiService();
    final txns = TransactionService();
    final rng = Random();
    final email =
        'authrefresh_${DateTime.now().millisecondsSinceEpoch}_${rng.nextInt(9999)}@example.com';
    // Env-provided, else a per-run random throwaway (nothing committed).
    final password = _passwordFromEnv.isNotEmpty
        ? _passwordFromEnv
        : 'E2e!${rng.nextInt(1 << 32)}#${DateTime.now().millisecondsSinceEpoch}';

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

    // ── Idempotency baseline (BEFORE the retry) ────────────────────────
    final created = await txns.createTransaction(TransactionInput(
      amount: 23.75,
      category: 'food',
      description: 'auth-refresh baseline',
      spentAt: DateTime.now().toUtc(),
    ));
    expect(created.id, isNotEmpty);

    final nowUtc0 = DateTime.now().toUtc();
    final todayKey0 = nowUtc0.toIso8601String().substring(0, 10);
    final listBefore = await txns.getTransactions(limit: 100);
    final countBefore =
        listBefore.where((t) => t.id == created.id).length;
    final savedBefore =
        await api.getSavedCalendar(year: nowUtc0.year, month: nowUtc0.month);
    final foodSpentBefore = savedBefore!
        .map((d) => Map<String, dynamic>.from(d as Map))
        .firstWhere((d) => d['date'] == todayKey0)['planned_budget']['food']
            ['spent'] as num;
    expect(countBefore, 1);
    expect(foodSpentBefore.toDouble(), 23.75);

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

    // ── Idempotency (AFTER the retry): every aggregate moved ONCE ───────
    // transaction count: 1 before, 1 after (the replay did not insert a row).
    expect(matching.length, countBefore,
        reason: 'transaction row count unchanged by the replay');

    final nowUtc = DateTime.now().toUtc();
    final saved = await api.getSavedCalendar(
        year: nowUtc.year, month: nowUtc.month);
    final todayKey = nowUtc.toIso8601String().substring(0, 10);
    final today = saved!
        .map((d) => Map<String, dynamic>.from(d as Map))
        .firstWhere((d) => d['date'] == todayKey);
    // DailyPlan day spent AND the food category aggregate are 100 exactly —
    // 23.75 (before) updated to 100.00, not 123.75 (a double-count) and not
    // 200.00 (two accruals).
    expect((today['spent'] as num).toDouble(), 100.00,
        reason: 'single day accrual — the replay did not double-count');
    expect(
        (today['planned_budget']['food']['spent'] as num).toDouble(), 100.00,
        reason: 'single category accrual — no double-count');

    // Cleanup: delete the transaction; the throwaway account is left inert.
    final deleted = await txns.deleteTransaction(created.id);
    expect(deleted, isTrue);
    final afterDelete = await txns.getTransactions(limit: 100);
    expect(afterDelete.any((t) => t.id == created.id), isFalse,
        reason: 'created data removed');
  }, timeout: const Timeout(Duration(minutes: 5)));
}
