import '../models/budget_intelligence_models.dart';
import 'logging_service.dart';

// Import all the enhanced services
import 'enhanced_income_service.dart';
import 'temporal_intelligence_service.dart';
import 'spending_velocity_service.dart';
import 'advanced_habit_recognition_service.dart';
import 'contextual_nudge_service.dart';
import 'social_comparison_service.dart';
import 'predictive_budget_service.dart';
import 'category_intelligence_service.dart';
import 'explanation_engine_service.dart';

/// Master budget engine integrating all enhanced intelligence services
class EnhancedMasterBudgetEngine {
  static final EnhancedMasterBudgetEngine _instance = EnhancedMasterBudgetEngine._internal();
  factory EnhancedMasterBudgetEngine() => _instance;
  EnhancedMasterBudgetEngine._internal();

  // Service instances
  final EnhancedIncomeService _incomeService = EnhancedIncomeService();
  final TemporalIntelligenceService _temporalService = TemporalIntelligenceService();
  final SpendingVelocityService _velocityService = SpendingVelocityService();
  final AdvancedHabitRecognitionService _habitService = AdvancedHabitRecognitionService();
  final ContextualNudgeService _nudgeService = ContextualNudgeService();
  final SocialComparisonService _socialService = SocialComparisonService();
  final PredictiveBudgetService _predictiveService = PredictiveBudgetService();
  final CategoryIntelligenceService _categoryService = CategoryIntelligenceService();
  final ExplanationEngineService _explanationService = ExplanationEngineService();

  /// Calculate enhanced daily budget with full intelligence integration
  Future<EnhancedBudgetResult> calculateEnhancedDailyBudget({
    required String userId,
    required Map<String, dynamic> userProfile,
    required List<Map<String, dynamic>> transactionHistory,
    required DateTime targetDate,
    Map<String, dynamic>? userFeedback,
  }) async {
    final calculationSteps = <String, dynamic>{};
    final insights = <String>[];
    final recommendations = <String>[];

    // Step 1: Enhanced Income Classification with Transitions
    final incomeClassification = await _incomeService.classifyIncomeEnhanced(
      (userProfile['monthlyIncome'] as num?)?.toDouble() ?? 0.0,
      countryCode: userProfile['countryCode']?.toString(),
      stateCode: userProfile['stateCode']?.toString(),
    );
    calculationSteps['incomeClassification'] = _mapIncomeClassificationToMap(incomeClassification);

    // Step 2: Learn and Apply Temporal Intelligence
    final spendingPattern = await _temporalService.learnSpendingPatterns(transactionHistory);
    final temporalAdjustment = await _temporalService.calculateTemporalAdjustment(
      0.0, // Will be set after base calculation
      targetDate,
      spendingPattern,
    );
    calculationSteps['temporalIntelligence'] = _mapTemporalBudgetToMap(temporalAdjustment);

    // Step 3: Spending Velocity Analysis
    AdaptiveBudgetAllocation? velocityAdjustment;
    if (transactionHistory.length >= 10) {
      final velocityAnalysis = await _velocityService.analyzeSpendingVelocity(
        recentTransactions: transactionHistory.take(30).toList(),
        historicalTransactions: transactionHistory,
        currentDailyBudget: (userProfile['dailyBudget'] as num?)?.toDouble() ?? 50.0,
        analysisDate: targetDate,
      );

      velocityAdjustment = await _velocityService.createAdaptiveBudgetAllocation(
        velocityAnalysis: velocityAnalysis,
        monthlyBudget: (userProfile['monthlyBudget'] as num?)?.toDouble() ?? 1500.0,
        startDate: targetDate,
        daysAhead: 30,
      );
      calculationSteps['velocityAnalysis'] = _mapAdaptiveBudgetToMap(velocityAdjustment);
    }

    // Step 4: Advanced Habit Recognition and Correction
    final habitAnalysis = await _habitService.analyzeSpendingHabits(transactionHistory);
    final behavioralCorrections = await _habitService.generateBehavioralCorrections(habitAnalysis.detectedHabits);
    calculationSteps['habitAnalysis'] = _mapHabitAnalysisToMap(habitAnalysis);
    calculationSteps['behavioralCorrections'] = _mapBehavioralCorrectionsToMap(behavioralCorrections);

    // Step 5: Category Intelligence Optimization
    final lifeEvents = await _categoryService.detectLifeEvents(transactionHistory);
    final categoryOptimization = await _categoryService.optimizeCategories(
      userId: userId,
      spendingHistory: transactionHistory,
      userGoals: userProfile['goals'] as Map<String, dynamic>? ?? {},
      currentFinancialState: userProfile,
    );
    calculationSteps['lifeEvents'] = _mapLifeEventsToMap(lifeEvents);
    calculationSteps['categoryOptimization'] = categoryOptimization;

    // Step 6: Calculate Base Daily Budget
    final baseDailyBudget = _calculateBaseDailyBudget(
      incomeClassification,
      userProfile,
      categoryOptimization,
    );

    // Step 7: Apply Intelligence Adjustments
    var adjustedBudget = baseDailyBudget;

    // Apply temporal adjustment
    adjustedBudget = _applyTemporalAdjustment(adjustedBudget, temporalAdjustment);

    // Apply velocity adjustment
    if (velocityAdjustment != null) {
      adjustedBudget = velocityAdjustment.adjustedDailyBudget;
    }

    // Apply behavioral corrections
    adjustedBudget = _applyBehavioralCorrections(adjustedBudget, behavioralCorrections);

    // Step 8: Generate Personalized Nudge
    try {
      await _nudgeService.generatePersonalizedNudge(
        userId: userId,
        context: NudgeContext.dailyCheckin,
        contextData: {
          'dailyBudget': adjustedBudget,
          'targetDate': targetDate.toIso8601String(),
          'userProfile': userProfile,
        },
      );
    } catch (e) {
      // Handle nudge generation failure gracefully
      LoggingService.instance.logError('Nudge generation failed', error: e);
    }

    // Step 9: Generate Tomorrow's Forecast
    try {
      await _predictiveService.generateSingleForecast(
        historicalData: transactionHistory,
        forecastDate: targetDate.add(const Duration(days: 1)),
      );
    } catch (e) {
      // Handle forecast generation failure gracefully
      LoggingService.instance.logError('Forecast generation failed', error: e);
    }

    // Step 10: Generate Social Insights
    List<SocialComparisonInsight> socialInsights = [];
    try {
      final userDemo = UserDemographicProfile(
        userId: userId,
        incomeTier: incomeClassification.primaryTier,
        interests: (userProfile['interests'] as List<dynamic>?)?.map((e) => e.toString()).toList() ?? [],
        spendingPersonality: userProfile['spendingPersonality'] as Map<String, dynamic>? ?? {},
      );

      socialInsights = await _socialService.generateSocialInsights(
        userId,
        userDemo,
        {
          'monthlySpending': _calculateMonthlySpending(transactionHistory),
          'savingsRate': _calculateSavingsRate(userProfile),
        },
      );
    } catch (e) {
      // Handle social insights failure gracefully
      LoggingService.instance.logError('Social insights generation failed', error: e);
    }

    // Step 11: Generate Explanation
    final explanationContext = ExplanationContext(
      userId: userId,
      userLevel: userProfile['experienceLevel']?.toString() ?? 'intermediate',
      userInterests: (userProfile['interests'] as List<dynamic>?)?.map((e) => e.toString()).toList() ?? [],
      preferVisualExplanations: userProfile['preferVisualExplanations'] as bool? ?? false,
      preferDetailedMath: userProfile['preferDetailedMath'] as bool? ?? false,
      communicationStyle: userProfile['communicationStyle']?.toString() ?? 'simple',
    );

    await _explanationService.generateSimpleExplanation(
      dailyBudget: adjustedBudget,
      monthlyIncome: (userProfile['monthlyIncome'] as num?)?.toDouble() ?? 0.0,
      userLevel: explanationContext.userLevel,
    );

    // Step 12: Calculate Confidence and Risk Score
    final confidence = _calculateOverallConfidence(calculationSteps, transactionHistory.length);
    final riskScore = _calculateRiskScore(habitAnalysis, velocityAdjustment, lifeEvents);

    // Step 13: Generate Final Insights and Recommendations
    insights.addAll(_generatePersonalizedInsights(
      incomeClassification,
      habitAnalysis,
      socialInsights,
      velocityAdjustment,
      lifeEvents,
    ));

    recommendations.addAll(_generateRecommendations(
      habitAnalysis,
      velocityAdjustment,
      lifeEvents,
      socialInsights,
    ));

    // Step 14: Generate Category Allocations
    final categoryAllocations = _generateCategoryAllocations(
      adjustedBudget,
      categoryOptimization,
      incomeClassification.primaryTier,
    );

    return EnhancedBudgetResult(
      dailyBudget: adjustedBudget,
      confidence: confidence,
      calculationBreakdown: calculationSteps,
      personalizedInsights: insights,
      recommendations: recommendations,
      categoryAllocations: categoryAllocations,
      riskScore: riskScore,
      metadata: {
        'calculationDate': DateTime.now().toIso8601String(),
        'targetDate': targetDate.toIso8601String(),
        'servicesUsed': [
          'income_classification',
          'temporal_intelligence',
          'velocity_analysis',
          'habit_recognition',
          'category_optimization',
          'social_comparison',
          'predictive_forecasting',
        ],
        'dataQuality': _assessDataQuality(transactionHistory),
        'userId': userId,
      },
    );
  }

  /// Generate comprehensive budget intelligence analysis
  Future<BudgetIntelligenceResult> generateBudgetIntelligence({
    required String userId,
    required Map<String, dynamic> userProfile,
    required List<Map<String, dynamic>> transactionHistory,
    required DateTime targetDate,
    Map<String, dynamic>? userFeedback,
  }) async {
    // Calculate enhanced budget first
    final currentBudget = await calculateEnhancedDailyBudget(
      userId: userId,
      userProfile: userProfile,
      transactionHistory: transactionHistory,
      targetDate: targetDate,
      userFeedback: userFeedback,
    );

    // Generate additional intelligence analysis
    final predictiveAnalysis = await _predictiveService.generateBudgetPredictions(
      historicalData: transactionHistory,
      currentFinancialState: userProfile,
      externalFactors: [],
      forecastDays: 30,
    );

    // Calculate overall health score
    final overallHealthScore = _calculateOverallHealthScore(
      currentBudget,
      predictiveAnalysis,
      transactionHistory,
    );

    // Generate actionable insights
    final actionableInsights = _generateActionableInsights(
      currentBudget,
      predictiveAnalysis,
      transactionHistory,
    );

    // Generate performance metrics
    final performanceMetrics = _generatePerformanceMetrics(
      currentBudget,
      predictiveAnalysis,
      transactionHistory,
      userProfile,
    );

    return BudgetIntelligenceResult(
      enhancedBudget: currentBudget,
      recommendedNudges: [],
      comprehensiveInsights: {
        'overallHealthScore': overallHealthScore,
        'actionableInsights': actionableInsights,
        'performanceMetrics': performanceMetrics,
      },
      futureProjections: predictiveAnalysis,
    );
  }

  // Helper methods for calculations and transformations

  double _calculateBaseDailyBudget(
    IncomeClassificationResult incomeClassification,
    Map<String, dynamic> userProfile,
    Map<String, dynamic> categoryOptimization,
  ) {
    final monthlyIncome = (userProfile['monthlyIncome'] as num?)?.toDouble() ?? 0.0;
    
    // Base percentage for flexible spending based on income tier
    double flexibleSpendingRatio;
    switch (incomeClassification.primaryTier) {
      case IncomeTier.low:
        flexibleSpendingRatio = 0.35; // 35% for flexible spending
        break;
      case IncomeTier.lowerMiddle:
        flexibleSpendingRatio = 0.40; // 40% for flexible spending
        break;
      case IncomeTier.middle:
        flexibleSpendingRatio = 0.45; // 45% for flexible spending
        break;
      case IncomeTier.upperMiddle:
        flexibleSpendingRatio = 0.50; // 50% for flexible spending
        break;
      case IncomeTier.high:
        flexibleSpendingRatio = 0.55; // 55% for flexible spending
        break;
    }

    // Apply tier blending if in transition
    if (incomeClassification.isInTransition && incomeClassification.secondaryTier != null) {
      final secondaryRatio = _getFlexibleSpendingRatio(incomeClassification.secondaryTier!);
      flexibleSpendingRatio = (flexibleSpendingRatio * incomeClassification.primaryWeight) +
                             (secondaryRatio * incomeClassification.secondaryWeight);
    }

    final monthlyFlexibleBudget = monthlyIncome * flexibleSpendingRatio;
    return monthlyFlexibleBudget / 30; // Convert to daily
  }

  double _getFlexibleSpendingRatio(IncomeTier tier) {
    switch (tier) {
      case IncomeTier.low:
        return 0.35;
      case IncomeTier.lowerMiddle:
        return 0.40;
      case IncomeTier.middle:
        return 0.45;
      case IncomeTier.upperMiddle:
        return 0.50;
      case IncomeTier.high:
        return 0.55;
    }
  }

  double _applyTemporalAdjustment(double baseBudget, TemporalBudgetResult temporalResult) {
    return temporalResult.adjustedDailyBudget;
  }

  double _applyBehavioralCorrections(double baseBudget, List<BehavioralCorrection> corrections) {
    double adjustedBudget = baseBudget;
    
    for (final correction in corrections) {
      adjustedBudget *= correction.budgetMultiplier;
    }
    
    return adjustedBudget;
  }

  double _calculateOverallConfidence(Map<String, dynamic> calculationSteps, int dataPoints) {
    double confidence = 0.5; // Base confidence
    
    // Higher confidence with more data
    if (dataPoints >= 100) confidence += 0.3;
    else if (dataPoints >= 50) confidence += 0.2;
    else if (dataPoints >= 20) confidence += 0.1;
    
    // Higher confidence with more services used
    final servicesUsed = calculationSteps.length;
    confidence += (servicesUsed * 0.05).clamp(0.0, 0.2);
    
    return confidence.clamp(0.0, 1.0);
  }

  double _calculateRiskScore(
    HabitAnalysisResult habitAnalysis,
    AdaptiveBudgetAllocation? velocityAdjustment,
    List<LifeEventDetection> lifeEvents,
  ) {
    double riskScore = 0.0;
    
    // Add risk from bad habits
    riskScore += habitAnalysis.overallHabitScore * 0.4;
    
    // Add risk from high spending velocity
    if (velocityAdjustment != null) {
      if (velocityAdjustment.allocationStrategy.contains('emergency') ||
          velocityAdjustment.allocationStrategy.contains('reduction')) {
        riskScore += 0.3;
      }
    }
    
    // Add risk from life events
    for (final event in lifeEvents) {
      riskScore += event.confidence * 0.1;
    }
    
    return riskScore.clamp(0.0, 1.0);
  }

  double _calculateMonthlySpending(List<Map<String, dynamic>> transactions) {
    final now = DateTime.now();
    final monthStart = DateTime(now.year, now.month, 1);
    
    return transactions
        .where((t) {
          final date = DateTime.tryParse(t['date']?.toString() ?? '') ?? DateTime.now();
          return date.isAfter(monthStart);
        })
        .fold(0.0, (sum, t) => sum + ((t['amount'] as num?)?.toDouble() ?? 0.0));
  }

  double _calculateSavingsRate(Map<String, dynamic> userProfile) {
    final monthlyIncome = (userProfile['monthlyIncome'] as num?)?.toDouble() ?? 0.0;
    final monthlySavings = (userProfile['monthlySavings'] as num?)?.toDouble() ?? 0.0;
    
    return monthlyIncome > 0 ? monthlySavings / monthlyIncome : 0.0;
  }

  List<String> _generatePersonalizedInsights(
    IncomeClassificationResult incomeClassification,
    HabitAnalysisResult habitAnalysis,
    List<SocialComparisonInsight> socialInsights,
    AdaptiveBudgetAllocation? velocityAdjustment,
    List<LifeEventDetection> lifeEvents,
  ) {
    final insights = <String>[];
    
    // Income tier insight
    final tierName = _getTierDisplayName(incomeClassification.primaryTier);
    insights.add('Your income places you in the $tierName category');
    
    // Habit insights
    if (habitAnalysis.detectedHabits.isNotEmpty) {
      final topHabit = habitAnalysis.detectedHabits.first;
      insights.add('Primary spending pattern detected: ${topHabit.habitName}');
    }
    
    // Social insights
    if (socialInsights.isNotEmpty) {
      insights.add(socialInsights.first.comparisonText);
    }
    
    // Life event insights
    if (lifeEvents.isNotEmpty) {
      final recentEvent = lifeEvents.first;
      insights.add('Recent life event detected: ${recentEvent.eventType}');
    }
    
    return insights.take(5).toList();
  }

  List<String> _generateRecommendations(
    HabitAnalysisResult habitAnalysis,
    AdaptiveBudgetAllocation? velocityAdjustment,
    List<LifeEventDetection> lifeEvents,
    List<SocialComparisonInsight> socialInsights,
  ) {
    final recommendations = <String>[];
    
    // Habit-based recommendations
    recommendations.addAll(habitAnalysis.recommendations.take(2));
    
    // Velocity-based recommendations
    if (velocityAdjustment != null) {
      recommendations.addAll(velocityAdjustment.recommendations.take(2));
    }
    
    // Life event recommendations
    for (final event in lifeEvents.take(1)) {
      recommendations.addAll(event.recommendedAdjustments.take(1));
    }
    
    // Social comparison recommendations
    for (final insight in socialInsights.take(1)) {
      recommendations.add(insight.recommendation);
    }
    
    return recommendations.take(6).toList();
  }

  Map<String, double> _generateCategoryAllocations(
    double dailyBudget,
    Map<String, dynamic> categoryOptimization,
    IncomeTier incomeTier,
  ) {
    // Default category allocations based on income tier
    Map<String, double> allocations;
    
    switch (incomeTier) {
      case IncomeTier.low:
        allocations = {
          'food': 0.35,
          'transportation': 0.20,
          'entertainment': 0.15,
          'shopping': 0.15,
          'other': 0.15,
        };
        break;
      case IncomeTier.high:
        allocations = {
          'food': 0.25,
          'transportation': 0.15,
          'entertainment': 0.25,
          'shopping': 0.20,
          'other': 0.15,
        };
        break;
      default: // middle tiers
        allocations = {
          'food': 0.30,
          'transportation': 0.18,
          'entertainment': 0.20,
          'shopping': 0.17,
          'other': 0.15,
        };
    }
    
    // Convert percentages to actual amounts
    return allocations.map((category, percentage) => 
        MapEntry(category, dailyBudget * percentage));
  }

  double _calculateOverallHealthScore(
    EnhancedBudgetResult currentBudget,
    PredictiveBudgetAnalysis predictiveAnalysis,
    List<Map<String, dynamic>> transactionHistory,
  ) {
    double healthScore = 0.5; // Base score
    
    // Higher score for higher confidence
    healthScore += currentBudget.confidence * 0.3;
    
    // Lower score for higher risk
    healthScore -= currentBudget.riskScore * 0.2;
    
    // Higher score for more stable predictions
    healthScore += predictiveAnalysis.overallConfidence * 0.2;
    
    return healthScore.clamp(0.0, 1.0);
  }

  List<String> _generateActionableInsights(
    EnhancedBudgetResult currentBudget,
    PredictiveBudgetAnalysis predictiveAnalysis,
    List<Map<String, dynamic>> transactionHistory,
  ) {
    final insights = <String>[];
    
    // Budget insights
    if (currentBudget.confidence > 0.8) {
      insights.add('High confidence in budget calculation - your spending patterns are predictable');
    }
    
    if (currentBudget.riskScore > 0.6) {
      insights.add('Elevated spending risk detected - consider implementing protective measures');
    }
    
    // Predictive insights
    if (predictiveAnalysis.riskWarnings.isNotEmpty) {
      insights.addAll(predictiveAnalysis.riskWarnings.take(2));
    }
    
    return insights.take(5).toList();
  }

  Map<String, dynamic> _generatePerformanceMetrics(
    EnhancedBudgetResult currentBudget,
    PredictiveBudgetAnalysis predictiveAnalysis,
    List<Map<String, dynamic>> transactionHistory,
    Map<String, dynamic> userProfile,
  ) {
    return {
      'budgetAccuracy': currentBudget.confidence,
      'riskLevel': currentBudget.riskScore,
      'predictiveAccuracy': predictiveAnalysis.overallConfidence,
      'dataQuality': _assessDataQuality(transactionHistory),
      'intelligenceServices': currentBudget.metadata['servicesUsed'],
      'lastUpdated': DateTime.now().toIso8601String(),
    };
  }

  double _assessDataQuality(List<Map<String, dynamic>> transactions) {
    if (transactions.isEmpty) return 0.0;
    
    double quality = 0.5; // Base quality
    
    // More transactions = higher quality
    if (transactions.length >= 100) quality += 0.3;
    else if (transactions.length >= 50) quality += 0.2;
    else if (transactions.length >= 20) quality += 0.1;
    
    // Check data completeness
    final completeTransactions = transactions.where((t) => 
        t['amount'] != null && 
        t['date'] != null && 
        t['category'] != null).length;
    
    final completenessRatio = completeTransactions / transactions.length;
    quality += completenessRatio * 0.2;
    
    return quality.clamp(0.0, 1.0);
  }

  String _getTierDisplayName(IncomeTier tier) {
    switch (tier) {
      case IncomeTier.low:
        return 'Foundation Builder';
      case IncomeTier.lowerMiddle:
        return 'Stability Seeker';
      case IncomeTier.middle:
        return 'Strategic Achiever';
      case IncomeTier.upperMiddle:
        return 'Wealth Accelerator';
      case IncomeTier.high:
        return 'Legacy Builder';
    }
  }

  // Mapping methods to convert service results to basic Maps for serialization

  Map<String, dynamic> _mapIncomeClassificationToMap(IncomeClassificationResult result) {
    return {
      'primaryTier': result.primaryTier.toString(),
      'secondaryTier': result.secondaryTier?.toString(),
      'primaryWeight': result.primaryWeight,
      'secondaryWeight': result.secondaryWeight,
      'transitionFactor': result.transitionFactor,
      'isInTransition': result.isInTransition,
      'metadata': result.metadata,
    };
  }

  Map<String, dynamic> _mapTemporalBudgetToMap(TemporalBudgetResult result) {
    return {
      'baseDailyBudget': result.baseDailyBudget,
      'adjustedDailyBudget': result.adjustedDailyBudget,
      'temporalMultiplier': result.temporalMultiplier,
      'primaryReason': result.primaryReason,
      'contributingFactors': result.contributingFactors,
      'confidenceLevel': result.confidenceLevel,
      'factorBreakdown': result.factorBreakdown,
    };
  }

  Map<String, dynamic> _mapAdaptiveBudgetToMap(AdaptiveBudgetAllocation allocation) {
    return {
      'originalDailyBudget': allocation.originalDailyBudget,
      'adjustedDailyBudget': allocation.adjustedDailyBudget,
      'totalRemainingBudget': allocation.totalRemainingBudget,
      'allocationStrategy': allocation.allocationStrategy,
      'recommendations': allocation.recommendations,
      'systemConfidence': allocation.systemConfidence,
    };
  }

  Map<String, dynamic> _mapHabitAnalysisToMap(HabitAnalysisResult analysis) {
    return {
      'detectedHabitsCount': analysis.detectedHabits.length,
      'categoryRiskScores': analysis.categoryRiskScores,
      'recommendations': analysis.recommendations,
      'overallHabitScore': analysis.overallHabitScore,
      'insights': analysis.insights,
    };
  }

  Map<String, dynamic> _mapBehavioralCorrectionsToMap(List<BehavioralCorrection> corrections) {
    return {
      'correctionCount': corrections.length,
      'totalBudgetMultiplier': corrections.fold(1.0, (product, c) => product * c.budgetMultiplier),
      'totalBufferMultiplier': corrections.fold(1.0, (product, c) => product * c.bufferMultiplier),
      'expectedImpact': corrections.fold(0.0, (sum, c) => sum + c.expectedImpact),
    };
  }

  Map<String, dynamic> _mapLifeEventsToMap(List<LifeEventDetection> events) {
    return {
      'eventCount': events.length,
      'events': events.map((e) => {
        'eventType': e.eventType,
        'confidence': e.confidence,
        'detectedAt': e.detectedAt.toIso8601String(),
        'indicators': e.indicators,
        'categoryImpacts': e.categoryImpacts,
      }).toList(),
    };
  }
}