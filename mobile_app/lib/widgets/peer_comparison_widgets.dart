import 'package:flutter/material.dart';
import '../utils/json_utils.dart';
import '../services/income_service.dart';
import '../services/api_service.dart';
import '../theme/app_typography.dart';
import '../utils/peer_data.dart';

// Re-exported so existing widget-side imports of hasSufficientPeerData keep
// resolving; the canonical definition lives in utils/peer_data.dart so that
// services can share it without importing Flutter.
export '../utils/peer_data.dart' show hasSufficientPeerData;

/// Peer spending insights widget for category breakdown
class PeerSpendingInsightsWidget extends StatelessWidget {
  final String category;
  final double userAmount;
  final double monthlyIncome;
  final Map<String, dynamic>? peerData;

  const PeerSpendingInsightsWidget({
    super.key,
    required this.category,
    required this.userAmount,
    required this.monthlyIncome,
    this.peerData,
  });

  @override
  Widget build(BuildContext context) {
    // Same rule as SpendingTrendsComparisonWidget: no peers, no comparison.
    if (!hasSufficientPeerData(peerData)) return const SizedBox.shrink();

    final incomeService = IncomeService();
    final tier = incomeService.classifyIncome(monthlyIncome);
    final primaryColor = incomeService.getIncomeTierPrimaryColor(tier);

    // No per-category fallback. /cohort/peer_comparison sends an overall
    // peer_average and no `categories` map at all, so `userAmount * 1.2` was
    // never a stand-in for a missing figure — it was the only figure, and
    // getPeerComparisonMessage turned it into "You spend 17% less on
    // $category than other ${tierName}s" for every category and every user,
    // because (u - 1.2u) / 1.2u is a constant.
    final peerAverage = asDoubleOrNull(asStringKeyedMap(asStringKeyedMap(
        peerData?['categories'])[category.toLowerCase()])['peer_average']);
    if (peerAverage == null || peerAverage <= 0) {
      return const SizedBox.shrink();
    }
    final userPercentage =
        incomeService.getIncomePercentage(userAmount, monthlyIncome);
    final peerPercentage =
        incomeService.getIncomePercentage(peerAverage, monthlyIncome);

    final isUserBetter = userAmount < peerAverage;
    final comparison = incomeService.getPeerComparisonMessage(
        tier, category, userAmount, peerAverage);

    return Card(
      elevation: 2,
      margin: const EdgeInsets.symmetric(vertical: 8),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
      ),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(
                  Icons.people_rounded,
                  color: primaryColor,
                  size: 20,
                ),
                const SizedBox(width: 8),
                Text(
                  'Peer Comparison: $category',
                  style: TextStyle(
                    fontFamily: AppTypography.fontHeading,
                    fontWeight: FontWeight.w600,
                    fontSize: 16,
                    color: primaryColor,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),

            // Comparison bars
            Column(
              children: [
                // User spending
                _buildComparisonBar(
                  label: 'Your Spending',
                  amount: userAmount,
                  percentage: userPercentage,
                  color: isUserBetter
                      ? Colors.green.shade600
                      : Colors.orange.shade600,
                  isHighlighted: true,
                ),
                const SizedBox(height: 12),

                // Peer average
                _buildComparisonBar(
                  label: 'Peer Average',
                  amount: peerAverage,
                  percentage: peerPercentage,
                  color: Colors.grey.shade600,
                  isHighlighted: false,
                ),
              ],
            ),

            const SizedBox(height: 16),

            // Insight message
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: (isUserBetter ? Colors.green : Colors.orange)
                    .withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Row(
                children: [
                  Icon(
                    isUserBetter ? Icons.trending_down : Icons.trending_up,
                    color: isUserBetter
                        ? Colors.green.shade600
                        : Colors.orange.shade600,
                    size: 16,
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      comparison,
                      style: TextStyle(
                        fontFamily: AppTypography.fontBody,
                        fontSize: 13,
                        color: (isUserBetter ? Colors.green : Colors.orange)
                            .shade700,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildComparisonBar({
    required String label,
    required double amount,
    required double percentage,
    required Color color,
    required bool isHighlighted,
  }) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(
              label,
              style: TextStyle(
                fontFamily: AppTypography.fontBody,
                fontSize: 14,
                fontWeight: isHighlighted ? FontWeight.w600 : FontWeight.w500,
                color: isHighlighted ? color : Colors.grey.shade700,
              ),
            ),
            Text(
              '\$${amount.toStringAsFixed(0)} (${percentage.toStringAsFixed(1)}%)',
              style: TextStyle(
                fontFamily: AppTypography.fontHeading,
                fontSize: 14,
                fontWeight: FontWeight.bold,
                color: color,
              ),
            ),
          ],
        ),
        const SizedBox(height: 6),
        LinearProgressIndicator(
          value: (percentage / 50).clamp(0.0, 1.0), // Max 50% for visualization
          backgroundColor: Colors.grey.shade200,
          valueColor: AlwaysStoppedAnimation<Color>(color),
          minHeight: isHighlighted ? 6 : 4,
        ),
      ],
    );
  }
}

/// Cohort insights widget showing behavioral patterns
class CohortInsightsWidget extends StatefulWidget {
  final double monthlyIncome;

  const CohortInsightsWidget({
    super.key,
    required this.monthlyIncome,
  });

  @override
  State<CohortInsightsWidget> createState() => _CohortInsightsWidgetState();
}

class _CohortInsightsWidgetState extends State<CohortInsightsWidget> {
  final ApiService _apiService = ApiService();
  final IncomeService _incomeService = IncomeService();

  Map<String, dynamic>? _cohortData;
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    _loadCohortInsights();
  }

  Future<void> _loadCohortInsights() async {
    try {
      final cohortInsights = await _apiService.getCohortInsights();
      if (mounted) {
        setState(() {
          _cohortData = cohortInsights;
          _isLoading = false;
        });
      }
    } catch (e) {
      // No fabricated cohort. A null cohort_size drives the existing
      // "nothing to rank against" empty state below rather than inventing
      // a peer group, a rank and a percentile for the user.
      if (mounted) {
        setState(() {
          _cohortData = <String, dynamic>{
            'error': 'Cohort insights service is currently unavailable',
            'cohort_size': null,
            'your_rank': null,
            'percentile': null,
            'top_insights': <String>[],
            'recommendations': <String>[],
          };
          _isLoading = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_isLoading) {
      return const Card(
        child: Padding(
          padding: EdgeInsets.all(20),
          child: Center(child: CircularProgressIndicator()),
        ),
      );
    }

    if (_cohortData == null) return Container();

    final tier = _incomeService.classifyIncome(widget.monthlyIncome);
    final primaryColor = _incomeService.getIncomeTierPrimaryColor(tier);
    final tierName = _incomeService.getIncomeTierName(tier);

    final cohortSize = asInt(_cohortData!['cohort_size']);
    final yourRank = asInt(_cohortData!['your_rank']);
    final percentile = asInt(_cohortData!['percentile']);
    final insights = asStringList(_cohortData!['top_insights']);
    final recommendations = asStringList(_cohortData!['recommendations']);

    // An empty cohort supports no ranking. This used to render
    // "0 users • You're #0 (0th percentile)" and, underneath, "Room for
    // improvement compared to peers" — a judgement passed on a first-day user
    // against nobody at all.
    if (cohortSize <= 0) {
      return Card(
        elevation: 3,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(Icons.groups_outlined, color: primaryColor, size: 28),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Your $tierName Cohort',
                      style: TextStyle(
                        fontFamily: AppTypography.fontHeading,
                        fontWeight: FontWeight.bold,
                        fontSize: 18,
                        color: primaryColor,
                      ),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      'No one else in your income range has joined yet, so '
                      'there is nothing to rank against.',
                      style: TextStyle(
                        fontFamily: AppTypography.fontBody,
                        fontSize: 14,
                        color: Colors.grey.shade700,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      );
    }

    return Card(
      elevation: 3,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
      ),
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(
                  Icons.groups_rounded,
                  color: primaryColor,
                  size: 28,
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Your $tierName Cohort',
                        style: TextStyle(
                          fontFamily: AppTypography.fontHeading,
                          fontWeight: FontWeight.bold,
                          fontSize: 18,
                          color: primaryColor,
                        ),
                      ),
                      Text(
                        '$cohortSize users • You\'re #$yourRank (${percentile}th percentile)',
                        style: const TextStyle(
                          fontFamily: AppTypography.fontBody,
                          fontSize: 14,
                          color: Colors.black87,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),

            const SizedBox(height: 20),

            // Percentile visualization
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: primaryColor.withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Column(
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text(
                        'Performance Ranking',
                        style: TextStyle(
                          fontFamily: AppTypography.fontHeading,
                          fontWeight: FontWeight.w600,
                          color: primaryColor,
                        ),
                      ),
                      Text(
                        '${percentile}th percentile',
                        style: TextStyle(
                          fontFamily: AppTypography.fontHeading,
                          fontWeight: FontWeight.bold,
                          fontSize: 16,
                          color: primaryColor,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  LinearProgressIndicator(
                    value: percentile / 100,
                    backgroundColor: Colors.grey.shade200,
                    valueColor: AlwaysStoppedAnimation<Color>(primaryColor),
                    minHeight: 8,
                  ),
                  const SizedBox(height: 8),
                  Text(
                    percentile >= 70
                        ? 'You\'re doing better than most!'
                        : percentile >= 50
                            ? 'You\'re on track with your peers'
                            : 'Room for improvement compared to peers',
                    style: TextStyle(
                      fontFamily: AppTypography.fontBody,
                      fontSize: 12,
                      color: primaryColor,
                    ),
                  ),
                ],
              ),
            ),

            const SizedBox(height: 20),

            // Key insights
            Text(
              'Cohort Insights',
              style: TextStyle(
                fontFamily: AppTypography.fontHeading,
                fontWeight: FontWeight.w600,
                fontSize: 16,
                color: primaryColor,
              ),
            ),
            const SizedBox(height: 12),

            ...insights.map(
              (insight) => Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Container(
                      margin: const EdgeInsets.only(top: 6),
                      width: 4,
                      height: 4,
                      decoration: BoxDecoration(
                        color: primaryColor,
                        shape: BoxShape.circle,
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Text(
                        insight,
                        style: const TextStyle(
                          fontFamily: AppTypography.fontBody,
                          fontSize: 14,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),

            if (recommendations.isNotEmpty) ...[
              const SizedBox(height: 16),
              Text(
                'Recommendations for Your Tier',
                style: TextStyle(
                  fontFamily: AppTypography.fontHeading,
                  fontWeight: FontWeight.w600,
                  fontSize: 16,
                  color: primaryColor,
                ),
              ),
              const SizedBox(height: 12),
              ...recommendations.map(
                (recommendation) => Container(
                  margin: const EdgeInsets.only(bottom: 8),
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: Colors.green.shade50,
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(color: Colors.green.shade200),
                  ),
                  child: Row(
                    children: [
                      Icon(
                        Icons.lightbulb_outline,
                        color: Colors.green.shade600,
                        size: 16,
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          recommendation,
                          style: TextStyle(
                            fontFamily: AppTypography.fontBody,
                            fontSize: 13,
                            color: Colors.green.shade700,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

/// Spending trends comparison widget
class SpendingTrendsComparisonWidget extends StatelessWidget {
  final Map<String, double> userSpending;
  final double monthlyIncome;
  final Map<String, dynamic>? peerData;

  const SpendingTrendsComparisonWidget({
    super.key,
    required this.userSpending,
    required this.monthlyIncome,
    this.peerData,
  });

  /// The server's own peer average for one category, or null when it did not
  /// send one. Never a value derived from the user's own spending.
  double? _peerAverageFor(String category) => asDoubleOrNull(asStringKeyedMap(
      asStringKeyedMap(peerData?['categories'])[category])['peer_average']);

  @override
  Widget build(BuildContext context) {
    // Nothing to compare against. The two cards above this one already tell
    // the user why, so stay silent rather than invent a peer average
    // (this used to fall back to userAmount * 1.15 and render "Peers $230"
    // beside a green thumbs-up, with peer_count = 0).
    if (!hasSufficientPeerData(peerData)) return const SizedBox.shrink();

    // A cohort exists, but that does not mean a PER-CATEGORY comparison does.
    // The endpoint sends one overall peer_average and no `categories` map, so
    // this fell through to `userAmount * 1.15` for every row: the "Peers"
    // figure beside each category was the user's own spending plus 15%, and
    // `isUserBetter` (userAmount < peerAmount) was therefore true for every
    // category, always — a green thumbs-up on every line, derived from
    // nothing. Only categories the server actually priced are shown.
    final comparable = userSpending.entries
        .where((entry) => (_peerAverageFor(entry.key) ?? 0) > 0)
        .toList();
    if (comparable.isEmpty) return const SizedBox.shrink();

    final incomeService = IncomeService();
    final tier = incomeService.classifyIncome(monthlyIncome);
    final primaryColor = incomeService.getIncomeTierPrimaryColor(tier);
    final categoryColors = {
      'food': Colors.orange.shade600,
      'transportation': Colors.blue.shade600,
      'entertainment': Colors.purple.shade600,
      'shopping': Colors.pink.shade600,
      'healthcare': Colors.green.shade600,
      'housing': Colors.brown.shade600,
    };

    return Card(
      elevation: 2,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
      ),
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(
                  Icons.trending_up_rounded,
                  color: primaryColor,
                  size: 24,
                ),
                const SizedBox(width: 12),
                Text(
                  'Spending vs Peers',
                  style: TextStyle(
                    fontFamily: AppTypography.fontHeading,
                    fontWeight: FontWeight.bold,
                    fontSize: 18,
                    color: primaryColor,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 20),
            ...comparable.map((entry) {
              final category = entry.key;
              final userAmount = entry.value;
              final peerAmount = _peerAverageFor(category)!;
              final userPercentage =
                  incomeService.getIncomePercentage(userAmount, monthlyIncome);
              final peerPercentage =
                  incomeService.getIncomePercentage(peerAmount, monthlyIncome);
              final categoryColor =
                  categoryColors[category] ?? Colors.grey.shade600;
              final isUserBetter = userAmount < peerAmount;

              return Container(
                margin: const EdgeInsets.only(bottom: 16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Text(
                          category.toUpperCase(),
                          style: TextStyle(
                            fontFamily: AppTypography.fontHeading,
                            fontWeight: FontWeight.w600,
                            fontSize: 14,
                            color: categoryColor,
                          ),
                        ),
                        Icon(
                          isUserBetter
                              ? Icons.thumb_up_rounded
                              : Icons.trending_up_rounded,
                          color: isUserBetter
                              ? Colors.green.shade600
                              : Colors.orange.shade600,
                          size: 16,
                        ),
                      ],
                    ),
                    const SizedBox(height: 8),

                    // User bar
                    Row(
                      children: [
                        SizedBox(
                          width: 40,
                          child: Text(
                            'You',
                            style: TextStyle(
                              fontFamily: AppTypography.fontBody,
                              fontSize: 12,
                              color: Colors.grey.shade600,
                            ),
                          ),
                        ),
                        Expanded(
                          child: LinearProgressIndicator(
                            value: (userPercentage / 30).clamp(0.0, 1.0),
                            backgroundColor: Colors.grey.shade200,
                            valueColor:
                                AlwaysStoppedAnimation<Color>(categoryColor),
                            minHeight: 6,
                          ),
                        ),
                        const SizedBox(width: 8),
                        SizedBox(
                          width: 60,
                          child: Text(
                            '\$${userAmount.toStringAsFixed(0)}',
                            style: TextStyle(
                              fontFamily: AppTypography.fontHeading,
                              fontWeight: FontWeight.bold,
                              fontSize: 12,
                              color: categoryColor,
                            ),
                            textAlign: TextAlign.end,
                          ),
                        ),
                      ],
                    ),

                    const SizedBox(height: 4),

                    // Peer bar
                    Row(
                      children: [
                        SizedBox(
                          width: 40,
                          child: Text(
                            'Peers',
                            style: TextStyle(
                              fontFamily: AppTypography.fontBody,
                              fontSize: 12,
                              color: Colors.grey.shade600,
                            ),
                          ),
                        ),
                        Expanded(
                          child: LinearProgressIndicator(
                            value: (peerPercentage / 30).clamp(0.0, 1.0),
                            backgroundColor: Colors.grey.shade200,
                            valueColor: AlwaysStoppedAnimation<Color>(
                                Colors.grey.shade500),
                            minHeight: 4,
                          ),
                        ),
                        const SizedBox(width: 8),
                        SizedBox(
                          width: 60,
                          child: Text(
                            '\$${peerAmount.toStringAsFixed(0)}',
                            style: TextStyle(
                              fontFamily: AppTypography.fontHeading,
                              fontWeight: FontWeight.w500,
                              fontSize: 12,
                              color: Colors.grey.shade600,
                            ),
                            textAlign: TextAlign.end,
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              );
            }),
          ],
        ),
      ),
    );
  }
}
