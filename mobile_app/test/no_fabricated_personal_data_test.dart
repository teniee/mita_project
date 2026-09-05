// Regression guard: the app must never invent a user's personal financial
// standing when a backend call fails.
//
// Several ApiService methods used to swallow their own exception and return
// hardcoded sample data. Because the API layer never rethrew, the honest
// empty/error states already written upstream were unreachable dead code:
//
//   * getCohortInsights()      -> {'cohort_size': 1247, 'your_rank': 312,
//                                  'percentile': 75, ...}
//     Rendered on the Insights screen (CohortInsightsWidget) and during
//     onboarding (OnboardingPeerComparisonScreen), telling a brand-new user
//     they ranked 312nd of 1247 people in the 75th percentile — an entirely
//     invented social standing. The onboarding screen's own honest catch
//     block could never fire.
//
//   * getAvailableChallenges() -> "Meal Prep Master" / "No-Spend Weekend" /
//     "Subscription Audit", each with a fabricated participant count, success
//     rate and a cash `reward_amount` — offers backed by no real money, shown
//     as joinable on the Challenges screen.
//
//   * getLeaderboard()         -> "BudgetNinja" and friends, ranking the user
//     against people who do not exist.
//
//   * CohortInsightsWidget._getDefaultCohortData() was a second fabrication
//     layer that would have re-introduced the same invented cohort even after
//     ApiService was made honest.
//
// All four now report unavailability (null cohort_size / empty list), which
// routes into the empty states that already existed:
//   - CohortInsightsWidget's "nothing to rank against" card (cohort_size <= 0)
//   - challenges_screen's "No challenges available right now"
//
// This test fails if any of that fabricated data is reintroduced.

import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

void main() {
  final apiService = File('lib/services/api_service.dart').readAsStringSync();
  final peerWidgets =
      File('lib/widgets/peer_comparison_widgets.dart').readAsStringSync();

  group('ApiService never fabricates personal or peer data', () {
    test('no invented cohort size, rank or percentile', () {
      for (final literal in ["'cohort_size': 1247", "'your_rank': 312"]) {
        expect(
          apiService,
          isNot(contains(literal)),
          reason: 'getCohortInsights() must report unavailability, not invent '
              'a cohort standing. A null cohort_size drives the existing '
              '"nothing to rank against" empty state.',
        );
      }
    });

    test('no invented challenges with fake rewards or participant counts', () {
      for (final literal in [
        "'Meal Prep Master'",
        "'No-Spend Weekend'",
        "'Subscription Audit'",
      ]) {
        expect(
          apiService,
          isNot(contains(literal)),
          reason: 'getAvailableChallenges() must return an empty list on '
              'failure. challenges_screen already renders "No challenges '
              'available right now".',
        );
      }
    });

    test('no invented leaderboard users', () {
      expect(
        apiService,
        isNot(contains("'BudgetNinja'")),
        reason: 'getLeaderboard() must return an empty list on failure rather '
            'than ranking the user against fictional people.',
      );
    });

    test('no "return demo ..." fallbacks remain', () {
      expect(
        apiService.toLowerCase(),
        isNot(contains('return demo')),
        reason: 'A "return demo" fallback shows invented data as if it were '
            'the user\'s own.',
      );
    });
  });

  group('CohortInsightsWidget has no second fabrication layer', () {
    test('_getDefaultCohortData is gone', () {
      expect(
        peerWidgets,
        isNot(contains('_getDefaultCohortData')),
        reason: 'This method fabricated a per-income-tier cohort size and '
            'rank, which would re-introduce the invented standing even with '
            'ApiService honest.',
      );
    });

    test('no per-tier invented cohort sizes or ranks', () {
      for (final literal in ['2847', '3241', '4126', '2089', '1653']) {
        expect(
          peerWidgets,
          isNot(contains(literal)),
          reason: 'Hardcoded cohort population $literal must not reappear.',
        );
      }
    });
  });
}
