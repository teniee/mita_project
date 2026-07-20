/// Regression test for onboarding submit resilience (J4).
///
/// Bug context: a failed onboarding submit (e.g. a transient 502) was
/// swallowed — the screen cached + marked onboarding complete locally BEFORE
/// the POST, ignored non-401 failures, and navigated to a fake completed
/// dashboard backed by shell/fallback data. A blocked submit must instead stay
/// on the setup screen with a retryable error and must NOT reach /main.
///
/// This test drives the deterministic no-credentials path (no token in the
/// mocked secure storage): the screen must surface a blocking, actionable
/// error and must not navigate away.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mita/screens/onboarding_finish_screen.dart';

import 'helpers/test_app.dart';

void main() {
  initTestEnvironment();

  testWidgets('a submit that cannot proceed blocks with an error, no /main nav',
      (WidgetTester tester) async {
    var reachedMain = false;

    await tester.pumpWidget(wrapWithProviders(
      const OnboardingFinishScreen(),
      routes: {
        '/main': (_) {
          reachedMain = true;
          return const Scaffold(body: Text('MAIN DASHBOARD'));
        },
      },
    ));

    // initState → _checkAuthAndSubmit runs; with no persisted token it must
    // stop on a blocking, actionable error instead of proceeding.
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 500));

    // Never silently navigated to the dashboard.
    expect(reachedMain, isFalse, reason: 'must not auto-navigate to /main');
    expect(find.text('MAIN DASHBOARD'), findsNothing);

    // A retry/recovery affordance is present (blocking, actionable error UI).
    final hasActionableError = find.textContaining('account').evaluate().isNotEmpty ||
        find.textContaining('log in').evaluate().isNotEmpty ||
        find.text('Retry').evaluate().isNotEmpty;
    expect(hasActionableError, isTrue,
        reason: 'a blocking, retryable error must be shown');
  });
}
