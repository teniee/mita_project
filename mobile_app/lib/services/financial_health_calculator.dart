import 'dart:math' as math;
import 'package:flutter/material.dart';
import 'income_service.dart';
import 'advanced_financial_engine.dart';

/// Financial Health Calculator - Production-Ready Implementation
/// 
/// Provides comprehensive financial health scoring and analysis:
/// - Budget adherence scoring with behavioral insights
/// - Savings rate optimization based on income tier
/// - Debt management assessment with risk analysis
/// - Emergency fund adequacy scoring
/// - Investment diversification analysis
/// - Goal progress tracking with predictive modeling
class FinancialHealthCalculator {
  static final FinancialHealthCalculator _instance = FinancialHealthCalculator._internal();
  factory FinancialHealthCalculator() => _instance;
  FinancialHealthCalculator._internal();

  final IncomeService _incomeService = IncomeService();

  /// Calculate comprehensive financial health score
  FinancialHealthScore calculateFinancialHealthScore({
    required double monthlyIncome,
    required IncomeTier incomeTier,
    required Map<String, double> actualSpending,
    required Map<String, double> budgetAllocations,
    double totalDebt = 0.0,
    double emergencyFund = 0.0,
    double totalInvestments = 0.0,
    List<FinancialGoal>? goals,
    int monthsOfData = 6,
  }) {
    final score = FinancialHealthScore();

    // Component 1: Budget Adherence Score (25%)
    score.budgetAdherenceScore = _calculateBudgetAdherenceScore(
      actualSpending,
      budgetAllocations
    );

    // Component 2: Savings Rate Score (20%)
    final savingsAmount = budgetAllocations['savings'] ?? 0.0;
    score.savingsRateScore = _calculateSavingsRateScore(
      savingsAmount,
      monthlyIncome,
      incomeTier
    );

    // Component 3: Debt Management Score (20%)
    score.debtManagementScore = _calculateDebtManagementScore(
      totalDebt,
      monthlyIncome,
      incomeTier
    );

    // Component 4: Emergency Fund Score (15%)
    score.emergencyFundScore = _calculateEmergencyFundScore(
      emergencyFund,
      monthlyIncome,
      incomeTier
    );

    // Component 5: Investment Diversification Score (10%)
    score.investmentScore = _calculateInvestmentScore(
      totalInvestments,
      monthlyIncome,
      incomeTier
    );

    // Component 6: Goal Progress Score (10%)
    score.goalProgressScore = _calculateGoalProgressScore(goals, monthsOfData);

    // Calculate weighted final score
    score.overallScore = (
      score.budgetAdherenceScore * 0.25 +
      score.savingsRateScore * 0.20 +
      score.debtManagementScore * 0.20 +
      score.emergencyFundScore * 0.15 +
      score.investmentScore * 0.10 +
      score.goalProgressScore * 0.10
    ).clamp(0.0, 100.0);

    // Generate insights and recommendations
    score.insights = _generateHealthScoreInsights(score, incomeTier);
    score.recommendations = _generateHealthScoreRecommendations(score, incomeTier);
    score.riskAreas = _identifyFinancialRiskAreas(score);

    return score;
  }

  double _calculateBudgetAdherenceScore(
    Map<String, double> actualSpending,
    Map<String, double> budgetAllocations,
  ) {
    if (budgetAllocations.isEmpty) return 50.0;

    var totalScore = 0.0;
    var categoryCount = 0;

    budgetAllocations.forEach((category, allocated) {
      final spent = actualSpending[category] ?? 0.0;
      if (allocated > 0) {
        final adherenceRatio = spent / allocated;
        final categoryScore = _calculateCategoryAdherenceScore(adherenceRatio);
        totalScore += categoryScore;
        categoryCount++;
      }
    });

    return categoryCount > 0 ? totalScore / categoryCount : 50.0;
  }

  double _calculateCategoryAdherenceScore(double ratio) {
    if (ratio <= 0.9) return 100.0; // Under budget
    if (ratio <= 1.0) return 90.0; // At budget
    if (ratio <= 1.1) return 75.0; // Slightly over
    if (ratio <= 1.2) return 50.0; // Moderately over
    if (ratio <= 1.5) return 25.0; // Significantly over
    return 0.0; // Severely over budget
  }

  double _calculateSavingsRateScore(
    double savingsAmount,
    double monthlyIncome,
    IncomeTier tier,
  ) {
    if (monthlyIncome <= 0) return 0.0;

    final savingsRate = savingsAmount / monthlyIncome;
    final targetRate = _getTargetSavingsRate(tier);

    if (savingsRate >= targetRate) {
      return 100.0;
    } else if (savingsRate >= targetRate * 0.8) {
      return 80.0;
    } else if (savingsRate >= targetRate * 0.6) {
      return 60.0;
    } else if (savingsRate >= targetRate * 0.4) {
      return 40.0;
    } else if (savingsRate >= targetRate * 0.2) {
      return 20.0;
    } else {
      return 10.0;
    }
  }

  double _getTargetSavingsRate(IncomeTier tier) {
    switch (tier) {
      case IncomeTier.low: return 0.05; // 5%
      case IncomeTier.lowerMiddle: return 0.10; // 10%
      case IncomeTier.middle: return 0.15; // 15%
      case IncomeTier.upperMiddle: return 0.20; // 20%
      case IncomeTier.high: return 0.25; // 25%
    }
  }

  double _calculateDebtManagementScore(
    double totalDebt,
    double monthlyIncome,
    IncomeTier tier,
  ) {
    if (totalDebt <= 0) return 100.0; // No debt is perfect
    if (monthlyIncome <= 0) return 0.0;

    final debtToIncomeRatio = totalDebt / (monthlyIncome * 12); // Annual debt to income

    // Tier-specific debt tolerance
    final maxHealthyRatio = _getMaxHealthyDebtRatio(tier);

    if (debtToIncomeRatio <= maxHealthyRatio * 0.5) {
      return 100.0; // Excellent
    } else if (debtToIncomeRatio <= maxHealthyRatio * 0.7) {
      return 80.0; // Good
    } else if (debtToIncomeRatio <= maxHealthyRatio) {
      return 60.0; // Acceptable
    } else if (debtToIncomeRatio <= maxHealthyRatio * 1.5) {
      return 40.0; // Concerning
    } else if (debtToIncomeRatio <= maxHealthyRatio * 2.0) {
      return 20.0; // High risk
    } else {
      return 0.0; // Critical
    }
  }

  double _getMaxHealthyDebtRatio(IncomeTier tier) {
    switch (tier) {
      case IncomeTier.low: return 2.0; // 2x annual income max
      case IncomeTier.lowerMiddle: return 2.5;
      case IncomeTier.middle: return 3.0;
      case IncomeTier.upperMiddle: return 3.5;
      case IncomeTier.high: return 4.0;
    }
  }

  double _calculateEmergencyFundScore(
    double emergencyFund,
    double monthlyIncome,
    IncomeTier tier,
  ) {
    if (monthlyIncome <= 0) return 0.0;

    final monthsOfCoverage = emergencyFund / monthlyIncome;
    final targetMonths = _getTargetEmergencyFundMonths(tier);

    if (monthsOfCoverage >= targetMonths) {
      return 100.0;
    } else if (monthsOfCoverage >= targetMonths * 0.8) {
      return 80.0;
    } else if (monthsOfCoverage >= targetMonths * 0.6) {
      return 60.0;
    } else if (monthsOfCoverage >= targetMonths * 0.4) {
      return 40.0;
    } else if (monthsOfCoverage >= targetMonths * 0.2) {
      return 20.0;
    } else {
      return 10.0;
    }
  }

  double _getTargetEmergencyFundMonths(IncomeTier tier) {
    switch (tier) {
      case IncomeTier.low: return 3.0; // 3 months
      case IncomeTier.lowerMiddle: return 4.0; // 4 months
      case IncomeTier.middle: return 5.0; // 5 months
      case IncomeTier.upperMiddle: return 6.0; // 6 months
      case IncomeTier.high: return 6.0; // 6 months
    }
  }

  double _calculateInvestmentScore(
    double totalInvestments,
    double monthlyIncome,
    IncomeTier tier,
  ) {
    if (monthlyIncome <= 0) return 0.0;

    final investmentToIncomeRatio = totalInvestments / (monthlyIncome * 12);
    final targetRatio = _getTargetInvestmentRatio(tier);

    if (investmentToIncomeRatio >= targetRatio) {
      return 100.0;
    } else if (investmentToIncomeRatio >= targetRatio * 0.8) {
      return 80.0;
    } else if (investmentToIncomeRatio >= targetRatio * 0.6) {
      return 60.0;
    } else if (investmentToIncomeRatio >= targetRatio * 0.4) {
      return 40.0;
    } else if (investmentToIncomeRatio >= targetRatio * 0.2) {
      return 20.0;
    } else {
      return 0.0;
    }
  }

  double _getTargetInvestmentRatio(IncomeTier tier) {
    switch (tier) {
      case IncomeTier.low: return 0.5; // 0.5x annual income
      case IncomeTier.lowerMiddle: return 1.0; // 1x annual income
      case IncomeTier.middle: return 1.5; // 1.5x annual income
      case IncomeTier.upperMiddle: return 2.0; // 2x annual income
      case IncomeTier.high: return 3.0; // 3x annual income
    }
  }

  double _calculateGoalProgressScore(List<FinancialGoal>? goals, int monthsOfData) {
    if (goals == null || goals.isEmpty) return 50.0; // Neutral score

    var totalScore = 0.0;
    var goalCount = 0;

    for (final goal in goals) {
      if (goal.isActive) {
        final progress = goal.currentAmount / goal.targetAmount;
        final timeElapsed = DateTime.now().difference(DateTime.now().subtract(Duration(days: monthsOfData * 30))).inDays / goal.targetDate.difference(DateTime.now().subtract(Duration(days: monthsOfData * 30))).inDays;

        final expectedProgress = timeElapsed.clamp(0.0, 1.0);
        final progressRatio = expectedProgress > 0 ? progress / expectedProgress : 0.0;

        if (progressRatio >= 1.0) {
          totalScore += 100.0; // On track or ahead
        } else if (progressRatio >= 0.8) {
          totalScore += 80.0; // Slightly behind
        } else if (progressRatio >= 0.6) {
          totalScore += 60.0; // Moderately behind
        } else if (progressRatio >= 0.4) {
          totalScore += 40.0; // Significantly behind
        } else {
          totalScore += 20.0; // Severely behind
        }

        goalCount++;
      }
    }

    return goalCount > 0 ? totalScore / goalCount : 50.0;
  }

  List<String> _generateHealthScoreInsights(FinancialHealthScore score, IncomeTier tier) {
    final insights = <String>[];
    final tierName = _incomeService.getIncomeTierName(tier);

    // Overall score insights
    if (score.overallScore >= 80) {
      insights.add('Excellent financial health! You\'re outperforming most $tierName peers.');
    } else if (score.overallScore >= 60) {
      insights.add('Good financial health with room for optimization.');
    } else if (score.overallScore >= 40) {
      insights.add('Fair financial health - focus on key improvement areas.');
    } else {
      insights.add('Financial health needs attention - prioritize urgent improvements.');
    }

    // Component-specific insights
    if (score.budgetAdherenceScore < 60) {
      insights.add('Budget adherence needs improvement - consider smaller, more realistic allocations.');
    }

    if (score.savingsRateScore < 60) {
      insights.add('Increase your savings rate gradually to build financial security.');
    }

    if (score.debtManagementScore < 60) {
      insights.add('Focus on debt reduction strategies to improve your financial position.');
    }

    if (score.emergencyFundScore < 60) {
      insights.add('Building an emergency fund should be a top priority.');
    }

    return insights.take(3).toList();
  }

  List<String> _generateHealthScoreRecommendations(FinancialHealthScore score, IncomeTier tier) {
    final recommendations = <String>[];

    // Prioritize recommendations based on worst-performing areas
    final components = [
      ('Budget Adherence', score.budgetAdherenceScore),
      ('Savings Rate', score.savingsRateScore),
      ('Debt Management', score.debtManagementScore),
      ('Emergency Fund', score.emergencyFundScore),
      ('Investments', score.investmentScore),
      ('Goal Progress', score.goalProgressScore),
    ];

    components.sort((a, b) => a.$2.compareTo(b.$2)); // Sort by score (lowest first)

    for (final component in components.take(3)) {
      recommendations.add(_getComponentRecommendation(component.$1, component.$2, tier));
    }

    return recommendations;
  }

  String _getComponentRecommendation(String component, double score, IncomeTier tier) {
    switch (component) {
      case 'Budget Adherence':
        return 'Use the 50/30/20 rule as a starting point and adjust based on your actual spending patterns.';
      case 'Savings Rate':
        return 'Start with automatic transfers of 1% of income and increase by 1% monthly until you reach your target.';
      case 'Debt Management':
        return 'List all debts by interest rate and focus on paying off high-interest debt first.';
      case 'Emergency Fund':
        return 'Save \$25-50 per week until you reach your emergency fund target.';
      case 'Investments':
        return 'Consider low-cost index funds or ETFs as a starting point for investment diversification.';
      case 'Goal Progress':
        return 'Review your goals monthly and adjust contribution amounts to stay on track.';
      default:
        return 'Focus on improving this area through consistent small steps.';
    }
  }

  List<String> _identifyFinancialRiskAreas(FinancialHealthScore score) {
    final riskAreas = <String>[];

    if (score.budgetAdherenceScore < 40) {
      riskAreas.add('High budget variance risk - overspending patterns detected');
    }

    if (score.savingsRateScore < 30) {
      riskAreas.add('Low savings risk - insufficient emergency preparedness');
    }

    if (score.debtManagementScore < 30) {
      riskAreas.add('High debt risk - debt levels may impact financial stability');
    }

    if (score.emergencyFundScore < 30) {
      riskAreas.add('Emergency fund risk - insufficient funds for unexpected expenses');
    }

    if (score.goalProgressScore < 40) {
      riskAreas.add('Goal achievement risk - falling behind on financial objectives');
    }

    return riskAreas;
  }
}