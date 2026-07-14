/// Mobile ↔ backend end-to-end journey through the app's real ApiService
/// (dio client, interceptors, secure token storage) against a live backend.
///
/// Run with a local backend:
///   flutter test test/integration/mobile_backend_journey_test.dart \
///     --dart-define=API_BASE_URL=http://localhost:8000
///
/// Skips itself (not fails) when no backend is reachable, like the other
/// live-API integration tests.
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

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  // The test binding installs a mock HttpOverrides that answers 400 to all
  // HTTP without touching the network; this file exists to exercise the
  // real backend, so restore real networking.
  HttpOverrides.global = null;
  SharedPreferences.setMockInitialValues(<String, Object>{});

  // Stateful secure-storage mock so token persistence behaves like the
  // real Keychain/Keystore across the journey.
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
    try {
      await Dio(BaseOptions(
        connectTimeout: const Duration(seconds: 5),
        receiveTimeout: const Duration(seconds: 5),
        validateStatus: (_) => true,
      )).get(AppConfig.fullHealthUrl);
      backendReachable = true;
    } catch (_) {
      backendReachable = false;
    }
  });

  bool skipIfUnreachable() {
    if (!backendReachable) {
      markTestSkipped('Backend not reachable at ${AppConfig.baseUrl}');
      return true;
    }
    return false;
  }

  test(
      'full mobile journey: register → login → onboarding → transaction '
      '→ calendar → refresh → persistence → logout', () async {
    if (skipIfUnreachable()) return;

    final api = ApiService();
    final email =
        'journey_${DateTime.now().millisecondsSinceEpoch}_${Random().nextInt(9999)}@example.com';
    const password = 'Str0ng!Journey#2026';

    // 1. Register through the app's registration path.
    final reg = await api.registerWithDetails(
      email,
      password,
      country: 'US',
      annualIncome: 72000,
      timezone: 'America/New_York',
    );
    expect(reg.statusCode, 201, reason: 'registration should succeed');

    // 2. Login and persist tokens the way the app does.
    final login = await api.login(email, password);
    expect(login.statusCode, 200);
    final data = login.data['data'] ?? login.data;
    final access = data['access_token'] as String;
    final refresh = data['refresh_token'] as String;
    await api.saveTokens(access, refresh);
    expect(await api.getToken(), isNotEmpty);

    // 3. Onboarding → budget generation.
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

    // 4. Create a transaction through the app path.
    await api.createTransaction({
      'amount': 23.75,
      'category': 'food',
      'description': 'Journey test lunch',
      'spent_at': DateTime.now().toUtc().toIso8601String(),
    });

    // 5. Calendar reflects a usable budget.
    //
    // 5a. The REAL production path (BudgetProvider.loadCalendarData):
    // /calendar/saved/{year}/{month} built from the DailyPlan rows that
    // onboarding persisted. Regression guard: every day must carry a
    // non-zero limit — with limit=0 the calendar traffic-light and
    // overspend detection silently degrade (the bug this test caught).
    final nowUtc = DateTime.now().toUtc();
    final saved = await api.getSavedCalendar(
      year: nowUtc.year,
      month: nowUtc.month,
    );
    expect(saved, isNotNull,
        reason: 'onboarding must persist a saved calendar');
    expect(saved!, isNotEmpty,
        reason: 'saved calendar must contain days for the current month');
    for (final raw in saved) {
      final day = Map<String, dynamic>.from(raw as Map);
      final date = day['date'] as String?;
      expect(date, isNotNull);
      expect(date, isNot(contains('T')),
          reason: 'day key must be YYYY-MM-DD for date-keyed merging');
      expect((day['limit'] as num).toDouble(), greaterThan(0),
          reason: 'day $date has no budget limit — traffic light broken');
    }
    final todayKey = nowUtc.toIso8601String().substring(0, 10);
    final todayEntry = saved
        .map((d) => Map<String, dynamic>.from(d as Map))
        .where((d) => d['date'] == todayKey)
        .toList();
    expect(todayEntry, hasLength(1),
        reason: 'today ($todayKey) must be present in the saved calendar');
    expect((todayEntry.first['spent'] as num).toDouble(),
        greaterThanOrEqualTo(23.75),
        reason: 'transaction must be reflected in today\'s spent amount');

    // 5b. Shell calendar fallback path also yields a usable budget.
    final calendar = await api.getCalendar(userIncome: 6000);
    expect(calendar, isNotEmpty,
        reason: 'onboarding should produce a calendar');

    // 5c. Edit and delete through the app's TransactionService — the same
    // real HTTP paths and secure-storage token the app uses.
    final txService = TransactionService();
    final txList = await txService.getTransactions(limit: 20);
    expect(txList, isNotEmpty,
        reason: 'created transaction must appear in the transaction list');
    final created = txList.firstWhere(
      (t) => t.description == 'Journey test lunch',
      orElse: () => txList.first,
    );

    final updated = await txService.updateTransaction(
      created.id,
      TransactionInput(
        amount: 31.25,
        category: created.category,
        description: 'Journey test lunch (edited)',
        spentAt: nowUtc,
      ),
    );
    expect(updated.amount, 31.25, reason: 'edit must persist the new amount');

    // Refreshing the calendar reflects the edited amount.
    final afterEdit = await api.getSavedCalendar(
      year: nowUtc.year,
      month: nowUtc.month,
    );
    final todayAfterEdit = afterEdit!
        .map((d) => Map<String, dynamic>.from(d as Map))
        .firstWhere((d) => d['date'] == todayKey);
    expect((todayAfterEdit['spent'] as num).toDouble(),
        greaterThanOrEqualTo(31.25),
        reason: 'edited amount must be reflected in today\'s spent');

    // Delete, then the calendar's spent drops back below the edited amount.
    expect(await txService.deleteTransaction(created.id), isTrue);
    final afterDelete = await api.getSavedCalendar(
      year: nowUtc.year,
      month: nowUtc.month,
    );
    final todayAfterDelete = afterDelete!
        .map((d) => Map<String, dynamic>.from(d as Map))
        .firstWhere((d) => d['date'] == todayKey);
    expect((todayAfterDelete['spent'] as num).toDouble(), lessThan(31.25),
        reason: 'deleted transaction must no longer count toward spent');

    // 5d. Error contracts stay typed failures, never crashes:
    // editing a nonexistent transaction surfaces the 404 as an exception.
    Object? notFoundError;
    try {
      await txService.updateTransaction(
        '00000000-0000-4000-8000-000000000000',
        TransactionInput(amount: 1.0, category: 'food'),
      );
    } catch (e) {
      notFoundError = e;
    }
    expect(notFoundError, isNotNull,
        reason: 'updating a nonexistent transaction must fail visibly');

    // 6. Token refresh works from the mobile client.
    final refreshed = await api.refreshAccessToken();
    expect(refreshed, isNotNull, reason: 'refresh flow should issue tokens');
    expect(refreshed!['access_token'], isNotEmpty);

    // 7. Session persistence: a fresh service instance sees stored tokens
    // (ApiService is a singleton; the secure store is the persistence layer).
    expect(secureStore.values.any((v) => v.isNotEmpty), isTrue,
        reason: 'tokens persisted in secure storage');

    // 8. Logout clears the session server-side and locally.
    await api.logout();
    expect(await api.getToken(), isNull,
        reason: 'logout should clear stored tokens');
  }, timeout: const Timeout(Duration(minutes: 3)));
}
