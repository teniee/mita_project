import 'dart:math' as math;
import 'income_service.dart';
import 'onboarding_state.dart';
import 'logging_service.dart';

/// Production-level budget calculation engine for MITA
/// Replaces all hardcoded financial data with intelligent algorithms based on real user onboarding data
class ProductionBudgetEngine {
  static final ProductionBudgetEngine _instance = ProductionBudgetEngine._internal();
  factory ProductionBudgetEngine() => _instance;
  ProductionBudgetEngine._internal();

  final IncomeService _incomeService = IncomeService();

  // Regional cost-of-living multipliers (based on economic data)
  static const Map<String, double> _costOfLivingMultipliers = {
    // North America
    'US-CA': 1.45, // California
    'US-NY': 1.35, // New York
    'US-WA': 1.25, // Washington
    'US-MA': 1.30, // Massachusetts
    'US-TX': 0.95, // Texas
    'US-FL': 1.00, // Florida
    'US-IL': 1.05, // Illinois
    'CA': 1.15, // Canada

    // Europe
    'GB': 1.20, // United Kingdom
    'DE': 1.10, // Germany
    'FR': 1.15, // France
    'IT': 1.05, // Italy
    'ES': 0.95, // Spain
    'NL': 1.25, // Netherlands
    'CH': 1.60, // Switzerland
    'NO': 1.50, // Norway
    'SE': 1.20, // Sweden
    'DK': 1.30, // Denmark

    // Default
    'DEFAULT': 1.00,
  };

  /// Calculate personalized daily budget based on user's real onboarding data
  DailyBudgetCalculation calculateDailyBudget({
    required OnboardingState onboardingData,
    DateTime? targetDate,
  }) {
    try {
      logInfo('Calculating personalized daily budget from onboarding data', tag: 'BUDGET_ENGINE');

      // 1. Extract core financial data
      if (onboardingData.income == null || onboardingData.income! <= 0) {
        throw ArgumentError('Monthly income is required for budget calculations');
      }
      final monthlyIncome = onboardingData.income!;
      final incomeTier = onboardingData.incomeTier ?? _incomeService.classifyIncome(monthlyIncome);
      final expenses = onboardingData.expenses;
      final goals = onboardingData.goals;
      final habits = onboardingData.habits;

      // 2. Calculate base daily budget using MITA methodology
      final baseDaily = _calculateBaseDailyBudget(monthlyIncome, incomeTier);

      // 3. Apply user's actual fixed expenses
      final adjustedForExpenses = _adjustForFixedExpenses(baseDaily, expenses, monthlyIncome);

      // 4. Apply goal-based prioritization
      final goalAdjusted = _applyGoalBasedAdjustments(adjustedForExpenses, goals, monthlyIncome);

      // 5. Apply behavioral habit corrections
      final habitAdjusted = _applyHabitBasedCorrections(goalAdjusted, habits, incomeTier);

      // 6. Apply regional cost-of-living adjustments
      final locationAdjusted = _applyLocationAdjustments(
          habitAdjusted, onboardingData.countryCode, onboardingData.stateCode);

      // 7. Apply date-specific adjustments (weekends, paydays, etc.)
      final finalDaily = _applyDateSpecificAdjustments(
          locationAdjusted, targetDate ?? DateTime.now(), habits, incomeTier);

      logInfo('Daily budget calculated: \$${finalDaily.totalDailyBudget.toStringAsFixed(2)}',
          tag: 'BUDGET_ENGINE');

      return finalDaily;
    } catch (e) {
      logError('Error calculating daily budget: $e', tag: 'BUDGET_ENGINE', error: e);
      if (onboardingData.income == null || onboardingData.income! <= 0) {
        throw ArgumentError('Monthly income is required for fallback budget');
      }
      return _getFallbackDailyBudget(onboardingData.income!);
    }
  }

  /// Generate intelligent category budget allocations based on user data
  CategoryBudgetAllocation calculateCategoryBudgets({
    required OnboardingState onboardingData,
    required DailyBudgetCalculation dailyBudget,
  }) {
    try {
      logInfo('Calculating personalized category budgets', tag: 'BUDGET_ENGINE');

      if (onboardingData.income == null || onboardingData.income! <= 0) {
        throw ArgumentError('Monthly income is required for budget calculations');
      }
      final monthlyIncome = onboardingData.income!;
      final incomeTier = onboardingData.incomeTier ?? _incomeService.classifyIncome(monthlyIncome);
      final userExpenses = onboardingData.expenses;
      final goals = onboardingData.goals;
      final habits = onboardingData.habits;

      // 1. Get base category weights for income tier
      final baseWeights = _getIntelligentCategoryWeights(incomeTier, goals, habits);

      // 2. Incorporate user's actual expense categories
      final userAdjusted =
          _incorporateUserExpenseCategories(baseWeights, userExpenses, monthlyIncome);

      // 3. Apply goal-specific category priorities
      final goalOptimized = _optimizeCategoriesForGoals(userAdjusted, goals, monthlyIncome);

      // 4. Apply behavioral spending pattern adjustments
      final behaviorAdjusted = _adjustCategoriesForBehavior(goalOptimized, habits, incomeTier);

      // 5. Calculate daily amounts for each category
      final dailyAllocations = _convertToDailyAllocations(behaviorAdjusted, monthlyIncome);

      // 6. Generate spending recommendations and insights
      final insights =
          _generateCategoryInsights(dailyAllocations, userExpenses, goals, habits, incomeTier);

      return CategoryBudgetAllocation(
        dailyAllocations: dailyAllocations,
        monthlyAllocations: behaviorAdjusted,
        insights: insights,
        confidence: _calculateCategoryConfidence(userExpenses, goals),
        lastUpdated: DateTime.now(),
      );
    } catch (e) {
      logError('Error calculating category budgets: $e', tag: 'BUDGET_ENGINE', error: e);
      if (onboardingData.income == null || onboardingData.income! <= 0) {
        throw ArgumentError('Monthly income is required for category allocation');
      }
      return _getFallbackCategoryAllocation(onboardingData.income!);
    }
  }

  /// Create dynamic budget rules that adapt based on spending patterns
  DynamicBudgetRules generateDynamicRules({
    required OnboardingState onboardingData,
    required Map<String, double>? currentMonthSpending,
    required int daysIntoMonth,
  }) {
    try {
      final habits = onboardingData.habits;
      final goals = onboardingData.goals;
      if (onboardingData.income == null || onboardingData.income! <= 0) {
        throw ArgumentError('Monthly income is required for tier classification');
      }
      final incomeTier =
          onboardingData.incomeTier ?? _incomeService.classifyIncome(onboardingData.income!);

      final rules = <BudgetRule>[];

      // 1. Habit-aware spending limits
      rules.addAll(_generateHabitBasedRules(habits, incomeTier));

      // 2. Goal-oriented redistribution rules
      if (onboardingData.income == null || onboardingData.income! <= 0) {
        throw ArgumentError('Monthly income is required for goal-based rules');
      }
      rules.addAll(_generateGoalBasedRules(goals, onboardingData.income!));

      // 3. Mid-month adjustment rules
      if (currentMonthSpending != null && daysIntoMonth > 10) {
        rules.addAll(
            _generateMidMonthAdjustmentRules(currentMonthSpending, daysIntoMonth, onboardingData));
      }

      // 4. Emergency reallocation rules
      rules.addAll(_generateEmergencyReallocationRules(habits, incomeTier));

      // 5. Weekend/weekday spending rules
      rules.addAll(_generateTemporalSpendingRules(habits, incomeTier));

      return DynamicBudgetRules(
        rules: rules,
        adaptationFrequency: _getAdaptationFrequency(incomeTier),
        confidenceLevel: _calculateRuleConfidence(habits, goals),
        lastUpdated: DateTime.now(),
      );
    } catch (e) {
      logError('Error generating dynamic rules: $e', tag: 'BUDGET_ENGINE', error: e);
      return DynamicBudgetRules(
          rules: [],
          adaptationFrequency: AdaptationFrequency.weekly,
          confidenceLevel: 0.5,
          lastUpdated: DateTime.now());
    }
  }

  /// Generate personalized financial nudges and recommendations
  PersonalizationEngine createPersonalizationEngine({
    required OnboardingState onboardingData,
  }) {
    try {
      final goals = onboardingData.goals;
      final habits = onboardingData.habits;
      if (onboardingData.income == null || onboardingData.income! <= 0) {
        throw ArgumentError('Monthly income is required for tier classification');
      }
      final incomeTier =
          onboardingData.incomeTier ?? _incomeService.classifyIncome(onboardingData.income!);
      if (onboardingData.income == null || onboardingData.income! <= 0) {
        throw ArgumentError('Monthly income is required for budget calculations');
      }
      final monthlyIncome = onboardingData.income!;

      // 1. Generate goal-based nudges
      final goalNudges = _generateGoalBasedNudges(goals, monthlyIncome, incomeTier);

      // 2. Generate habit-breaking interventions
      final habitNudges = _generateHabitInterventions(habits, incomeTier);

      // 3. Generate income-tier specific strategies
      final tierStrategies = _generateIncomeTierStrategies(incomeTier, monthlyIncome);

      // 4. Generate behavioral economics nudges
      final behavioralNudges = _generateBehavioralNudges(habits, goals, incomeTier);

      // 5. Create personalized success metrics
      final successMetrics = _createPersonalizedMetrics(goals, habits, monthlyIncome);

      return PersonalizationEngine(
        goalNudges: goalNudges,
        habitInterventions: habitNudges,
        tierStrategies: tierStrategies,
        behavioralNudges: behavioralNudges,
        successMetrics: successMetrics,
        personalityProfile: _generatePersonalityProfile(habits, goals, incomeTier),
        lastUpdated: DateTime.now(),
      );
    } catch (e) {
      logError('Error creating personalization engine: $e', tag: 'BUDGET_ENGINE', error: e);
      return PersonalizationEngine(
        goalNudges: [],
        habitInterventions: [],
        tierStrategies: [],
        behavioralNudges: [],
        successMetrics: [],
        personalityProfile: PersonalityProfile.balanced,
        lastUpdated: DateTime.now(),
      );
    }
  }

  // ============================================================================
  // CORE CALCULATION METHODS
  // ============================================================================

  /// Calculate base daily budget using MITA's methodology
  DailyBudgetCalculation _calculateBaseDailyBudget(double monthlyIncome, IncomeTier tier) {
    // MITA's daily budget model: Focus on available spending after fixed commitments
    final fixedCommitmentRatio = _getFixedCommitmentRatio(tier);
    final savingsTargetRatio = _getSavingsTargetRatio(tier);

    // Calculate available daily spending
    final availableForSpending = monthlyIncome * (1.0 - fixedCommitmentRatio - savingsTargetRatio);
    final dailyBudget = availableForSpending / 30.0; // 30-day average

    // Calculate redistribution buffer (MITA's flexible budgeting)
    final redistributionBuffer = dailyBudget * 0.15; // 15% flexibility

    return DailyBudgetCalculation(
      totalDailyBudget: dailyBudget,
      baseAmount: dailyBudget - redistributionBuffer,
      redistributionBuffer: redistributionBuffer,
      fixedCommitments: monthlyIncome * fixedCommitmentRatio / 30.0,
      savingsTarget: monthlyIncome * savingsTargetRatio / 30.0,
      confidence: 0.9,
      methodology: 'MITA Daily Budget Model',
    );
  }

  /// Apply user's actual fixed expenses to budget calculation
  DailyBudgetCalculation _adjustForFixedExpenses(DailyBudgetCalculation baseDaily,
      List<Map<String, dynamic>> userExpenses, double monthlyIncome) {
    if (userExpenses.isEmpty) return baseDaily;

    // Calculate actual fixed expenses from user data
    double totalFixed = 0.0;
    final fixedCategories = [
      'housing',
      'rent',
      'mortgage',
      'insurance',
      'utilities',
      'subscriptions'
    ];

    for (final expense in userExpenses) {
      final category = expense['category']?.toString().toLowerCase() ?? '';
      final amount = (expense['amount'] as num?)?.toDouble() ?? 0.0;

      if (fixedCategories.any((fixed) => category.contains(fixed))) {
        totalFixed += amount;
      }
    }

    // Adjust available spending based on actual fixed expenses
    final actualFixedDaily = totalFixed / 30.0;
    final adjustedAvailable = (monthlyIncome / 30.0) - actualFixedDaily - baseDaily.savingsTarget;

    return DailyBudgetCalculation(
      totalDailyBudget:
          math.max(adjustedAvailable, baseDaily.totalDailyBudget * 0.5), // Minimum safety
      baseAmount: math.max(adjustedAvailable * 0.85, baseDaily.baseAmount * 0.5),
      redistributionBuffer: math.max(adjustedAvailable * 0.15, 10.0), // Minimum $10 buffer
      fixedCommitments: actualFixedDaily,
      savingsTarget: baseDaily.savingsTarget,
      confidence: 0.95, // Higher confidence with real data
      methodology: 'User-Adjusted MITA Model',
    );
  }

  /// Apply goal-based budget prioritization
  DailyBudgetCalculation _applyGoalBasedAdjustments(
      DailyBudgetCalculation baseDaily, List<String> goals, double monthlyIncome) {
    if (goals.isEmpty) return baseDaily;

    double savingsBoost = 0.0;
    double spendingReduction = 0.0;

    // Apply goal-specific adjustments
    for (final goal in goals) {
      switch (goal.toLowerCase()) {
        case 'save_more':
          savingsBoost += monthlyIncome * 0.05 / 30.0; // Extra 5% to savings
          spendingReduction += monthlyIncome * 0.05 / 30.0;
          break;
        case 'pay_off_debt':
          savingsBoost += monthlyIncome * 0.08 / 30.0; // Extra 8% to debt payments
          spendingReduction += monthlyIncome * 0.08 / 30.0;
          break;
        case 'investing':
          savingsBoost += monthlyIncome * 0.06 / 30.0; // Extra 6% to investments
          spendingReduction += monthlyIncome * 0.06 / 30.0;
          break;
        case 'budgeting':
          // Increase awareness, slight spending reduction
          spendingReduction += monthlyIncome * 0.03 / 30.0;
          break;
      }
    }

    return DailyBudgetCalculation(
      totalDailyBudget: math.max(
          baseDaily.totalDailyBudget - spendingReduction, baseDaily.totalDailyBudget * 0.6),
      baseAmount: math.max(baseDaily.baseAmount - spendingReduction, baseDaily.baseAmount * 0.6),
      redistributionBuffer: baseDaily.redistributionBuffer,
      fixedCommitments: baseDaily.fixedCommitments,
      savingsTarget: baseDaily.savingsTarget + savingsBoost,
      confidence: 0.9,
      methodology: 'Goal-Optimized MITA Model',
    );
  }

  /// Apply behavioral habit corrections
  DailyBudgetCalculation _applyHabitBasedCorrections(
      DailyBudgetCalculation baseDaily, List<String> habits, IncomeTier tier) {
    if (habits.isEmpty) return baseDaily;

    double spendingMultiplier = 1.0;
    double bufferMultiplier = 1.0;

    // Apply habit-specific corrections
    for (final habit in habits) {
      switch (habit.toLowerCase()) {
        case 'impulse_buying':
          spendingMultiplier *= 0.85; // Reduce by 15% to account for impulse spending
          bufferMultiplier *= 1.3; // Increase buffer for flexibility
          break;
        case 'no_budgeting':
          spendingMultiplier *= 0.9; // Conservative start
          bufferMultiplier *= 1.2;
          break;
        case 'forgot_subscriptions':
          spendingMultiplier *= 0.95; // Slight reduction for forgotten costs
          break;
        case 'credit_dependency':
          spendingMultiplier *= 0.8; // Significant reduction to break cycle
          bufferMultiplier *= 1.4;
          break;
      }
    }

    return DailyBudgetCalculation(
      totalDailyBudget: baseDaily.totalDailyBudget * spendingMultiplier,
      baseAmount: baseDaily.baseAmount * spendingMultiplier,
      redistributionBuffer: baseDaily.redistributionBuffer * bufferMultiplier,
      fixedCommitments: baseDaily.fixedCommitments,
      savingsTarget: baseDaily.savingsTarget,
      confidence: 0.85, // Lower confidence due to behavioral unpredictability
      methodology: 'Habit-Aware MITA Model',
    );
  }

  /// Apply regional cost-of-living adjustments
  DailyBudgetCalculation _applyLocationAdjustments(
      DailyBudgetCalculation baseDaily, String? countryCode, String? stateCode) {
    if (countryCode == null) return baseDaily;

    // Get location-specific multiplier
    final locationKey = stateCode != null ? '$countryCode-$stateCode' : countryCode;
    final multiplier =
        _costOfLivingMultipliers[locationKey] ?? _costOfLivingMultipliers['DEFAULT']!;

    // Adjust spending categories that are affected by location
    const locationSensitiveRatio = 0.7; // 70% of spending is location-sensitive
    final adjustedBase = baseDaily.baseAmount * (1.0 + (multiplier - 1.0) * locationSensitiveRatio);
    final adjustedTotal =
        baseDaily.totalDailyBudget * (1.0 + (multiplier - 1.0) * locationSensitiveRatio);

    return DailyBudgetCalculation(
      totalDailyBudget: adjustedTotal,
      baseAmount: adjustedBase,
      redistributionBuffer: baseDaily.redistributionBuffer,
      fixedCommitments: baseDaily.fixedCommitments * multiplier,
      savingsTarget: baseDaily.savingsTarget, // Savings target unchanged
      confidence: 0.85,
      methodology: 'Location-Adjusted MITA Model',
    );
  }

  /// Apply date-specific adjustments (weekends, paydays, etc.)
  DailyBudgetCalculation _applyDateSpecificAdjustments(
      DailyBudgetCalculation baseDaily, DateTime targetDate, List<String> habits, IncomeTier tier) {
    double dateMultiplier = 1.0;

    // Weekend adjustment
    final isWeekend = targetDate.weekday >= 6;
    if (isWeekend) {
      dateMultiplier *= 1.2; // 20% more for weekend spending
    }

    // Payday adjustment (assume bi-weekly)
    final dayOfMonth = targetDate.day;
    final isPayday = dayOfMonth == 1 || dayOfMonth == 15;
    if (isPayday && habits.contains('impulse_buying')) {
      dateMultiplier *= 0.9; // Reduce payday spending for impulse buyers
    }

    // Month-end tightening
    if (dayOfMonth > 25) {
      dateMultiplier *= 0.85; // Tighten budget near month-end
    }

    return DailyBudgetCalculation(
      totalDailyBudget: baseDaily.totalDailyBudget * dateMultiplier,
      baseAmount: baseDaily.baseAmount * dateMultiplier,
      redistributionBuffer: baseDaily.redistributionBuffer,
      fixedCommitments: baseDaily.fixedCommitments,
      savingsTarget: baseDaily.savingsTarget,
      confidence: 0.8,
      methodology: 'Date-Optimized MITA Model',
    );
  }

  // ============================================================================
  // CATEGORY BUDGET CALCULATION METHODS
  // ============================================================================

  /// Get intelligent category weights based on income tier, goals, and habits
  Map<String, double> _getIntelligentCategoryWeights(
      IncomeTier tier, List<String> goals, List<String> habits) {
    // Start with base weights from income service
    final baseWeights = _incomeService.getDefaultBudgetWeights(tier);
    final adjustedWeights = Map<String, double>.from(baseWeights);

    // Apply goal-based adjustments
    for (final goal in goals) {
      switch (goal.toLowerCase()) {
        case 'save_more':
          adjustedWeights['savings'] = (adjustedWeights['savings'] ?? 0.1) * 1.3;
          adjustedWeights['entertainment'] = (adjustedWeights['entertainment'] ?? 0.1) * 0.8;
          break;
        case 'pay_off_debt':
          adjustedWeights['debt'] = (adjustedWeights['debt'] ?? 0.05) + 0.08;
          adjustedWeights['entertainment'] = (adjustedWeights['entertainment'] ?? 0.1) * 0.7;
          break;
        case 'investing':
          adjustedWeights['investments'] = (adjustedWeights['investments'] ?? 0.05) + 0.06;
          adjustedWeights['shopping'] = (adjustedWeights['shopping'] ?? 0.1) * 0.85;
          break;
      }
    }

    // Apply habit-based adjustments
    for (final habit in habits) {
      switch (habit.toLowerCase()) {
        case 'impulse_buying':
          adjustedWeights['entertainment'] = (adjustedWeights['entertainment'] ?? 0.1) * 0.8;
          adjustedWeights['shopping'] = (adjustedWeights['shopping'] ?? 0.1) * 0.75;
          adjustedWeights['savings'] = (adjustedWeights['savings'] ?? 0.1) * 1.15;
          break;
        case 'forgot_subscriptions':
          adjustedWeights['subscriptions'] = (adjustedWeights['subscriptions'] ?? 0.03) + 0.02;
          break;
        case 'credit_dependency':
          adjustedWeights['debt'] = (adjustedWeights['debt'] ?? 0.05) + 0.10;
          adjustedWeights['entertainment'] = (adjustedWeights['entertainment'] ?? 0.1) * 0.6;
          break;
      }
    }

    return _normalizeWeights(adjustedWeights);
  }

  /// Incorporate user's actual expense categories
  Map<String, double> _incorporateUserExpenseCategories(Map<String, double> baseWeights,
      List<Map<String, dynamic>> userExpenses, double monthlyIncome) {
    if (userExpenses.isEmpty) return baseWeights;

    // Calculate actual spending by category
    final userCategorySpending = <String, double>{};
    double totalUserSpending = 0.0;

    for (final expense in userExpenses) {
      final category = expense['category']?.toString().toLowerCase() ?? 'other';
      final amount = (expense['amount'] as num?)?.toDouble() ?? 0.0;
      userCategorySpending[category] = (userCategorySpending[category] ?? 0.0) + amount;
      totalUserSpending += amount;
    }

    if (totalUserSpending == 0) return baseWeights;

    // Blend user's actual patterns with recommended weights (70% user, 30% recommended)
    final blendedWeights = <String, double>{};

    // First, add all user categories with their actual weights
    userCategorySpending.forEach((category, amount) {
      final userWeight = amount / monthlyIncome;
      final recommendedWeight = baseWeights[category] ?? 0.0;
      blendedWeights[category] = (userWeight * 0.7) + (recommendedWeight * 0.3);
    });

    // Then add recommended categories that user doesn't have
    baseWeights.forEach((category, weight) {
      if (!blendedWeights.containsKey(category)) {
        blendedWeights[category] = weight * 0.3; // Reduced weight for missing categories
      }
    });

    return _normalizeWeights(blendedWeights);
  }

  /// Optimize category allocations for specific goals
  Map<String, double> _optimizeCategoriesForGoals(
      Map<String, double> baseWeights, List<String> goals, double monthlyIncome) {
    if (goals.isEmpty) return baseWeights;

    final optimized = Map<String, double>.from(baseWeights);

    for (final goal in goals) {
      switch (goal.toLowerCase()) {
        case 'save_more':
          _redistributeToCategory(optimized, 'savings', 0.05);
          break;
        case 'pay_off_debt':
          _redistributeToCategory(optimized, 'debt', 0.08);
          break;
        case 'investing':
          _redistributeToCategory(optimized, 'investments', 0.06);
          break;
        case 'budgeting':
          // Encourage more conscious food and transportation spending
          _redistributeFromCategories(optimized, ['entertainment', 'shopping'], 0.03);
          break;
      }
    }

    return _normalizeWeights(optimized);
  }

  /// Adjust categories based on behavioral patterns
  Map<String, double> _adjustCategoriesForBehavior(
      Map<String, double> baseWeights, List<String> habits, IncomeTier tier) {
    if (habits.isEmpty) return baseWeights;

    final adjusted = Map<String, double>.from(baseWeights);

    for (final habit in habits) {
      switch (habit.toLowerCase()) {
        case 'impulse_buying':
          // Reduce discretionary spending categories
          adjusted['entertainment'] = (adjusted['entertainment'] ?? 0.0) * 0.8;
          adjusted['shopping'] = (adjusted['shopping'] ?? 0.0) * 0.75;
          adjusted['miscellaneous'] = (adjusted['miscellaneous'] ?? 0.0) * 0.7;
          break;
        case 'no_budgeting':
          // Conservative adjustments across all categories
          adjusted.updateAll((key, value) => key == 'savings' ? value * 1.1 : value * 0.95);
          break;
        case 'credit_dependency':
          // Aggressive debt reduction focus
          adjusted['debt'] = (adjusted['debt'] ?? 0.0) + 0.12;
          adjusted['entertainment'] = (adjusted['entertainment'] ?? 0.0) * 0.6;
          adjusted['shopping'] = (adjusted['shopping'] ?? 0.0) * 0.5;
          break;
        case 'forgot_subscriptions':
          // Add explicit subscription tracking
          adjusted['subscriptions'] = (adjusted['subscriptions'] ?? 0.0) + 0.025;
          break;
      }
    }

    return _normalizeWeights(adjusted);
  }

  // ============================================================================
  // HELPER METHODS
  // ============================================================================

  /// Get fixed commitment ratio based on income tier
  double _getFixedCommitmentRatio(IncomeTier tier) {
    switch (tier) {
      case IncomeTier.low:
        return 0.65; // Higher fixed costs as % of income
      case IncomeTier.lowerMiddle:
        return 0.58;
      case IncomeTier.middle:
        return 0.52;
      case IncomeTier.upperMiddle:
        return 0.45;
      case IncomeTier.high:
        return 0.40; // More flexibility at higher incomes
    }
  }

  /// Get savings target ratio based on income tier
  double _getSavingsTargetRatio(IncomeTier tier) {
    switch (tier) {
      case IncomeTier.low:
        return 0.05; // 5% savings rate
      case IncomeTier.lowerMiddle:
        return 0.08; // 8% savings rate
      case IncomeTier.middle:
        return 0.15; // 15% savings rate
      case IncomeTier.upperMiddle:
        return 0.22; // 22% savings rate
      case IncomeTier.high:
        return 0.30; // 30% savings rate
    }
  }

  /// Normalize category weights to sum to 1.0
  Map<String, double> _normalizeWeights(Map<String, double> weights) {
    final total = weights.values.fold(0.0, (sum, weight) => sum + weight);
    if (total <= 0) return weights;

    // Don't normalize if already close to 1.0, just return the weights as monetary amounts
    if (total > 10.0) {
      // These are monetary amounts, not weights
      return weights;
    }

    return weights.map((key, value) => MapEntry(key, value / total));
  }

  /// Convert monthly allocations to daily amounts
  Map<String, double> _convertToDailyAllocations(
      Map<String, double> monthlyWeights, double monthlyIncome) {
    return monthlyWeights
        .map((category, weight) => MapEntry(category, (monthlyIncome * weight) / 30.0));
  }

  /// Redistribute weight to a specific category
  void _redistributeToCategory(Map<String, double> weights, String targetCategory, double amount) {
    final donorCategories = ['entertainment', 'shopping', 'miscellaneous'];
    final totalDonor = donorCategories.fold(0.0, (sum, cat) => sum + (weights[cat] ?? 0.0));

    if (totalDonor > amount) {
      // Proportionally reduce donor categories
      for (final donor in donorCategories) {
        final currentWeight = weights[donor] ?? 0.0;
        if (currentWeight > 0) {
          final reduction = (currentWeight / totalDonor) * amount;
          weights[donor] = currentWeight - reduction;
        }
      }
      weights[targetCategory] = (weights[targetCategory] ?? 0.0) + amount;
    }
  }

  /// Redistribute weight from multiple categories
  void _redistributeFromCategories(
      Map<String, double> weights, List<String> fromCategories, double amount) {
    final totalFrom = fromCategories.fold(0.0, (sum, cat) => sum + (weights[cat] ?? 0.0));

    if (totalFrom > amount) {
      for (final category in fromCategories) {
        final currentWeight = weights[category] ?? 0.0;
        if (currentWeight > 0) {
          final reduction = (currentWeight / totalFrom) * amount;
          weights[category] = currentWeight - reduction;
        }
      }
    }
  }

  /// Generate category insights and recommendations
  List<CategoryInsight> _generateCategoryInsights(
      Map<String, double> dailyAllocations,
      List<Map<String, dynamic>> userExpenses,
      List<String> goals,
      List<String> habits,
      IncomeTier tier) {
    final insights = <CategoryInsight>[];

    // Add goal-specific insights
    if (goals.contains('save_more')) {
      insights.add(CategoryInsight(
        category: 'savings',
        message: 'Your savings rate is optimized for your goal. Consider automating transfers.',
        type: InsightType.opportunity,
        priority: InsightPriority.high,
        actionable: true,
      ));
    }

    // Add habit-specific insights
    if (habits.contains('impulse_buying')) {
      insights.add(CategoryInsight(
        category: 'entertainment',
        message: 'Budget reduced to account for impulse purchases. Use the 24-hour rule.',
        type: InsightType.warning,
        priority: InsightPriority.medium,
        actionable: true,
      ));
    }

    // Add tier-specific insights
    final tierName = _incomeService.getIncomeTierName(tier);
    insights.add(CategoryInsight(
      category: 'general',
      message: 'As a $tierName, focus on ${_getTierFocusArea(tier)}',
      type: InsightType.information,
      priority: InsightPriority.medium,
      actionable: false,
    ));

    return insights;
  }

  String _getTierFocusArea(IncomeTier tier) {
    switch (tier) {
      case IncomeTier.low:
        return 'building emergency fund and reducing expenses';
      case IncomeTier.lowerMiddle:
        return 'consistent saving habits and skill development';
      case IncomeTier.middle:
        return 'investment growth and homeownership preparation';
      case IncomeTier.upperMiddle:
        return 'tax optimization and diversified investments';
      case IncomeTier.high:
        return 'wealth preservation and generational planning';
    }
  }

  /// Calculate confidence level for category allocations
  double _calculateCategoryConfidence(List<Map<String, dynamic>> userExpenses, List<String> goals) {
    double confidence = 0.5; // Base confidence

    // Increase confidence with more expense data
    if (userExpenses.length >= 5) confidence += 0.2;
    if (userExpenses.length >= 10) confidence += 0.1;

    // Increase confidence with clear goals
    if (goals.isNotEmpty) confidence += 0.1;
    if (goals.length >= 2) confidence += 0.1;

    return math.min(confidence, 1.0);
  }

  // ============================================================================
  // DYNAMIC RULES GENERATION METHODS
  // ============================================================================

  List<BudgetRule> _generateHabitBasedRules(List<String> habits, IncomeTier tier) {
    final rules = <BudgetRule>[];

    for (final habit in habits) {
      switch (habit.toLowerCase()) {
        case 'impulse_buying':
          rules.add(BudgetRule(
            id: 'impulse_protection',
            description: 'Impulse purchase protection',
            condition: 'spending_velocity > 1.5 in entertainment or shopping',
            action: 'reduce_daily_budget_by_20_percent',
            priority: RulePriority.high,
            frequency: RuleFrequency.daily,
          ));
          break;
        case 'no_budgeting':
          rules.add(BudgetRule(
            id: 'budget_awareness',
            description: 'Budget awareness reminder',
            condition: 'daily_spending > 80_percent_of_budget',
            action: 'send_warning_notification',
            priority: RulePriority.medium,
            frequency: RuleFrequency.daily,
          ));
          break;
        case 'credit_dependency':
          rules.add(BudgetRule(
            id: 'credit_limit',
            description: 'Credit usage limitation',
            condition: 'weekly_spending > weekly_budget',
            action: 'suggest_cash_only_mode',
            priority: RulePriority.high,
            frequency: RuleFrequency.weekly,
          ));
          break;
      }
    }

    return rules;
  }

  List<BudgetRule> _generateGoalBasedRules(List<String> goals, double monthlyIncome) {
    final rules = <BudgetRule>[];

    for (final goal in goals) {
      switch (goal.toLowerCase()) {
        case 'save_more':
          rules.add(BudgetRule(
            id: 'savings_protection',
            description: 'Protect savings target',
            condition: 'monthly_savings < target_savings_amount',
            action: 'redistribute_from_discretionary_spending',
            priority: RulePriority.high,
            frequency: RuleFrequency.weekly,
          ));
          break;
        case 'pay_off_debt':
          rules.add(BudgetRule(
            id: 'debt_priority',
            description: 'Prioritize debt payments',
            condition: 'debt_payment < minimum_target',
            action: 'reallocate_entertainment_to_debt',
            priority: RulePriority.critical,
            frequency: RuleFrequency.weekly,
          ));
          break;
      }
    }

    return rules;
  }

  List<BudgetRule> _generateMidMonthAdjustmentRules(
      Map<String, double> currentSpending, int daysIntoMonth, OnboardingState onboardingData) {
    final rules = <BudgetRule>[];
    if (onboardingData.income == null || onboardingData.income! <= 0) {
      throw ArgumentError('Monthly income is required for personalization');
    }
    final monthlyIncome = onboardingData.income!;

    // Calculate spending velocity
    final expectedSpending =
        (monthlyIncome * 0.7) * (daysIntoMonth / 30.0); // Expected 70% spending
    final actualSpending = currentSpending.values.fold(0.0, (sum, amount) => sum + amount);

    if (actualSpending > expectedSpending * 1.2) {
      rules.add(BudgetRule(
        id: 'overspending_correction',
        description: 'Mid-month overspending correction',
        condition: 'current_spending > 120_percent_expected',
        action: 'reduce_remaining_budget_by_25_percent',
        priority: RulePriority.high,
        frequency: RuleFrequency.immediate,
      ));
    }

    return rules;
  }

  List<BudgetRule> _generateEmergencyReallocationRules(List<String> habits, IncomeTier tier) {
    final rules = <BudgetRule>[];

    rules.add(BudgetRule(
      id: 'emergency_reallocation',
      description: 'Emergency expense reallocation',
      condition: 'emergency_expense_detected',
      action: 'reallocate_from_non_essential_categories',
      priority: RulePriority.critical,
      frequency: RuleFrequency.immediate,
    ));

    return rules;
  }

  List<BudgetRule> _generateTemporalSpendingRules(List<String> habits, IncomeTier tier) {
    final rules = <BudgetRule>[];

    rules.add(BudgetRule(
      id: 'weekend_adjustment',
      description: 'Weekend spending adjustment',
      condition: 'day_of_week in [saturday, sunday]',
      action: 'increase_entertainment_budget_by_20_percent',
      priority: RulePriority.low,
      frequency: RuleFrequency.weekly,
    ));

    rules.add(BudgetRule(
      id: 'month_end_tightening',
      description: 'Month-end budget tightening',
      condition: 'days_remaining_in_month < 5',
      action: 'reduce_discretionary_spending_by_30_percent',
      priority: RulePriority.medium,
      frequency: RuleFrequency.daily,
    ));

    return rules;
  }

  AdaptationFrequency _getAdaptationFrequency(IncomeTier tier) {
    switch (tier) {
      case IncomeTier.low:
      case IncomeTier.lowerMiddle:
        return AdaptationFrequency.daily; // More frequent adjustments needed
      case IncomeTier.middle:
        return AdaptationFrequency.weekly;
      case IncomeTier.upperMiddle:
      case IncomeTier.high:
        return AdaptationFrequency.monthly; // More stable, less frequent adjustments
    }
  }

  double _calculateRuleConfidence(List<String> habits, List<String> goals) {
    double confidence = 0.6; // Base confidence

    if (habits.isNotEmpty) confidence += 0.2;
    if (goals.isNotEmpty) confidence += 0.2;

    return math.min(confidence, 1.0);
  }

  // ============================================================================
  // PERSONALIZATION ENGINE METHODS
  // ============================================================================

  List<GoalNudge> _generateGoalBasedNudges(
      List<String> goals, double monthlyIncome, IncomeTier tier) {
    final nudges = <GoalNudge>[];

    for (final goal in goals) {
      switch (goal.toLowerCase()) {
        case 'save_more':
          nudges.add(GoalNudge(
            goal: 'save_more',
            message:
                'You\'re on track! Consider automating an extra \$${(monthlyIncome * 0.02).toStringAsFixed(0)} to savings.',
            frequency: NudgeFrequency.weekly,
            effectiveness: 0.85,
          ));
          break;
        case 'pay_off_debt':
          nudges.add(GoalNudge(
            goal: 'pay_off_debt',
            message: 'Every extra payment saves you interest. Try the debt avalanche method.',
            frequency: NudgeFrequency.daily,
            effectiveness: 0.9,
          ));
          break;
      }
    }

    return nudges;
  }

  List<HabitIntervention> _generateHabitInterventions(List<String> habits, IncomeTier tier) {
    final interventions = <HabitIntervention>[];

    for (final habit in habits) {
      switch (habit.toLowerCase()) {
        case 'impulse_buying':
          interventions.add(HabitIntervention(
            habit: 'impulse_buying',
            intervention:
                'Use the 24-hour rule: Wait a full day before non-essential purchases over \$50.',
            type: InterventionType.delayTactic,
            effectiveness: 0.8,
          ));
          break;
        case 'credit_dependency':
          interventions.add(HabitIntervention(
            habit: 'credit_dependency',
            intervention: 'Try a cash-only week for discretionary spending to build awareness.',
            type: InterventionType.behaviorReplacement,
            effectiveness: 0.9,
          ));
          break;
      }
    }

    return interventions;
  }

  List<TierStrategy> _generateIncomeTierStrategies(IncomeTier tier, double monthlyIncome) {
    final strategies = <TierStrategy>[];

    switch (tier) {
      case IncomeTier.low:
        strategies.add(TierStrategy(
          tier: tier,
          strategy: 'Focus on the 50/30/20 rule and build a \$500 emergency fund first.',
          priority: StrategyPriority.critical,
          timeframe: 'immediate',
        ));
        break;
      case IncomeTier.middle:
        strategies.add(TierStrategy(
          tier: tier,
          strategy:
              'Balance debt payoff, emergency fund growth, and begin investing with index funds.',
          priority: StrategyPriority.high,
          timeframe: 'quarterly',
        ));
        break;
      case IncomeTier.high:
        strategies.add(TierStrategy(
          tier: tier,
          strategy:
              'Optimize tax-advantaged accounts, diversify investments, and consider real estate.',
          priority: StrategyPriority.medium,
          timeframe: 'annually',
        ));
        break;
      default:
        strategies.add(TierStrategy(
          tier: tier,
          strategy: 'Build consistent saving habits while growing your income potential.',
          priority: StrategyPriority.high,
          timeframe: 'monthly',
        ));
    }

    return strategies;
  }

  List<BehavioralNudge> _generateBehavioralNudges(
      List<String> habits, List<String> goals, IncomeTier tier) {
    final nudges = <BehavioralNudge>[];

    // Loss framing nudge
    nudges.add(BehavioralNudge(
      type: NudgeType.lossFraming,
      message: 'You have \$XX left for today - protect it!',
      trigger: 'daily_budget_check',
      effectiveness: 0.75,
    ));

    // Social proof nudge
    final tierName = _incomeService.getIncomeTierName(tier);
    nudges.add(BehavioralNudge(
      type: NudgeType.socialProof,
      message: '78% of $tierName users save more than \$500/month.',
      trigger: 'weekly_review',
      effectiveness: 0.7,
    ));

    // Progress celebration
    nudges.add(BehavioralNudge(
      type: NudgeType.progress,
      message: 'Congrats! You\'ve stayed under budget for 3 days in a row!',
      trigger: 'achievement_unlock',
      effectiveness: 0.85,
    ));

    return nudges;
  }

  List<SuccessMetric> _createPersonalizedMetrics(
      List<String> goals, List<String> habits, double monthlyIncome) {
    final metrics = <SuccessMetric>[];

    // Goal-based metrics
    if (goals.contains('save_more')) {
      metrics.add(SuccessMetric(
        name: 'Savings Rate',
        target: 20.0, // 20% savings rate
        unit: 'percentage',
        frequency: MetricFrequency.monthly,
      ));
    }

    // Habit-based metrics
    if (habits.contains('impulse_buying')) {
      metrics.add(SuccessMetric(
        name: 'Impulse Purchase Days',
        target: 2.0, // Max 2 impulse purchase days per month
        unit: 'days',
        frequency: MetricFrequency.monthly,
      ));
    }

    // Universal metrics
    metrics.add(SuccessMetric(
      name: 'Budget Adherence',
      target: 85.0, // 85% adherence rate
      unit: 'percentage',
      frequency: MetricFrequency.weekly,
    ));

    return metrics;
  }

  PersonalityProfile _generatePersonalityProfile(
      List<String> habits, List<String> goals, IncomeTier tier) {
    // Analyze habits and goals to determine personality
    final hasImpulsiveHabits = habits.any((h) => ['impulse_buying', 'no_budgeting'].contains(h));
    final hasConservativeGoals = goals.any((g) => ['save_more', 'budgeting'].contains(g));

    if (hasConservativeGoals && !hasImpulsiveHabits) {
      return PersonalityProfile.conservative;
    } else if (hasImpulsiveHabits && !hasConservativeGoals) {
      return PersonalityProfile.aggressive;
    } else {
      return PersonalityProfile.balanced;
    }
  }

  // ============================================================================
  // FALLBACK METHODS
  // ============================================================================

  DailyBudgetCalculation _getFallbackDailyBudget(double monthlyIncome) {
    final dailyBudget = (monthlyIncome * 0.7) / 30.0; // Simple 70% rule

    return DailyBudgetCalculation(
      totalDailyBudget: dailyBudget,
      baseAmount: dailyBudget * 0.85,
      redistributionBuffer: dailyBudget * 0.15,
      fixedCommitments: monthlyIncome * 0.25 / 30.0,
      savingsTarget: monthlyIncome * 0.15 / 30.0,
      confidence: 0.5,
      methodology: 'Fallback Simple Model',
    );
  }

  CategoryBudgetAllocation _getFallbackCategoryAllocation(double monthlyIncome) {
    final tier = _incomeService.classifyIncome(monthlyIncome);
    final weights = _incomeService.getDefaultBudgetWeights(tier);
    final dailyAllocations = _convertToDailyAllocations(weights, monthlyIncome);

    return CategoryBudgetAllocation(
      dailyAllocations: dailyAllocations,
      monthlyAllocations: weights.map((k, v) => MapEntry(k, monthlyIncome * v)),
      insights: [],
      confidence: 0.5,
      lastUpdated: DateTime.now(),
    );
  }

  /// Calculate optimal budget (public method for tests)
  Map<String, double> calculateOptimalBudget({
    required double monthlyIncome,
    required IncomeTier tier,
    List<String>? goals,
    List<String>? habits,
  }) {
    final weights = _incomeService.getDefaultBudgetWeights(tier);
    return weights.map((k, v) => MapEntry(k, monthlyIncome * v));
  }
}

// ============================================================================
// DATA CLASSES
// ============================================================================

class DailyBudgetCalculation {
  final double totalDailyBudget;
  final double baseAmount;
  final double redistributionBuffer;
  final double fixedCommitments;
  final double savingsTarget;
  final double confidence;
  final String methodology;

  DailyBudgetCalculation({
    required this.totalDailyBudget,
    required this.baseAmount,
    required this.redistributionBuffer,
    required this.fixedCommitments,
    required this.savingsTarget,
    required this.confidence,
    required this.methodology,
  });

  double get availableSpending => baseAmount;
  double get flexibilityAmount => redistributionBuffer;
}

class CategoryBudgetAllocation {
  final Map<String, double> dailyAllocations;
  final Map<String, double> monthlyAllocations;
  final List<CategoryInsight> insights;
  final double confidence;
  final DateTime lastUpdated;

  CategoryBudgetAllocation({
    required this.dailyAllocations,
    required this.monthlyAllocations,
    required this.insights,
    required this.confidence,
    required this.lastUpdated,
  });
}

class CategoryInsight {
  final String category;
  final String message;
  final InsightType type;
  final InsightPriority priority;
  final bool actionable;

  CategoryInsight({
    required this.category,
    required this.message,
    required this.type,
    required this.priority,
    required this.actionable,
  });
}

class DynamicBudgetRules {
  final List<BudgetRule> rules;
  final AdaptationFrequency adaptationFrequency;
  final double confidenceLevel;
  final DateTime lastUpdated;

  DynamicBudgetRules({
    required this.rules,
    required this.adaptationFrequency,
    required this.confidenceLevel,
    required this.lastUpdated,
  });
}

class BudgetRule {
  final String id;
  final String description;
  final String condition;
  final String action;
  final RulePriority priority;
  final RuleFrequency frequency;

  BudgetRule({
    required this.id,
    required this.description,
    required this.condition,
    required this.action,
    required this.priority,
    required this.frequency,
  });
}

class PersonalizationEngine {
  final List<GoalNudge> goalNudges;
  final List<HabitIntervention> habitInterventions;
  final List<TierStrategy> tierStrategies;
  final List<BehavioralNudge> behavioralNudges;
  final List<SuccessMetric> successMetrics;
  final PersonalityProfile personalityProfile;
  final DateTime lastUpdated;

  PersonalizationEngine({
    required this.goalNudges,
    required this.habitInterventions,
    required this.tierStrategies,
    required this.behavioralNudges,
    required this.successMetrics,
    required this.personalityProfile,
    required this.lastUpdated,
  });
}

class GoalNudge {
  final String goal;
  final String message;
  final NudgeFrequency frequency;
  final double effectiveness;

  GoalNudge({
    required this.goal,
    required this.message,
    required this.frequency,
    required this.effectiveness,
  });
}

class HabitIntervention {
  final String habit;
  final String intervention;
  final InterventionType type;
  final double effectiveness;

  HabitIntervention({
    required this.habit,
    required this.intervention,
    required this.type,
    required this.effectiveness,
  });
}

class TierStrategy {
  final IncomeTier tier;
  final String strategy;
  final StrategyPriority priority;
  final String timeframe;

  TierStrategy({
    required this.tier,
    required this.strategy,
    required this.priority,
    required this.timeframe,
  });
}

class BehavioralNudge {
  final NudgeType type;
  final String message;
  final String trigger;
  final double effectiveness;

  BehavioralNudge({
    required this.type,
    required this.message,
    required this.trigger,
    required this.effectiveness,
  });
}

class SuccessMetric {
  final String name;
  final double target;
  final String unit;
  final MetricFrequency frequency;

  SuccessMetric({
    required this.name,
    required this.target,
    required this.unit,
    required this.frequency,
  });
}

// Enums
enum InsightType { warning, opportunity, achievement, information }

enum InsightPriority { low, medium, high, critical }

enum AdaptationFrequency { daily, weekly, monthly }

enum RulePriority { low, medium, high, critical }

enum RuleFrequency { immediate, daily, weekly, monthly }

enum NudgeFrequency { daily, weekly, monthly }

enum InterventionType { delayTactic, behaviorReplacement, environmentalChange, socialSupport }

enum StrategyPriority { low, medium, high, critical }

enum NudgeType { lossFraming, socialProof, progress, scarcity, commitment }

enum MetricFrequency { daily, weekly, monthly }

enum PersonalityProfile { conservative, balanced, aggressive }
