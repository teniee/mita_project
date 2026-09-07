/// With no peers, MITA must say so — not invent an average, a percentile or a
/// rank.
///
/// `/api/cohort/peer_comparison` is explicit when it cannot compare:
///   {"peer_average": null, "percentile": null, "peer_count": 0,
///    "comparison": "insufficient_peer_data"}
///
/// The Peer Insights screen used to paper over every one of those:
///   * `percentile ?? 50`  -> "You're in the 50th percentile"
///   * `peer_average ?? 0.0` -> "Peer Average $0" with a red "+0%" badge
///   * `cohort_size 0`     -> "0 users • You're #0 (0th percentile)" plus
///                            "Room for improvement compared to peers"
///   * `?? userAmount * 1.15` -> "Peers $230" beside a green thumbs-up
/// all shown to a first-day user whose cohort was empty.
library;

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:mita/widgets/income_tier_widgets.dart';
import 'package:mita/widgets/peer_comparison_widgets.dart';

Widget _host(Widget child) => MaterialApp(
      home: Scaffold(body: SingleChildScrollView(child: child)),
    );

/// Exactly what the API returns for a user with no peers.
const Map<String, dynamic> _noPeers = {
  'your_spending': 200.0,
  'peer_average': null,
  'peer_median': null,
  'percentile': null,
  'comparison': 'insufficient_peer_data',
  'savings_potential': 0,
  'peer_count': 0,
  'note': 'Need more users in database for peer comparison',
};

const Map<String, dynamic> _withPeers = {
  'your_spending': 200.0,
  'peer_average': 320.0,
  'peer_median': 300.0,
  'percentile': 30,
  'comparison': 'below_average',
  'savings_potential': 0,
  'peer_count': 12,
};

/// The same envelope plus a per-category map. The endpoint does NOT send this
/// today (app/api/cohort/routes.py returns nine keys and no `categories`), so
/// it stands for the only payload that may legitimately drive a per-category
/// peer bar — and proves the widget still works if the server starts sending
/// one.
const Map<String, dynamic> _withCategoryPeers = {
  ..._withPeers,
  'categories': {
    'transportation': {'peer_average': 320.0},
  },
};

void main() {
  group('hasSufficientPeerData', () {
    test('false when the API says the data is insufficient', () {
      expect(hasSufficientPeerData(_noPeers), isFalse);
    });

    test('false when the cohort is empty even if an average slipped through',
        () {
      expect(
        hasSufficientPeerData(const {'peer_count': 0, 'peer_average': 100.0}),
        isFalse,
      );
    });

    test('false when there is no average to compare against', () {
      expect(
        hasSufficientPeerData(const {'peer_count': 5, 'peer_average': null}),
        isFalse,
      );
    });

    test('false for a missing payload', () {
      expect(hasSufficientPeerData(null), isFalse);
    });

    test('true only with a real cohort and a real average', () {
      expect(hasSufficientPeerData(_withPeers), isTrue);
    });
  });

  group('PeerComparisonCard with no peers', () {
    testWidgets('states plainly that there is nothing to compare against',
        (tester) async {
      await tester.pumpWidget(_host(
        const PeerComparisonCard(comparisonData: _noPeers, monthlyIncome: 6000),
      ));
      await tester.pump();

      expect(find.textContaining('Not enough people'), findsOneWidget);
    });

    testWidgets('renders no percentile, no peer average, no verdict badge',
        (tester) async {
      await tester.pumpWidget(_host(
        const PeerComparisonCard(comparisonData: _noPeers, monthlyIncome: 6000),
      ));
      await tester.pump();

      expect(find.textContaining('percentile'), findsNothing,
          reason: 'a percentile against zero peers is meaningless');
      expect(find.text('Peer Average'), findsNothing);
      expect(find.text('\$0'), findsNothing,
          reason: 'a null peer average must not render as \$0');
      expect(find.textContaining('%'), findsNothing,
          reason: 'no +/-% verdict without peers');
    });
  });

  group('SpendingTrendsComparisonWidget with no peers', () {
    testWidgets('renders nothing rather than an invented peer bar',
        (tester) async {
      await tester.pumpWidget(_host(
        const SpendingTrendsComparisonWidget(
          userSpending: {'transportation': 200.0},
          monthlyIncome: 6000,
          peerData: _noPeers,
        ),
      ));
      await tester.pump();

      expect(find.text('Spending vs Peers'), findsNothing);
      expect(find.text('Peers'), findsNothing);
      // 200 * 1.15 = 230 — the old fabricated fallback.
      expect(find.textContaining('230'), findsNothing);
    });

    testWidgets('renders the real peer average when the server sends one',
        (tester) async {
      await tester.pumpWidget(_host(
        const SpendingTrendsComparisonWidget(
          userSpending: {'transportation': 200.0},
          monthlyIncome: 6000,
          peerData: _withCategoryPeers,
        ),
      ));
      await tester.pump();

      expect(find.text('Spending vs Peers'), findsOneWidget);
      expect(find.text('\$320'), findsOneWidget,
          reason: "the server's own figure, not one derived from the user");
    });
  });

  // A real cohort does not imply a per-category comparison.
  //
  // hasSufficientPeerData() passes as soon as the endpoint reports a cohort
  // and an overall peer_average, but the per-category rows read
  // peerData['categories'][c]['peer_average'] — a key the endpoint never
  // sends. Each row therefore fell through to `userAmount * 1.15`, so the
  // "Peers" figure was the user's own spending plus 15%, and
  // `isUserBetter` (userAmount < peerAmount) was true for every category,
  // always: a green thumbs-up on every line, for every user, derived from
  // nothing. This is the same fabrication the no-peers case already guarded,
  // one layer further in.
  group(
      'SpendingTrendsComparisonWidget with a real cohort but no '
      'per-category peer data', () {
    testWidgets('invents no per-category peer figure', (tester) async {
      await tester.pumpWidget(_host(
        const SpendingTrendsComparisonWidget(
          userSpending: {'transportation': 200.0, 'food': 400.0},
          monthlyIncome: 6000,
          peerData: _withPeers,
        ),
      ));
      await tester.pump();

      expect(find.text('\$230'), findsNothing,
          reason: '200 * 1.15 — the user\'s own spending sold back to them');
      expect(find.text('\$460'), findsNothing, reason: '400 * 1.15');
      expect(find.text('Spending vs Peers'), findsNothing,
          reason: 'no comparable category means no comparison card at all');
    });

    testWidgets('shows only the categories the server actually priced',
        (tester) async {
      await tester.pumpWidget(_host(
        const SpendingTrendsComparisonWidget(
          // Only transportation is priced in _withCategoryPeers.
          userSpending: {'transportation': 200.0, 'food': 400.0},
          monthlyIncome: 6000,
          peerData: _withCategoryPeers,
        ),
      ));
      await tester.pump();

      expect(find.text('TRANSPORTATION'), findsOneWidget);
      expect(find.text('FOOD'), findsNothing,
          reason: 'no peer average for food, so no food comparison');
      expect(find.text('\$460'), findsNothing);
    });
  });

  // PeerSpendingInsightsWidget has no callers today, but carried the same
  // fallback with a 1.2 multiplier. Because (u - 1.2u) / 1.2u is a constant,
  // getPeerComparisonMessage rendered "You spend 17% less on {category} than
  // other {tier}s" for every category and every user.
  group('PeerSpendingInsightsWidget', () {
    testWidgets('states no comparison without a real per-category average',
        (tester) async {
      await tester.pumpWidget(_host(
        const PeerSpendingInsightsWidget(
          category: 'food',
          userAmount: 400.0,
          monthlyIncome: 6000,
          peerData: _withPeers,
        ),
      ));
      await tester.pump();

      expect(find.textContaining('17%'), findsNothing);
      expect(find.textContaining('less on food'), findsNothing);
      expect(find.text('\$480'), findsNothing, reason: '400 * 1.2');
    });
  });
}
