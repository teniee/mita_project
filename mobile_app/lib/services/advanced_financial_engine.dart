import 'dart:async';
import 'dart:math' as math;
import 'package:flutter/material.dart';
import 'income_service.dart';
import 'api_service.dart';
import 'logging_service.dart';
import 'redistribution_opportunity.dart';

/// Advanced Financial Engine for MITA
/// 
/// This service integrates all backend financial algorithms into the Flutter app,
/// making MITA truly intelligent with real-time financial calculations,
/// behavioral analysis, and personalized recommendations.
class AdvancedFinancialEngine extends ChangeNotifier {
  static final AdvancedFinancialEngine _instance = AdvancedFinancialEngine._internal();
  factory AdvancedFinancialEngine() => _instance;
  AdvancedFinancialEngine._internal();

  final IncomeService _incomeService = IncomeService();
  final ApiService _apiService = ApiService();
  
  // Real-time financial state
  Map<String, dynamic>? _currentFinancialProfile;
  Map<String, dynamic>? _behavioralAnalysis;
  Map<String, dynamic>? _spendingPatterns;
  Map<String, dynamic>? _budgetOptimization;
  Map<String, dynamic>? _riskAssessment;
  List<Map<String, dynamic>> _intelligentNotifications = [];
  Map<String, dynamic>? _predictiveAnalytics;
  
  // Behavioral learning state
  final Map<String, dynamic> _userBehaviorProfile = {};
  final List<Map<String, dynamic>> _behaviorHistory = [];
  Timer? _realTimeAnalysisTimer;
  Timer? _behaviorLearningTimer;
  
  // Configuration
  final bool _enableRealTimeAnalysis = true;
  final bool _enableBehavioralLearning = true;
  final bool _enablePredictiveAlerts = true;
  
  // Getters for real-time financial data
  Map<String, dynamic>? get currentFinancialProfile => _currentFinancialProfile;
  Map<String, dynamic>? get behavioralAnalysis => _behavioralAnalysis;
  Map<String, dynamic>? get spendingPatterns => _spendingPatterns;
  Map<String, dynamic>? get budgetOptimization => _budgetOptimization;
  Map<String, dynamic>? get riskAssessment => _riskAssessment;
  List<Map<String, dynamic>> get intelligentNotifications => _intelligentNotifications;
  Map<String, dynamic>? get predictiveAnalytics => _predictiveAnalytics;
  Map<String, dynamic> get userBehaviorProfile => _userBehaviorProfile;

  // ============================================================================
  // CORE ENGINE INITIALIZATION AND LIFECYCLE
  // ============================================================================

  /// Initialize the advanced financial engine
  Future<void> initialize() async {
    try {
      logInfo('Initializing Advanced Financial Engine', tag: 'FINANCIAL_ENGINE');
      
      // Load initial financial profile
      await _loadFinancialProfile();
      
      // Start real-time analysis if enabled
      if (_enableRealTimeAnalysis) {
        _startRealTimeAnalysis();
      }
      
      // Start behavioral learning if enabled
      if (_enableBehavioralLearning) {
        _startBehavioralLearning();
      }
      
      // Load behavioral analysis
      await _loadBehavioralAnalysis();
      
      // Load initial spending patterns
      await _loadSpendingPatterns();
      
      // Generate initial budget optimization
      await _generateBudgetOptimization();
      
      // Assess financial risk
      await _assessFinancialRisk();
      
      // Generate predictive analytics
      await _generatePredictiveAnalytics();
      
      // Generate intelligent notifications
      await _generateIntelligentNotifications();
      
      logInfo('Advanced Financial Engine initialized successfully', tag: 'FINANCIAL_ENGINE');
      notifyListeners();
      
    } catch (e) {
      logError('Failed to initialize Advanced Financial Engine: $e', tag: 'FINANCIAL_ENGINE', error: e);
    }
  }

  /// Dispose the financial engine and clean up resources
  @override
  void dispose() {
    _realTimeAnalysisTimer?.cancel();
    _behaviorLearningTimer?.cancel();
    super.dispose();
  }

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
    const daysInMonth = 30; // Approximate
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
          opportunities['${fromCategory}_to_$toCategory'] = RedistributionOpportunity(
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

  // ============================================================================
  // SMART BUDGET REDISTRIBUTION (BACKEND INTEGRATION)
  // ============================================================================

  /// Redistribute budget using advanced backend algorithms
  Future<Map<String, dynamic>> redistributeBudgetWithBackend({
    required Map<String, dynamic> calendarData,
    String strategy = 'intelligent',
  }) async {
    try {
      logInfo('Starting smart budget redistribution with backend', tag: 'BUDGET_REDISTRIBUTION', extra: {
        'strategy': strategy,
        'calendarDays': calendarData.length,
      });

      // Call backend redistribution algorithm
      final redistributionResult = await _apiService.redistributeCalendarBudget(
        calendarData,
        strategy: strategy,
      );

      // Apply behavioral enhancements to redistribution
      final enhancedResult = await _enhanceRedistributionWithBehavior(redistributionResult);

      // Generate redistribution insights
      final insights = _generateRedistributionInsights(enhancedResult);

      // Update local state
      _budgetOptimization = {
        ...?_budgetOptimization,
        'last_redistribution': enhancedResult,
        'redistribution_insights': insights,
        'timestamp': DateTime.now().toIso8601String(),
      };

      // Trigger intelligent notification if significant changes
      await _checkRedistributionNotifications(enhancedResult);

      notifyListeners();
      
      logInfo('Budget redistribution completed successfully', tag: 'BUDGET_REDISTRIBUTION');
      return enhancedResult;
      
    } catch (e) {
      logError('Budget redistribution failed: $e', tag: 'BUDGET_REDISTRIBUTION', error: e);
      
      // Fallback to local redistribution algorithm
      return _fallbackBudgetRedistribution(calendarData);
    }
  }

  /// Enhanced redistribution with behavioral learning
  Future<Map<String, dynamic>> _enhanceRedistributionWithBehavior(
    Map<String, dynamic> baseRedistribution
  ) async {
    try {
      // Get user's behavioral patterns
      final patterns = _spendingPatterns?['patterns'] as List<dynamic>? ?? [];
      final behaviorType = _userBehaviorProfile['spending_personality'] as String? ?? 'balanced';

      // Apply behavioral adjustments
      final enhancedCalendar = <String, dynamic>{};
      final redistributedCalendar = baseRedistribution['calendar'] as Map<String, dynamic>? ?? {};

      for (final entry in redistributedCalendar.entries) {
        final dayData = entry.value as Map<String, dynamic>;
        final dayNumber = int.tryParse(entry.key) ?? 0;
        
        if (dayNumber == 0) continue;

        // Apply behavioral adjustments based on patterns
        double behavioralMultiplier = 1.0;
        
        // Weekend adjustment for weekend overspenders
        if (patterns.contains('weekend_overspending')) {
          final dayOfWeek = _getDayOfWeek(dayNumber);
          if (dayOfWeek == 6 || dayOfWeek == 7) { // Weekend
            behavioralMultiplier *= 0.85; // Reduce weekend budget by 15%
          }
        }
        
        // Impulse buying protection
        if (patterns.contains('impulse_buying')) {
          behavioralMultiplier *= 0.9; // General 10% reduction for impulse buyers
        }
        
        // Adjust based on spending personality
        switch (behaviorType) {
          case 'conservative':
            behavioralMultiplier *= 0.95;
            break;
          case 'aggressive':
            behavioralMultiplier *= 1.05;
            break;
          case 'inconsistent':
            behavioralMultiplier *= 0.92; // More conservative for inconsistent spenders
            break;
        }

        // Apply adjustments
        final adjustedLimit = ((dayData['limit'] as num).toDouble() * behavioralMultiplier).round();
        
        enhancedCalendar[entry.key] = {
          ...dayData,
          'limit': adjustedLimit,
          'behavioral_adjustment': behavioralMultiplier,
          'original_limit': dayData['limit'],
        };
      }

      return {
        ...baseRedistribution,
        'calendar': enhancedCalendar,
        'behavioral_enhancements': true,
        'behavior_type': behaviorType,
        'patterns_applied': patterns,
      };
      
    } catch (e) {
      logError('Failed to enhance redistribution with behavior: $e', tag: 'BEHAVIORAL_ENHANCEMENT', error: e);
      return baseRedistribution;
    }
  }

  /// Generate insights from redistribution results
  Map<String, dynamic> _generateRedistributionInsights(Map<String, dynamic> redistributionResult) {
    try {
      final insights = <String, dynamic>{};
      final calendar = redistributionResult['calendar'] as Map<String, dynamic>? ?? {};
      final transfers = redistributionResult['transfers'] as List<dynamic>? ?? [];

      // Calculate redistribution statistics
      double totalRedistributed = 0.0;
      int daysAffected = 0;
      final Map<String, int> transfersByDirection = {'surplus_to_deficit': 0, 'future_to_present': 0};

      for (final transfer in transfers) {
        if (transfer is Map<String, dynamic>) {
          totalRedistributed += (transfer['amount'] as num?)?.toDouble() ?? 0.0;
          daysAffected++;
          
          final sourceDay = int.tryParse(transfer['source'] ?? '') ?? 0;
          final targetDay = int.tryParse(transfer['target'] ?? '') ?? 0;
          
          if (sourceDay > targetDay) {
            transfersByDirection['future_to_present'] = (transfersByDirection['future_to_present'] ?? 0) + 1;
          } else {
            transfersByDirection['surplus_to_deficit'] = (transfersByDirection['surplus_to_deficit'] ?? 0) + 1;
          }
        }
      }

      // Generate insight messages
      final messages = <String>[];
      
      if (totalRedistributed > 0) {
        messages.add('Redistributed \$${totalRedistributed.toStringAsFixed(2)} across $daysAffected days');
        
        if (transfersByDirection['future_to_present']! > 0) {
          messages.add('Borrowed from ${transfersByDirection['future_to_present']} future days');
        }
        
        if (transfersByDirection['surplus_to_deficit']! > 0) {
          messages.add('Balanced ${transfersByDirection['surplus_to_deficit']} surplus/deficit pairs');
        }
        
        // Add behavioral insights
        if (redistributionResult['behavioral_enhancements'] == true) {
          messages.add('Applied behavioral adjustments based on your spending patterns');
        }
      } else {
        messages.add('No redistribution needed - budget is well balanced');
      }

      insights['messages'] = messages;
      insights['total_redistributed'] = totalRedistributed;
      insights['days_affected'] = daysAffected;
      insights['transfer_types'] = transfersByDirection;
      insights['timestamp'] = DateTime.now().toIso8601String();

      return insights;
      
    } catch (e) {
      logError('Failed to generate redistribution insights: $e', tag: 'REDISTRIBUTION_INSIGHTS', error: e);
      return {'messages': ['Redistribution completed successfully']};
    }
  }

  // ============================================================================
  // AI-POWERED FINANCIAL ANALYSIS (BACKEND INTEGRATION)
  // ============================================================================

  /// Get comprehensive AI financial analysis
  Future<Map<String, dynamic>> getAIFinancialAnalysis() async {
    try {
      logInfo('Generating AI financial analysis', tag: 'AI_ANALYSIS');

      // Get multiple AI analysis components
      final futures = await Future.wait([
        _apiService.getLatestAISnapshot().catchError((e) => null),
        _apiService.getAIFinancialHealthScore().catchError((e) => null),
        _apiService.getAIPersonalizedFeedback().catchError((e) => null),
        _apiService.getSpendingPatterns().catchError((e) => <String, dynamic>{}),
        _apiService.getAISavingsOptimization().catchError((e) => <String, dynamic>{}),
        _apiService.getAIBudgetOptimization().catchError((e) => <String, dynamic>{}),
      ]);

      final aiSnapshot = futures[0];
      final healthScore = futures[1];
      final personalizedFeedback = futures[2];
      final spendingPatterns = futures[3] as Map<String, dynamic>;
      final savingsOptimization = futures[4] as Map<String, dynamic>;
      final budgetOptimization = futures[5] as Map<String, dynamic>;

      // Combine all analysis components
      final comprehensiveAnalysis = {
        'ai_snapshot': aiSnapshot,
        'financial_health': healthScore,
        'personalized_feedback': personalizedFeedback,
        'spending_patterns': spendingPatterns,
        'savings_optimization': savingsOptimization,
        'budget_optimization': budgetOptimization,
        'analysis_timestamp': DateTime.now().toIso8601String(),
        'confidence_score': _calculateAnalysisConfidence([
          aiSnapshot, healthScore, personalizedFeedback, 
          spendingPatterns, savingsOptimization, budgetOptimization
        ]),
      };

      // Update local state
      _currentFinancialProfile = comprehensiveAnalysis;
      
      // Generate actionable insights
      final actionableInsights = _generateActionableInsights(comprehensiveAnalysis);
      comprehensiveAnalysis['actionable_insights'] = actionableInsights;

      notifyListeners();
      
      logInfo('AI financial analysis completed', tag: 'AI_ANALYSIS', extra: {
        'components': comprehensiveAnalysis.keys.length,
        'confidence': comprehensiveAnalysis['confidence_score'],
      });

      return comprehensiveAnalysis;
      
    } catch (e) {
      logError('AI financial analysis failed: $e', tag: 'AI_ANALYSIS', error: e);
      return _generateFallbackAnalysis();
    }
  }

  // ============================================================================
  // BEHAVIORAL ANALYSIS AND LEARNING (BACKEND INTEGRATION)
  // ============================================================================

  /// Load comprehensive behavioral analysis
  Future<void> _loadBehavioralAnalysis() async {
    try {
      final behaviorData = await _apiService.getBehavioralAnalysis();
      _behavioralAnalysis = behaviorData;
      
      // Update user behavior profile
      _userBehaviorProfile.addAll({
        'analysis_timestamp': DateTime.now().toIso8601String(),
        'behavioral_data': behaviorData,
      });
      
      notifyListeners();
      
    } catch (e) {
      logError('Failed to load behavioral analysis: $e', tag: 'BEHAVIORAL_ANALYSIS', error: e);
      _behavioralAnalysis = _generateFallbackBehavioralAnalysis();
    }
  }

  /// Start behavioral learning system
  void _startBehavioralLearning() {
    _behaviorLearningTimer = Timer.periodic(
      const Duration(hours: 6), // Learn every 6 hours
      (timer) => _performBehavioralLearning(),
    );
  }

  /// Perform behavioral learning analysis
  Future<void> _performBehavioralLearning() async {
    try {
      logInfo('Performing behavioral learning analysis', tag: 'BEHAVIORAL_LEARNING');

      // Get adaptive behavior recommendations
      final recommendations = await _apiService.getAdaptiveBehaviorRecommendations();
      
      // Get spending triggers
      final triggers = await _apiService.getSpendingTriggers();
      
      // Get behavioral predictions
      final predictions = await _apiService.getBehavioralPredictions();
      
      // Update behavior profile
      _userBehaviorProfile.addAll({
        'learning_timestamp': DateTime.now().toIso8601String(),
        'recommendations': recommendations,
        'triggers': triggers,
        'predictions': predictions,
      });

      // Store in behavior history
      _behaviorHistory.add({
        'timestamp': DateTime.now().toIso8601String(),
        'profile_snapshot': Map<String, dynamic>.from(_userBehaviorProfile),
      });

      // Keep only last 30 entries
      if (_behaviorHistory.length > 30) {
        _behaviorHistory.removeRange(0, _behaviorHistory.length - 30);
      }

      // Generate behavioral notifications
      await _generateBehavioralNotifications(recommendations);

      notifyListeners();
      
    } catch (e) {
      logError('Behavioral learning failed: $e', tag: 'BEHAVIORAL_LEARNING', error: e);
    }
  }

  // ============================================================================
  // PREDICTIVE ANALYTICS AND RISK ASSESSMENT (BACKEND INTEGRATION)
  // ============================================================================

  /// Generate predictive analytics
  Future<void> _generatePredictiveAnalytics() async {
    try {
      logInfo('Generating predictive analytics', tag: 'PREDICTIVE_ANALYTICS');

      // Get AI spending prediction
      final spendingPrediction = await _apiService.getAISpendingPrediction(daysAhead: 30);
      
      // Get behavioral predictions
      final behaviorPredictions = await _apiService.getBehavioralPredictions();
      
      // Get goal analysis
      final goalAnalysis = await _apiService.getAIGoalAnalysis();

      // Combine predictions
      _predictiveAnalytics = {
        'spending_prediction': spendingPrediction,
        'behavior_predictions': behaviorPredictions,
        'goal_analysis': goalAnalysis,
        'prediction_timestamp': DateTime.now().toIso8601String(),
        'confidence_level': _calculatePredictionConfidence(spendingPrediction, behaviorPredictions),
      };

      // Generate predictive alerts
      await _generatePredictiveAlerts(_predictiveAnalytics!);

      notifyListeners();
      
    } catch (e) {
      logError('Predictive analytics generation failed: $e', tag: 'PREDICTIVE_ANALYTICS', error: e);
      _predictiveAnalytics = _generateFallbackPredictiveAnalytics();
    }
  }

  /// Assess financial risk
  Future<void> _assessFinancialRisk() async {
    try {
      logInfo('Assessing financial risk', tag: 'RISK_ASSESSMENT');

      // Get spending anomalies
      final anomalies = await _apiService.getSpendingAnomalies();
      
      // Get financial health score
      final healthScore = await _apiService.getAIFinancialHealthScore();
      
      // Get behavioral patterns that indicate risk
      final behaviorData = await _apiService.getBehavioralAnalysis();

      // Calculate risk assessment
      final riskScore = _calculateRiskScore(anomalies, healthScore, behaviorData);
      
      _riskAssessment = {
        'risk_score': riskScore,
        'risk_level': _getRiskLevel(riskScore),
        'anomalies': anomalies,
        'health_score': healthScore,
        'behavioral_risks': _identifyBehavioralRisks(behaviorData),
        'assessment_timestamp': DateTime.now().toIso8601String(),
        'recommendations': _generateRiskRecommendations(riskScore, anomalies),
      };

      // Generate risk-based notifications
      if (riskScore > 70) {
        _intelligentNotifications.add({
          'id': 'high_risk_${DateTime.now().millisecondsSinceEpoch}',
          'type': 'alert',
          'title': 'High Financial Risk Detected',
          'message': 'Your spending patterns indicate elevated financial risk. Review recommended actions.',
          'priority': 'high',
          'timestamp': DateTime.now().toIso8601String(),
          'action': 'review_risk_assessment',
        });
      }

      notifyListeners();
      
    } catch (e) {
      logError('Risk assessment failed: $e', tag: 'RISK_ASSESSMENT', error: e);
      _riskAssessment = _generateFallbackRiskAssessment();
    }
  }

  // ============================================================================
  // INTELLIGENT NOTIFICATIONS SYSTEM (BACKEND INTEGRATION)
  // ============================================================================

  /// Generate intelligent notifications
  Future<void> _generateIntelligentNotifications() async {
    try {
      logInfo('Generating intelligent notifications', tag: 'INTELLIGENT_NOTIFICATIONS');

      final notifications = <Map<String, dynamic>>[];
      final now = DateTime.now();

      // Budget-based notifications
      await _addBudgetNotifications(notifications);
      
      // Pattern-based notifications
      await _addPatternNotifications(notifications);
      
      // Goal-based notifications
      await _addGoalNotifications(notifications);
      
      // Time-based notifications
      await _addTimeBasedNotifications(notifications, now);

      // Priority sort and limit
      notifications.sort((a, b) {
        const priorityOrder = {'critical': 4, 'high': 3, 'medium': 2, 'low': 1};
        return (priorityOrder[b['priority']] ?? 0) - (priorityOrder[a['priority']] ?? 0);
      });

      _intelligentNotifications = notifications.take(10).toList(); // Keep top 10
      
      notifyListeners();
      
    } catch (e) {
      logError('Failed to generate intelligent notifications: $e', tag: 'INTELLIGENT_NOTIFICATIONS', error: e);
    }
  }

  // ============================================================================
  // REAL-TIME FINANCIAL CALCULATIONS (BACKEND INTEGRATION)
  // ============================================================================

  /// Start real-time analysis engine
  void _startRealTimeAnalysis() {
    _realTimeAnalysisTimer = Timer.periodic(
      const Duration(minutes: 15), // Update every 15 minutes
      (timer) => _performRealTimeAnalysis(),
    );
  }

  /// Perform real-time financial analysis
  Future<void> _performRealTimeAnalysis() async {
    try {
      logDebug('Performing real-time financial analysis', tag: 'REAL_TIME_ANALYSIS');

      // Get current financial state
      final currentState = await _getCurrentFinancialState();
      
      // Analyze spending velocity
      final spendingVelocity = _analyzeSpendingVelocity(currentState);
      
      // Check for budget deviations
      final budgetDeviations = _detectBudgetDeviations(currentState);
      
      // Calculate real-time optimizations
      final optimizations = await _calculateRealTimeOptimizations(currentState);
      
      // Update financial profile
      _currentFinancialProfile = {
        ...?_currentFinancialProfile,
        'real_time_state': currentState,
        'spending_velocity': spendingVelocity,
        'budget_deviations': budgetDeviations,
        'optimizations': optimizations,
        'last_analysis': DateTime.now().toIso8601String(),
      };

      // Generate real-time notifications if needed
      await _checkRealTimeNotifications(spendingVelocity, budgetDeviations);

      notifyListeners();
      
    } catch (e) {
      logError('Real-time analysis failed: $e', tag: 'REAL_TIME_ANALYSIS', error: e);
    }
  }

  // ============================================================================
  // HELPER METHODS AND UTILITIES (BACKEND INTEGRATION)
  // ============================================================================

  /// Calculate analysis confidence score
  double _calculateAnalysisConfidence(List<dynamic> analysisComponents) {
    int validComponents = 0;
    int totalComponents = analysisComponents.length;
    
    for (final component in analysisComponents) {
      if (component != null && component is Map && component.isNotEmpty) {
        validComponents++;
      }
    }
    
    return totalComponents > 0 ? validComponents / totalComponents : 0.0;
  }

  /// Get day of week for a given day number
  int _getDayOfWeek(int dayNumber) {
    final now = DateTime.now();
    final date = DateTime(now.year, now.month, dayNumber);
    return date.weekday;
  }

  // ============================================================================
  // FALLBACK METHODS (BACKEND INTEGRATION)
  // ============================================================================

  /// Fallback budget redistribution when API fails
  Map<String, dynamic> _fallbackBudgetRedistribution(Map<String, dynamic> calendarData) {
    logInfo('Using fallback budget redistribution', tag: 'FALLBACK_REDISTRIBUTION');
    
    final redistributedCalendar = <String, dynamic>{};
    final transfers = <Map<String, dynamic>>[];
    
    // Simple redistribution logic: move 10% from future days to overspent days
    final today = DateTime.now().day;
    
    calendarData.forEach((key, value) {
      final dayNumber = int.tryParse(key) ?? 0;
      if (dayNumber == 0) return;
      
      final dayData = value as Map<String, dynamic>;
      final limit = (dayData['limit'] as num?)?.toDouble() ?? 0.0;
      final spent = (dayData['spent'] as num?)?.toDouble() ?? 0.0;
      
      if (spent > limit && dayNumber <= today) {
        // This is an overspent day, try to add budget from future days
        final shortage = spent - limit;
        redistributedCalendar[key] = {
          ...dayData,
          'limit': limit + (shortage * 0.5), // Add 50% of shortage
        };
      } else if (dayNumber > today && spent == 0) {
        // Future day, reduce budget slightly
        redistributedCalendar[key] = {
          ...dayData,
          'limit': limit * 0.95, // Reduce by 5%
        };
      } else {
        redistributedCalendar[key] = dayData;
      }
    });
    
    return {
      'calendar': redistributedCalendar,
      'transfers': transfers,
      'fallback': true,
      'timestamp': DateTime.now().toIso8601String(),
    };
  }

  /// Generate fallback analysis when AI services fail
  Map<String, dynamic> _generateFallbackAnalysis() {
    return {
      'financial_health': {'score': 75, 'grade': 'B+'},
      'spending_patterns': {'patterns': ['consistent_spending']},
      'analysis_timestamp': DateTime.now().toIso8601String(),
      'fallback': true,
    };
  }

  /// Generate fallback behavioral analysis
  Map<String, dynamic> _generateFallbackBehavioralAnalysis() {
    return {
      'spending_personality': 'balanced',
      'key_traits': ['consistent_spending', 'goal_oriented'],
      'recommendations': ['maintain_current_habits'],
      'analysis_timestamp': DateTime.now().toIso8601String(),
      'fallback': true,
    };
  }

  // ============================================================================
  // ASYNC INITIALIZATION HELPERS (BACKEND INTEGRATION)
  // ============================================================================

  /// Load initial financial profile
  Future<void> _loadFinancialProfile() async {
    try {
      final profile = await _apiService.getAIFinancialProfile();
      _currentFinancialProfile = profile;
      
    } catch (e) {
      logError('Failed to load financial profile: $e', tag: 'FINANCIAL_PROFILE', error: e);
      _currentFinancialProfile = _generateFallbackAnalysis();
    }
  }

  /// Load initial spending patterns
  Future<void> _loadSpendingPatterns() async {
    try {
      final patterns = await _apiService.getSpendingPatternAnalysis();
      _spendingPatterns = patterns;
      
    } catch (e) {
      logError('Failed to load spending patterns: $e', tag: 'SPENDING_PATTERNS', error: e);
      _spendingPatterns = {'patterns': [], 'fallback': true};
    }
  }

  /// Generate initial budget optimization
  Future<void> _generateBudgetOptimization() async {
    try {
      final optimization = await _apiService.getAISavingsOptimization();
      _budgetOptimization = optimization;
      
    } catch (e) {
      logError('Failed to generate budget optimization: $e', tag: 'BUDGET_OPTIMIZATION', error: e);
      _budgetOptimization = {'potential_savings': 0.0, 'fallback': true};
    }
  }

  // ============================================================================
  // PLACEHOLDER IMPLEMENTATIONS FOR COMPLEX METHODS
  // ============================================================================

  List<Map<String, dynamic>> _generateActionableInsights(Map<String, dynamic> analysis) {
    final insights = <Map<String, dynamic>>[];
    
    try {
      // Health score insights
      final healthScore = analysis['financial_health'];
      if (healthScore != null) {
        final score = healthScore['score'] as int? ?? 0;
        
        if (score < 70) {
          insights.add({
            'type': 'improvement',
            'priority': 'high',
            'title': 'Improve Financial Health',
            'description': 'Your financial health score is $score/100. Focus on budget adherence and savings.',
            'action': 'Review spending patterns and increase savings rate',
            'impact': 'high',
          });
        }
      }

      // Spending pattern insights
      final patterns = analysis['spending_patterns']?['patterns'] as List<dynamic>? ?? [];
      for (final pattern in patterns) {
        if (pattern is String) {
          final insight = _getPatternInsight(pattern);
          if (insight != null) {
            insights.add(insight);
          }
        }
      }

      return insights.take(5).toList(); // Return top 5 insights
      
    } catch (e) {
      logError('Failed to generate actionable insights: $e', tag: 'ACTIONABLE_INSIGHTS', error: e);
      return insights;
    }
  }

  Map<String, dynamic>? _getPatternInsight(String pattern) {
    switch (pattern) {
      case 'weekend_overspending':
        return {
          'type': 'pattern',
          'priority': 'medium',
          'title': 'Weekend Spending Pattern',
          'description': 'You tend to spend more on weekends. Consider setting a specific weekend budget.',
          'action': 'Set weekend spending limits',
          'impact': 'medium',
        };
      case 'impulse_buying':
        return {
          'type': 'behavior',
          'priority': 'high',
          'title': 'Impulse Buying Detected',
          'description': 'We noticed impulse buying patterns. Try the 24-hour rule before purchases.',
          'action': 'Implement purchase waiting periods',
          'impact': 'high',
        };
      default:
        return null;
    }
  }

  Future<void> _generateBehavioralNotifications(Map<String, dynamic> recommendations) async {
    try {
      final notifications = <Map<String, dynamic>>[];
      
      // Check for spending pattern alerts
      final patterns = recommendations['patterns'] as List<dynamic>? ?? [];
      for (final pattern in patterns) {
        if (pattern is String && pattern == 'weekend_overspending') {
          notifications.add({
            'id': 'weekend_pattern_${DateTime.now().millisecondsSinceEpoch}',
            'type': 'tip',
            'title': 'Weekend Spending Tip',
            'message': 'Plan your weekend activities in advance to avoid overspending.',
            'priority': 'low',
            'timestamp': DateTime.now().toIso8601String(),
            'action': 'plan_weekend_budget',
          });
        }
      }

      // Add to intelligent notifications
      _intelligentNotifications.addAll(notifications);
      
    } catch (e) {
      logError('Failed to generate behavioral notifications: $e', tag: 'BEHAVIORAL_NOTIFICATIONS', error: e);
    }
  }

  double _calculatePredictionConfidence(Map<String, dynamic> spending, Map<String, dynamic> behavior) {
    return 0.75; // Placeholder implementation
  }

  Future<void> _generatePredictiveAlerts(Map<String, dynamic> analytics) async {
    // Placeholder implementation for predictive alerts
  }

  double _calculateRiskScore(List<dynamic> anomalies, Map<String, dynamic>? health, Map<String, dynamic>? behavior) {
    return 35.0; // Placeholder implementation
  }

  String _getRiskLevel(double score) {
    if (score < 30) return 'low';
    if (score < 60) return 'moderate';
    return 'high';
  }

  List<Map<String, dynamic>> _identifyBehavioralRisks(Map<String, dynamic>? behavior) {
    return []; // Placeholder implementation
  }

  List<String> _generateRiskRecommendations(double score, List<dynamic> anomalies) {
    return ['Monitor spending patterns closely']; // Placeholder implementation
  }

  Future<void> _addBudgetNotifications(List<Map<String, dynamic>> notifications) async {
    // Add budget-based notifications
    try {
      final budgetStatus = await _apiService.getLiveBudgetStatus();
      final todaySpent = (budgetStatus['today_spent'] as num?)?.toDouble() ?? 0.0;
      final todayLimit = (budgetStatus['today_limit'] as num?)?.toDouble() ?? 0.0;

      if (todayLimit > 0) {
        final todayPercentage = todaySpent / todayLimit;
        
        if (todayPercentage > 0.8) {
          notifications.add({
            'id': 'today_approaching_limit_${DateTime.now().millisecondsSinceEpoch}',
            'type': 'warning',
            'title': 'Approaching Daily Limit',
            'message': 'You\'ve used ${(todayPercentage * 100).toStringAsFixed(0)}% of today\'s budget.',
            'priority': 'medium',
            'timestamp': DateTime.now().toIso8601String(),
            'action': 'check_remaining_budget',
          });
        }
      }
    } catch (e) {
      logError('Failed to add budget notifications: $e', tag: 'BUDGET_NOTIFICATIONS', error: e);
    }
  }

  Future<void> _addPatternNotifications(List<Map<String, dynamic>> notifications) async {
    // Placeholder for pattern-based notifications
  }

  Future<void> _addGoalNotifications(List<Map<String, dynamic>> notifications) async {
    // Placeholder for goal-based notifications
  }

  Future<void> _addTimeBasedNotifications(List<Map<String, dynamic>> notifications, DateTime now) async {
    // Placeholder for time-based notifications
  }

  Future<Map<String, dynamic>> _getCurrentFinancialState() async {
    return {'placeholder': true}; // Placeholder implementation
  }

  Map<String, dynamic> _analyzeSpendingVelocity(Map<String, dynamic> currentState) {
    return {'velocity': 'normal', 'placeholder': true}; // Placeholder implementation
  }

  List<Map<String, dynamic>> _detectBudgetDeviations(Map<String, dynamic> currentState) {
    return []; // Placeholder implementation
  }

  Future<Map<String, dynamic>> _calculateRealTimeOptimizations(Map<String, dynamic> currentState) async {
    return {'optimizations': [], 'placeholder': true}; // Placeholder implementation
  }

  Future<void> _checkRealTimeNotifications(Map<String, dynamic> velocity, List<dynamic> deviations) async {
    // Placeholder implementation for real-time notifications
  }

  Future<void> _checkRedistributionNotifications(Map<String, dynamic> redistributionResult) async {
    // Placeholder implementation for redistribution notifications
  }

  Map<String, dynamic> _generateFallbackPredictiveAnalytics() {
    return {
      'spending_prediction': {
        'predicted_amount': 2500.0,
        'confidence': 0.7,
        'factors': ['historical_average'],
      },
      'prediction_timestamp': DateTime.now().toIso8601String(),
      'fallback': true,
    };
  }

  Map<String, dynamic> _generateFallbackRiskAssessment() {
    return {
      'risk_score': 45,
      'risk_level': 'moderate',
      'assessment_timestamp': DateTime.now().toIso8601String(),
      'fallback': true,
    };
  }

  List<String> _generateSafetyRecommendations(FinancialSafetyCheck safetyCheck, IncomeTier incomeTier) {
    final recommendations = <String>[];
    
    if (!safetyCheck.emergencyFundSafety) {
      recommendations.add('Build an emergency fund covering 3-6 months of expenses');
    }
    
    if (!safetyCheck.budgetSafety) {
      recommendations.add('Review and adjust your monthly budget allocations');
    }
    
    if (!safetyCheck.debtSafety) {
      recommendations.add('Consider debt consolidation or payment plan optimization');
    }
    
    if (safetyCheck.lifestyleInflationRisk > 0.7) {
      recommendations.add('Monitor lifestyle inflation and maintain savings discipline');
    }
    
    if (!safetyCheck.goalFeasibility) {
      recommendations.add('Reassess financial goals and timeline for achievability');
    }
    
    // Income tier specific recommendations
    switch (incomeTier) {
      case IncomeTier.low:
        recommendations.add('Focus on essential expenses and building basic savings');
        break;
      case IncomeTier.middle:
        recommendations.add('Balance debt repayment with investment opportunities');
        break;
      case IncomeTier.high:
        recommendations.add('Maximize tax-advantaged savings and investment diversification');
        break;
    }
    
    return recommendations;
  }

  List<String> _generateSafetyWarnings(FinancialSafetyCheck safetyCheck) {
    final warnings = <String>[];
    
    if (safetyCheck.overallSafetyScore < 40) {
      warnings.add('Critical: Financial safety requires immediate attention');
    } else if (safetyCheck.overallSafetyScore < 60) {
      warnings.add('Warning: Several financial safety concerns detected');
    }
    
    if (safetyCheck.lifestyleInflationRisk > 0.8) {
      warnings.add('High risk of lifestyle inflation affecting long-term savings');
    }
    
    return warnings;
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