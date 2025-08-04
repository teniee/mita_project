import 'dart:math' as math;
import 'package:flutter/material.dart';
import 'income_service.dart';
import 'advanced_financial_engine.dart';

/// Financial Safety Validator - Production-Ready Implementation
/// 
/// Provides comprehensive financial safety validation:
/// - Income classification validation
/// - Budget allocation safety checks  
/// - Debt level assessment with tier-specific thresholds
/// - Emergency fund adequacy validation
/// - Goal feasibility analysis
/// - Lifestyle inflation risk assessment
/// - Overall safety scoring with actionable recommendations
class FinancialSafetyValidator {
  static final FinancialSafetyValidator _instance = FinancialSafetyValidator._internal();
  factory FinancialSafetyValidator() => _instance;
  FinancialSafetyValidator._internal();

  final IncomeService _incomeService = IncomeService();

  /// Comprehensive financial safety validation
  FinancialSafetyCheck performSafetyCheck({
    required double monthlyIncome,
    required IncomeTier incomeTier,
    required Map<String, double> plannedSpending,
    double totalDebt = 0.0,
    double emergencyFund = 0.0,
    List<FinancialGoal>? goals,
  }) {
    final safetyCheck = FinancialSafetyCheck();

    try {
      // Check 1: Income Validation
      safetyCheck.incomeValidation = _validateIncomeClassification(monthlyIncome, incomeTier);

      // Check 2: Budget Allocation Safety
      safetyCheck.budgetSafety = _validateBudgetAllocations(plannedSpending, monthlyIncome, incomeTier);

      // Check 3: Debt Safety Levels
      safetyCheck.debtSafety = _validateDebtLevels(totalDebt, monthlyIncome, incomeTier);

      // Check 4: Emergency Fund Adequacy
      safetyCheck.emergencyFundSafety = _validateEmergencyFund(emergencyFund, monthlyIncome, incomeTier);

      // Check 5: Goal Feasibility
      safetyCheck.goalFeasibility = _validateGoalFeasibility(goals, monthlyIncome, plannedSpending);

      // Check 6: Lifestyle Inflation Risk
      safetyCheck.lifestyleInflationRisk = _assessLifestyleInflationRisk(plannedSpending, monthlyIncome, incomeTier);

      // Overall safety score
      safetyCheck.overallSafetyScore = _calculateOverallSafetyScore(safetyCheck);

      // Generate warnings and recommendations
      safetyCheck.warnings = _generateSafetyWarnings(safetyCheck);
      safetyCheck.recommendations = _generateSafetyRecommendations(safetyCheck, incomeTier);

      return safetyCheck;
    } catch (e) {
      return FinancialSafetyCheck()..overallSafetyScore = 50.0; // Neutral fallback
    }
  }

  bool _validateIncomeClassification(double monthlyIncome, IncomeTier incomeTier) {
    final calculatedTier = _incomeService.classifyIncome(monthlyIncome);
    return calculatedTier == incomeTier;
  }

  bool _validateBudgetAllocations(
    Map<String, double> plannedSpending,
    double monthlyIncome,
    IncomeTier incomeTier,
  ) {
    final totalPlanned = plannedSpending.values.fold(0.0, (sum, amount) => sum + amount);
    
    // Check 1: Total doesn't exceed income
    if (totalPlanned > monthlyIncome * 1.05) { // Allow 5% buffer for rounding
      return false;
    }

    // Check 2: Essential categories are adequately funded
    final essentialCategories = ['housing', 'food', 'utilities', 'healthcare'];
    final recommendedWeights = _incomeService.getDefaultBudgetWeights(incomeTier);
    
    for (final category in essentialCategories) {
      final planned = plannedSpending[category] ?? 0.0;
      final recommended = monthlyIncome * (recommendedWeights[category] ?? 0.0);
      
      // Essential categories should be at least 70% of recommended
      if (planned < recommended * 0.7) {
        return false;
      }
    }

    // Check 3: No single category dominates budget (except housing)
    plannedSpending.forEach((category, amount) {
      final percentage = amount / monthlyIncome;
      if (category != 'housing' && percentage > 0.4) { // 40% max for non-housing
        return false;
      }
    });

    return true;
  }

  bool _validateDebtLevels(double totalDebt, double monthlyIncome, IncomeTier incomeTier) {
    if (totalDebt <= 0) return true; // No debt is always safe
    if (monthlyIncome <= 0) return false;

    final debtToIncomeRatio = totalDebt / (monthlyIncome * 12);
    final maxSafeRatio = _getMaxSafeDebtRatio(incomeTier);
    
    return debtToIncomeRatio <= maxSafeRatio;
  }

  double _getMaxSafeDebtRatio(IncomeTier tier) {
    switch (tier) {
      case IncomeTier.low: return 1.5; // 1.5x annual income max
      case IncomeTier.lowerMiddle: return 2.0;
      case IncomeTier.middle: return 2.5;
      case IncomeTier.upperMiddle: return 3.0;
      case IncomeTier.high: return 3.5;
    }
  }

  bool _validateEmergencyFund(double emergencyFund, double monthlyIncome, IncomeTier incomeTier) {
    if (monthlyIncome <= 0) return false;
    
    final monthsOfCoverage = emergencyFund / monthlyIncome;
    final minRequiredMonths = _getMinEmergencyFundMonths(incomeTier);
    
    return monthsOfCoverage >= minRequiredMonths;
  }

  double _getMinEmergencyFundMonths(IncomeTier tier) {
    switch (tier) {
      case IncomeTier.low: return 1.0; // 1 month minimum
      case IncomeTier.lowerMiddle: return 2.0; // 2 months minimum
      case IncomeTier.middle: return 3.0; // 3 months minimum
      case IncomeTier.upperMiddle: return 3.0; // 3 months minimum
      case IncomeTier.high: return 3.0; // 3 months minimum
    }
  }

  bool _validateGoalFeasibility(
    List<FinancialGoal>? goals,
    double monthlyIncome,
    Map<String, double> plannedSpending,
  ) {
    if (goals == null || goals.isEmpty) return true;

    final totalSpending = plannedSpending.values.fold(0.0, (sum, amount) => sum + amount);
    final availableForGoals = monthlyIncome - totalSpending;
    
    final totalGoalContributions = goals
        .where((goal) => goal.isActive)
        .fold<double>(0, (sum, goal) => sum + goal.monthlyContribution);

    // Check if total goal contributions are feasible
    if (totalGoalContributions > availableForGoals) {
      return false;
    }

    // Check individual goal feasibility
    for (final goal in goals.where((g) => g.isActive)) {
      final remainingAmount = goal.targetAmount - goal.currentAmount;
      final monthsToTarget = goal.targetDate.difference(DateTime.now()).inDays / 30.44;
      
      if (monthsToTarget > 0) {
        final requiredMonthlyContribution = remainingAmount / monthsToTarget;
        
        // Goal should be achievable with reasonable contribution
        if (requiredMonthlyContribution > monthlyIncome * 0.3) { // Max 30% of income per goal
          return false;
        }
      }
    }

    return true;
  }

  double _assessLifestyleInflationRisk(
    Map<String, double> plannedSpending,
    double monthlyIncome,
    IncomeTier incomeTier,
  ) {
    var riskScore = 0.0;

    // Check entertainment spending
    final entertainment = plannedSpending['entertainment'] ?? 0.0;
    final entertainmentPercentage = entertainment / monthlyIncome;
    if (entertainmentPercentage > _getMaxSafeEntertainmentPercentage(incomeTier)) {
      riskScore += 0.3;
    }

    // Check dining out vs home cooking
    final food = plannedSpending['food'] ?? 0.0;
    final dining = plannedSpending['dining_out'] ?? 0.0;
    if (dining > food * 0.5) { // Dining out more than 50% of food budget
      riskScore += 0.2;
    }

    // Check discretionary categories total
    final discretionary = (plannedSpending['entertainment'] ?? 0.0) +
                         (plannedSpending['shopping'] ?? 0.0) +
                         (plannedSpending['hobbies'] ?? 0.0);
    final discretionaryPercentage = discretionary / monthlyIncome;
    if (discretionaryPercentage > 0.25) { // More than 25% on discretionary
      riskScore += 0.3;
    }

    // Check savings rate
    final savings = plannedSpending['savings'] ?? 0.0;
    final savingsRate = savings / monthlyIncome;
    final targetSavingsRate = _getTargetSavingsRate(incomeTier);
    if (savingsRate < targetSavingsRate * 0.5) { // Less than half target savings rate
      riskScore += 0.2;
    }

    return math.min(riskScore, 1.0);
  }

  double _getMaxSafeEntertainmentPercentage(IncomeTier tier) {
    switch (tier) {
      case IncomeTier.low: return 0.05; // 5%
      case IncomeTier.lowerMiddle: return 0.08; // 8%
      case IncomeTier.middle: return 0.10; // 10%
      case IncomeTier.upperMiddle: return 0.12; // 12%
      case IncomeTier.high: return 0.15; // 15%
    }
  }

  double _getTargetSavingsRate(IncomeTier tier) {
    switch (tier) {
      case IncomeTier.low: return 0.05;
      case IncomeTier.lowerMiddle: return 0.10;
      case IncomeTier.middle: return 0.15;
      case IncomeTier.upperMiddle: return 0.20;
      case IncomeTier.high: return 0.25;
    }
  }

  double _calculateOverallSafetyScore(FinancialSafetyCheck safetyCheck) {
    var score = 100.0;

    // Deduct points for failed checks
    if (!safetyCheck.incomeValidation) score -= 5.0;
    if (!safetyCheck.budgetSafety) score -= 25.0;
    if (!safetyCheck.debtSafety) score -= 20.0;
    if (!safetyCheck.emergencyFundSafety) score -= 15.0;
    if (!safetyCheck.goalFeasibility) score -= 15.0;

    // Deduct points for lifestyle inflation risk
    score -= safetyCheck.lifestyleInflationRisk * 20.0;

    return math.max(score, 0.0);
  }

  List<String> _generateSafetyWarnings(FinancialSafetyCheck safetyCheck) {
    final warnings = <String>[];

    if (!safetyCheck.incomeValidation) {
      warnings.add('Income classification mismatch detected - verify your income tier');
    }

    if (!safetyCheck.budgetSafety) {
      warnings.add('Budget allocations exceed safe limits - reduce spending or increase income');
    }

    if (!safetyCheck.debtSafety) {
      warnings.add('Debt levels are above safe thresholds for your income tier');
    }

    if (!safetyCheck.emergencyFundSafety) {
      warnings.add('Emergency fund is below recommended minimum for your situation');
    }

    if (!safetyCheck.goalFeasibility) {
      warnings.add('Current financial goals may not be achievable with planned spending');
    }

    if (safetyCheck.lifestyleInflationRisk > 0.6) {
      warnings.add('High lifestyle inflation risk detected - monitor discretionary spending');
    }

    return warnings;
  }

  List<String> _generateSafetyRecommendations(FinancialSafetyCheck safetyCheck, IncomeTier tier) {
    final recommendations = <String>[];

    if (!safetyCheck.budgetSafety) {
      recommendations.add('Review and reduce non-essential spending categories by 10-15%');
    }

    if (!safetyCheck.debtSafety) {
      recommendations.add('Focus on debt reduction - consider debt consolidation or payment plan optimization');
    }

    if (!safetyCheck.emergencyFundSafety) {
      final minMonths = _getMinEmergencyFundMonths(tier);
      recommendations.add('Build emergency fund to cover at least $minMonths months of expenses');
    }

    if (!safetyCheck.goalFeasibility) {
      recommendations.add('Reassess financial goals timeline or reduce goal amounts for feasibility');
    }

    if (safetyCheck.lifestyleInflationRisk > 0.5) {
      recommendations.add('Implement the 24-hour rule for non-essential purchases over \$50');
    }

    // General safety recommendations
    if (safetyCheck.overallSafetyScore < 70) {
      recommendations.add('Consider consulting with a financial advisor for personalized guidance');
    }

    return recommendations;
  }
}