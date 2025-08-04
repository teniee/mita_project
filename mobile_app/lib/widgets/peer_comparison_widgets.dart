import 'package:flutter/material.dart';
import '../services/income_service.dart';
import '../services/api_service.dart';

/// Peer spending insights widget for category breakdown
class PeerSpendingInsightsWidget extends StatelessWidget {
  final String category;
  final double userAmount;
  final double monthlyIncome;
  final Map<String, dynamic>? peerData;

  const PeerSpendingInsightsWidget({
    Key? key,
    required this.category,
    required this.userAmount,
    required this.monthlyIncome,
    this.peerData,
  }) : super(key: key);

  @override
  Widget build(BuildContext context) {
    final incomeService = IncomeService();
    final tier = incomeService.classifyIncome(monthlyIncome);
    final primaryColor = incomeService.getIncomeTierPrimaryColor(tier);
    
    final peerAverage = peerData?['categories']?[category.toLowerCase()]?['peer_average'] ?? userAmount * 1.2;
    final userPercentage = incomeService.getIncomePercentage(userAmount, monthlyIncome);
    final peerPercentage = incomeService.getIncomePercentage(peerAverage, monthlyIncome);
    final difference = ((userAmount - peerAverage) / peerAverage * 100);
    
    final isUserBetter = userAmount < peerAverage;
    final comparison = incomeService.getPeerComparisonMessage(tier, category, userAmount, peerAverage);

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
                    fontFamily: 'Sora',
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
                  color: isUserBetter ? Colors.green.shade600 : Colors.orange.shade600,
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
                color: (isUserBetter ? Colors.green : Colors.orange).withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Row(
                children: [
                  Icon(
                    isUserBetter ? Icons.trending_down : Icons.trending_up,
                    color: isUserBetter ? Colors.green.shade600 : Colors.orange.shade600,
                    size: 16,
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      comparison,
                      style: TextStyle(
                        fontFamily: 'Manrope',
                        fontSize: 13,
                        color: (isUserBetter ? Colors.green : Colors.orange).shade700,
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
                fontFamily: 'Manrope',
                fontSize: 14,
                fontWeight: isHighlighted ? FontWeight.w600 : FontWeight.w500,
                color: isHighlighted ? color : Colors.grey.shade700,
              ),
            ),
            Text(
              '\$${amount.toStringAsFixed(0)} (${percentage.toStringAsFixed(1)}%)',
              style: TextStyle(
                fontFamily: 'Sora',
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
    Key? key,
    required this.monthlyIncome,
  }) : super(key: key);

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
      if (mounted) {
        setState(() {
          _cohortData = _getDefaultCohortData();
          _isLoading = false;
        });
      }
    }
  }

  Map<String, dynamic> _getDefaultCohortData() {
    final tier = _incomeService.classifyIncome(widget.monthlyIncome);
    final tierName = _incomeService.getIncomeTierName(tier);
    
    return {
      'cohort_size': tier == IncomeTier.low ? 2847 
                   : tier == IncomeTier.lowerMiddle ? 3241
                   : tier == IncomeTier.middle ? 4126 
                   : tier == IncomeTier.upperMiddle ? 2089
                   : 1653,
      'your_rank': tier == IncomeTier.low ? 842 
                 : tier == IncomeTier.lowerMiddle ? 973
                 : tier == IncomeTier.middle ? 1247 
                 : tier == IncomeTier.upperMiddle ? 542
                 : 423,
      'percentile': 70,
      'top_insights': [
        '$tierName users typically save ${tier == IncomeTier.low ? "8-12" : tier == IncomeTier.lowerMiddle ? "12-16" : tier == IncomeTier.middle ? "15-20" : tier == IncomeTier.upperMiddle ? "20-28" : "25-35"}% of income',
        'Most peers spend ${tier == IncomeTier.low ? "40" : tier == IncomeTier.lowerMiddle ? "35-38" : tier == IncomeTier.middle ? "30-35" : tier == IncomeTier.upperMiddle ? "28-32" : "25-30"}% on housing',
        'Food expenses average ${tier == IncomeTier.low ? "15-18" : tier == IncomeTier.lowerMiddle ? "13-16" : tier == IncomeTier.middle ? "12-15" : tier == IncomeTier.upperMiddle ? "10-13" : "8-12"}% in your group',
      ],
      'recommendations': _incomeService.getFinancialTips(tier).take(3).toList(),
    };
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
    
    final cohortSize = _cohortData!['cohort_size'] ?? 0;
    final yourRank = _cohortData!['your_rank'] ?? 0;
    final percentile = _cohortData!['percentile'] ?? 0;
    final insights = List<String>.from(_cohortData!['top_insights'] ?? []);
    final recommendations = List<String>.from(_cohortData!['recommendations'] ?? []);

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
                          fontFamily: 'Sora',
                          fontWeight: FontWeight.bold,
                          fontSize: 18,
                          color: primaryColor,
                        ),
                      ),
                      Text(
                        '$cohortSize users • You\'re #$yourRank (${percentile}th percentile)',
                        style: const TextStyle(
                          fontFamily: 'Manrope',
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
                          fontFamily: 'Sora',
                          fontWeight: FontWeight.w600,
                          color: primaryColor,
                        ),
                      ),
                      Text(
                        '${percentile}th percentile',
                        style: TextStyle(
                          fontFamily: 'Sora',
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
                    percentile >= 70 ? 'You\'re doing better than most!' 
                    : percentile >= 50 ? 'You\'re on track with your peers'
                    : 'Room for improvement compared to peers',
                    style: TextStyle(
                      fontFamily: 'Manrope',
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
                fontFamily: 'Sora',
                fontWeight: FontWeight.w600,
                fontSize: 16,
                color: primaryColor,
              ),
            ),
            const SizedBox(height: 12),
            
            ...insights.map((insight) => 
              Padding(
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
                          fontFamily: 'Manrope',
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
                  fontFamily: 'Sora',
                  fontWeight: FontWeight.w600,
                  fontSize: 16,
                  color: primaryColor,
                ),
              ),
              const SizedBox(height: 12),
              
              ...recommendations.map((recommendation) => 
                Container(
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
                            fontFamily: 'Manrope',
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
    Key? key,
    required this.userSpending,
    required this.monthlyIncome,
    this.peerData,
  }) : super(key: key);

  @override
  Widget build(BuildContext context) {
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
                    fontFamily: 'Sora',
                    fontWeight: FontWeight.bold,
                    fontSize: 18,
                    color: primaryColor,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 20),
            
            ...userSpending.entries.map((entry) {
              final category = entry.key;
              final userAmount = entry.value;
              final peerAmount = peerData?['categories']?[category]?['peer_average'] ?? userAmount * 1.15;
              final userPercentage = incomeService.getIncomePercentage(userAmount, monthlyIncome);
              final peerPercentage = incomeService.getIncomePercentage(peerAmount, monthlyIncome);
              final categoryColor = categoryColors[category] ?? Colors.grey.shade600;
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
                            fontFamily: 'Sora',
                            fontWeight: FontWeight.w600,
                            fontSize: 14,
                            color: categoryColor,
                          ),
                        ),
                        Icon(
                          isUserBetter ? Icons.thumb_up_rounded : Icons.trending_up_rounded,
                          color: isUserBetter ? Colors.green.shade600 : Colors.orange.shade600,
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
                              fontFamily: 'Manrope',
                              fontSize: 12,
                              color: Colors.grey.shade600,
                            ),
                          ),
                        ),
                        Expanded(
                          child: LinearProgressIndicator(
                            value: (userPercentage / 30).clamp(0.0, 1.0),
                            backgroundColor: Colors.grey.shade200,
                            valueColor: AlwaysStoppedAnimation<Color>(categoryColor),
                            minHeight: 6,
                          ),
                        ),
                        const SizedBox(width: 8),
                        SizedBox(
                          width: 60,
                          child: Text(
                            '\$${userAmount.toStringAsFixed(0)}',
                            style: TextStyle(
                              fontFamily: 'Sora',
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
                              fontFamily: 'Manrope',
                              fontSize: 12,
                              color: Colors.grey.shade600,
                            ),
                          ),
                        ),
                        Expanded(
                          child: LinearProgressIndicator(
                            value: (peerPercentage / 30).clamp(0.0, 1.0),
                            backgroundColor: Colors.grey.shade200,
                            valueColor: AlwaysStoppedAnimation<Color>(Colors.grey.shade500),
                            minHeight: 4,
                          ),
                        ),
                        const SizedBox(width: 8),
                        SizedBox(
                          width: 60,
                          child: Text(
                            '\$${peerAmount.toStringAsFixed(0)}',
                            style: TextStyle(
                              fontFamily: 'Sora',
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
            }).toList(),
          ],
        ),
      ),
    );
  }
}