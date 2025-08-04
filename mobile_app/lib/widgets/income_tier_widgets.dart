import 'package:flutter/material.dart';
import '../services/income_service.dart';

/// Income tier display card with Material 3 styling
class IncomeTierCard extends StatelessWidget {
  final double monthlyIncome;
  final bool showDetails;
  final VoidCallback? onTap;

  const IncomeTierCard({
    Key? key,
    required this.monthlyIncome,
    this.showDetails = true,
    this.onTap,
  }) : super(key: key);

  @override
  Widget build(BuildContext context) {
    final incomeService = IncomeService();
    final tier = incomeService.classifyIncome(monthlyIncome);
    final tierName = incomeService.getIncomeTierName(tier);
    final tierDescription = incomeService.getIncomeTierDescription(tier);
    final rangeString = incomeService.getIncomeRangeString(tier);
    final primaryColor = incomeService.getIncomeTierPrimaryColor(tier);
    final secondaryColor = incomeService.getIncomeTierSecondaryColor(tier);
    final icon = incomeService.getIncomeTierIcon(tier);

    return Card(
      elevation: 2,
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
      ),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(16),
        child: Container(
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(16),
            gradient: LinearGradient(
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
              colors: [
                secondaryColor,
                secondaryColor.withValues(alpha: 0.7),
              ],
            ),
          ),
          child: Padding(
            padding: const EdgeInsets.all(20),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Container(
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: primaryColor,
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Icon(
                        icon,
                        color: Colors.white,
                        size: 24,
                      ),
                    ),
                    const SizedBox(width: 16),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            tierName,
                            style: Theme.of(context).textTheme.titleLarge?.copyWith(
                              fontWeight: FontWeight.bold,
                              color: primaryColor,
                              fontFamily: 'Sora',
                            ),
                          ),
                          const SizedBox(height: 4),
                          Text(
                            rangeString,
                            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                              color: primaryColor.withValues(alpha: 0.8),
                              fontFamily: 'Manrope',
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
                if (showDetails) ...[
                  const SizedBox(height: 16),
                  Text(
                    tierDescription,
                    style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                      color: Colors.black87,
                      fontFamily: 'Manrope',
                    ),
                  ),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }
}

/// Compact income tier badge
class IncomeTierBadge extends StatelessWidget {
  final double monthlyIncome;
  final bool showIcon;

  const IncomeTierBadge({
    Key? key,
    required this.monthlyIncome,
    this.showIcon = true,
  }) : super(key: key);

  @override
  Widget build(BuildContext context) {
    final incomeService = IncomeService();
    final tier = incomeService.classifyIncome(monthlyIncome);
    final tierName = incomeService.getIncomeTierName(tier);
    final primaryColor = incomeService.getIncomeTierPrimaryColor(tier);
    final icon = incomeService.getIncomeTierIcon(tier);

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      decoration: BoxDecoration(
        color: primaryColor.withValues(alpha: 0.1),
        border: Border.all(color: primaryColor.withValues(alpha: 0.3)),
        borderRadius: BorderRadius.circular(20),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (showIcon) ...[
            Icon(
              icon,
              size: 16,
              color: primaryColor,
            ),
            const SizedBox(width: 6),
          ],
          Text(
            tierName,
            style: TextStyle(
              color: primaryColor,
              fontWeight: FontWeight.w600,
              fontSize: 12,
              fontFamily: 'Sora',
            ),
          ),
        ],
      ),
    );
  }
}

/// Income percentage indicator
class IncomePercentageIndicator extends StatelessWidget {
  final double amount;
  final double monthlyIncome;
  final String label;
  final bool showProgressBar;

  const IncomePercentageIndicator({
    Key? key,
    required this.amount,
    required this.monthlyIncome,
    required this.label,
    this.showProgressBar = true,
  }) : super(key: key);

  @override
  Widget build(BuildContext context) {
    final incomeService = IncomeService();
    final percentage = incomeService.getIncomePercentage(amount, monthlyIncome);
    final category = incomeService.getSpendingPercentageCategory(percentage);
    
    Color getPercentageColor() {
      if (percentage < 5) return Colors.green;
      if (percentage < 15) return Colors.lightGreen;
      if (percentage < 30) return Colors.orange;
      if (percentage < 50) return Colors.deepOrange;
      return Colors.red;
    }

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: Colors.grey.shade200),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                label,
                style: Theme.of(context).textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.w600,
                  fontFamily: 'Sora',
                ),
              ),
              Text(
                '${percentage.toStringAsFixed(1)}%',
                style: Theme.of(context).textTheme.titleMedium?.copyWith(
                  color: getPercentageColor(),
                  fontWeight: FontWeight.bold,
                  fontFamily: 'Sora',
                ),
              ),
            ],
          ),
          const SizedBox(height: 4),
          Text(
            '$category impact on income',
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
              color: Colors.grey.shade600,
              fontFamily: 'Manrope',
            ),
          ),
          if (showProgressBar) ...[
            const SizedBox(height: 12),
            LinearProgressIndicator(
              value: (percentage / 100).clamp(0.0, 1.0),
              backgroundColor: Colors.grey.shade200,
              valueColor: AlwaysStoppedAnimation<Color>(getPercentageColor()),
              minHeight: 6,
            ),
          ],
        ],
      ),
    );
  }
}

/// Peer comparison card
class PeerComparisonCard extends StatelessWidget {
  final Map<String, dynamic> comparisonData;
  final double monthlyIncome;

  const PeerComparisonCard({
    Key? key,
    required this.comparisonData,
    required this.monthlyIncome,
  }) : super(key: key);

  @override
  Widget build(BuildContext context) {
    final incomeService = IncomeService();
    final tier = incomeService.classifyIncome(monthlyIncome);
    final tierName = incomeService.getIncomeTierName(tier);
    final primaryColor = incomeService.getIncomeTierPrimaryColor(tier);
    
    final yourSpending = comparisonData['your_spending'] as double? ?? 0.0;
    final peerAverage = comparisonData['peer_average'] as double? ?? 0.0;
    final percentile = comparisonData['percentile'] as int? ?? 50;
    final insights = List<String>.from(comparisonData['insights'] ?? []);

    final isAboveAverage = yourSpending > peerAverage;
    final difference = ((yourSpending - peerAverage) / peerAverage * 100).abs();

    return Card(
      elevation: 3,
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
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
                  Icons.people_rounded,
                  color: primaryColor,
                  size: 28,
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Compare with $tierName Peers',
                        style: Theme.of(context).textTheme.titleLarge?.copyWith(
                          fontWeight: FontWeight.bold,
                          fontFamily: 'Sora',
                        ),
                      ),
                      Text(
                        'You\'re in the ${percentile}th percentile',
                        style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                          color: primaryColor,
                          fontFamily: 'Manrope',
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
            const SizedBox(height: 20),
            
            // Spending comparison
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: primaryColor.withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Row(
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'Your Spending',
                          style: Theme.of(context).textTheme.bodySmall?.copyWith(
                            color: Colors.grey.shade600,
                            fontFamily: 'Manrope',
                          ),
                        ),
                        Text(
                          '\$${yourSpending.toStringAsFixed(0)}',
                          style: Theme.of(context).textTheme.titleLarge?.copyWith(
                            fontWeight: FontWeight.bold,
                            fontFamily: 'Sora',
                          ),
                        ),
                      ],
                    ),
                  ),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                    decoration: BoxDecoration(
                      color: isAboveAverage ? Colors.red.shade100 : Colors.green.shade100,
                      borderRadius: BorderRadius.circular(20),
                    ),
                    child: Text(
                      '${isAboveAverage ? '+' : '-'}${difference.toStringAsFixed(0)}%',
                      style: TextStyle(
                        color: isAboveAverage ? Colors.red.shade700 : Colors.green.shade700,
                        fontWeight: FontWeight.bold,
                        fontSize: 12,
                        fontFamily: 'Sora',
                      ),
                    ),
                  ),
                  const SizedBox(width: 16),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.end,
                      children: [
                        Text(
                          'Peer Average',
                          style: Theme.of(context).textTheme.bodySmall?.copyWith(
                            color: Colors.grey.shade600,
                            fontFamily: 'Manrope',
                          ),
                        ),
                        Text(
                          '\$${peerAverage.toStringAsFixed(0)}',
                          style: Theme.of(context).textTheme.titleLarge?.copyWith(
                            color: Colors.grey.shade700,
                            fontWeight: FontWeight.bold,
                            fontFamily: 'Sora',
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
            
            if (insights.isNotEmpty) ...[
              const SizedBox(height: 16),
              Text(
                'Key Insights',
                style: Theme.of(context).textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.w600,
                  fontFamily: 'Sora',
                ),
              ),
              const SizedBox(height: 8),
              ...insights.take(3).map((insight) => Padding(
                padding: const EdgeInsets.only(bottom: 6),
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
                        style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                          fontFamily: 'Manrope',
                        ),
                      ),
                    ),
                  ],
                ),
              )),
            ],
          ],
        ),
      ),
    );
  }
}

/// Income-based goal suggestion card
class IncomeBasedGoalCard extends StatelessWidget {
  final Map<String, dynamic> goalData;
  final double monthlyIncome;
  final VoidCallback? onAddGoal;

  const IncomeBasedGoalCard({
    Key? key,
    required this.goalData,
    required this.monthlyIncome,
    this.onAddGoal,
  }) : super(key: key);

  @override
  Widget build(BuildContext context) {
    final incomeService = IncomeService();
    final tier = incomeService.classifyIncome(monthlyIncome);
    final primaryColor = incomeService.getIncomeTierPrimaryColor(tier);
    
    final title = goalData['title'] as String? ?? '';
    final description = goalData['description'] as String? ?? '';
    final targetAmount = goalData['target_amount'] as double? ?? 0.0;
    final monthlyTarget = goalData['monthly_target'] as double? ?? 0.0;
    final priority = goalData['priority'] as String? ?? 'medium';
    final iconData = goalData['icon'] as IconData? ?? Icons.flag_rounded;

    Color getPriorityColor() {
      switch (priority) {
        case 'high':
          return Colors.red.shade600;
        case 'medium':
          return Colors.orange.shade600;
        case 'low':
          return Colors.green.shade600;
        default:
          return Colors.grey.shade600;
      }
    }

    return Card(
      elevation: 2,
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
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
                Container(
                  padding: const EdgeInsets.all(10),
                  decoration: BoxDecoration(
                    color: primaryColor.withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Icon(
                    iconData,
                    color: primaryColor,
                    size: 20,
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Text(
                            title,
                            style: Theme.of(context).textTheme.titleMedium?.copyWith(
                              fontWeight: FontWeight.w600,
                              fontFamily: 'Sora',
                            ),
                          ),
                          const SizedBox(width: 8),
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                            decoration: BoxDecoration(
                              color: getPriorityColor().withValues(alpha: 0.1),
                              borderRadius: BorderRadius.circular(10),
                            ),
                            child: Text(
                              priority.toUpperCase(),
                              style: TextStyle(
                                color: getPriorityColor(),
                                fontSize: 10,
                                fontWeight: FontWeight.bold,
                                fontFamily: 'Sora',
                              ),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 4),
                      Text(
                        description,
                        style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                          color: Colors.grey.shade600,
                          fontFamily: 'Manrope',
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),
            Row(
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Target Amount',
                        style: Theme.of(context).textTheme.bodySmall?.copyWith(
                          color: Colors.grey.shade600,
                          fontFamily: 'Manrope',
                        ),
                      ),
                      Text(
                        '\$${targetAmount.toStringAsFixed(0)}',
                        style: Theme.of(context).textTheme.titleMedium?.copyWith(
                          fontWeight: FontWeight.bold,
                          fontFamily: 'Sora',
                        ),
                      ),
                    ],
                  ),
                ),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Monthly Target',
                        style: Theme.of(context).textTheme.bodySmall?.copyWith(
                          color: Colors.grey.shade600,
                          fontFamily: 'Manrope',
                        ),
                      ),
                      Text(
                        '\$${monthlyTarget.toStringAsFixed(0)}',
                        style: Theme.of(context).textTheme.titleMedium?.copyWith(
                          color: primaryColor,
                          fontWeight: FontWeight.bold,
                          fontFamily: 'Sora',
                        ),
                      ),
                    ],
                  ),
                ),
                if (onAddGoal != null)
                  ElevatedButton(
                    onPressed: onAddGoal,
                    style: ElevatedButton.styleFrom(
                      backgroundColor: primaryColor,
                      foregroundColor: Colors.white,
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(8),
                      ),
                      padding: const EdgeInsets.symmetric(horizontal: 16),
                    ),
                    child: const Text(
                      'Add Goal',
                      style: TextStyle(
                        fontSize: 12,
                        fontFamily: 'Sora',
                      ),
                    ),
                  ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

/// Income-aware spending category breakdown
class IncomeCategoryBreakdown extends StatelessWidget {
  final Map<String, double> categorySpending;
  final double monthlyIncome;

  const IncomeCategoryBreakdown({
    Key? key,
    required this.categorySpending,
    required this.monthlyIncome,
  }) : super(key: key);

  @override
  Widget build(BuildContext context) {
    final incomeService = IncomeService();
    final tier = incomeService.classifyIncome(monthlyIncome);
    final recommendedWeights = incomeService.getDefaultBudgetWeights(tier);
    final primaryColor = incomeService.getIncomeTierPrimaryColor(tier);

    return Card(
      elevation: 2,
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
      ),
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Spending vs Income',
              style: Theme.of(context).textTheme.titleLarge?.copyWith(
                fontWeight: FontWeight.bold,
                fontFamily: 'Sora',
              ),
            ),
            const SizedBox(height: 4),
            Text(
              'How your spending compares to income-appropriate levels',
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                color: Colors.grey.shade600,
                fontFamily: 'Manrope',
              ),
            ),
            const SizedBox(height: 20),
            ...categorySpending.entries.map((entry) {
              final category = entry.key;
              final amount = entry.value;
              final percentage = incomeService.getIncomePercentage(amount, monthlyIncome);
              final recommendedPercentage = (recommendedWeights[category.toLowerCase()] ?? 0.1) * 100;
              final isOverRecommended = percentage > recommendedPercentage;
              
              return Padding(
                padding: const EdgeInsets.only(bottom: 16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Text(
                          category.toUpperCase(),
                          style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                            fontWeight: FontWeight.w600,
                            fontFamily: 'Sora',
                          ),
                        ),
                        Text(
                          '${percentage.toStringAsFixed(1)}% of income',
                          style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                            color: isOverRecommended ? Colors.red.shade600 : primaryColor,
                            fontWeight: FontWeight.w600,
                            fontFamily: 'Sora',
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 8),
                    LinearProgressIndicator(
                      value: (percentage / 50).clamp(0.0, 1.0), // Max 50% for visualization
                      backgroundColor: Colors.grey.shade200,
                      valueColor: AlwaysStoppedAnimation<Color>(
                        isOverRecommended ? Colors.red.shade400 : primaryColor,
                      ),
                      minHeight: 6,
                    ),
                    const SizedBox(height: 4),
                    Text(
                      isOverRecommended 
                        ? '${(percentage - recommendedPercentage).toStringAsFixed(1)}% above recommended'
                        : '${(recommendedPercentage - percentage).toStringAsFixed(1)}% below recommended',
                      style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        color: isOverRecommended ? Colors.red.shade600 : Colors.green.shade600,
                        fontFamily: 'Manrope',
                      ),
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