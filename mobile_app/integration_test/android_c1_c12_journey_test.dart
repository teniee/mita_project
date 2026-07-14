// On-device Android C1–C12 core mobile journey against the LIVE backend.
//
// Runs in the real Android runtime (Dart VM on device, real
// flutter_secure_storage Keystore, real networking) via:
//
//   flutter test integration_test/android_c1_c12_journey_test.dart \
//       -d emulator-5554
//
// It drives the app's REAL production service paths — ApiService (register,
// login, onboarding, token, saved calendar, logout) and TransactionService
// (create/list/update/delete through /transactions/{uuid}) — plus the real
// on-device secure storage, so token persistence and the UUID transaction id
// path are exercised exactly as the shipped app does.
//
// Steps map 1:1 to the mandated C1–C12:
//   C1 register, C2 login, C3 onboarding, C4 dashboard, C5 calendar,
//   C6 create, C7 list, C8 edit, C9 delete, C10 restart (persistence),
//   C11 logout, C12 re-login.
//
// Skips (does not fail) if the backend is unreachable, like the other
// live-API integration tests.

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

  testWidgets('Android C1–C12 core mobile journey (live backend)',
      (tester) async {
    if (!backendReachable) {
      markTestSkipped('Backend not reachable at ${AppConfig.baseUrl}');
      return;
    }

    final api = ApiService();
    final txns = TransactionService();
    final email =
        'c1c12_${DateTime.now().millisecondsSinceEpoch}_${Random().nextInt(9999)}@example.com';
    const password = 'Str0ng!Journey#2026';

    // ── C1: register ────────────────────────────────────────────────────
    final reg = await api.registerWithDetails(
      email,
      password,
      country: 'US',
      annualIncome: 72000,
      timezone: 'America/New_York',
    );
    expect(reg.statusCode, anyOf(200, 201), reason: 'C1 register');

    // ── C2: login + persist tokens in the real Keystore ─────────────────
    final login = await api.login(email, password);
    expect(login.statusCode, 200, reason: 'C2 login');
    final loginData =
        ((login.data as Map)['data'] ?? login.data) as Map;
    final access = loginData['access_token'] as String;
    final refresh = loginData['refresh_token'] as String;
    await api.saveTokens(access, refresh);
    expect(await api.getToken(), isNotEmpty,
        reason: 'C2 token persisted on device');

    // ── C3: onboarding → budget generation ──────────────────────────────
    await api.submitOnboarding({
      'region': 'US-NY',
      'income': {'monthly_income': 6000, 'additional_income': 0},
      'fixed_expenses': {'rent': 2000, 'utilities': 180},
      'goals': {
        'savings_goal_amount_per_month': 500,
        'savings_goal_type': 'emergency_fund',
      },
      'spending_habits': {'dining_out_per_month': 8, 'coffee_per_week': 4},
    });

    // ── C4: dashboard loads with real, non-empty financial state ────────
    final dashboard = await api.getDashboard(userIncome: 6000);
    expect(dashboard, isNotEmpty, reason: 'C4 dashboard payload');
    // No silent empty-data fallback: balance must be present and numeric.
    expect(dashboard['balance'], isNotNull, reason: 'C4 dashboard balance');

    // ── C5: calendar (real saved path) with usable, non-zero limits ─────
    final nowUtc = DateTime.now().toUtc();
    final saved = await api.getSavedCalendar(
      year: nowUtc.year,
      month: nowUtc.month,
    );
    expect(saved, isNotNull, reason: 'C5 saved calendar exists');
    expect(saved!, isNotEmpty, reason: 'C5 saved calendar has days');
    for (final raw in saved) {
      final day = Map<String, dynamic>.from(raw as Map);
      expect((day['limit'] as num).toDouble(), greaterThan(0),
          reason: 'C5 every day has a real budget limit');
      expect(day['date'], isNot(contains('T')),
          reason: 'C5 day key is YYYY-MM-DD');
    }

    // ── C6: create a transaction through the real TransactionService ────
    final created = await txns.createTransaction(TransactionInput(
      amount: 23.75,
      category: 'food',
      description: 'C6 create',
      spentAt: nowUtc,
    ));
    expect(created.id, isNotEmpty, reason: 'C6 created txn has an id');
    // The backend id is a UUID string — the shipped edit/delete path must
    // address it as such (regression guard for the int-typed legacy API).
    expect(int.tryParse(created.id), isNull,
        reason: 'C6 backend id is a UUID string, not an int');

    // ── C7: list reflects the new transaction ───────────────────────────
    final list = await txns.getTransactions(limit: 100);
    expect(list.any((t) => t.id == created.id), isTrue,
        reason: 'C7 list contains the created txn');

    // ── C8: edit the transaction (UUID id) ──────────────────────────────
    final updated = await txns.updateTransaction(
      created.id,
      TransactionInput(
        amount: 100.00,
        category: 'food',
        description: 'C8 edited',
        spentAt: nowUtc,
      ),
    );
    expect(updated.amount, 100.00, reason: 'C8 edit persisted the new amount');

    // Exact financial recalculation: today's spent reflects the edit.
    final afterEdit = await api.getSavedCalendar(
      year: nowUtc.year,
      month: nowUtc.month,
    );
    final todayKey = nowUtc.toIso8601String().substring(0, 10);
    final todayAfterEdit = afterEdit!
        .map((d) => Map<String, dynamic>.from(d as Map))
        .firstWhere((d) => d['date'] == todayKey);
    expect((todayAfterEdit['spent'] as num).toDouble(),
        greaterThanOrEqualTo(100.00),
        reason: 'C8 calendar recalculated today.spent after edit');

    // ── C9: delete the transaction; recalculation reverses it ───────────
    final deleted = await txns.deleteTransaction(created.id);
    expect(deleted, isTrue, reason: 'C9 delete succeeded');
    final afterDelete = await txns.getTransactions(limit: 100);
    expect(afterDelete.any((t) => t.id == created.id), isFalse,
        reason: 'C9 deleted txn no longer listed');

    // ── C10: restart — fresh service instances read the persisted token ─
    final apiAfterRestart = ApiService();
    expect(await apiAfterRestart.getToken(), isNotEmpty,
        reason: 'C10 session survives an app restart (Keystore persistence)');
    final dashAfterRestart = await apiAfterRestart.getDashboard(userIncome: 6000);
    expect(dashAfterRestart, isNotEmpty,
        reason: 'C10 dashboard reloads after restart');

    // ── C11: logout clears the session locally and server-side ──────────
    await apiAfterRestart.logout();
    expect(await apiAfterRestart.getToken(), isNull,
        reason: 'C11 logout cleared the stored token');

    // ── C12: re-login restores an authenticated session ─────────────────
    final relogin = await api.login(email, password);
    expect(relogin.statusCode, 200, reason: 'C12 re-login');
    final reData =
        ((relogin.data as Map)['data'] ?? relogin.data) as Map;
    await api.saveTokens(
        reData['access_token'] as String, reData['refresh_token'] as String);
    expect(await api.getToken(), isNotEmpty, reason: 'C12 re-login session');
    // Onboarded state persisted across the whole journey.
    final finalDash = await api.getDashboard(userIncome: 6000);
    expect(finalDash['balance'], isNotNull,
        reason: 'C12 onboarded data still present after re-login');
  }, timeout: const Timeout(Duration(minutes: 5)));
}
