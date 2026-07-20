/// Regression tests for cache poisoning (J6).
///
/// Bug context (session-6 journey): after a failed onboarding submit the app
/// fell back to a synthetic "MITA User" / income-0 profile, and that fallback
/// could survive restarts and short-circuit the 2h freshness TTL so a retry
/// kept serving it instead of server truth.
///
/// isUsableCachedProfile is the guard that stops the synthetic placeholder (and
/// empty maps) from being loaded as if they were a real cached profile — a
/// restart then re-fetches server truth instead of rendering the fake state.
import 'package:flutter_test/flutter_test.dart';
import 'package:mita/services/user_data_manager.dart';

void main() {
  group('UserDataManager.isUsableCachedProfile', () {
    test('rejects the synthetic default placeholder profile', () {
      // Signature of _getDefaultUserProfile(): placeholder email + income 0.
      final placeholder = {
        'name': 'MITA User',
        'email': 'user@mita.finance',
        'income': 0.0,
        'profile_completion': 0,
      };
      expect(UserDataManager.isUsableCachedProfile(placeholder), isFalse);
    });

    test('rejects an empty cached profile', () {
      expect(UserDataManager.isUsableCachedProfile(<String, dynamic>{}), isFalse);
    });

    test('accepts a real server profile', () {
      final real = {
        'id': 'ff5bf4be-2709-4af9-8acf-b09eb5b81d12',
        'email': 'journey@example.com',
        'income': 6000.0,
        'profile_completion': 28,
      };
      expect(UserDataManager.isUsableCachedProfile(real), isTrue);
    });

    test('accepts a transformed-onboarding profile without an email key', () {
      // cacheOnboardingData stores a transformed profile that carries income
      // but no email — it must not be mistaken for the placeholder.
      final onboardingProfile = {
        'income': 6000.0,
        'region': 'US-NY',
        'goals': ['emergency_fund'],
      };
      expect(UserDataManager.isUsableCachedProfile(onboardingProfile), isTrue);
    });
  });
}
