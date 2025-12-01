import 'dart:math';
import '../models/budget_intelligence_models.dart';
import 'income_service.dart' as legacy_income;
import 'onboarding_state.dart';
import 'logging_service.dart';

/// Enhanced production-ready budget service with advanced intelligence
/// Fully compatible with existing MITA infrastructure
class EnhancedBudgetService {
  static final EnhancedBudgetService _instance =
      EnhancedBudgetService._internal();
  factory EnhancedBudgetService() => _instance;
  EnhancedBudgetService._internal();

  final legacy_income.IncomeService _incomeService =
      legacy_income.IncomeService();

  /// Enhanced daily budget calculation with comprehensive intelligence
  Future<EnhancedBudgetCalculationResult> calculateEnhancedDailyBudget({
    required OnboardingState onboardingData,
    DateTime? targetDate,
    String? userId,
    List<Map<String, dynamic>>? transactionHistory,
    Map<String, dynamic>? userMetrics,
    bool enableAdvancedFeatures = true,
  }) async {
    try {
      logInfo('Starting enhanced budget calculation', tag: 'ENHANCED_BUDGET');

      final actualTargetDate = targetDate ?? DateTime.now();
      final actualUserId =
          userId ?? 'user_${DateTime.now().millisecondsSinceEpoch}';
      final actualTransactions = transactionHistory ?? [];
      final actualMetrics = userMetrics ?? {};

      // Step 1: Enhanced Income Classification
      final incomeClassification =
          await _performEnhancedIncomeClassification(onboardingData);

      // Step 2: Base Budget Calculation
      final baseBudgetResult =
          await _calculateBaseBudget(onboardingData, incomeClassification);

      // Step 3: Apply Intelligence Enhancements
      final enhancedResult = await _applyIntelligenceEnhancements(
        baseBudgetResult,
        onboardingData,
        actualTargetDate,
        actualTransactions,
        actualMetrics,
        enableAdvancedFeatures,
      );

      // Step 4: Generate Insights and Recommendations
      final insights = await _generatePersonalizedInsights(
        enhancedResult,
        onboardingData,
        actualTransactions,
        incomeClassification,
      );

      // Step 5: Calculate Risk Assessment
      final riskAssessment = _calculateRiskAssessment(
        enhancedResult,
        onboardingData,
        actualTransactions,
      );

      // Step 6: Generate Explanations
      final explanation = _generateBudgetExplanation(
        enhancedResult,
        onboardingData,
        incomeClassification,
        actualTargetDate,
      );

      logInfo('Enhanced budget calculation completed successfully',
          tag: 'ENHANCED_BUDGET');

      return EnhancedBudgetCalculationResult(
        // Core budget values
        dailyBudget: enhancedResult.adjustedDailyBudget,
        confidence: enhancedResult.confidence,

        // Enhanced intelligence
        insights: insights,
        riskScore: riskAssessment,
        explanation: explanation,

        // Metadata
        metadata: {
          'calculatedAt': DateTime.now().toIso8601String(),
          'targetDate': actualTargetDate.toIso8601String(),
          'userId': actualUserId,
          'advancedFeaturesEnabled': enableAdvancedFeatures,
          'dataQuality': _assessDataQuality(actualTransactions),
          'algorithmVersion': '2.0.0',
        },

        // Legacy compatibility
        legacyFormat: {
          'totalDailyBudget': enhancedResult.adjustedDailyBudget,
          'baseAmount': baseBudgetResult.baseAmount,
          'redistributionBuffer': enhancedResult.adjustedDailyBudget * 0.15,
          'fixedCommitments': baseBudgetResult.fixedCommitments,
          'savingsTarget': baseBudgetResult.savingsTarget,
          'confidence': enhancedResult.confidence,
          'methodology': 'enhanced_intelligence_v2',
        },
      );
    } catch (e) {
      logError('Error in enhanced budget calculation: $e',
          tag: 'ENHANCED_BUDGET');

      // Fallback to basic calculation
      return await _calculateFallbackBudget(onboardingData, targetDate);
    }
  }

  /// Enhanced income classification with smooth transitions
  Future<IncomeClassificationResult> _performEnhancedIncomeClassification(
    OnboardingState onboardingData,
  ) async {
    final monthlyIncome = onboardingData.income ?? 0.0;
    final legacyTier = _incomeService.classifyIncome(monthlyIncome);
    final baseTier = _convertLegacyTierToNew(legacyTier);

    // Check for transition zones (within 15% of tier boundaries)
    const tierBoundaries = [3000.0, 4500.0, 7000.0, 12000.0];
    const transitionZoneWidth = 0.15;

    for (int i = 0; i < tierBoundaries.length; i++) {
      final boundary = tierBoundaries[i];
      final lowerBound = boundary * (1.0 - transitionZoneWidth);
      final upperBound = boundary * (1.0 + transitionZoneWidth);

      if (monthlyIncome >= lowerBound && monthlyIncome <= upperBound) {
        // In transition zone
        final transitionFactor =
            (monthlyIncome - lowerBound) / (upperBound - lowerBound);
        final smoothFactor = _sigmoidTransition(transitionFactor);

        final lowerTier = _getTierByIndex(i);
        final upperTier = _getTierByIndex(i + 1);

        return IncomeClassificationResult(
          primaryTier: smoothFactor > 0.5 ? upperTier : lowerTier,
          secondaryTier: smoothFactor > 0.5 ? lowerTier : upperTier,
          primaryWeight: smoothFactor > 0.5 ? smoothFactor : 1.0 - smoothFactor,
          secondaryWeight:
              smoothFactor > 0.5 ? 1.0 - smoothFactor : smoothFactor,
          transitionFactor: smoothFactor,
          isInTransition: true,
          metadata: {
            'monthlyIncome': monthlyIncome,
            'boundary': boundary,
            'transitionZone': 'tier_${i}_to_${i + 1}',
          },
        );
      }
    }

    // Not in transition zone
    return IncomeClassificationResult(
      primaryTier: baseTier,
      primaryWeight: 1.0,
      secondaryWeight: 0.0,
      transitionFactor: 0.0,
      isInTransition: false,
      metadata: {
        'monthlyIncome': monthlyIncome,
        'solidTier': true,
      },
    );
  }

  /// Calculate base budget with enhanced parameters
  Future<BaseBudgetResult> _calculateBaseBudget(
    OnboardingState onboardingData,
    IncomeClassificationResult incomeClassification,
  ) async {
    final monthlyIncome = onboardingData.income ?? 0.0;

    // Get tier-specific ratios with blending if in transition
    final budgetRatios = _getBlendedBudgetRatios(incomeClassification);

    final fixedCommitments =
        monthlyIncome * budgetRatios['fixedCommitmentRatio']!;
    final savingsTarget = monthlyIncome * budgetRatios['savingsTargetRatio']!;
    final availableSpending = monthlyIncome - fixedCommitments - savingsTarget;
    final baseAmount = availableSpending / 30;

    return BaseBudgetResult(
      baseAmount: baseAmount,
      fixedCommitments: fixedCommitments,
      savingsTarget: savingsTarget,
      availableSpending: availableSpending,
      budgetRatios: budgetRatios,
    );
  }

  /// Apply intelligence enhancements to base budget
  Future<EnhancedBudgetResult> _applyIntelligenceEnhancements(
    BaseBudgetResult baseBudget,
    OnboardingState onboardingData,
    DateTime targetDate,
    List<Map<String, dynamic>> transactions,
    Map<String, dynamic> userMetrics,
    bool enableAdvancedFeatures,
  ) async {
    var adjustedBudget = baseBudget.baseAmount;
    var confidence = 0.8; // Base confidence
    final enhancements = <String>[];

    // Temporal Intelligence
    final temporalAdjustment =
        _calculateTemporalAdjustment(targetDate, transactions);
    adjustedBudget *= temporalAdjustment.multiplier;
    confidence *= temporalAdjustment.confidence;
    if (temporalAdjustment.reason.isNotEmpty) {
      enhancements.add(temporalAdjustment.reason);
    }

    // Goal-Based Adjustments
    if (onboardingData.goals.isNotEmpty) {
      final goalAdjustment = _calculateGoalAdjustments(onboardingData.goals);
      adjustedBudget *= goalAdjustment.multiplier;
      confidence *= goalAdjustment.confidence;
      enhancements.add(goalAdjustment.reason);
    }

    // Behavioral Habit Corrections
    if (onboardingData.habits.isNotEmpty) {
      final habitAdjustment = _calculateHabitAdjustments(onboardingData.habits);
      adjustedBudget *= habitAdjustment.multiplier;
      confidence *= habitAdjustment.confidence;
      enhancements.add(habitAdjustment.reason);
    }

    // Advanced features (if enabled and sufficient data)
    if (enableAdvancedFeatures && transactions.length >= 10) {
      // Spending velocity adjustment
      final velocityAdjustment =
          _calculateSpendingVelocityAdjustment(transactions);
      adjustedBudget *= velocityAdjustment.multiplier;
      confidence *= velocityAdjustment.confidence;
      if (velocityAdjustment.reason.isNotEmpty) {
        enhancements.add(velocityAdjustment.reason);
      }

      // Habit recognition
      final detectedHabits = _detectSpendingHabits(transactions);
      if (detectedHabits.isNotEmpty) {
        final habitCorrection = _calculateHabitCorrections(detectedHabits);
        adjustedBudget *= habitCorrection.multiplier;
        confidence *= habitCorrection.confidence;
        enhancements.add(habitCorrection.reason);
      }
    }

    return EnhancedBudgetResult(
      adjustedDailyBudget: adjustedBudget,
      confidence: confidence.clamp(0.0, 1.0),
      enhancements: enhancements,
      baseBudget: baseBudget,
    );
  }

  /// Generate personalized insights
  Future<List<String>> _generatePersonalizedInsights(
    EnhancedBudgetResult enhancedResult,
    OnboardingState onboardingData,
    List<Map<String, dynamic>> transactions,
    IncomeClassificationResult incomeClassification,
  ) async {
    final insights = <String>[];

    // Income tier insight
    if (incomeClassification.isInTransition) {
      insights.add(
          'Your income places you between ${incomeClassification.secondaryTier} and ${incomeClassification.primaryTier} tiers - budget optimized for both');
    } else {
      insights.add(
          'Your budget is optimized for ${incomeClassification.primaryTier} income tier');
    }

    // Budget adjustment insights
    final adjustmentPercentage = ((enhancedResult.adjustedDailyBudget /
                    enhancedResult.baseBudget.baseAmount -
                1.0) *
            100)
        .round();
    if (adjustmentPercentage.abs() > 5) {
      insights.add(
          'Your daily budget has been ${adjustmentPercentage > 0 ? 'increased' : 'decreased'} by ${adjustmentPercentage.abs()}% based on your patterns');
    }

    // Goal alignment insights
    if (onboardingData.goals.isNotEmpty) {
      insights.add(
          'Budget adjusted to support your goals: ${onboardingData.goals.join(', ')}');
    }

    // Confidence insights
    if (enhancedResult.confidence > 0.8) {
      insights.add('High confidence budget based on your financial profile');
    } else if (enhancedResult.confidence < 0.6) {
      insights.add(
          'Medium confidence - budget will improve as we learn your spending patterns');
    }

    // Transaction-based insights
    if (transactions.length >= 30) {
      insights.add(
          'Budget personalized using ${transactions.length} transaction patterns');
    }

    return insights.take(4).toList(); // Limit to top 4 insights
  }

  /// Calculate risk assessment
  double _calculateRiskAssessment(
    EnhancedBudgetResult enhancedResult,
    OnboardingState onboardingData,
    List<Map<String, dynamic>> transactions,
  ) {
    var riskScore = 0.0;

    // Income vs budget ratio risk
    final monthlyIncome = onboardingData.income ?? 0.0;
    final monthlyBudget = enhancedResult.adjustedDailyBudget * 30;
    final budgetRatio = monthlyBudget / monthlyIncome;

    if (budgetRatio > 0.6)
      riskScore += 0.3;
    else if (budgetRatio > 0.4) riskScore += 0.1;

    // Goal risk
    if (onboardingData.goals.length > 3) riskScore += 0.2;

    // Habit risk
    final riskHabits = ['impulse_buying', 'credit_dependency', 'no_budgeting'];
    final hasRiskHabits =
        onboardingData.habits.any((habit) => riskHabits.contains(habit));
    if (hasRiskHabits) riskScore += 0.3;

    // Confidence risk
    if (enhancedResult.confidence < 0.6) riskScore += 0.2;

    return riskScore.clamp(0.0, 1.0);
  }

  /// Generate budget explanation
  String _generateBudgetExplanation(
    EnhancedBudgetResult enhancedResult,
    OnboardingState onboardingData,
    IncomeClassificationResult incomeClassification,
    DateTime targetDate,
  ) {
    final monthlyIncome = onboardingData.income ?? 0.0;
    final spendingRatio = monthlyIncome > 0
        ? (enhancedResult.adjustedDailyBudget * 30) / monthlyIncome
        : 0.0;

    var explanation =
        'Your daily budget of \$${enhancedResult.adjustedDailyBudget.toStringAsFixed(0)} ';
    explanation +=
        'represents ${(spendingRatio * 100).toStringAsFixed(0)}% of your monthly income ';
    explanation +=
        'and is calculated using enhanced algorithms that consider your ';
    explanation += '${incomeClassification.primaryTier} income classification';

    if (incomeClassification.isInTransition) {
      explanation += ' (with smooth transition blending)';
    }

    explanation += ', financial goals, and spending patterns.';

    if (enhancedResult.enhancements.isNotEmpty) {
      explanation +=
          ' Key adjustments: ${enhancedResult.enhancements.join(', ')}.';
    }

    return explanation;
  }

  // Helper methods for calculations

  double _sigmoidTransition(double x) {
    return 1.0 / (1.0 + exp(-6.0 * (x - 0.5)));
  }

  IncomeTier _getTierByIndex(int index) {
    switch (index) {
      case 0:
        return IncomeTier.low;
      case 1:
        return IncomeTier.lowerMiddle;
      case 2:
        return IncomeTier.middle;
      case 3:
        return IncomeTier.upperMiddle;
      case 4:
        return IncomeTier.high;
      default:
        return IncomeTier.high;
    }
  }

  Map<String, double> _getBlendedBudgetRatios(
      IncomeClassificationResult classification) {
    if (!classification.isInTransition) {
      return _getBudgetRatiosForTier(classification.primaryTier);
    }

    // Blend ratios from both tiers
    final primaryRatios = _getBudgetRatiosForTier(classification.primaryTier);
    final secondaryRatios =
        _getBudgetRatiosForTier(classification.secondaryTier!);

    return {
      'fixedCommitmentRatio': primaryRatios['fixedCommitmentRatio']! *
              classification.primaryWeight +
          secondaryRatios['fixedCommitmentRatio']! *
              classification.secondaryWeight,
      'savingsTargetRatio':
          primaryRatios['savingsTargetRatio']! * classification.primaryWeight +
              secondaryRatios['savingsTargetRatio']! *
                  classification.secondaryWeight,
    };
  }

  IncomeTier _convertLegacyTierToNew(legacy_income.IncomeTier legacyTier) {
    switch (legacyTier) {
      case legacy_income.IncomeTier.low:
        return IncomeTier.low;
      case legacy_income.IncomeTier.lowerMiddle:
        return IncomeTier.lowerMiddle;
      case legacy_income.IncomeTier.middle:
        return IncomeTier.middle;
      case legacy_income.IncomeTier.upperMiddle:
        return IncomeTier.upperMiddle;
      case legacy_income.IncomeTier.high:
        return IncomeTier.high;
    }
  }

  Map<String, double> _getBudgetRatiosForTier(IncomeTier tier) {
    switch (tier) {
      case IncomeTier.low:
        return {'fixedCommitmentRatio': 0.65, 'savingsTargetRatio': 0.05};
      case IncomeTier.lowerMiddle:
        return {'fixedCommitmentRatio': 0.58, 'savingsTargetRatio': 0.08};
      case IncomeTier.middle:
        return {'fixedCommitmentRatio': 0.52, 'savingsTargetRatio': 0.15};
      case IncomeTier.upperMiddle:
        return {'fixedCommitmentRatio': 0.45, 'savingsTargetRatio': 0.22};
      case IncomeTier.high:
        return {'fixedCommitmentRatio': 0.40, 'savingsTargetRatio': 0.30};
    }
  }

  BudgetAdjustment _calculateTemporalAdjustment(
      DateTime targetDate, List<Map<String, dynamic>> transactions) {
    var multiplier = 1.0;
    var confidence = 1.0;
    var reason = '';

    // Weekend adjustment
    if (targetDate.weekday >= 6) {
      multiplier *= 1.15;
      reason = 'Weekend spending increase';
    }

    // Month-end adjustment
    if (targetDate.day > 25) {
      multiplier *= 0.85;
      reason = 'Month-end conservation';
    }

    // Holiday adjustment (basic)
    if (targetDate.month == 12 && targetDate.day > 20) {
      multiplier *= 1.3;
      reason = 'Holiday season increase';
    }

    return BudgetAdjustment(
      multiplier: multiplier,
      confidence: confidence,
      reason: reason,
    );
  }

  BudgetAdjustment _calculateGoalAdjustments(List<String> goals) {
    var multiplier = 1.0;
    var confidence = 1.0;
    var reason = '';

    if (goals.contains('save_more')) {
      multiplier *= 0.95; // 5% reduction for increased saving
      reason = 'Adjusted for savings goal';
    }

    if (goals.contains('pay_off_debt')) {
      multiplier *= 0.92; // 8% reduction for debt payment
      reason = 'Adjusted for debt payoff goal';
    }

    if (goals.contains('investing')) {
      multiplier *= 0.94; // 6% reduction for investing
      reason = 'Adjusted for investment goal';
    }

    return BudgetAdjustment(
      multiplier: multiplier,
      confidence: confidence,
      reason: reason,
    );
  }

  BudgetAdjustment _calculateHabitAdjustments(List<String> habits) {
    var multiplier = 1.0;
    var confidence = 1.0;
    var reason = '';

    if (habits.contains('impulse_buying')) {
      multiplier *= 0.85; // 15% reduction for impulse control
      reason = 'Adjusted for impulse buying habit';
    }

    if (habits.contains('no_budgeting')) {
      multiplier *= 0.90; // 10% reduction for budget awareness
      reason = 'Adjusted for budgeting habit development';
    }

    if (habits.contains('credit_dependency')) {
      multiplier *= 0.80; // 20% reduction for credit control
      reason = 'Adjusted for credit dependency';
    }

    return BudgetAdjustment(
      multiplier: multiplier,
      confidence: confidence,
      reason: reason,
    );
  }

  BudgetAdjustment _calculateSpendingVelocityAdjustment(
      List<Map<String, dynamic>> transactions) {
    if (transactions.length < 10) {
      return BudgetAdjustment(multiplier: 1.0, confidence: 1.0, reason: '');
    }

    // Calculate recent vs historical spending velocity
    final recentTransactions = transactions.take(7).toList();
    final recentTotal = recentTransactions.fold(
        0.0, (sum, t) => sum + ((t['amount'] as num?)?.toDouble() ?? 0.0));
    final recentAvg = recentTotal / 7;

    final historicalTotal = transactions.fold(
        0.0, (sum, t) => sum + ((t['amount'] as num?)?.toDouble() ?? 0.0));
    final historicalAvg = historicalTotal / transactions.length;

    if (historicalAvg > 0) {
      final velocityRatio = recentAvg / historicalAvg;

      if (velocityRatio > 1.5) {
        return BudgetAdjustment(
          multiplier: 0.85,
          confidence: 0.8,
          reason: 'High spending velocity detected',
        );
      } else if (velocityRatio < 0.6) {
        return BudgetAdjustment(
          multiplier: 1.15,
          confidence: 0.8,
          reason: 'Low spending velocity - budget increase',
        );
      }
    }

    return BudgetAdjustment(multiplier: 1.0, confidence: 1.0, reason: '');
  }

  List<String> _detectSpendingHabits(List<Map<String, dynamic>> transactions) {
    final habits = <String>[];

    // Simple impulse buying detection
    final largeTransactions = transactions
        .where((t) => ((t['amount'] as num?)?.toDouble() ?? 0.0) > 100)
        .length;
    if (largeTransactions > transactions.length * 0.2) {
      habits.add('impulse_buying');
    }

    // Weekend spending pattern
    final weekendTransactions = transactions.where((t) {
      final date = DateTime.parse(
          t['date']?.toString() ?? DateTime.now().toIso8601String());
      return date.weekday >= 6;
    }).length;

    if (weekendTransactions > transactions.length * 0.4) {
      habits.add('weekend_spending');
    }

    return habits;
  }

  BudgetAdjustment _calculateHabitCorrections(List<String> detectedHabits) {
    var multiplier = 1.0;
    var reason = '';

    if (detectedHabits.contains('impulse_buying')) {
      multiplier *= 0.9;
      reason = 'Impulse buying pattern detected';
    }

    if (detectedHabits.contains('weekend_spending')) {
      multiplier *= 0.95;
      reason = 'High weekend spending pattern';
    }

    return BudgetAdjustment(
      multiplier: multiplier,
      confidence: 0.7,
      reason: reason,
    );
  }

  double _assessDataQuality(List<Map<String, dynamic>> transactions) {
    if (transactions.isEmpty) return 0.0;
    if (transactions.length < 10) return 0.3;
    if (transactions.length < 30) return 0.6;
    if (transactions.length < 90) return 0.8;
    return 1.0;
  }

  /// Fallback calculation for error cases
  Future<EnhancedBudgetCalculationResult> _calculateFallbackBudget(
    OnboardingState onboardingData,
    DateTime? targetDate,
  ) async {
    final monthlyIncome = onboardingData.income ?? 0.0;
    final dailyBudget = (monthlyIncome * 0.3) / 30; // Simple 30% rule

    return EnhancedBudgetCalculationResult(
      dailyBudget: dailyBudget,
      confidence: 0.5,
      insights: ['Fallback calculation - basic 30% spending rule applied'],
      riskScore: 0.5,
      explanation:
          'Basic budget calculation using 30% of income for daily spending',
      metadata: {'fallback': true},
      legacyFormat: {
        'totalDailyBudget': dailyBudget,
        'baseAmount': dailyBudget,
        'redistributionBuffer': dailyBudget * 0.15,
        'fixedCommitments': monthlyIncome * 0.55,
        'savingsTarget': monthlyIncome * 0.15,
        'confidence': 0.5,
        'methodology': 'fallback',
      },
    );
  }
}

// Supporting data classes
class EnhancedBudgetCalculationResult {
  final double dailyBudget;
  final double confidence;
  final List<String> insights;
  final double riskScore;
  final String explanation;
  final Map<String, dynamic> metadata;
  final Map<String, dynamic> legacyFormat;

  EnhancedBudgetCalculationResult({
    required this.dailyBudget,
    required this.confidence,
    required this.insights,
    required this.riskScore,
    required this.explanation,
    required this.metadata,
    required this.legacyFormat,
  });
}

class BaseBudgetResult {
  final double baseAmount;
  final double fixedCommitments;
  final double savingsTarget;
  final double availableSpending;
  final Map<String, double> budgetRatios;

  BaseBudgetResult({
    required this.baseAmount,
    required this.fixedCommitments,
    required this.savingsTarget,
    required this.availableSpending,
    required this.budgetRatios,
  });
}

class EnhancedBudgetResult {
  final double adjustedDailyBudget;
  final double confidence;
  final List<String> enhancements;
  final BaseBudgetResult baseBudget;

  EnhancedBudgetResult({
    required this.adjustedDailyBudget,
    required this.confidence,
    required this.enhancements,
    required this.baseBudget,
  });
}

class BudgetAdjustment {
  final double multiplier;
  final double confidence;
  final String reason;

  BudgetAdjustment({
    required this.multiplier,
    required this.confidence,
    required this.reason,
  });
}
