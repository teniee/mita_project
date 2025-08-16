import '../models/budget_intelligence_models.dart';

/// Transparent explanation engine for budget algorithm reasoning
class ExplanationEngineService {
  static final ExplanationEngineService _instance = ExplanationEngineService._internal();
  factory ExplanationEngineService() => _instance;
  ExplanationEngineService._internal();

  /// Generate comprehensive budget calculation explanation using external models
  Future<BudgetExplanation> explainBudgetCalculation({
    required Map<String, dynamic> inputData,
    required Map<String, dynamic> calculationResults,
    required ExplanationContext context,
    bool includeAlternativeScenarios = false,
  }) async {
    final steps = <String>[];
    final factorContributions = <String, double>{};
    final keyInsights = <String>[];

    // Step 1: Income Analysis
    final incomeAnalysis = _explainIncomeAnalysis(inputData, calculationResults);
    steps.add(incomeAnalysis['description'] as String);
    factorContributions['income'] = incomeAnalysis['impactWeight'] as double;

    // Step 2: Income Tier Classification
    final tierAnalysis = _explainIncomeTierClassification(inputData, calculationResults);
    steps.add(tierAnalysis['description'] as String);
    factorContributions['incomeTier'] = tierAnalysis['impactWeight'] as double;

    // Step 3: Fixed Commitments Calculation
    final fixedAnalysis = _explainFixedCommitmentsCalculation(inputData, calculationResults);
    steps.add(fixedAnalysis['description'] as String);
    factorContributions['fixedCommitments'] = fixedAnalysis['impactWeight'] as double;

    // Step 4: Savings Target Calculation
    final savingsAnalysis = _explainSavingsTargetCalculation(inputData, calculationResults);
    steps.add(savingsAnalysis['description'] as String);
    factorContributions['savingsTarget'] = savingsAnalysis['impactWeight'] as double;

    // Step 5: Available Spending Calculation
    final availableAnalysis = _explainAvailableSpendingCalculation(inputData, calculationResults);
    steps.add(availableAnalysis['description'] as String);
    factorContributions['availableSpending'] = availableAnalysis['impactWeight'] as double;

    // Step 6: Daily Budget Derivation
    final dailyAnalysis = _explainDailyBudgetDerivation(inputData, calculationResults);
    steps.add(dailyAnalysis['description'] as String);
    factorContributions['dailyCalculation'] = dailyAnalysis['impactWeight'] as double;

    // Additional steps for location, goals, habits, temporal adjustments
    if (inputData['location'] != null) {
      final locationAnalysis = _explainLocationAdjustments(inputData, calculationResults);
      steps.add(locationAnalysis['description'] as String);
      factorContributions['locationAdjustment'] = locationAnalysis['impactWeight'] as double;
    }

    if (inputData['goals'] != null) {
      final goalsAnalysis = _explainGoalAdjustments(inputData, calculationResults);
      steps.add(goalsAnalysis['description'] as String);
      factorContributions['goalAdjustments'] = goalsAnalysis['impactWeight'] as double;
    }

    if (inputData['habits'] != null) {
      final habitsAnalysis = _explainHabitCorrections(inputData, calculationResults);
      steps.add(habitsAnalysis['description'] as String);
      factorContributions['habitCorrections'] = habitsAnalysis['impactWeight'] as double;
    }

    if (inputData['temporalFactors'] != null) {
      final temporalAnalysis = _explainTemporalAdjustments(inputData, calculationResults);
      steps.add(temporalAnalysis['description'] as String);
      factorContributions['temporalAdjustments'] = temporalAnalysis['impactWeight'] as double;
    }

    // Generate key insights
    keyInsights.addAll(_generateKeyInsights(steps, factorContributions, context));

    // Create summary explanation
    final summaryExplanation = _generateSummaryExplanation(
      steps,
      factorContributions,
      calculationResults,
      context,
    );

    return BudgetExplanation(
      explanationId: 'budget_explanation_${DateTime.now().millisecondsSinceEpoch}',
      primaryExplanation: summaryExplanation,
      detailedSteps: steps,
      calculations: calculationResults,
      assumptions: ['Income stability', 'Fixed expense estimates', 'Standard month length'],
      userLevel: context.userLevel,
    );
  }

  /// Generate simple explanation for basic budget result
  Future<BudgetExplanation> generateSimpleExplanation({
    required double dailyBudget,
    required double monthlyIncome,
    required String userLevel,
  }) async {
    final spendingRatio = monthlyIncome > 0 ? (dailyBudget * 30) / monthlyIncome : 0.0;
    
    String explanation;
    switch (userLevel) {
      case 'beginner':
        explanation = 'Your daily budget of \$${dailyBudget.toStringAsFixed(0)} comes from taking your monthly income, setting aside money for essential expenses and savings, then dividing what\'s left by 30 days.';
        break;
      case 'advanced':
        explanation = 'Your daily budget of \$${dailyBudget.toStringAsFixed(0)} represents ${(spendingRatio * 100).toStringAsFixed(1)}% of your monthly income, calculated using income tier classification and multi-factor optimization.';
        break;
      default:
        explanation = 'Your daily budget of \$${dailyBudget.toStringAsFixed(0)} gives you ${(spendingRatio * 100).toStringAsFixed(0)}% of your income for flexible spending while covering essentials and savings.';
    }

    return BudgetExplanation(
      explanationId: 'simple_explanation_${DateTime.now().millisecondsSinceEpoch}',
      primaryExplanation: explanation,
      detailedSteps: [explanation],
      calculations: {
        'dailyBudget': dailyBudget,
        'monthlyIncome': monthlyIncome,
        'spendingRatio': spendingRatio,
      },
      assumptions: ['Standard budget methodology'],
      userLevel: userLevel,
    );
  }

  /// Generate explanation for budget adjustments
  Future<BudgetExplanation> explainBudgetAdjustment({
    required double originalBudget,
    required double adjustedBudget,
    required String adjustmentReason,
    required Map<String, dynamic> adjustmentData,
  }) async {
    final difference = adjustedBudget - originalBudget;
    final percentChange = originalBudget > 0 ? (difference / originalBudget * 100) : 0.0;
    
    final explanation = 'Your budget was ${difference > 0 ? 'increased' : 'decreased'} by \$${difference.abs().toStringAsFixed(0)} (${percentChange.abs().toStringAsFixed(0)}%) due to $adjustmentReason.';
    
    final detailedSteps = [
      'Original budget: \$${originalBudget.toStringAsFixed(0)}',
      'Adjustment: ${difference > 0 ? '+' : ''}\$${difference.toStringAsFixed(0)}',
      'Reason: $adjustmentReason',
      'New budget: \$${adjustedBudget.toStringAsFixed(0)}',
    ];

    return BudgetExplanation(
      explanationId: 'adjustment_explanation_${DateTime.now().millisecondsSinceEpoch}',
      primaryExplanation: explanation,
      detailedSteps: detailedSteps,
      calculations: {
        'originalBudget': originalBudget,
        'adjustedBudget': adjustedBudget,
        'adjustment': difference,
        'percentChange': percentChange,
        ...adjustmentData,
      },
      assumptions: ['Adjustment factors are temporary', 'Budget will normalize over time'],
      userLevel: 'intermediate',
    );
  }

  /// Personalize explanation based on user context
  String personalizeExplanation(String baseExplanation, ExplanationContext context) {
    String personalized = baseExplanation;

    // Adjust complexity based on user level
    switch (context.userLevel) {
      case 'beginner':
        personalized = _simplifyExplanation(personalized);
        break;
      case 'advanced':
        personalized = _addTechnicalDetails(personalized);
        break;
    }

    // Adjust communication style
    switch (context.communicationStyle) {
      case 'conversational':
        personalized = _makeConversational(personalized);
        break;
      case 'technical':
        personalized = _makeTechnical(personalized);
        break;
    }

    return personalized;
  }

  // Explanation step implementations

  Map<String, dynamic> _explainIncomeAnalysis(
    Map<String, dynamic> inputData,
    Map<String, dynamic> results,
  ) {
    final monthlyIncome = (inputData['monthlyIncome'] as num?)?.toDouble() ?? 0.0;
    final adjustedIncome = (results['adjustedIncome'] as num?)?.toDouble() ?? monthlyIncome;

    return {
      'stepNumber': 1,
      'stepName': 'Income Analysis',
      'description': 'Your monthly income of \$${monthlyIncome.toStringAsFixed(0)} forms the foundation for all budget calculations. ${adjustedIncome != monthlyIncome ? 'We adjusted it to \$${adjustedIncome.toStringAsFixed(0)} based on stability patterns.' : ''}',
      'inputValue': monthlyIncome,
      'outputValue': adjustedIncome,
      'formula': 'Adjusted Income = Monthly Income × Income Stability Factor',
      'reasoning': 'We start with your reported monthly income and may adjust it based on income stability patterns if available.',
      'impactWeight': 0.4, // High impact on final budget
    };
  }

  Map<String, dynamic> _explainIncomeTierClassification(
    Map<String, dynamic> inputData,
    Map<String, dynamic> results,
  ) {
    final monthlyIncome = (inputData['monthlyIncome'] as num?)?.toDouble() ?? 0.0;
    final incomeTier = results['incomeTier']?.toString() ?? 'middle';
    final tierName = _getTierDisplayName(incomeTier);

    return {
      'stepNumber': 2,
      'stepName': 'Income Tier Classification',
      'description': 'Your income places you in the $tierName category, which determines your budget parameters and spending ratios.',
      'inputValue': monthlyIncome,
      'outputValue': _getTierNumericValue(incomeTier),
      'formula': 'Income Tier = Classification(Monthly Income, Location Adjustments)',
      'reasoning': 'Income tiers help us apply research-based budget ratios that work best for people in similar financial situations.',
      'impactWeight': 0.25,
    };
  }

  Map<String, dynamic> _explainFixedCommitmentsCalculation(
    Map<String, dynamic> inputData,
    Map<String, dynamic> results,
  ) {
    final adjustedIncome = (results['adjustedIncome'] as num?)?.toDouble() ?? 0.0;
    final fixedCommitmentRatio = (results['fixedCommitmentRatio'] as num?)?.toDouble() ?? 0.5;
    final fixedCommitments = adjustedIncome * fixedCommitmentRatio;

    return {
      'stepNumber': 3,
      'stepName': 'Fixed Commitments',
      'description': 'Essential expenses like rent, utilities, and debt payments are calculated first. We allocate ${(fixedCommitmentRatio * 100).toStringAsFixed(0)}% of your income (\$${fixedCommitments.toStringAsFixed(0)}) for these necessities.',
      'inputValue': adjustedIncome,
      'outputValue': fixedCommitments,
      'formula': 'Fixed Commitments = Adjusted Income × Fixed Commitment Ratio',
      'reasoning': 'Your income tier determines the recommended ratio for fixed expenses. This ensures essential needs are covered first.',
      'impactWeight': 0.3,
    };
  }

  Map<String, dynamic> _explainSavingsTargetCalculation(
    Map<String, dynamic> inputData,
    Map<String, dynamic> results,
  ) {
    final adjustedIncome = (results['adjustedIncome'] as num?)?.toDouble() ?? 0.0;
    final savingsTargetRatio = (results['savingsTargetRatio'] as num?)?.toDouble() ?? 0.15;
    final savingsTarget = adjustedIncome * savingsTargetRatio;

    return {
      'stepNumber': 4,
      'stepName': 'Savings Target',
      'description': 'A portion of your income (${(savingsTargetRatio * 100).toStringAsFixed(0)}% = \$${savingsTarget.toStringAsFixed(0)}) is allocated for savings and future goals to build financial security.',
      'inputValue': adjustedIncome,
      'outputValue': savingsTarget,
      'formula': 'Savings Target = Adjusted Income × Savings Target Ratio',
      'reasoning': 'Automatic savings allocation helps build financial security. The ratio increases with higher income tiers.',
      'impactWeight': 0.2,
    };
  }

  Map<String, dynamic> _explainAvailableSpendingCalculation(
    Map<String, dynamic> inputData,
    Map<String, dynamic> results,
  ) {
    final adjustedIncome = (results['adjustedIncome'] as num?)?.toDouble() ?? 0.0;
    final fixedCommitments = (results['fixedCommitments'] as num?)?.toDouble() ?? 0.0;
    final savingsTarget = (results['savingsTarget'] as num?)?.toDouble() ?? 0.0;
    final availableSpending = adjustedIncome - fixedCommitments - savingsTarget;

    return {
      'stepNumber': 5,
      'stepName': 'Available Spending',
      'description': 'After fixed costs (\$${fixedCommitments.toStringAsFixed(0)}) and savings (\$${savingsTarget.toStringAsFixed(0)}), you have \$${availableSpending.toStringAsFixed(0)} available for flexible spending.',
      'inputValue': adjustedIncome,
      'outputValue': availableSpending,
      'formula': 'Available Spending = Income - Fixed Commitments - Savings Target',
      'reasoning': 'This represents the money available for discretionary spending like food, entertainment, and shopping.',
      'impactWeight': 0.15,
    };
  }

  Map<String, dynamic> _explainDailyBudgetDerivation(
    Map<String, dynamic> inputData,
    Map<String, dynamic> results,
  ) {
    final availableSpending = (results['availableSpending'] as num?)?.toDouble() ?? 0.0;
    final dailyBudget = availableSpending / 30; // Assuming 30 days per month

    return {
      'stepNumber': 6,
      'stepName': 'Daily Budget Calculation',
      'description': 'Your available spending (\$${availableSpending.toStringAsFixed(0)}) is divided by 30 days to give you a daily budget of \$${dailyBudget.toStringAsFixed(0)}.',
      'inputValue': availableSpending,
      'outputValue': dailyBudget,
      'formula': 'Daily Budget = Available Spending ÷ 30 days',
      'reasoning': 'Breaking down your budget into daily amounts makes it easier to track and control spending.',
      'impactWeight': 0.1,
    };
  }

  Map<String, dynamic> _explainLocationAdjustments(
    Map<String, dynamic> inputData,
    Map<String, dynamic> results,
  ) {
    final baseBudget = (results['baseDailyBudget'] as num?)?.toDouble() ?? 0.0;
    final locationMultiplier = (results['locationMultiplier'] as num?)?.toDouble() ?? 1.0;
    final adjustedBudget = baseBudget * locationMultiplier;
    final location = inputData['location']?.toString() ?? 'Unknown';

    return {
      'stepNumber': 7,
      'stepName': 'Location Adjustment',
      'description': 'Your budget is adjusted for the cost of living in $location. The ${locationMultiplier > 1 ? 'higher' : 'lower'} cost of living ${locationMultiplier > 1 ? 'increases' : 'decreases'} your budget to \$${adjustedBudget.toStringAsFixed(0)}.',
      'inputValue': baseBudget,
      'outputValue': adjustedBudget,
      'formula': 'Adjusted Budget = Base Budget × Location Multiplier',
      'reasoning': 'Different locations have different costs of living. This adjustment ensures your budget reflects local prices.',
      'impactWeight': 0.1,
    };
  }

  Map<String, dynamic> _explainGoalAdjustments(
    Map<String, dynamic> inputData,
    Map<String, dynamic> results,
  ) {
    final baseBudget = (results['baseAfterLocation'] as num?)?.toDouble() ?? 0.0;
    final goalAdjustment = (results['goalAdjustment'] as num?)?.toDouble() ?? 0.0;
    final adjustedBudget = baseBudget + goalAdjustment;
    final goals = inputData['goals'] as List<dynamic>? ?? [];
    final goalNames = goals.map((g) => g.toString()).toList();

    return {
      'stepNumber': 8,
      'stepName': 'Goal-Based Adjustments',
      'description': 'Your budget is fine-tuned based on your financial goals: ${goalNames.join(', ')}. This ${goalAdjustment > 0 ? 'increases' : 'decreases'} your budget by \$${goalAdjustment.abs().toStringAsFixed(0)}.',
      'inputValue': baseBudget,
      'outputValue': adjustedBudget,
      'formula': 'Goal-Adjusted Budget = Base Budget + Goal Adjustments',
      'reasoning': 'Different financial goals require different spending patterns. These adjustments help you achieve your objectives.',
      'impactWeight': 0.08,
    };
  }

  Map<String, dynamic> _explainHabitCorrections(
    Map<String, dynamic> inputData,
    Map<String, dynamic> results,
  ) {
    final baseBudget = (results['baseAfterGoals'] as num?)?.toDouble() ?? 0.0;
    final habitAdjustment = (results['habitAdjustment'] as num?)?.toDouble() ?? 0.0;
    final adjustedBudget = baseBudget + habitAdjustment;
    final habits = inputData['habits'] as List<dynamic>? ?? [];
    final habitNames = habits.map((h) => h.toString()).toList();

    return {
      'stepNumber': 9,
      'stepName': 'Behavioral Corrections',
      'description': 'Your budget accounts for spending habits: ${habitNames.join(', ')}. We apply a ${habitAdjustment > 0 ? 'protective buffer' : 'spending encouragement'} of \$${habitAdjustment.abs().toStringAsFixed(0)}.',
      'inputValue': baseBudget,
      'outputValue': adjustedBudget,
      'formula': 'Habit-Corrected Budget = Goal-Adjusted Budget + Habit Corrections',
      'reasoning': 'We apply research-based adjustments to help counteract common spending habits and improve your success rate.',
      'impactWeight': 0.07,
    };
  }

  Map<String, dynamic> _explainTemporalAdjustments(
    Map<String, dynamic> inputData,
    Map<String, dynamic> results,
  ) {
    final baseBudget = (results['baseAfterHabits'] as num?)?.toDouble() ?? 0.0;
    final temporalAdjustment = (results['temporalAdjustment'] as num?)?.toDouble() ?? 0.0;
    final finalBudget = baseBudget + temporalAdjustment;

    return {
      'stepNumber': 10,
      'stepName': 'Temporal Adjustments',
      'description': 'Final adjustments based on the specific day, week, and month patterns. ${_getTemporalAdjustmentReason(temporalAdjustment)} by \$${temporalAdjustment.abs().toStringAsFixed(0)}.',
      'inputValue': baseBudget,
      'outputValue': finalBudget,
      'formula': 'Final Budget = Habit-Corrected Budget + Temporal Adjustments',
      'reasoning': 'Spending patterns vary by day of week, time of month, and season. These final adjustments account for these patterns.',
      'impactWeight': 0.05,
    };
  }

  // Text processing methods for personalization

  String _simplifyExplanation(String explanation) {
    return explanation
        .replaceAll('algorithm', 'system')
        .replaceAll('optimization', 'improvement')
        .replaceAll('parameters', 'settings')
        .replaceAll('coefficients', 'factors');
  }

  String _addTechnicalDetails(String explanation) {
    // Add more technical terminology and details
    return explanation; // Placeholder
  }

  String _makeConversational(String explanation) {
    return explanation
        .replaceAll('Your budget is calculated', 'Here\'s how we figure out your budget')
        .replaceAll('We apply', 'We add in')
        .replaceAll('The result is', 'This gives you');
  }

  String _makeTechnical(String explanation) {
    return explanation
        .replaceAll('figured out', 'calculated')
        .replaceAll('Here\'s how', 'The methodology for');
  }

  // Insight and summary generation

  List<String> _generateKeyInsights(
    List<String> steps,
    Map<String, double> contributions,
    ExplanationContext context,
  ) {
    final insights = <String>[];

    // Find highest impact factors
    final sortedFactors = contributions.entries.toList()
      ..sort((a, b) => b.value.compareTo(a.value));

    if (sortedFactors.isNotEmpty) {
      final topFactor = sortedFactors.first;
      insights.add('Your ${_getFactorDisplayName(topFactor.key)} has the biggest impact on your budget (${(topFactor.value * 100).toStringAsFixed(0)}% influence)');
    }

    // Add contextual insights based on user level
    switch (context.userLevel) {
      case 'beginner':
        insights.add('Your budget follows proven financial principles that work for people in similar situations');
        break;
      case 'advanced':
        insights.add('The algorithm uses multi-factor optimization with behavioral economics principles');
        break;
      default:
        insights.add('Your budget balances immediate needs with long-term financial health');
    }

    return insights.take(3).toList();
  }

  String _generateSummaryExplanation(
    List<String> steps,
    Map<String, double> contributions,
    Map<String, dynamic> results,
    ExplanationContext context,
  ) {
    final finalAmount = (results['finalDailyBudget'] as num?)?.toDouble() ?? 0.0;
    final monthlyIncome = (results['adjustedIncome'] as num?)?.toDouble() ?? 0.0;
    final spendingRatio = monthlyIncome > 0 ? (finalAmount * 30) / monthlyIncome : 0.0;

    String summary = 'Your daily budget of \$${finalAmount.toStringAsFixed(0)} is calculated ';

    switch (context.userLevel) {
      case 'beginner':
        summary += 'by taking your monthly income, setting aside money for essential expenses and savings, then dividing the remainder by 30 days. ';
        summary += 'This represents ${(spendingRatio * 100).toStringAsFixed(0)}% of your monthly income available for flexible spending.';
        break;
      case 'advanced':
        summary += 'using a multi-factor algorithm that considers your income tier classification, location-adjusted cost ratios, goal-based optimizations, and behavioral habit corrections. ';
        summary += 'The final amount represents ${(spendingRatio * 100).toStringAsFixed(1)}% of your adjusted monthly income allocated to discretionary spending.';
        break;
      default:
        summary += 'by analyzing your income, expenses, goals, and spending patterns. ';
        summary += 'This amount (${(spendingRatio * 100).toStringAsFixed(0)}% of your income) gives you flexibility while ensuring your essential needs and savings goals are met.';
    }

    return summary;
  }

  // Helper methods

  String _getTierDisplayName(String tier) {
    switch (tier) {
      case 'low': return 'Foundation Builder';
      case 'lowerMiddle': return 'Stability Seeker';
      case 'middle': return 'Strategic Achiever';
      case 'upperMiddle': return 'Wealth Accelerator';
      case 'high': return 'Legacy Builder';
      default: return 'Budget Optimizer';
    }
  }

  double _getTierNumericValue(String tier) {
    switch (tier) {
      case 'low': return 1.0;
      case 'lowerMiddle': return 2.0;
      case 'middle': return 3.0;
      case 'upperMiddle': return 4.0;
      case 'high': return 5.0;
      default: return 3.0;
    }
  }

  String _getTemporalAdjustmentReason(double adjustment) {
    if (adjustment > 0) {
      return 'Budget increased';
    } else if (adjustment < 0) {
      return 'Budget decreased';
    } else {
      return 'No temporal adjustment needed';
    }
  }

  String _getFactorDisplayName(String factor) {
    switch (factor) {
      case 'income': return 'monthly income';
      case 'incomeTier': return 'income tier classification';
      case 'fixedCommitments': return 'fixed expenses';
      case 'savingsTarget': return 'savings goals';
      case 'locationAdjustment': return 'location cost adjustments';
      case 'goalAdjustments': return 'financial goals';
      case 'habitCorrections': return 'spending habit corrections';
      case 'temporalAdjustments': return 'timing-based adjustments';
      default: return factor;
    }
  }
}