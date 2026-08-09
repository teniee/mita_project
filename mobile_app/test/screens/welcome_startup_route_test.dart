import 'package:flutter_test/flutter_test.dart';
import 'package:mita/screens/welcome_screen.dart';

/// Regression for the expired-session launch.
///
/// Device-reproduced against the local branch backend: an account that had
/// completed onboarding was left past the refresh-token lifetime. On relaunch
/// `/users/me` 401'd, the refresh 401'd, and UserProvider reported
/// `hasCompletedOnboarding == false` — the same value a brand new user has.
/// The splash then routed that user into onboarding step 1, which they could
/// never finish because submitting onboarding requires a live session.
///
/// The discriminator is whether any identity was resolved at all.
void main() {
  group('resolveStartupRoute', () {
    test('onboarded user goes to the dashboard', () {
      expect(
        resolveStartupRoute(hasOnboarded: true, hasProfile: true),
        StartupRoute.main,
      );
    });

    test('onboarded user still reaches the dashboard without a fresh profile',
        () {
      // Offline-first: a cached onboarding flag must not be downgraded just
      // because this launch could not refetch the profile.
      expect(
        resolveStartupRoute(hasOnboarded: true, hasProfile: false),
        StartupRoute.main,
      );
    });

    test('genuinely new user with a resolved identity goes to onboarding', () {
      expect(
        resolveStartupRoute(hasOnboarded: false, hasProfile: true),
        StartupRoute.onboarding,
      );
    });

    test('expired session goes to login, never to onboarding', () {
      // The defect: no identity resolved + hasOnboarded false used to fall
      // through to onboarding.
      expect(
        resolveStartupRoute(hasOnboarded: false, hasProfile: false),
        isNot(StartupRoute.onboarding),
      );
      expect(
        resolveStartupRoute(hasOnboarded: false, hasProfile: false),
        StartupRoute.login,
      );
    });
  });
}
