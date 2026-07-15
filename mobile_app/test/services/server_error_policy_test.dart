// Phase-1 regressions for the red "Server error" toast.
//
// Production evidence (2026-07-14): a fresh session's only non-2xx was
// POST /api/ai/snapshot -> 500, and the global Dio interceptor toasted the
// red "Server error" SnackBar for it even though the dashboard never asked
// the user for AI data. These tests pin the client-side policy that came
// out of that session:
//  * only core-journey paths may raise the global toast,
//  * identical toasts within a short window collapse to one,
//  * the onboarding payload's nested income map coerces to a number.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mita/services/api_service.dart';
import 'package:mita/services/message_service.dart';
import 'package:mita/services/user_data_manager.dart';

void main() {
  group('ApiService.isCoreJourneyPath', () {
    test('core-journey requests keep the global server-error toast', () {
      expect(ApiService.isCoreJourneyPath('/auth/login'), isTrue);
      expect(ApiService.isCoreJourneyPath('/onboarding/submit'), isTrue);
      expect(ApiService.isCoreJourneyPath('/transactions/'), isTrue);
      expect(ApiService.isCoreJourneyPath('/transactions/abc-123'), isTrue);
      expect(ApiService.isCoreJourneyPath('/dashboard'), isTrue);
      expect(ApiService.isCoreJourneyPath('/calendar/saved/2026/7'), isTrue);
      expect(ApiService.isCoreJourneyPath('/users/me'), isTrue);
      expect(ApiService.isCoreJourneyPath('/budget/daily'), isTrue);
      expect(ApiService.isCoreJourneyPath('/budget/live_status'), isTrue);
    });

    test('background/enrichment requests do not toast globally', () {
      expect(ApiService.isCoreJourneyPath('/ai/snapshot'), isFalse);
      expect(ApiService.isCoreJourneyPath('/ai/financial-health-score'),
          isFalse);
      expect(ApiService.isCoreJourneyPath('/cohort/insights'), isFalse);
      expect(ApiService.isCoreJourneyPath('/analytics/monthly'), isFalse);
      expect(ApiService.isCoreJourneyPath('/insights/income_based_tips'),
          isFalse);
      expect(ApiService.isCoreJourneyPath('/budget/suggestions'), isFalse);
      expect(ApiService.isCoreJourneyPath('/budget/adaptations'), isFalse);
      expect(ApiService.isCoreJourneyPath('/habits/'), isFalse);
      expect(ApiService.isCoreJourneyPath('/notifications/register-token'),
          isFalse);
    });
  });

  group('MessageService error dedupe', () {
    testWidgets('identical errors within the window show one SnackBar',
        (tester) async {
      await tester.pumpWidget(MaterialApp(
        scaffoldMessengerKey: MessageService.instance.messengerKey,
        home: const Scaffold(body: SizedBox()),
      ));

      MessageService.instance.showError('Server error. Please try again.');
      MessageService.instance.showError('Server error. Please try again.');
      MessageService.instance.showError('Server error. Please try again.');
      await tester.pump();

      expect(find.text('Server error. Please try again.'), findsOneWidget);

      // A DIFFERENT error must still surface (dedupe is per-message). It
      // queues behind the visible SnackBar (4s display + enter/exit
      // animations ≈ 5s — verified empirically), so pump in small steps
      // until the queue rotates.
      MessageService.instance.showError('Session expired. Please log in.');
      var found = false;
      for (var i = 0; i < 12 && !found; i++) {
        await tester.pump(const Duration(milliseconds: 500));
        found = find.text('Session expired. Please log in.').evaluate().isNotEmpty;
      }
      expect(found, isTrue,
          reason: 'a distinct error message must not be deduped away');

      // Let queued SnackBar timers drain so the test ends cleanly.
      await tester.pump(const Duration(seconds: 5));
      await tester.pump(const Duration(seconds: 1));
    });
  });

  group('UserDataManager.monthlyIncomeFrom', () {
    test('coerces the onboarding payload income map to a number', () {
      expect(
        UserDataManager.monthlyIncomeFrom(
            {'monthly_income': 6000, 'additional_income': 0}),
        6000.0,
      );
      expect(
        UserDataManager.monthlyIncomeFrom({'monthly_income': '6000'}),
        6000.0,
      );
    });

    test('passes through flat numeric and string income', () {
      expect(UserDataManager.monthlyIncomeFrom(6000), 6000.0);
      expect(UserDataManager.monthlyIncomeFrom(6000.5), 6000.5);
      expect(UserDataManager.monthlyIncomeFrom('4500'), 4500.0);
    });

    test('degrades to 0.0 on null/garbage instead of throwing', () {
      expect(UserDataManager.monthlyIncomeFrom(null), 0.0);
      expect(UserDataManager.monthlyIncomeFrom(<String, dynamic>{}), 0.0);
      expect(UserDataManager.monthlyIncomeFrom('not-a-number'), 0.0);
    });
  });
}
