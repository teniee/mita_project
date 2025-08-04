import 'dart:math' as math;
import 'package:flutter/material.dart';
import 'income_service.dart';
import 'api_service.dart';
import 'logging_service.dart';\nimport 'redistribution_opportunity.dart';

/// Advanced Financial Engine for MITA
/// Production-ready financial algorithms with behavioral economics integration
/// 
/// This service provides:
/// - Optimized budget calculations with behavioral insights
/// - Advanced spending prediction algorithms
/// - Financial health scoring
/// - Risk assessment and safety checks
/// - Personalized recommendations based on behavioral patterns
class AdvancedFinancialEngine {
  static final AdvancedFinancialEngine _instance = AdvancedFinancialEngine._internal();
  factory AdvancedFinancialEngine() => _instance;
  AdvancedFinancialEngine._internal();

  final IncomeService _incomeService = IncomeService();
  final ApiService _apiService = ApiService();

  // ===========================================================================
  // BUDGET CALCULATION ALGORITHMS (OPTIMIZED)
  // ===========================================================================

  /// Calculate optimal budget allocation using behavioral economics principles
  /// 
  /// Uses a multi-factor algorithm considering:
  /// - Income tier behavioral patterns
  /// - Historical spending patterns
  /// - Psychological comfort zones
  /// - Goal-oriented adjustments
  /// - Regional cost-of-living factors
  BudgetAllocation calculateOptimalBudget({
    required double monthlyIncome,
    required IncomeTier incomeTier,
    Map<String, double>? historicalSpending,
    List<FinancialGoal>? activeGoals,
    String? locationCode,
    BehavioralProfile? behavioralProfile,
  }) {
    try {
      logInfo('Calculating optimal budget for income: \$${monthlyIncome.toStringAsFixed(2)}, tier: $incomeTier');

      // Step 1: Get base tier allocations
      final baseWeights = _incomeService.getDefaultBudgetWeights(incomeTier);
      
      // Step 2: Apply behavioral adjustments
      final behavioralWeights = _applyBehavioralAdjustments(
        baseWeights, 
        incomeTier, 
        behavioralProfile
      );
      
      // Step 3: Incorporate historical spending patterns
      final historicalWeights = _incorporateHistoricalPatterns(
        behavioralWeights,
        historicalSpending,
        monthlyIncome
      );
      
      // Step 4: Apply goal-oriented optimizations
      final goalOptimizedWeights = _applyGoalOptimizations(
        historicalWeights,
        activeGoals,
        monthlyIncome,
        incomeTier
      );
      
      // Step 5: Regional cost-of-living adjustments
      final finalWeights = _applyRegionalAdjustments(
        goalOptimizedWeights,
        locationCode,
        incomeTier
      );

      // Step 6: Calculate final allocations with validation
      final allocations = _calculateFinalAllocations(
        finalWeights,
        monthlyIncome,
        incomeTier
      );

      logInfo('Budget calculation completed successfully');
      return allocations;

    } catch (e, stackTrace) {
      logError('Error calculating optimal budget: $e', error: e, stackTrace: stackTrace);
      // Fallback to safe tier-based allocation
      return _getFallbackBudgetAllocation(monthlyIncome, incomeTier);
    }
  }

  /// Advanced budget redistribution algorithm
  /// 
  /// Implements MITA's core redistribution theory:
  /// - Identifies overspending and underspending patterns
  /// - Applies behavioral nudges for optimal redistribution
  /// - Considers future spending predictions
  /// - Maintains psychological comfort boundaries
  BudgetRedistribution calculateBudgetRedistribution({
    required Map<String, double> currentAllocations,
    required Map<String, double> actualSpending,
    required double monthlyIncome,
    required IncomeTier incomeTier,
    int remainingDaysInMonth = 15,
    BehavioralProfile? behavioralProfile,
  }) {
    try {
      final redistribution = BudgetRedistribution();
      
      // Calculate spending velocity by category
      final spendingVelocity = _calculateSpendingVelocity(
        actualSpending,
        currentAllocations,
        remainingDaysInMonth
      );

      // Identify redistribution opportunities
      final opportunities = _identifyRedistributionOpportunities(
        currentAllocations,
        actualSpending,
        spendingVelocity,
        incomeTier
      );

      // Apply behavioral constraints
      final behaviorallyConstrainedOpportunities = _applyBehavioralConstraints(
        opportunities,
        behavioralProfile,
        incomeTier
      );

      // Calculate optimal transfers
      final transfers = _calculateOptimalTransfers(
        behaviorallyConstrainedOpportunities,
        monthlyIncome,
        incomeTier
      );

      redistribution.transfers = transfers;
      redistribution.confidence = _calculateRedistributionConfidence(transfers, incomeTier);
      redistribution.behavioralImpact = _assessBehavioralImpact(transfers, behavioralProfile);
      redistribution.projectedSavings = _calculateProjectedSavings(transfers, remainingDaysInMonth);

      return redistribution;

    } catch (e, stackTrace) {
      logError('Error calculating budget redistribution: $e', error: e, stackTrace: stackTrace);
      return BudgetRedistribution(); // Empty redistribution
    }
  }

  // ===========================================================================
  // SPENDING PREDICTION ALGORITHMS (ENHANCED)
  // ===========================================================================

  /// Advanced spending prediction using machine learning principles
  /// 
  /// Combines multiple prediction models:
  /// - Time series analysis
  /// - Behavioral pattern recognition
  /// - Seasonal adjustments
  /// - Goal-impact modeling
  /// - Economic indicator integration
  Future<SpendingPrediction> predictFutureSpending({
    required Map<String, List<double>> historicalSpending, // Last 12 months by category
    required double monthlyIncome,
    required IncomeTier incomeTier,
    BehavioralProfile? behavioralProfile,
    Map<String, dynamic>? seasonalFactors,
    Map<String, dynamic>? economicIndicators,
  }) async {
    try {
      logInfo('Generating spending prediction for income tier: $incomeTier');

      final prediction = SpendingPrediction();

      // Model 1: Time Series Trend Analysis
      final trendPredictions = _calculateTrendPredictions(historicalSpending);
      
      // Model 2: Behavioral Pattern Analysis
      final behavioralPredictions = _calculateBehavioralPredictions(
        historicalSpending,
        behavioralProfile,
        incomeTier
      );
      
      // Model 3: Seasonal Adjustment Model
      final seasonalPredictions = _calculateSeasonalPredictions(
        trendPredictions,
        seasonalFactors,
        DateTime.now().month
      );
      
      // Model 4: Economic Impact Model
      final economicAdjustedPredictions = _calculateEconomicAdjustments(
        seasonalPredictions,
        economicIndicators,
        incomeTier
      );

      // Ensemble: Combine all models with weighted averages
      final finalPredictions = _combineModels([
        PredictionModel('trend', trendPredictions, 0.3),
        PredictionModel('behavioral', behavioralPredictions, 0.35),
        PredictionModel('seasonal', seasonalPredictions, 0.2),
        PredictionModel('economic', economicAdjustedPredictions, 0.15),
      ]);

      prediction.categoryPredictions = finalPredictions;
      prediction.totalPredicted = finalPredictions.values.fold(0.0, (sum, value) => sum + value);
      prediction.confidence = _calculatePredictionConfidence(historicalSpending, finalPredictions);
      prediction.riskFactors = _identifyRiskFactors(finalPredictions, monthlyIncome, incomeTier);
      prediction.recommendations = _generatePredictionRecommendations(finalPredictions, monthlyIncome, incomeTier);

      logInfo('Spending prediction completed with ${prediction.confidence.toStringAsFixed(1)}% confidence');
      return prediction;

    } catch (e, stackTrace) {
      logError('Error predicting future spending: $e', error: e, stackTrace: stackTrace);
      return SpendingPrediction(); // Empty prediction
    }
  }

  // ===========================================================================
  // FINANCIAL HEALTH SCORING SYSTEM
  // ===========================================================================

  /// Calculate comprehensive financial health score (0-100)
  /// 
  /// Factors considered:
  /// - Budget adherence (25%)
  /// - Savings rate (20%)
  /// - Debt-to-income ratio (20%)
  /// - Emergency fund adequacy (15%)
  /// - Investment diversification (10%)
  /// - Goal progress (10%)
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
    try {
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

      logInfo('Financial health score calculated: ${score.overallScore.toStringAsFixed(1)}');
      return score;

    } catch (e, stackTrace) {
      logError('Error calculating financial health score: $e', error: e, stackTrace: stackTrace);
      return FinancialHealthScore()..overallScore = 50.0; // Neutral fallback
    }
  }

  // ===========================================================================
  // BEHAVIORAL ECONOMICS IMPLEMENTATION
  // ===========================================================================

  /// Apply behavioral nudges based on user's spending patterns and psychology
  List<BehavioralNudge> generateBehavioralNudges({
    required IncomeTier incomeTier,
    required Map<String, double> recentSpending,
    required double monthlyIncome,
    BehavioralProfile? profile,
    List<String>? spendingTriggers,
  }) {
    final nudges = <BehavioralNudge>[];
    
    try {
      // Loss Aversion Nudges
      nudges.addAll(_generateLossAversionNudges(recentSpending, monthlyIncome, incomeTier));
      
      // Social Proof Nudges
      nudges.addAll(_generateSocialProofNudges(recentSpending, monthlyIncome, incomeTier));
      
      // Anchoring Nudges
      nudges.addAll(_generateAnchoringNudges(recentSpending, monthlyIncome, incomeTier));
      
      // Mental Accounting Nudges
      nudges.addAll(_generateMentalAccountingNudges(recentSpending, profile, incomeTier));
      
      // Commitment Device Nudges
      nudges.addAll(_generateCommitmentNudges(profile, incomeTier));

      // Sort by behavioral impact and relevance
      nudges.sort((a, b) => b.impactScore.compareTo(a.impactScore));
      
      return nudges.take(5).toList(); // Return top 5 most effective nudges

    } catch (e, stackTrace) {
      logError('Error generating behavioral nudges: $e', error: e, stackTrace: stackTrace);
      return [];
    }
  }

  // ===========================================================================
  // FINANCIAL SAFETY CHECKS AND VALIDATION
  // ===========================================================================

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

    } catch (e, stackTrace) {
      logError('Error performing financial safety check: $e', error: e, stackTrace: stackTrace);
      return FinancialSafetyCheck()..overallSafetyScore = 50.0; // Neutral fallback
    }
  }

  // ===========================================================================
  // PRIVATE HELPER METHODS
  // ===========================================================================

  Map<String, double> _applyBehavioralAdjustments(
    Map<String, double> baseWeights,
    IncomeTier incomeTier,
    BehavioralProfile? profile,
  ) {
    if (profile == null) return Map.from(baseWeights);
    
    final adjustedWeights = Map<String, double>.from(baseWeights);
    
    // Apply risk tolerance adjustments
    if (profile.riskTolerance == RiskTolerance.low) {
      adjustedWeights['savings'] = (adjustedWeights['savings']! * 1.1).clamp(0.0, 0.4);
      adjustedWeights['entertainment'] = (adjustedWeights['entertainment']! * 0.9).clamp(0.0, 0.2);
    } else if (profile.riskTolerance == RiskTolerance.high) {
      adjustedWeights['savings'] = (adjustedWeights['savings']! * 1.2).clamp(0.0, 0.5);
      adjustedWeights['entertainment'] = (adjustedWeights['entertainment']! * 1.1).clamp(0.0, 0.15);
    }
    
    // Apply spending personality adjustments
    switch (profile.spendingPersonality) {
      case SpendingPersonality.saver:
        adjustedWeights['savings'] = (adjustedWeights['savings']! * 1.15).clamp(0.0, 0.45);
        break;
      case SpendingPersonality.spender:
        adjustedWeights['entertainment'] = (adjustedWeights['entertainment']! * 1.1).clamp(0.0, 0.2);
        break;
      case SpendingPersonality.balanced:
        // No major adjustments for balanced personality
        break;
    }
    
    // Normalize to ensure sum equals 1.0
    return _normalizeWeights(adjustedWeights);
  }

  Map<String, double> _normalizeWeights(Map<String, double> weights) {
    final sum = weights.values.fold(0.0, (sum, weight) => sum + weight);
    if (sum == 0.0) return weights;
    
    return weights.map((key, value) => MapEntry(key, value / sum));
  }

  BudgetAllocation _getFallbackBudgetAllocation(double monthlyIncome, IncomeTier incomeTier) {
    final weights = _incomeService.getDefaultBudgetWeights(incomeTier);
    final allocations = weights.map((key, weight) => MapEntry(key, monthlyIncome * weight));
    
    return BudgetAllocation(
      allocations: allocations,
      confidence: 0.5, // Low confidence for fallback
      behavioralAlignment: 0.3,
      optimizationOpportunities: ['Review and customize your budget based on actual spending patterns'],
    );
  }

  Map<String, double> _incorporateHistoricalPatterns(
    Map<String, double> weights,
    Map<String, double>? historicalSpending,
    double monthlyIncome,
  ) {
    if (historicalSpending == null || historicalSpending.isEmpty) return weights;
    
    final adjustedWeights = Map<String, double>.from(weights);
    final totalHistorical = historicalSpending.values.fold(0.0, (sum, value) => sum + value);
    
    if (totalHistorical > 0) {
      historicalSpending.forEach((category, amount) {
        final historicalWeight = amount / totalHistorical;
        final currentWeight = adjustedWeights[category] ?? 0.0;
        
        // Blend historical and recommended weights (70% historical, 30% recommended)
        adjustedWeights[category] = (historicalWeight * 0.7 + currentWeight * 0.3).clamp(0.0, 0.6);
      });
    }
    
    return _normalizeWeights(adjustedWeights);
  }

  Map<String, double> _applyGoalOptimizations(
    Map<String, double> weights,
    List<FinancialGoal>? goals,
    double monthlyIncome,
    IncomeTier incomeTier,
  ) {
    if (goals == null || goals.isEmpty) return weights;
    
    final adjustedWeights = Map<String, double>.from(weights);
    double totalGoalAdjustment = 0.0;
    
    for (final goal in goals) {
      if (goal.isActive && goal.monthlyContribution > 0) {
        final contributionWeight = goal.monthlyContribution / monthlyIncome;
        
        // Increase savings allocation for active goals
        if (goal.category == 'savings' || goal.category == 'emergency') {
          adjustedWeights['savings'] = (adjustedWeights['savings']! + contributionWeight * 0.5).clamp(0.0, 0.5);
          totalGoalAdjustment += contributionWeight * 0.5;
        }
      }
    }
    
    // Reduce other categories proportionally to accommodate goal adjustments
    if (totalGoalAdjustment > 0) {
      final otherCategories = adjustedWeights.keys.where((k) => k != 'savings').toList();
      final reductionPerCategory = totalGoalAdjustment / otherCategories.length;
      
      for (final category in otherCategories) {
        adjustedWeights[category] = (adjustedWeights[category]! - reductionPerCategory).clamp(0.05, 1.0);
      }
    }
    
    return _normalizeWeights(adjustedWeights);
  }

  Map<String, double> _applyRegionalAdjustments(
    Map<String, double> weights,
    String? locationCode,
    IncomeTier incomeTier,
  ) {
    // For now, return weights as-is
    // Future implementation would adjust based on regional cost-of-living data
    return weights;
  }

  BudgetAllocation _calculateFinalAllocations(
    Map<String, double> weights,
    double monthlyIncome,
    IncomeTier incomeTier,
  ) {
    final allocations = weights.map((key, weight) => MapEntry(key, monthlyIncome * weight));
    
    return BudgetAllocation(
      allocations: allocations,
      confidence: 0.85, // High confidence for properly calculated allocations
      behavioralAlignment: 0.8,
      optimizationOpportunities: _identifyOptimizationOpportunities(allocations, incomeTier),
    );
  }

  List<String> _identifyOptimizationOpportunities(
    Map<String, double> allocations,
    IncomeTier incomeTier,
  ) {
    final opportunities = <String>[];
    
    // Check for optimization opportunities based on tier
    switch (incomeTier) {
      case IncomeTier.low:
        if ((allocations['savings'] ?? 0.0) < allocations.values.fold(0.0, (sum, v) => sum + v) * 0.05) {
          opportunities.add('Consider increasing savings rate to at least 5% of income');
        }
        break;
      case IncomeTier.lowerMiddle:
        if ((allocations['savings'] ?? 0.0) < allocations.values.fold(0.0, (sum, v) => sum + v) * 0.10) {
          opportunities.add('Consider increasing savings rate to 10-15% of income');
        }
        break;
      case IncomeTier.middle:
      case IncomeTier.upperMiddle:
      case IncomeTier.high:
        if ((allocations['savings'] ?? 0.0) < allocations.values.fold(0.0, (sum, v) => sum + v) * 0.20) {
          opportunities.add('Consider increasing savings rate to 20%+ of income');
        }
        break;
    }
    
    return opportunities;
  }

  // ===========================================================================
  // SPENDING VELOCITY AND REDISTRIBUTION CALCULATIONS
  // ===========================================================================

  Map<String, double> _calculateSpendingVelocity(
    Map<String, double> actualSpending,
    Map<String, double> allocations,
    int remainingDays,
  ) {
    final velocity = <String, double>{};
    final daysInMonth = 30; // Approximate
    final daysPassed = daysInMonth - remainingDays;
    
    actualSpending.forEach((category, spent) {
      final allocated = allocations[category] ?? 0.0;
      if (allocated > 0 && daysPassed > 0) {
        final dailySpendingRate = spent / daysPassed;
        final projectedMonthlySpending = dailySpendingRate * daysInMonth;
        velocity[category] = projectedMonthlySpending / allocated; // Velocity ratio
      }
    });
    
    return velocity;
  }

  Map<String, RedistributionOpportunity> _identifyRedistributionOpportunities(
    Map<String, double> allocations,
    Map<String, double> actualSpending,
    Map<String, double> spendingVelocity,
    IncomeTier incomeTier,
  ) {
    final opportunities = <String, RedistributionOpportunity>{};
    
    // Find overspending categories (velocity > 1.2)
    final overspendingCategories = <String>[];
    final underspendingCategories = <String>[];
    
    spendingVelocity.forEach((category, velocity) {
      if (velocity > 1.2) {
        overspendingCategories.add(category);
      } else if (velocity < 0.8) {
        underspendingCategories.add(category);
      }
    });
    
    // Create redistribution opportunities
    for (final fromCategory in underspendingCategories) {
      for (final toCategory in overspendingCategories) {
        final fromAllocation = allocations[fromCategory] ?? 0.0;
        final toAllocation = allocations[toCategory] ?? 0.0;
        final fromVelocity = spendingVelocity[fromCategory] ?? 1.0;
        final toVelocity = spendingVelocity[toCategory] ?? 1.0;
        
        final surplus = fromAllocation * (1.0 - fromVelocity);
        final deficit = toAllocation * (toVelocity - 1.0);
        final transferAmount = math.min(surplus, deficit).abs();
        
        if (transferAmount > 10.0) { // Minimum transfer threshold
          opportunities['${fromCategory}_to_${toCategory}'] = RedistributionOpportunity(
            fromCategory: fromCategory,
            toCategory: toCategory,
            amount: transferAmount,
            confidence: _calculateTransferConfidence(fromVelocity, toVelocity),
          );
        }
      }
    }
    
    return opportunities;
  }

  Map<String, RedistributionOpportunity> _applyBehavioralConstraints(
    Map<String, RedistributionOpportunity> opportunities,
    BehavioralProfile? profile,
    IncomeTier incomeTier,
  ) {
    if (profile == null) return opportunities;
    
    final constrainedOpportunities = <String, RedistributionOpportunity>{};
    
    opportunities.forEach((key, opportunity) {
      var adjustedAmount = opportunity.amount;
      
      // Apply risk tolerance constraints
      if (profile.riskTolerance == RiskTolerance.low) {
        adjustedAmount *= 0.5; // Conservative redistribution
      } else if (profile.riskTolerance == RiskTolerance.high) {
        adjustedAmount *= 1.2; // Aggressive redistribution
      }
      
      // Apply spending personality constraints
      if (profile.spendingPersonality == SpendingPersonality.saver) {
        // Savers prefer to keep buffers
        adjustedAmount *= 0.8;
      }
      
      constrainedOpportunities[key] = RedistributionOpportunity(
        fromCategory: opportunity.fromCategory,
        toCategory: opportunity.toCategory,
        amount: adjustedAmount,
        confidence: opportunity.confidence,
      );
    });
    
    return constrainedOpportunities;
  }

  List<BudgetTransfer> _calculateOptimalTransfers(
    Map<String, RedistributionOpportunity> opportunities,
    double monthlyIncome,
    IncomeTier incomeTier,
  ) {
    final transfers = <BudgetTransfer>[];
    
    // Sort opportunities by confidence and amount
    final sortedOpportunities = opportunities.values.toList()
      ..sort((a, b) => (b.confidence * b.amount).compareTo(a.confidence * a.amount));
    
    final maxTransferAmount = monthlyIncome * 0.1; // Max 10% of income in transfers
    var totalTransferred = 0.0;
    
    for (final opportunity in sortedOpportunities) {
      if (totalTransferred + opportunity.amount <= maxTransferAmount) {
        transfers.add(BudgetTransfer(
          fromCategory: opportunity.fromCategory,
          toCategory: opportunity.toCategory,
          amount: opportunity.amount,
          reason: 'Optimizing based on spending velocity patterns',
          confidenceLevel: opportunity.confidence,
        ));
        totalTransferred += opportunity.amount;
      }
    }
    
    return transfers;
  }

  double _calculateTransferConfidence(double fromVelocity, double toVelocity) {
    // Higher confidence when there's clear underspending and overspending
    final velocityDifference = (toVelocity - fromVelocity).abs();
    return math.min(velocityDifference / 2.0, 1.0);
  }

  double _calculateRedistributionConfidence(List<BudgetTransfer> transfers, IncomeTier tier) {
    if (transfers.isEmpty) return 0.0;
    
    final avgConfidence = transfers.fold<double>(0, (sum, t) => sum + t.confidenceLevel) / transfers.length;
    
    // Adjust based on tier - higher tiers can handle more complex redistributions
    switch (tier) {
      case IncomeTier.low:
        return avgConfidence * 0.8; // Lower confidence for complex changes
      case IncomeTier.lowerMiddle:
        return avgConfidence * 0.9;
      case IncomeTier.middle:
        return avgConfidence;
      case IncomeTier.upperMiddle:
      case IncomeTier.high:
        return avgConfidence * 1.1; // Higher confidence for sophisticated users
    }
  }

  double _assessBehavioralImpact(List<BudgetTransfer> transfers, BehavioralProfile? profile) {
    if (transfers.isEmpty) return 0.0;
    if (profile == null) return 0.5;
    
    // Calculate impact based on user's behavioral traits
    var impactScore = 0.5;
    
    // Risk tolerance affects comfort with changes
    switch (profile.riskTolerance) {
      case RiskTolerance.low:
        impactScore = math.max(0.2, impactScore - 0.2);
        break;
      case RiskTolerance.high:
        impactScore = math.min(0.9, impactScore + 0.2);
        break;
      case RiskTolerance.moderate:
        break;
    }
    
    // Spending personality affects adaptation to changes
    switch (profile.spendingPersonality) {
      case SpendingPersonality.saver:
        impactScore = math.min(0.8, impactScore + 0.1); // Savers adapt well to optimization
        break;
      case SpendingPersonality.spender:
        impactScore = math.max(0.3, impactScore - 0.1); // Spenders may resist restrictions
        break;
      case SpendingPersonality.balanced:
        break;
    }
    
    return impactScore;
  }

  double _calculateProjectedSavings(List<BudgetTransfer> transfers, int remainingDays) {
    final totalTransferred = transfers.fold<double>(0, (sum, t) => sum + t.amount);
    final dailySavings = totalTransferred / 30; // Approximate daily savings
    return dailySavings * remainingDays;
  }
}

// ===========================================================================
// DATA CLASSES
// ===========================================================================

class BudgetAllocation {
  final Map<String, double> allocations;
  final double confidence;
  final double behavioralAlignment;
  final List<String> optimizationOpportunities;

  BudgetAllocation({
    required this.allocations,
    required this.confidence,
    required this.behavioralAlignment,
    required this.optimizationOpportunities,
  });
}

class BudgetRedistribution {
  List<BudgetTransfer> transfers = [];
  double confidence = 0.0;
  double behavioralImpact = 0.0;
  double projectedSavings = 0.0;
}

class BudgetTransfer {
  final String fromCategory;
  final String toCategory;
  final double amount;
  final String reason;
  final double confidenceLevel;

  BudgetTransfer({
    required this.fromCategory,
    required this.toCategory,
    required this.amount,
    required this.reason,
    required this.confidenceLevel,
  });
}

class SpendingPrediction {
  Map<String, double> categoryPredictions = {};
  double totalPredicted = 0.0;
  double confidence = 0.0;
  List<String> riskFactors = [];
  List<String> recommendations = [];
}

class PredictionModel {
  final String name;
  final Map<String, double> predictions;
  final double weight;

  PredictionModel(this.name, this.predictions, this.weight);
}

class FinancialHealthScore {
  double overallScore = 0.0;
  double budgetAdherenceScore = 0.0;
  double savingsRateScore = 0.0;
  double debtManagementScore = 0.0;
  double emergencyFundScore = 0.0;
  double investmentScore = 0.0;
  double goalProgressScore = 0.0;
  List<String> insights = [];
  List<String> recommendations = [];
  List<String> riskAreas = [];
}

class BehavioralNudge {
  final String title;
  final String message;
  final NudgeType type;
  final double impactScore;
  final Color? color;
  final IconData? icon;

  BehavioralNudge({
    required this.title,
    required this.message,
    required this.type,
    required this.impactScore,
    this.color,
    this.icon,
  });
}

enum NudgeType {
  lossAversion,
  socialProof,
  anchoring,
  mentalAccounting,
  commitment,
}

class FinancialSafetyCheck {
  double overallSafetyScore = 0.0;
  bool incomeValidation = true;
  bool budgetSafety = true;
  bool debtSafety = true;
  bool emergencyFundSafety = true;
  bool goalFeasibility = true;
  double lifestyleInflationRisk = 0.0;
  List<String> warnings = [];
  List<String> recommendations = [];
}

class BehavioralProfile {
  final RiskTolerance riskTolerance;
  final SpendingPersonality spendingPersonality;
  final List<String> spendingTriggers;
  final double impulsivityScore;
  final double planningHorizon; // in months

  BehavioralProfile({
    required this.riskTolerance,
    required this.spendingPersonality,
    required this.spendingTriggers,
    required this.impulsivityScore,
    required this.planningHorizon,
  });
}

enum RiskTolerance { low, moderate, high }
enum SpendingPersonality { saver, balanced, spender }

class FinancialGoal {
  final String id;
  final String title;
  final String category;
  final double targetAmount;
  final double currentAmount;
  final double monthlyContribution;
  final DateTime targetDate;
  final bool isActive;

  FinancialGoal({
    required this.id,
    required this.title,
    required this.category,
    required this.targetAmount,
    required this.currentAmount,
    required this.monthlyContribution,
    required this.targetDate,
    required this.isActive,
  });
}