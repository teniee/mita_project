/// Peer comparisons must come from real peers or not at all.
///
/// `SocialComparisonService.generateSocialInsights()` used to fall back to
/// `_generateFallbackPeerData()` — a hardcoded table of per-income-tier peer
/// averages (2200 / 3200 / 4800 / 7500 / 12000) and cohort sizes
/// (1500 / 2200 / 3100 / 1800 / 800) — whenever the peer API reported an
/// error. Since `ApiService.getPeerComparison()` returns an honest
/// `{'error': ...}` envelope on *any* failure, that fallback fired on every
/// peer-API failure, and `_generateComparisonText()` then told the user
/// "You spend 12% more than similar users" against a peer group that was a
/// constant in the source file.
///
/// That text is not confined to a peer widget. It reaches the Daily Budget
/// screen through:
///   EnhancedMasterBudgetEngine._generatePersonalizedInsights
///     -> personalizedInsights
///     -> EnhancedProductionBudgetEngine.intelligentInsights
///     -> BudgetAdapterService.getEnhancedBudgetSuggestions() suggestions[].message
///     -> BudgetProvider.budgetSuggestions
///     -> daily_budget_screen's "AI Budget Suggestions" card.
///
/// `_extractPeerData()` also defaulted a missing peer savings rate to 0.15 and
/// a missing cohort to 1000 people, so even a *successful* response missing
/// those fields produced confident comparisons.

import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:mita/models/budget_intelligence_models.dart';
import 'package:mita/services/api_service.dart';
import 'package:mita/services/social_comparison_service.dart';
import 'package:mocktail/mocktail.dart';

class _MockApiService extends Mock implements ApiService {}

UserDemographicProfile _profile() => UserDemographicProfile(
      userId: 'u1',
      incomeTier: IncomeTier.middle,
      interests: const <String>[],
      spendingPersonality: const <String, dynamic>{},
    );

const _metrics = <String, dynamic>{
  'monthlySpending': 3000.0,
  'savingsRate': 0.10,
};

/// Exactly what ApiService.getPeerComparison() returns when the call fails.
const _apiFailureEnvelope = <String, dynamic>{
  'error': 'Peer comparison service is currently unavailable',
  'your_spending': null,
  'peer_average': null,
  'peer_median': null,
  'percentile': null,
  'categories': <String, dynamic>{},
  'insights': <String>[],
};

/// Exactly what the backend sends when the cohort is empty.
const _insufficientPeers = <String, dynamic>{
  'your_spending': 3000.0,
  'peer_average': null,
  'peer_median': null,
  'percentile': null,
  'comparison': 'insufficient_peer_data',
  'peer_count': 0,
};

const _realPeers = <String, dynamic>{
  'your_spending': 3000.0,
  'peer_average': 2000.0,
  'peer_savings_rate': 0.20,
  'peer_count': 42,
  'cohort_size': 42,
};

void main() {
  late _MockApiService api;
  late SocialComparisonService service;

  setUp(() {
    api = _MockApiService();
    service = SocialComparisonService.withApiService(api);
  });

  group('no peer data means no comparison', () {
    test('API failure yields no social insights at all', () async {
      when(() => api.getPeerComparison())
          .thenAnswer((_) async => _apiFailureEnvelope);

      final insights =
          await service.generateSocialInsights('u1', _profile(), _metrics);

      expect(insights, isEmpty,
          reason: 'An unavailable peer service must produce no comparison, '
              'not a comparison against hardcoded per-tier averages.');
    });

    test('an empty cohort yields no social insights', () async {
      when(() => api.getPeerComparison())
          .thenAnswer((_) async => _insufficientPeers);

      final insights =
          await service.generateSocialInsights('u1', _profile(), _metrics);

      expect(insights, isEmpty);
    });

    test('a success payload with no peer_average yields nothing', () async {
      when(() => api.getPeerComparison()).thenAnswer((_) async => {
            'your_spending': 3000.0,
            'peer_average': null,
            'peer_count': 25,
          });

      final insights =
          await service.generateSocialInsights('u1', _profile(), _metrics);

      expect(insights, isEmpty);
    });

    test('no fabricated peer text can reach the caller on failure', () async {
      when(() => api.getPeerComparison())
          .thenAnswer((_) async => _apiFailureEnvelope);

      final insights =
          await service.generateSocialInsights('u1', _profile(), _metrics);

      // This is the string that used to travel all the way to the Daily
      // Budget screen's "AI Budget Suggestions" card.
      expect(
        insights.map((i) => i.comparisonText),
        isNot(anyElement(contains('similar users'))),
      );
    });
  });

  group('the fabrication machinery is gone from the source', () {
    /// Strip `//` comments so the guards match real code, not the comment
    /// left where the fabrication used to be (which names it deliberately).
    String code(String src) =>
        src.split('\n').where((l) => !l.trimLeft().startsWith('//')).join('\n');

    final source = code(
        File('lib/services/social_comparison_service.dart').readAsStringSync());
    final master = code(File('lib/services/enhanced_master_budget_engine.dart')
        .readAsStringSync());

    test('_generateFallbackPeerData and its callee are deleted', () {
      expect(source, isNot(contains('_generateFallbackPeerData')));
      expect(source, isNot(contains('_generateInsightsFromFallbackData')));
    });

    test('no hardcoded per-tier peer averages or cohort sizes', () {
      for (final literal in [
        "'averageSpending': 7500.0",
        "'averageSpending': 12000.0",
        "'sampleSize': 3100.0",
        "'sampleSize': 1800.0",
      ]) {
        expect(source, isNot(contains(literal)));
      }
    });

    test('no invented savings-rate or sample-size defaults', () {
      expect(source, isNot(contains('?? 0.15')));
      expect(source, isNot(contains('?? 1000.0')));
    });

    test('the master engine still guards both social consumers', () {
      // With generateSocialInsights() returning [], these two guards are what
      // stop an empty list from becoming a rendered claim. If either is
      // rewritten to index unconditionally, peer text could reach
      // intelligentInsights -> suggestions[].message -> daily_budget_screen.
      expect(master, contains('if (socialInsights.isNotEmpty) {'));
      expect(master, contains('for (final insight in socialInsights.take(1))'));
    });
  });

  group('real peer data still produces comparisons', () {
    test('a genuine cohort produces spending and savings insights', () async {
      when(() => api.getPeerComparison()).thenAnswer((_) async => _realPeers);

      final insights =
          await service.generateSocialInsights('u1', _profile(), _metrics);

      expect(insights, isNotEmpty,
          reason: 'Real peers must still produce a real comparison.');
      expect(
        insights.map((i) => i.insightType),
        containsAll(<String>['spending_comparison', 'savings_comparison']),
      );
      // The comparison is against the value the server actually sent.
      expect(insights.first.peerAverage, 2000.0);
    });

    test('a missing peer savings rate drops only the savings insight',
        () async {
      when(() => api.getPeerComparison()).thenAnswer((_) async => {
            'your_spending': 3000.0,
            'peer_average': 2000.0,
            'peer_count': 42,
            // no peer_savings_rate — must NOT be invented as 0.15
          });

      final insights =
          await service.generateSocialInsights('u1', _profile(), _metrics);

      expect(
          insights.map((i) => i.insightType), contains('spending_comparison'));
      expect(insights.map((i) => i.insightType),
          isNot(contains('savings_comparison')),
          reason: 'A peer savings rate the server never sent must not be '
              'defaulted to 0.15 and compared against.');
    });

    test('sample size is never invented as 1000', () async {
      when(() => api.getPeerComparison()).thenAnswer((_) async => {
            'your_spending': 3000.0,
            'peer_average': 2000.0,
            'peer_count': 42,
          });

      final insights =
          await service.generateSocialInsights('u1', _profile(), _metrics);

      for (final insight in insights) {
        expect(insight.metadata['sampleSize'], isNot(1000.0));
      }
    });
  });
}
