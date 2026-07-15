// Regression for the cold-start routing race (session-5, device-reproduced):
// MITAApp's bootstrap starts UserProvider.initialize() at launch; the
// welcome screen then awaits its own initialize() call. The old guard
// returned IMMEDIATELY while the first run was still in flight, so the
// welcome screen read the default hasCompletedOnboarding == false and
// routed an already-onboarded user back to onboarding on every restart.
//
// Contract pinned here: concurrent initialize() callers JOIN the same
// in-flight run — the second await must not complete before the first run
// finishes, and the work must run exactly once.

import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mita/providers/user_provider.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() {
    // flutter_secure_storage: return null for every read — a tokenless
    // cold start, which resolves initialize() into `unauthenticated`
    // without any network access.
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(
      const MethodChannel('plugins.it_nomads.com/flutter_secure_storage'),
      (call) async {
        if (call.method == 'readAll') return <String, String>{};
        return null;
      },
    );
  });

  test('concurrent initialize() callers join one in-flight run', () async {
    final provider = UserProvider();

    var loadingTransitions = 0;
    var completedTransitions = 0;
    provider.addListener(() {
      if (provider.state == UserState.loading) loadingTransitions++;
      if (provider.state == UserState.unauthenticated ||
          provider.state == UserState.error) {
        completedTransitions++;
      }
    });

    // Fire both callers in the same microtask turn — the second must join,
    // not skip.
    final first = provider.initialize();
    final second = provider.initialize();
    await Future.wait([first, second]);

    expect(provider.state, isNot(UserState.loading),
        reason: 'both awaits must resolve only after the run finished');
    expect(loadingTransitions, 1,
        reason: 'the initialization body must run exactly once');
    expect(completedTransitions, greaterThanOrEqualTo(1));
  });
}
