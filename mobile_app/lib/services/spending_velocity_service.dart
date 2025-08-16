import 'dart:math';
import '../models/budget_intelligence_models.dart';

/// Advanced spending velocity intelligence for adaptive budget allocation
class SpendingVelocityService {
  static final SpendingVelocityService _instance = SpendingVelocityService._internal();
  factory SpendingVelocityService() => _instance;
  SpendingVelocityService._internal();

  /// Analyze current spending velocity against historical patterns
  Future<SpendingVelocityAnalysis> analyzeSpendingVelocity({
    required List<Map<String, dynamic>> recentTransactions,
    required List<Map<String, dynamic>> historicalTransactions,
    required double currentDailyBudget,
    required DateTime analysisDate,
  }) async {
    // Calculate current spending velocity (spending per day)
    final currentVelocity = _calculateCurrentVelocity(recentTransactions, analysisDate);
    
    // Calculate normal/historical velocity
    final normalVelocity = _calculateNormalVelocity(historicalTransactions);
    
    // Calculate velocity ratio
    final velocityRatio = normalVelocity > 0 ? currentVelocity / normalVelocity : 1.0;
    
    // Categorize velocity
    final velocityCategory = _categorizeVelocity(velocityRatio);
    
    // Calculate optimal remaining budget distribution
    final remainingBudgetOptimal = _calculateOptimalRemainingBudget(
      currentVelocity,
      normalVelocity,
      currentDailyBudget,
      analysisDate,
    );
    
    // Calculate redistribution amount
    final redistributionAmount = remainingBudgetOptimal - currentDailyBudget;
    
    // Generate insights
    final insights = _generateVelocityInsights(velocityRatio, velocityCategory, currentVelocity, normalVelocity);
    
    // Calculate confidence based on data quality
    final confidence = _calculateAnalysisConfidence(recentTransactions, historicalTransactions);
    
    return SpendingVelocityAnalysis(
      currentVelocity: currentVelocity,
      normalVelocity: normalVelocity,
      velocityRatio: velocityRatio,
      velocityCategory: velocityCategory,
      remainingBudgetOptimal: remainingBudgetOptimal,
      redistributionAmount: redistributionAmount,
      insights: insights,
      confidence: confidence,
      metadata: {
        'analysisDate': analysisDate.toIso8601String(),
        'recentTransactionCount': recentTransactions.length,
        'historicalTransactionCount': historicalTransactions.length,
        'currentDailyBudget': currentDailyBudget,
      },
    );
  }

  /// Create adaptive budget allocation based on velocity analysis
  Future<AdaptiveBudgetAllocation> createAdaptiveBudgetAllocation({
    required SpendingVelocityAnalysis velocityAnalysis,
    required double monthlyBudget,
    required DateTime startDate,
    int daysAhead = 30,
  }) async {
    final strategy = _determineAllocationStrategy(velocityAnalysis);
    
    // Calculate future budget allocations
    final futureBudgetAllocations = <DateTime, double>{};
    final dailyBaseAllocation = monthlyBudget / 30;
    
    for (int i = 0; i < daysAhead; i++) {
      final date = startDate.add(Duration(days: i));
      final dayBudget = _calculateDayBudget(
        dailyBaseAllocation,
        velocityAnalysis,
        date,
        strategy,
      );
      futureBudgetAllocations[date] = dayBudget;
    }
    
    // Calculate total remaining budget
    final totalRemainingBudget = futureBudgetAllocations.values.reduce((a, b) => a + b);
    
    // Generate recommendations
    final recommendations = _generateAllocationRecommendations(velocityAnalysis, strategy);
    
    // Calculate system confidence
    final systemConfidence = velocityAnalysis.confidence * 0.9; // Slightly lower for allocation predictions
    
    return AdaptiveBudgetAllocation(
      originalDailyBudget: dailyBaseAllocation,
      adjustedDailyBudget: velocityAnalysis.remainingBudgetOptimal,
      futureBudgetAllocations: futureBudgetAllocations,
      totalRemainingBudget: totalRemainingBudget,
      allocationStrategy: strategy,
      recommendations: recommendations,
      systemConfidence: systemConfidence,
    );
  }

  /// Detect spending patterns and provide velocity-based insights
  Future<List<String>> detectSpendingPatterns(
    List<Map<String, dynamic>> transactions,
  ) async {
    final patterns = <String>[];
    
    if (transactions.length < 10) {
      patterns.add('Insufficient transaction history for pattern detection');
      return patterns;
    }
    
    // Analyze spending consistency
    final dailySpending = _groupByDay(transactions);
    final spendingVariance = _calculateVariance(dailySpending.values.toList());
    
    if (spendingVariance > 50) {
      patterns.add('High spending variability detected - consider more consistent budgeting');
    } else if (spendingVariance < 10) {
      patterns.add('Very consistent spending pattern - good budget discipline');
    }
    
    // Analyze weekly patterns
    final weeklyPattern = _analyzeWeeklyPattern(transactions);
    if (weeklyPattern.isNotEmpty) {
      patterns.add(weeklyPattern);
    }
    
    // Analyze spending acceleration/deceleration
    final trendPattern = _analyzeTrend(transactions);
    if (trendPattern.isNotEmpty) {
      patterns.add(trendPattern);
    }
    
    return patterns.take(3).toList();
  }

  // Helper methods for velocity calculations

  double _calculateCurrentVelocity(List<Map<String, dynamic>> recentTransactions, DateTime analysisDate) {
    if (recentTransactions.isEmpty) return 0.0;
    
    // Calculate spending over the last 7 days
    final cutoffDate = analysisDate.subtract(const Duration(days: 7));
    final recentSpending = recentTransactions
        .where((t) {
          final date = DateTime.tryParse(t['date']?.toString() ?? '') ?? DateTime.now();
          return date.isAfter(cutoffDate);
        })
        .fold(0.0, (sum, t) => sum + ((t['amount'] as num?)?.toDouble() ?? 0.0));
    
    return recentSpending / 7; // Daily average over last 7 days
  }

  double _calculateNormalVelocity(List<Map<String, dynamic>> historicalTransactions) {
    if (historicalTransactions.isEmpty) return 0.0;
    
    final totalSpending = historicalTransactions.fold(0.0, 
        (sum, t) => sum + ((t['amount'] as num?)?.toDouble() ?? 0.0));
    
    // Calculate number of unique days
    final uniqueDays = historicalTransactions
        .map((t) => DateTime.tryParse(t['date']?.toString() ?? ''))
        .where((date) => date != null)
        .map((date) => '${date!.year}-${date.month}-${date.day}')
        .toSet()
        .length;
    
    return uniqueDays > 0 ? totalSpending / uniqueDays : 0.0;
  }

  String _categorizeVelocity(double velocityRatio) {
    if (velocityRatio < 0.5) {
      return 'very_low';
    } else if (velocityRatio < 0.8) {
      return 'low';
    } else if (velocityRatio <= 1.2) {
      return 'normal';
    } else if (velocityRatio <= 1.5) {
      return 'high';
    } else {
      return 'very_high';
    }
  }

  double _calculateOptimalRemainingBudget(
    double currentVelocity,
    double normalVelocity,
    double currentDailyBudget,
    DateTime analysisDate,
  ) {
    // Base calculation on velocity ratio
    final velocityRatio = normalVelocity > 0 ? currentVelocity / normalVelocity : 1.0;
    
    // Apply velocity-based adjustment
    var adjustmentFactor = 1.0;
    
    if (velocityRatio > 1.5) {
      // High velocity - reduce budget
      adjustmentFactor = 0.85;
    } else if (velocityRatio > 1.2) {
      // Moderate high velocity - slight reduction
      adjustmentFactor = 0.95;
    } else if (velocityRatio < 0.8) {
      // Low velocity - can increase budget
      adjustmentFactor = 1.15;
    } else if (velocityRatio < 0.5) {
      // Very low velocity - significant increase possible
      adjustmentFactor = 1.25;
    }
    
    // Apply time-of-month factor
    final dayOfMonth = analysisDate.day;
    if (dayOfMonth > 25) {
      // End of month - be more conservative
      adjustmentFactor *= 0.9;
    } else if (dayOfMonth <= 5) {
      // Beginning of month - can be more flexible
      adjustmentFactor *= 1.05;
    }
    
    return currentDailyBudget * adjustmentFactor;
  }

  List<String> _generateVelocityInsights(
    double velocityRatio,
    String velocityCategory,
    double currentVelocity,
    double normalVelocity,
  ) {
    final insights = <String>[];
    
    switch (velocityCategory) {
      case 'very_high':
        insights.add('Spending velocity is ${(velocityRatio * 100).round()}% above normal - consider reducing daily expenses');
        insights.add('Current pace: \$${currentVelocity.toStringAsFixed(2)}/day vs normal \$${normalVelocity.toStringAsFixed(2)}/day');
        break;
      case 'high':
        insights.add('Spending slightly elevated at ${((velocityRatio - 1) * 100).round()}% above normal');
        insights.add('Monitor discretionary spending categories closely');
        break;
      case 'normal':
        insights.add('Spending velocity is within normal range');
        insights.add('Good budget adherence - maintain current patterns');
        break;
      case 'low':
        insights.add('Spending velocity is ${((1 - velocityRatio) * 100).round()}% below normal');
        insights.add('Opportunity to increase flexible spending or boost savings');
        break;
      case 'very_low':
        insights.add('Very low spending velocity - ${((1 - velocityRatio) * 100).round()}% below normal');
        insights.add('Consider if underspending affects quality of life');
        break;
    }
    
    return insights;
  }

  double _calculateAnalysisConfidence(
    List<Map<String, dynamic>> recentTransactions,
    List<Map<String, dynamic>> historicalTransactions,
  ) {
    var confidence = 0.5; // Base confidence
    
    // Increase confidence based on recent data quantity
    if (recentTransactions.length >= 10) confidence += 0.2;
    if (recentTransactions.length >= 20) confidence += 0.1;
    
    // Increase confidence based on historical data quantity
    if (historicalTransactions.length >= 50) confidence += 0.1;
    if (historicalTransactions.length >= 100) confidence += 0.1;
    
    return confidence.clamp(0.0, 1.0);
  }

  String _determineAllocationStrategy(SpendingVelocityAnalysis analysis) {
    switch (analysis.velocityCategory) {
      case 'very_high':
        return 'emergency_conservation';
      case 'high':
        return 'controlled_reduction';
      case 'normal':
        return 'balanced_allocation';
      case 'low':
        return 'flexible_increase';
      case 'very_low':
        return 'boost_spending';
      default:
        return 'balanced_allocation';
    }
  }

  double _calculateDayBudget(
    double baseBudget,
    SpendingVelocityAnalysis analysis,
    DateTime date,
    String strategy,
  ) {
    var multiplier = 1.0;
    
    // Apply strategy-based multiplier
    switch (strategy) {
      case 'emergency_conservation':
        multiplier = 0.7;
        break;
      case 'controlled_reduction':
        multiplier = 0.85;
        break;
      case 'balanced_allocation':
        multiplier = 1.0;
        break;
      case 'flexible_increase':
        multiplier = 1.15;
        break;
      case 'boost_spending':
        multiplier = 1.3;
        break;
    }
    
    // Apply weekend adjustment
    if (date.weekday >= 6) {
      multiplier *= 1.1; // 10% weekend boost
    }
    
    return baseBudget * multiplier;
  }

  List<String> _generateAllocationRecommendations(
    SpendingVelocityAnalysis analysis,
    String strategy,
  ) {
    final recommendations = <String>[];
    
    switch (strategy) {
      case 'emergency_conservation':
        recommendations.add('Implement immediate spending controls');
        recommendations.add('Focus on essential expenses only');
        recommendations.add('Review and pause non-critical subscriptions');
        break;
      case 'controlled_reduction':
        recommendations.add('Reduce discretionary spending by 15%');
        recommendations.add('Monitor daily spending more closely');
        recommendations.add('Consider meal planning to reduce food costs');
        break;
      case 'balanced_allocation':
        recommendations.add('Maintain current spending patterns');
        recommendations.add('Continue tracking for optimization opportunities');
        break;
      case 'flexible_increase':
        recommendations.add('Opportunity for strategic spending increases');
        recommendations.add('Consider quality-of-life improvements');
        recommendations.add('Build emergency fund with surplus');
        break;
      case 'boost_spending':
        recommendations.add('Significant underspending detected');
        recommendations.add('Evaluate if needs are being met adequately');
        recommendations.add('Consider investing surplus in long-term goals');
        break;
    }
    
    return recommendations;
  }

  Map<String, double> _groupByDay(List<Map<String, dynamic>> transactions) {
    final dailySpending = <String, double>{};
    
    for (final transaction in transactions) {
      final date = DateTime.tryParse(transaction['date']?.toString() ?? '') ?? DateTime.now();
      final dateKey = '${date.year}-${date.month}-${date.day}';
      final amount = (transaction['amount'] as num?)?.toDouble() ?? 0.0;
      
      dailySpending[dateKey] = (dailySpending[dateKey] ?? 0.0) + amount;
    }
    
    return dailySpending;
  }

  double _calculateVariance(List<double> values) {
    if (values.isEmpty) return 0.0;
    
    final mean = values.reduce((a, b) => a + b) / values.length;
    final squaredDiffs = values.map((value) => pow(value - mean, 2)).toList();
    return squaredDiffs.reduce((a, b) => a + b) / values.length;
  }

  String _analyzeWeeklyPattern(List<Map<String, dynamic>> transactions) {
    final weekdaySpending = <double>[];
    final weekendSpending = <double>[];
    
    for (final transaction in transactions) {
      final date = DateTime.tryParse(transaction['date']?.toString() ?? '') ?? DateTime.now();
      final amount = (transaction['amount'] as num?)?.toDouble() ?? 0.0;
      
      if (date.weekday >= 6) {
        weekendSpending.add(amount);
      } else {
        weekdaySpending.add(amount);
      }
    }
    
    if (weekdaySpending.isEmpty || weekendSpending.isEmpty) return '';
    
    final weekdayAvg = weekdaySpending.reduce((a, b) => a + b) / weekdaySpending.length;
    final weekendAvg = weekendSpending.reduce((a, b) => a + b) / weekendSpending.length;
    
    if (weekendAvg > weekdayAvg * 1.2) {
      return 'Weekend spending is ${((weekendAvg / weekdayAvg - 1) * 100).round()}% higher than weekdays';
    } else if (weekdayAvg > weekendAvg * 1.2) {
      return 'Weekday spending is ${((weekdayAvg / weekendAvg - 1) * 100).round()}% higher than weekends';
    }
    
    return '';
  }

  String _analyzeTrend(List<Map<String, dynamic>> transactions) {
    if (transactions.length < 14) return '';
    
    // Sort transactions by date
    final sortedTransactions = List<Map<String, dynamic>>.from(transactions);
    sortedTransactions.sort((a, b) {
      final dateA = DateTime.tryParse(a['date']?.toString() ?? '') ?? DateTime.now();
      final dateB = DateTime.tryParse(b['date']?.toString() ?? '') ?? DateTime.now();
      return dateA.compareTo(dateB);
    });
    
    // Compare first half vs second half spending
    final midpoint = sortedTransactions.length ~/ 2;
    final firstHalf = sortedTransactions.take(midpoint);
    final secondHalf = sortedTransactions.skip(midpoint);
    
    final firstHalfAvg = firstHalf.isEmpty ? 0.0 : 
        firstHalf.fold(0.0, (sum, t) => sum + ((t['amount'] as num?)?.toDouble() ?? 0.0)) / firstHalf.length;
    final secondHalfAvg = secondHalf.isEmpty ? 0.0 :
        secondHalf.fold(0.0, (sum, t) => sum + ((t['amount'] as num?)?.toDouble() ?? 0.0)) / secondHalf.length;
    
    if (secondHalfAvg > firstHalfAvg * 1.15) {
      return 'Spending trend increasing - ${((secondHalfAvg / firstHalfAvg - 1) * 100).round()}% higher recently';
    } else if (firstHalfAvg > secondHalfAvg * 1.15) {
      return 'Spending trend decreasing - ${((1 - secondHalfAvg / firstHalfAvg) * 100).round()}% lower recently';
    }
    
    return '';
  }
}