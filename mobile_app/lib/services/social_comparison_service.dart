import '../models/budget_intelligence_models.dart';
import 'api_service.dart';
import '../utils/peer_data.dart';

/// Social comparison intelligence service for peer-based insights
class SocialComparisonService {
  static final SocialComparisonService _instance =
      SocialComparisonService._internal();
  factory SocialComparisonService() => _instance;
  SocialComparisonService._internal() : _apiService = ApiService();

  /// Test seam: inject a stubbed [ApiService] so the peer-data guard can be
  /// exercised for real API failure / insufficient-cohort / valid-cohort
  /// responses without touching the network or the singleton.
  SocialComparisonService.withApiService(this._apiService);

  final ApiService _apiService;

  /// Generate social comparison insights
  Future<List<SocialComparisonInsight>> generateSocialInsights(
    String userId,
    UserDemographicProfile userProfile,
    Map<String, dynamic> userMetrics,
  ) async {
    final insights = <SocialComparisonInsight>[];

    // Get real peer comparison data from backend
    final peerComparisonData = await _apiService.getPeerComparison();

    // No peers, no comparison. This used to fall back to
    // _generateFallbackPeerData(), a hardcoded table of per-income-tier peer
    // averages (2200/3200/4800/7500/12000) and cohort sizes
    // (1500/2200/3100/1800/800). Those fed _generateComparisonText(), so the
    // user was told "You spend 12% more than similar users" against a peer
    // group that was a constant in this file. That text is not cosmetic: it
    // reaches the Daily Budget screen through
    //   master engine -> personalizedInsights -> intelligentInsights
    //   -> BudgetAdapterService suggestions[].message -> daily_budget_screen.
    // An unavailable peer service now yields no social insights at all; the
    // caller keeps whatever non-peer insights it derived from real data.
    if (!hasSufficientPeerData(peerComparisonData)) {
      return const <SocialComparisonInsight>[];
    }

    final peerData = _extractPeerData(peerComparisonData);
    final peerAverage = peerData['averageSpending'];
    if (peerAverage == null || peerAverage <= 0) {
      return const <SocialComparisonInsight>[];
    }

    // Spending comparison
    final userSpending =
        (userMetrics['monthlySpending'] as num?)?.toDouble() ?? 0.0;
    final peerAverageSpending = peerAverage;
    final spendingPercentile =
        _calculatePercentile(userSpending, peerAverageSpending);

    insights.add(SocialComparisonInsight(
      insightId: 'spending_comparison_${DateTime.now().millisecondsSinceEpoch}',
      insightType: 'spending_comparison',
      category: 'overall_spending',
      userValue: userSpending,
      peerAverage: peerAverageSpending,
      percentile: spendingPercentile,
      comparisonText: _generateComparisonText(
          'spending', spendingPercentile, userSpending, peerAverageSpending),
      recommendation: _generateRecommendation('spending', spendingPercentile),
      confidenceLevel: 0.8,
      metadata: {
        'sampleSize': peerData['sampleSize'],
        'incomeTier': userProfile.incomeTier.toString(),
      },
    ));

    // Savings rate comparison — only when the API actually sent a peer
    // savings rate. This used to default to 0.15, so "You save 40% less than
    // similar users" could be measured against a 15% peer rate that no peer
    // ever reported.
    final peerAverageSavingsRate = peerData['averageSavingsRate'];
    if (peerAverageSavingsRate == null || peerAverageSavingsRate <= 0) {
      return insights;
    }
    final userSavingsRate =
        (userMetrics['savingsRate'] as num?)?.toDouble() ?? 0.0;
    final savingsPercentile =
        _calculatePercentile(userSavingsRate, peerAverageSavingsRate);

    insights.add(SocialComparisonInsight(
      insightId: 'savings_comparison_${DateTime.now().millisecondsSinceEpoch}',
      insightType: 'savings_comparison',
      category: 'savings_rate',
      userValue: userSavingsRate,
      peerAverage: peerAverageSavingsRate,
      percentile: savingsPercentile,
      comparisonText: _generateComparisonText('savings_rate', savingsPercentile,
          userSavingsRate, peerAverageSavingsRate),
      recommendation:
          _generateRecommendation('savings_rate', savingsPercentile),
      confidenceLevel: 0.8,
      metadata: {
        'sampleSize': peerData['sampleSize'],
        'incomeTier': userProfile.incomeTier.toString(),
      },
    ));

    return insights;
  }

  /// Extract peer data from the API response.
  ///
  /// Every value is nullable on purpose. The old version defaulted a missing
  /// peer savings rate to 0.15 and a missing cohort to 1000 people, so a
  /// response that carried no such fields still produced confident
  /// comparisons and a "sampleSize: 1000" badge. A field the server did not
  /// send is absent here, and the caller skips the insight that needs it.
  Map<String, double?> _extractPeerData(Map<String, dynamic> apiResponse) {
    return {
      'averageSpending': (apiResponse['peer_average'] as num?)?.toDouble(),
      'averageSavingsRate':
          (apiResponse['peer_savings_rate'] as num?)?.toDouble(),
      'sampleSize': (apiResponse['cohort_size'] as num?)?.toDouble() ??
          (apiResponse['peer_count'] as num?)?.toDouble(),
    };
  }

  double _calculatePercentile(double userValue, double peerAverage) {
    // Simplified percentile calculation
    final ratio = userValue / peerAverage;
    if (ratio > 1.5) return 0.95;
    if (ratio > 1.2) return 0.80;
    if (ratio > 1.0) return 0.65;
    if (ratio > 0.8) return 0.45;
    if (ratio > 0.6) return 0.25;
    return 0.10;
  }

  String _generateComparisonText(
      String metric, double percentile, double userValue, double peerAverage) {
    switch (metric) {
      case 'spending':
        if (percentile > 0.8) {
          return 'You spend ${((userValue / peerAverage - 1) * 100).round()}% more than similar users';
        } else if (percentile < 0.3) {
          return 'You spend ${((1 - userValue / peerAverage) * 100).round()}% less than similar users';
        } else {
          return 'Your spending is similar to users in your income tier';
        }
      case 'savings_rate':
        if (percentile > 0.8) {
          return 'You save ${((userValue / peerAverage - 1) * 100).round()}% more than similar users';
        } else if (percentile < 0.3) {
          return 'You save ${((1 - userValue / peerAverage) * 100).round()}% less than similar users';
        } else {
          return 'Your savings rate is similar to users in your income tier';
        }
      default:
        return 'Your performance is within normal range';
    }
  }

  String _generateRecommendation(String metric, double percentile) {
    switch (metric) {
      case 'spending':
        if (percentile > 0.8) {
          return 'Consider reviewing your spending categories to identify areas for reduction';
        } else if (percentile < 0.3) {
          return 'Great spending discipline! Consider if you can invest the surplus';
        } else {
          return 'Your spending level is well-balanced for your income tier';
        }
      case 'savings_rate':
        if (percentile > 0.8) {
          return 'Excellent savings rate! You\'re ahead of most peers in your tier';
        } else if (percentile < 0.3) {
          return 'Consider increasing your savings rate by 2-3% to match your peers';
        } else {
          return 'Your savings rate is on track with similar users';
        }
      default:
        return 'Keep monitoring your financial metrics';
    }
  }
}
