import '../models/budget_intelligence_models.dart';

/// Goal interference detection and conflict resolution service
class GoalInterferenceService {
  static final GoalInterferenceService _instance =
      GoalInterferenceService._internal();
  factory GoalInterferenceService() => _instance;
  GoalInterferenceService._internal();

  // Private storage for goal data
  final Map<String, FinancialGoal> _goals = {};
  final List<GoalInterference> _detectedInterferences = [];
  final List<GoalResolutionStrategy> _strategies = [];

  /// Detect interferences between financial goals
  Future<List<GoalInterference>> detectGoalInterferences(
    List<FinancialGoal> goals,
    Map<String, dynamic> currentFinancialState,
  ) async {
    final interferences = <GoalInterference>[];

    // Store goals for analysis
    for (final goal in goals) {
      _goals[goal.goalId] = goal;
    }

    // 1. Resource competition analysis
    final resourceInterferences =
        await _analyzeResourceCompetition(goals, currentFinancialState);
    interferences.addAll(resourceInterferences);

    // 2. Timeline conflict analysis
    final timelineInterferences = await _analyzeTimelineConflicts(goals);
    interferences.addAll(timelineInterferences);

    // 3. Priority conflict analysis
    final priorityInterferences = await _analyzePriorityConflicts(goals);
    interferences.addAll(priorityInterferences);

    // 4. Constraint violation analysis
    final constraintInterferences =
        await _analyzeConstraintViolations(goals, currentFinancialState);
    interferences.addAll(constraintInterferences);

    // Sort by severity and probability
    interferences.sort((a, b) {
      final scoreA = a.severity * a.probability;
      final scoreB = b.severity * b.probability;
      return scoreB.compareTo(scoreA);
    });

    _detectedInterferences.clear();
    _detectedInterferences.addAll(interferences);
    return interferences;
  }

  /// Generate resolution strategies for detected interferences
  Future<List<GoalResolutionStrategy>> generateResolutionStrategies(
    List<GoalInterference> interferences,
    List<FinancialGoal> goals,
  ) async {
    final strategies = <GoalResolutionStrategy>[];

    for (final interference in interferences) {
      // Get relevant goals for this interference
      final relevantGoals = goals
          .where((g) => interference.conflictingGoalIds.contains(g.goalId))
          .toList();

      if (relevantGoals.isEmpty) continue;

      // Generate strategy based on interference type
      final strategyList =
          await _generateStrategiesForInterference(interference, relevantGoals);
      strategies.addAll(strategyList);
    }

    // Sort strategies by effectiveness
    strategies.sort(
        (a, b) => b.expectedEffectiveness.compareTo(a.expectedEffectiveness));

    _strategies.clear();
    _strategies.addAll(strategies);
    return strategies;
  }

  /// Optimize goal portfolio for maximum achievability
  Future<GoalOptimizationResult> optimizeGoalPortfolio(
    List<FinancialGoal> goals,
    Map<String, dynamic> currentFinancialState,
  ) async {
    // 1. Detect all interferences
    final interferences =
        await detectGoalInterferences(goals, currentFinancialState);

    // 2. Generate resolution strategies
    final strategies = await generateResolutionStrategies(interferences, goals);

    // 3. Apply optimization
    final optimizedGoals =
        await _applyOptimization(goals, strategies, currentFinancialState);

    // 4. Calculate resource allocation
    final resourceAllocation = _calculateOptimalResourceAllocation(
        optimizedGoals, currentFinancialState);

    // 5. Calculate feasibility score
    final feasibilityScore =
        _calculateFeasibilityScore(optimizedGoals, currentFinancialState);

    // 6. Generate warnings and opportunities
    final warnings = _generateWarnings(optimizedGoals, interferences);
    final opportunities =
        _generateOpportunities(optimizedGoals, currentFinancialState);

    return GoalOptimizationResult(
      optimizedGoals: optimizedGoals,
      detectedInterferences: interferences,
      recommendedStrategies: strategies,
      resourceAllocation: resourceAllocation,
      overallFeasibilityScore: feasibilityScore,
      warnings: warnings,
      opportunities: opportunities,
    );
  }

  /// Analyze resource competition between goals
  Future<List<GoalInterference>> _analyzeResourceCompetition(
    List<FinancialGoal> goals,
    Map<String, dynamic> currentFinancialState,
  ) async {
    final interferences = <GoalInterference>[];
    final monthlyIncome =
        (currentFinancialState['monthlyIncome'] as num?)?.toDouble() ?? 0.0;
    final fixedExpenses =
        (currentFinancialState['fixedExpenses'] as num?)?.toDouble() ?? 0.0;
    final availableForGoals = monthlyIncome - fixedExpenses;

    final totalRequiredContribution = goals.fold<double>(
      0.0,
      (sum, goal) => sum + goal.monthlyRequiredContribution,
    );

    if (totalRequiredContribution > availableForGoals * 0.8) {
      // High resource competition
      for (int i = 0; i < goals.length; i++) {
        for (int j = i + 1; j < goals.length; j++) {
          final goal1 = goals[i];
          final goal2 = goals[j];

          final competitionSeverity =
              _calculateResourceCompetition(goal1, goal2, availableForGoals);

          if (competitionSeverity > 0.3) {
            interferences.add(GoalInterference(
              interferenceId: 'resource_${goal1.goalId}_${goal2.goalId}',
              conflictingGoalIds: [goal1.goalId, goal2.goalId],
              interferenceType: 'resource_competition',
              severity: competitionSeverity,
              probability: 0.8,
              description:
                  'Goals ${goal1.name} and ${goal2.name} compete for limited financial resources',
              rootCauses: ['insufficient_income', 'high_goal_requirements'],
              resourceCompetition: {
                goal1.goalId: goal1.monthlyRequiredContribution,
                goal2.goalId: goal2.monthlyRequiredContribution,
              },
              detectedAt: DateTime.now(),
            ));
          }
        }
      }
    }

    return interferences;
  }

  /// Analyze timeline conflicts between goals
  Future<List<GoalInterference>> _analyzeTimelineConflicts(
      List<FinancialGoal> goals) async {
    final interferences = <GoalInterference>[];

    // Group goals by target timeframe
    final goalsByTimeframe = <String, List<FinancialGoal>>{};

    for (final goal in goals) {
      final timeframe = _getTimeframe(goal.targetDate);
      goalsByTimeframe.putIfAbsent(timeframe, () => []).add(goal);
    }

    // Check for conflicts within each timeframe
    for (final timeframeGoals in goalsByTimeframe.values) {
      if (timeframeGoals.length > 1) {
        // Sort by priority
        timeframeGoals.sort((a, b) => b.priority.compareTo(a.priority));

        // Check if high-priority goals conflict with lower-priority ones
        for (int i = 0; i < timeframeGoals.length; i++) {
          for (int j = i + 1; j < timeframeGoals.length; j++) {
            final highPriorityGoal = timeframeGoals[i];
            final lowPriorityGoal = timeframeGoals[j];

            if (highPriorityGoal.priority > lowPriorityGoal.priority) {
              interferences.add(GoalInterference(
                interferenceId:
                    'timeline_${highPriorityGoal.goalId}_${lowPriorityGoal.goalId}',
                conflictingGoalIds: [
                  highPriorityGoal.goalId,
                  lowPriorityGoal.goalId
                ],
                interferenceType: 'timeline_conflict',
                severity: 0.6,
                probability: 0.7,
                description:
                    'Goals ${highPriorityGoal.name} and ${lowPriorityGoal.name} have conflicting timelines',
                rootCauses: ['overlapping_deadlines', 'priority_mismatch'],
                resourceCompetition: {},
                detectedAt: DateTime.now(),
              ));
            }
          }
        }
      }
    }

    return interferences;
  }

  /// Analyze priority conflicts
  Future<List<GoalInterference>> _analyzePriorityConflicts(
      List<FinancialGoal> goals) async {
    final interferences = <GoalInterference>[];

    // Check for goals with similar priority but different resource requirements
    final goalsByPriority = <int, List<FinancialGoal>>{};

    for (final goal in goals) {
      goalsByPriority.putIfAbsent(goal.priority, () => []).add(goal);
    }

    for (final priorityGoals in goalsByPriority.values) {
      if (priorityGoals.length > 1) {
        // Check resource requirements variance
        final contributions =
            priorityGoals.map((g) => g.monthlyRequiredContribution).toList();
        final avgContribution =
            contributions.reduce((a, b) => a + b) / contributions.length;

        for (final goal in priorityGoals) {
          if ((goal.monthlyRequiredContribution - avgContribution).abs() >
              avgContribution * 0.5) {
            interferences.add(GoalInterference(
              interferenceId: 'priority_${goal.goalId}',
              conflictingGoalIds: priorityGoals.map((g) => g.goalId).toList(),
              interferenceType: 'priority_conflict',
              severity: 0.4,
              probability: 0.6,
              description:
                  'Goal ${goal.name} has misaligned priority vs resource requirements',
              rootCauses: ['priority_resource_mismatch'],
              resourceCompetition: {},
              detectedAt: DateTime.now(),
            ));
          }
        }
      }
    }

    return interferences;
  }

  /// Analyze constraint violations
  Future<List<GoalInterference>> _analyzeConstraintViolations(
    List<FinancialGoal> goals,
    Map<String, dynamic> currentFinancialState,
  ) async {
    final interferences = <GoalInterference>[];

    for (final goal in goals) {
      final constraints = goal.constraints;

      // Check budget constraints
      if (constraints.containsKey('max_monthly_contribution')) {
        final maxContribution =
            (constraints['max_monthly_contribution'] as num?)?.toDouble() ??
                double.infinity;
        if (goal.monthlyRequiredContribution > maxContribution) {
          interferences.add(GoalInterference(
            interferenceId: 'constraint_${goal.goalId}',
            conflictingGoalIds: [goal.goalId],
            interferenceType: 'constraint_violation',
            severity: 0.8,
            probability: 0.9,
            description:
                'Goal ${goal.name} exceeds maximum monthly contribution constraint',
            rootCauses: ['budget_constraint_violation'],
            resourceCompetition: {},
            detectedAt: DateTime.now(),
          ));
        }
      }

      // Check timeline constraints
      if (constraints.containsKey('min_completion_date')) {
        final minDate = constraints['min_completion_date'] as DateTime?;
        if (minDate != null && goal.targetDate.isBefore(minDate)) {
          interferences.add(GoalInterference(
            interferenceId: 'timeline_constraint_${goal.goalId}',
            conflictingGoalIds: [goal.goalId],
            interferenceType: 'timeline_constraint_violation',
            severity: 0.7,
            probability: 0.8,
            description:
                'Goal ${goal.name} target date violates minimum completion constraint',
            rootCauses: ['timeline_constraint_violation'],
            resourceCompetition: {},
            detectedAt: DateTime.now(),
          ));
        }
      }
    }

    return interferences;
  }

  /// Generate strategies for specific interference
  Future<List<GoalResolutionStrategy>> _generateStrategiesForInterference(
    GoalInterference interference,
    List<FinancialGoal> goals,
  ) async {
    final strategies = <GoalResolutionStrategy>[];

    switch (interference.interferenceType) {
      case 'resource_competition':
        strategies.addAll(
            _generateResourceCompetitionStrategies(interference, goals));
        break;
      case 'timeline_conflict':
        strategies
            .addAll(_generateTimelineConflictStrategies(interference, goals));
        break;
      case 'priority_conflict':
        strategies
            .addAll(_generatePriorityConflictStrategies(interference, goals));
        break;
      case 'constraint_violation':
        strategies.addAll(
            _generateConstraintViolationStrategies(interference, goals));
        break;
    }

    return strategies;
  }

  /// Generate resource competition resolution strategies
  List<GoalResolutionStrategy> _generateResourceCompetitionStrategies(
    GoalInterference interference,
    List<FinancialGoal> goals,
  ) {
    final strategies = <GoalResolutionStrategy>[];

    // Strategy 1: Reduce contribution amounts proportionally
    strategies.add(GoalResolutionStrategy(
      strategyId: 'reduce_contributions_${interference.interferenceId}',
      strategyType: 'contribution_reduction',
      description:
          'Reduce monthly contributions to competing goals proportionally',
      adjustments: {},
      expectedEffectiveness: 0.7,
      tradeoffs: ['Extended timeline', 'Reduced goal amounts'],
      goalImpacts: {},
      implementationSteps: [
        'Calculate total over-allocation',
        'Reduce each goal contribution proportionally',
        'Extend timelines to maintain target amounts'
      ],
    ));

    // Strategy 2: Extend timelines
    strategies.add(GoalResolutionStrategy(
      strategyId: 'extend_timelines_${interference.interferenceId}',
      strategyType: 'timeline_extension',
      description:
          'Extend target dates to reduce monthly contribution pressure',
      adjustments: {},
      expectedEffectiveness: 0.8,
      tradeoffs: ['Delayed goal achievement'],
      goalImpacts: {},
      implementationSteps: [
        'Identify flexible goals',
        'Calculate extended timelines',
        'Adjust monthly contributions accordingly'
      ],
    ));

    // Strategy 3: Prioritize goals
    strategies.add(GoalResolutionStrategy(
      strategyId: 'prioritize_goals_${interference.interferenceId}',
      strategyType: 'goal_prioritization',
      description: 'Focus resources on highest priority goals first',
      adjustments: {},
      expectedEffectiveness: 0.6,
      tradeoffs: ['Some goals may be significantly delayed'],
      goalImpacts: {},
      implementationSteps: [
        'Rank goals by priority and urgency',
        'Allocate full resources to top priority',
        'Queue remaining goals sequentially'
      ],
    ));

    return strategies;
  }

  /// Generate timeline conflict resolution strategies
  List<GoalResolutionStrategy> _generateTimelineConflictStrategies(
    GoalInterference interference,
    List<FinancialGoal> goals,
  ) {
    final strategies = <GoalResolutionStrategy>[];

    // Strategy: Stagger goal timelines
    strategies.add(GoalResolutionStrategy(
      strategyId: 'stagger_timelines_${interference.interferenceId}',
      strategyType: 'timeline_staggering',
      description: 'Stagger goal completion dates to avoid resource conflicts',
      adjustments: {},
      expectedEffectiveness: 0.8,
      tradeoffs: ['Some goals delayed'],
      goalImpacts: {},
      implementationSteps: [
        'Identify timeline conflicts',
        'Create staggered completion schedule',
        'Adjust monthly contributions accordingly'
      ],
    ));

    return strategies;
  }

  /// Generate priority conflict resolution strategies
  List<GoalResolutionStrategy> _generatePriorityConflictStrategies(
    GoalInterference interference,
    List<FinancialGoal> goals,
  ) {
    final strategies = <GoalResolutionStrategy>[];

    // Strategy: Realign priorities with resources
    strategies.add(GoalResolutionStrategy(
      strategyId: 'realign_priorities_${interference.interferenceId}',
      strategyType: 'priority_realignment',
      description: 'Adjust goal priorities to match available resources',
      adjustments: {},
      expectedEffectiveness: 0.7,
      tradeoffs: ['Changed goal priorities'],
      goalImpacts: {},
      implementationSteps: [
        'Review goal importance vs cost',
        'Adjust priorities based on feasibility',
        'Reallocate resources accordingly'
      ],
    ));

    return strategies;
  }

  /// Generate constraint violation resolution strategies
  List<GoalResolutionStrategy> _generateConstraintViolationStrategies(
    GoalInterference interference,
    List<FinancialGoal> goals,
  ) {
    final strategies = <GoalResolutionStrategy>[];

    // Strategy: Adjust goal parameters within constraints
    strategies.add(GoalResolutionStrategy(
      strategyId: 'adjust_parameters_${interference.interferenceId}',
      strategyType: 'parameter_adjustment',
      description: 'Modify goal amounts or timelines to satisfy constraints',
      adjustments: {},
      expectedEffectiveness: 0.9,
      tradeoffs: ['Modified goal parameters'],
      goalImpacts: {},
      implementationSteps: [
        'Identify constraint violations',
        'Calculate feasible parameters',
        'Update goal specifications'
      ],
    ));

    return strategies;
  }

  /// Apply optimization strategies to goals
  Future<List<FinancialGoal>> _applyOptimization(
    List<FinancialGoal> goals,
    List<GoalResolutionStrategy> strategies,
    Map<String, dynamic> currentFinancialState,
  ) async {
    // For now, return original goals
    // In a full implementation, this would apply the optimization strategies
    return goals;
  }

  /// Calculate optimal resource allocation
  Map<String, double> _calculateOptimalResourceAllocation(
    List<FinancialGoal> goals,
    Map<String, dynamic> currentFinancialState,
  ) {
    final allocation = <String, double>{};

    for (final goal in goals) {
      allocation[goal.goalId] = goal.monthlyRequiredContribution;
    }

    return allocation;
  }

  /// Calculate overall feasibility score
  double _calculateFeasibilityScore(
    List<FinancialGoal> goals,
    Map<String, dynamic> currentFinancialState,
  ) {
    final monthlyIncome =
        (currentFinancialState['monthlyIncome'] as num?)?.toDouble() ?? 0.0;
    final fixedExpenses =
        (currentFinancialState['fixedExpenses'] as num?)?.toDouble() ?? 0.0;
    final availableForGoals = monthlyIncome - fixedExpenses;

    final totalRequired = goals.fold<double>(
      0.0,
      (sum, goal) => sum + goal.monthlyRequiredContribution,
    );

    if (totalRequired <= 0) return 1.0;

    final utilizationRatio = availableForGoals / totalRequired;
    return utilizationRatio.clamp(0.0, 1.0);
  }

  /// Generate warnings for optimized goals
  List<String> _generateWarnings(
    List<FinancialGoal> goals,
    List<GoalInterference> interferences,
  ) {
    final warnings = <String>[];

    for (final interference in interferences) {
      if (interference.severity > 0.7) {
        warnings.add(
            'High severity interference detected: ${interference.description}');
      }
    }

    return warnings;
  }

  /// Generate opportunities for optimized goals
  List<String> _generateOpportunities(
    List<FinancialGoal> goals,
    Map<String, dynamic> currentFinancialState,
  ) {
    final opportunities = <String>[];

    // Check for income increase opportunities
    final monthlyIncome =
        (currentFinancialState['monthlyIncome'] as num?)?.toDouble() ?? 0.0;
    final totalRequired = goals.fold<double>(
        0.0, (sum, goal) => sum + goal.monthlyRequiredContribution);

    if (totalRequired > monthlyIncome * 0.3) {
      opportunities.add('Consider increasing income to achieve goals faster');
    }

    return opportunities;
  }

  /// Calculate resource competition between two goals
  double _calculateResourceCompetition(
    FinancialGoal goal1,
    FinancialGoal goal2,
    double availableResources,
  ) {
    final combined =
        goal1.monthlyRequiredContribution + goal2.monthlyRequiredContribution;
    if (availableResources <= 0) return 1.0;

    final overAllocation = (combined - availableResources) / availableResources;
    return overAllocation.clamp(0.0, 1.0);
  }

  /// Get timeframe category for a target date
  String _getTimeframe(DateTime targetDate) {
    final now = DateTime.now();
    final monthsUntil = targetDate.difference(now).inDays / 30;

    if (monthsUntil <= 6) return 'short_term';
    if (monthsUntil <= 24) return 'medium_term';
    return 'long_term';
  }
}
