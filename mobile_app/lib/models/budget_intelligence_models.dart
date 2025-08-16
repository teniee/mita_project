
/// Data models for the budget intelligence system
library;

// Income tier enumeration
enum IncomeTier {
  low,
  lowerMiddle,
  middle,
  upperMiddle,
  high,
}

// Enhanced Income Service Models
class IncomeClassificationResult {
  final IncomeTier primaryTier;
  final IncomeTier? secondaryTier;
  final double primaryWeight;
  final double secondaryWeight;
  final double transitionFactor;
  final bool isInTransition;
  final Map<String, dynamic> metadata;

  IncomeClassificationResult({
    required this.primaryTier,
    this.secondaryTier,
    required this.primaryWeight,
    required this.secondaryWeight,
    required this.transitionFactor,
    required this.isInTransition,
    required this.metadata,
  });

  /// Get effective tier weights for calculations
  Map<IncomeTier, double> getTierWeights() {
    if (!isInTransition || secondaryTier == null) {
      return {primaryTier: 1.0};
    }
    return {
      primaryTier: primaryWeight,
      secondaryTier!: secondaryWeight,
    };
  }
}

class RegionalIncomeData {
  final String regionId;
  final String regionName;
  final Map<IncomeTier, double> tierThresholds;
  final double medianIncome;
  final Map<String, dynamic> costOfLivingAdjustments;
  final DateTime lastUpdated;

  RegionalIncomeData({
    required this.regionId,
    required this.regionName,
    required this.tierThresholds,
    required this.medianIncome,
    required this.costOfLivingAdjustments,
    required this.lastUpdated,
  });
}

// Goal Interference Service Models
/// Financial goal definition
class FinancialGoal {
  final String goalId;
  final String goalType;
  final String name;
  final double targetAmount;
  final DateTime targetDate;
  final double currentProgress;
  final double monthlyRequiredContribution;
  final int priority;
  final Map<String, dynamic> constraints;
  final bool isFlexible;

  FinancialGoal({
    required this.goalId,
    required this.goalType,
    required this.name,
    required this.targetAmount,
    required this.targetDate,
    required this.currentProgress,
    required this.monthlyRequiredContribution,
    required this.priority,
    required this.constraints,
    required this.isFlexible,
  });
}

/// Goal interference detection result
class GoalInterference {
  final String interferenceId;
  final List<String> conflictingGoalIds;
  final String interferenceType;
  final double severity;
  final double probability;
  final String description;
  final List<String> rootCauses;
  final Map<String, double> resourceCompetition;
  final DateTime detectedAt;

  GoalInterference({
    required this.interferenceId,
    required this.conflictingGoalIds,
    required this.interferenceType,
    required this.severity,
    required this.probability,
    required this.description,
    required this.rootCauses,
    required this.resourceCompetition,
    required this.detectedAt,
  });
}

/// Goal resolution strategy
class GoalResolutionStrategy {
  final String strategyId;
  final String strategyType;
  final String description;
  final Map<String, dynamic> adjustments;
  final double expectedEffectiveness;
  final List<String> tradeoffs;
  final Map<String, double> goalImpacts;
  final List<String> implementationSteps;

  GoalResolutionStrategy({
    required this.strategyId,
    required this.strategyType,
    required this.description,
    required this.adjustments,
    required this.expectedEffectiveness,
    required this.tradeoffs,
    required this.goalImpacts,
    required this.implementationSteps,
  });
}

/// Goal optimization result
class GoalOptimizationResult {
  final List<FinancialGoal> optimizedGoals;
  final List<GoalInterference> detectedInterferences;
  final List<GoalResolutionStrategy> recommendedStrategies;
  final Map<String, double> resourceAllocation;
  final double overallFeasibilityScore;
  final List<String> warnings;
  final List<String> opportunities;

  GoalOptimizationResult({
    required this.optimizedGoals,
    required this.detectedInterferences,
    required this.recommendedStrategies,
    required this.resourceAllocation,
    required this.overallFeasibilityScore,
    required this.warnings,
    required this.opportunities,
  });
}

// Advanced Habit Recognition Models
class DetectedHabit {
  final String habitId;
  final String habitName;
  final String category;
  final double confidence;
  final double impactScore;
  final List<String> indicators;
  final List<String> evidenceTransactions;
  final Map<String, dynamic> parameters;
  final DateTime firstDetected;
  final DateTime lastObserved;
  final int observationCount;

  DetectedHabit({
    required this.habitId,
    required this.habitName,
    required this.category,
    required this.confidence,
    required this.impactScore,
    required this.indicators,
    required this.evidenceTransactions,
    required this.parameters,
    required this.firstDetected,
    required this.lastObserved,
    required this.observationCount,
  });
}

class HabitAnalysisResult {
  final List<DetectedHabit> detectedHabits;
  final Map<String, double> categoryRiskScores;
  final List<String> recommendations;
  final double overallHabitScore;
  final Map<String, dynamic> insights;

  HabitAnalysisResult({
    required this.detectedHabits,
    required this.categoryRiskScores,
    required this.recommendations,
    required this.overallHabitScore,
    required this.insights,
  });
}

class BehavioralCorrection {
  final String habitId;
  final String correctionType;
  final double budgetMultiplier;
  final double bufferMultiplier;
  final Map<String, double> categoryAdjustments;
  final List<String> interventions;
  final double expectedImpact;

  BehavioralCorrection({
    required this.habitId,
    required this.correctionType,
    required this.budgetMultiplier,
    required this.bufferMultiplier,
    required this.categoryAdjustments,
    required this.interventions,
    required this.expectedImpact,
  });
}

// Temporal Intelligence Models
class TemporalSpendingPattern {
  final Map<int, double> dayOfWeekMultipliers;
  final Map<int, double> dayOfMonthMultipliers;
  final Map<int, double> monthOfYearMultipliers;
  final Map<String, double> holidayMultipliers;
  final Map<String, double> seasonalMultipliers;
  final double paydayEffect;
  final double weekendEffect;
  final double monthEndEffect;
  final double confidenceScore;

  TemporalSpendingPattern({
    required this.dayOfWeekMultipliers,
    required this.dayOfMonthMultipliers,
    required this.monthOfYearMultipliers,
    required this.holidayMultipliers,
    required this.seasonalMultipliers,
    required this.paydayEffect,
    required this.weekendEffect,
    required this.monthEndEffect,
    required this.confidenceScore,
  });
}

class TemporalBudgetResult {
  final double baseDailyBudget;
  final double adjustedDailyBudget;
  final double temporalMultiplier;
  final String primaryReason;
  final List<String> contributingFactors;
  final double confidenceLevel;
  final Map<String, double> factorBreakdown;

  TemporalBudgetResult({
    required this.baseDailyBudget,
    required this.adjustedDailyBudget,
    required this.temporalMultiplier,
    required this.primaryReason,
    required this.contributingFactors,
    required this.confidenceLevel,
    required this.factorBreakdown,
  });
}

// Spending Velocity Models
class SpendingVelocityAnalysis {
  final double currentVelocity;
  final double normalVelocity;
  final double velocityRatio;
  final String velocityCategory;
  final double remainingBudgetOptimal;
  final double redistributionAmount;
  final List<String> insights;
  final double confidence;
  final Map<String, dynamic> metadata;

  SpendingVelocityAnalysis({
    required this.currentVelocity,
    required this.normalVelocity,
    required this.velocityRatio,
    required this.velocityCategory,
    required this.remainingBudgetOptimal,
    required this.redistributionAmount,
    required this.insights,
    required this.confidence,
    required this.metadata,
  });
}

class AdaptiveBudgetAllocation {
  final double originalDailyBudget;
  final double adjustedDailyBudget;
  final Map<DateTime, double> futureBudgetAllocations;
  final double totalRemainingBudget;
  final String allocationStrategy;
  final List<String> recommendations;
  final double systemConfidence;

  AdaptiveBudgetAllocation({
    required this.originalDailyBudget,
    required this.adjustedDailyBudget,
    required this.futureBudgetAllocations,
    required this.totalRemainingBudget,
    required this.allocationStrategy,
    required this.recommendations,
    required this.systemConfidence,
  });
}

// Contextual Nudge Service Models
enum NudgeType {
  lossAversion,
  socialProof,
  anchoring,
  mentalAccounting,
  commitmentDevice,
  scarcity,
  progressCelebration,
  impactFraming,
  freshStart,
  implementation,
}

enum NudgeContext {
  beforePurchase,
  afterPurchase,
  dailyCheckin,
  weeklyReview,
  goalSetting,
  budgetAlert,
  monthEnd,
  emergency,
}

class PersonalizedNudge {
  final String nudgeId;
  final NudgeType nudgeType;
  final NudgeContext context;
  final String message;
  final String actionText;
  final double expectedEffectiveness;
  final Map<String, dynamic> personalizedData;
  final DateTime createdAt;
  final DateTime? expiresAt;

  PersonalizedNudge({
    required this.nudgeId,
    required this.nudgeType,
    required this.context,
    required this.message,
    required this.actionText,
    required this.expectedEffectiveness,
    required this.personalizedData,
    required this.createdAt,
    this.expiresAt,
  });
}

class NudgeEffectivenessResult {
  final String nudgeId;
  final bool wasEffective;
  final double effectiveness;
  final Map<String, dynamic> metadata;
  final DateTime recordedAt;

  NudgeEffectivenessResult({
    required this.nudgeId,
    required this.wasEffective,
    required this.effectiveness,
    required this.metadata,
    required this.recordedAt,
  });
}

// Social Comparison Models
class UserDemographicProfile {
  final String userId;
  final IncomeTier incomeTier;
  final List<String> interests;
  final Map<String, dynamic> spendingPersonality;

  UserDemographicProfile({
    required this.userId,
    required this.incomeTier,
    required this.interests,
    required this.spendingPersonality,
  });
}

class SocialComparisonInsight {
  final String insightId;
  final String insightType;
  final String category;
  final double userValue;
  final double peerAverage;
  final double percentile;
  final String comparisonText;
  final String recommendation;
  final double confidenceLevel;
  final Map<String, dynamic> metadata;

  SocialComparisonInsight({
    required this.insightId,
    required this.insightType,
    required this.category,
    required this.userValue,
    required this.peerAverage,
    required this.percentile,
    required this.comparisonText,
    required this.recommendation,
    required this.confidenceLevel,
    required this.metadata,
  });
}

// Predictive Budget Service Models
class BudgetForecast {
  final double forecastedDailyBudget;
  final double confidence;
  final String primaryFactor;
  final Map<String, double> contributingFactors;
  final DateTime forecastDate;

  BudgetForecast({
    required this.forecastedDailyBudget,
    required this.confidence,
    required this.primaryFactor,
    required this.contributingFactors,
    required this.forecastDate,
  });
}

class PredictiveBudgetAnalysis {
  final List<BudgetForecast> forecasts;
  final Map<String, double> trendAnalysis;
  final List<String> riskWarnings;
  final double overallConfidence;

  PredictiveBudgetAnalysis({
    required this.forecasts,
    required this.trendAnalysis,
    required this.riskWarnings,
    required this.overallConfidence,
  });
}

// Explanation Engine Service Models
class BudgetExplanation {
  final String explanationId;
  final String primaryExplanation;
  final List<String> detailedSteps;
  final Map<String, dynamic> calculations;
  final List<String> assumptions;
  final String userLevel;

  BudgetExplanation({
    required this.explanationId,
    required this.primaryExplanation,
    required this.detailedSteps,
    required this.calculations,
    required this.assumptions,
    required this.userLevel,
  });
}

class ExplanationContext {
  final String userId;
  final String userLevel;
  final List<String> userInterests;
  final bool preferVisualExplanations;
  final bool preferDetailedMath;
  final String communicationStyle;

  ExplanationContext({
    required this.userId,
    required this.userLevel,
    required this.userInterests,
    required this.preferVisualExplanations,
    required this.preferDetailedMath,
    required this.communicationStyle,
  });
}

// Category Intelligence Models
class LifeEventDetection {
  final String eventId;
  final String eventType;
  final DateTime detectedAt;
  final double confidence;
  final List<String> indicators;
  final Map<String, double> categoryImpacts;
  final List<String> recommendedAdjustments;
  final Duration expectedDuration;

  LifeEventDetection({
    required this.eventId,
    required this.eventType,
    required this.detectedAt,
    required this.confidence,
    required this.indicators,
    required this.categoryImpacts,
    required this.recommendedAdjustments,
    required this.expectedDuration,
  });
}

// Enhanced Master Budget Models
class EnhancedBudgetResult {
  final double dailyBudget;
  final double confidence;
  final Map<String, dynamic> calculationBreakdown;
  final List<String> personalizedInsights;
  final List<String> recommendations;
  final Map<String, double> categoryAllocations;
  final double riskScore;
  final Map<String, dynamic> metadata;

  EnhancedBudgetResult({
    required this.dailyBudget,
    required this.confidence,
    required this.calculationBreakdown,
    required this.personalizedInsights,
    required this.recommendations,
    required this.categoryAllocations,
    required this.riskScore,
    required this.metadata,
  });

  // Additional properties for Master Budget Engine compatibility
  PersonalizedNudge? get suggestedNudge => null;
  BudgetForecast? get tomorrowForecast => null;
  BudgetExplanation get explanation => BudgetExplanation(
    explanationId: 'default',
    primaryExplanation: 'Budget calculated using enhanced algorithms',
    detailedSteps: [],
    calculations: {},
    assumptions: [],
    userLevel: 'intermediate',
  );
}

class BudgetIntelligenceResult {
  final EnhancedBudgetResult enhancedBudget;
  final List<PersonalizedNudge> recommendedNudges;
  final Map<String, dynamic> comprehensiveInsights;
  final PredictiveBudgetAnalysis futureProjections;

  BudgetIntelligenceResult({
    required this.enhancedBudget,
    required this.recommendedNudges,
    required this.comprehensiveInsights,
    required this.futureProjections,
  });
}