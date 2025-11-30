import '../models/budget_intelligence_models.dart';
import 'api_service.dart';

/// Social comparison intelligence service for peer-based insights
class SocialComparisonService {
  static final SocialComparisonService _instance = SocialComparisonService._internal();
  factory SocialComparisonService() => _instance;
  SocialComparisonService._internal();

  final _apiService = ApiService();

  /// Generate social comparison insights
  Future<List<SocialComparisonInsight>> generateSocialInsights(
    String userId,
    UserDemographicProfile userProfile,
    Map<String, dynamic> userMetrics,
  ) async {
    final insights = <SocialComparisonInsight>[];

    // Get real peer comparison data from backend
    final peerComparisonData = await _apiService.getPeerComparison();

    // Check if API returned valid data
    if (peerComparisonData['error'] != null) {
      // Fallback to estimated data if API is unavailable
      final peerData = _generateFallbackPeerData(userProfile.incomeTier);
      return _generateInsightsFromFallbackData(peerData, userMetrics);
    }

    final peerData = _extractPeerData(peerComparisonData);

    // Spending comparison
    final userSpending = (userMetrics['monthlySpending'] as num?)?.toDouble() ?? 0.0;
    final peerAverageSpending = peerData['averageSpending']!;
    final spendingPercentile = _calculatePercentile(userSpending, peerAverageSpending);

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

    // Savings rate comparison
    final userSavingsRate = (userMetrics['savingsRate'] as num?)?.toDouble() ?? 0.0;
    final peerAverageSavingsRate = peerData['averageSavingsRate']!;
    final savingsPercentile = _calculatePercentile(userSavingsRate, peerAverageSavingsRate);

    insights.add(SocialComparisonInsight(
      insightId: 'savings_comparison_${DateTime.now().millisecondsSinceEpoch}',
      insightType: 'savings_comparison',
      category: 'savings_rate',
      userValue: userSavingsRate,
      peerAverage: peerAverageSavingsRate,
      percentile: savingsPercentile,
      comparisonText: _generateComparisonText(
          'savings_rate', savingsPercentile, userSavingsRate, peerAverageSavingsRate),
      recommendation: _generateRecommendation('savings_rate', savingsPercentile),
      confidenceLevel: 0.8,
      metadata: {
        'sampleSize': peerData['sampleSize'],
        'incomeTier': userProfile.incomeTier.toString(),
      },
    ));

    return insights;
  }

  /// Extract peer data from API response
  Map<String, double> _extractPeerData(Map<String, dynamic> apiResponse) {
    return {
      'averageSpending': (apiResponse['peer_average'] as num?)?.toDouble() ?? 0.0,
      'averageSavingsRate': (apiResponse['peer_savings_rate'] as num?)?.toDouble() ?? 0.15,
      'sampleSize': (apiResponse['cohort_size'] as num?)?.toDouble() ?? 1000.0,
    };
  }

  /// Generate fallback insights when API is unavailable
  List<SocialComparisonInsight> _generateInsightsFromFallbackData(
    Map<String, double> peerData,
    Map<String, dynamic> userMetrics,
  ) {
    final insights = <SocialComparisonInsight>[];

    final userSpending = (userMetrics['monthlySpending'] as num?)?.toDouble() ?? 0.0;
    final peerAverageSpending = peerData['averageSpending']!;
    final spendingPercentile = _calculatePercentile(userSpending, peerAverageSpending);

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
      confidenceLevel: 0.6, // Lower confidence for fallback data
      metadata: {
        'sampleSize': peerData['sampleSize'],
        'fallback': true,
      },
    ));

    return insights;
  }

  Map<String, double> _generateFallbackPeerData(IncomeTier incomeTier) {
    // Fallback peer averages based on income tier (used when API is unavailable)
    switch (incomeTier) {
      case IncomeTier.low:
        return {
          'averageSpending': 2200.0,
          'averageSavingsRate': 0.08,
          'sampleSize': 1500.0,
        };
      case IncomeTier.lowerMiddle:
        return {
          'averageSpending': 3200.0,
          'averageSavingsRate': 0.12,
          'sampleSize': 2200.0,
        };
      case IncomeTier.middle:
        return {
          'averageSpending': 4800.0,
          'averageSavingsRate': 0.18,
          'sampleSize': 3100.0,
        };
      case IncomeTier.upperMiddle:
        return {
          'averageSpending': 7500.0,
          'averageSavingsRate': 0.25,
          'sampleSize': 1800.0,
        };
      case IncomeTier.high:
        return {
          'averageSpending': 12000.0,
          'averageSavingsRate': 0.35,
          'sampleSize': 800.0,
        };
    }
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
