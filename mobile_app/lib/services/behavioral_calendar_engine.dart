import 'package:flutter/material.dart';
import 'income_service.dart';
import 'advanced_financial_engine.dart';
import 'logging_service.dart';

/// Enhanced Behavioral Calendar Engine for MITA
/// 
/// Implements advanced calendar-based budgeting with behavioral psychology:
/// - Dynamic daily budget allocation based on spending patterns
/// - Behavioral nudges based on calendar context
/// - Seasonal spending adjustments
/// - Weekend/weekday behavioral differences
/// - Predictive budget redistribution
/// - Celebration and milestone tracking
class BehavioralCalendarEngine {
  static final BehavioralCalendarEngine _instance = BehavioralCalendarEngine._internal();
  factory BehavioralCalendarEngine() => _instance;
  BehavioralCalendarEngine._internal();

  final IncomeService _incomeService = IncomeService();
  final AdvancedFinancialEngine _financialEngine = AdvancedFinancialEngine();

  // ===========================================================================
  // ADVANCED DAILY BUDGET CALCULATION
  // ===========================================================================

  /// Calculate daily budget with behavioral and calendar awareness
  /// 
  /// Factors considered:
  /// - Day of week spending patterns
  /// - Payday cycles and income tier behavior
  /// - Remaining days in month
  /// - Historical spending velocity
  /// - Seasonal adjustments
  /// - Goal-oriented modifications
  /// - Emergency fund protection
  Map<String, dynamic> calculateBehavioralDailyBudget({
    required double monthlyIncome,
    required IncomeTier incomeTier,
    required DateTime currentDate,
    Map<String, double>? monthToDateSpending,
    Map<String, List<double>>? historicalDailySpending, // Last 90 days
    List<FinancialGoal>? activeGoals,
    BehavioralProfile? behavioralProfile,
  }) {
    try {
      logInfo('Calculating behavioral daily budget for ${currentDate.toIso8601String()}');

      final daysInMonth = DateTime(currentDate.year, currentDate.month + 1, 0).day;
      final remainingDays = daysInMonth - currentDate.day + 1;
      final dayOfWeek = currentDate.weekday;
      
      // Step 1: Get base daily allocation
      final baseDailyAmount = monthlyIncome / daysInMonth;
      
      // Step 2: Apply behavioral spending patterns
      final behavioralAdjustment = _calculateBehavioralDayAdjustment(
        incomeTier, 
        dayOfWeek, 
        behavioralProfile
      );
      
      // Step 3: Apply historical spending velocity adjustments
      final velocityAdjustment = _calculateSpendingVelocityAdjustment(
        historicalDailySpending, 
        dayOfWeek, 
        incomeTier
      );
      
      // Step 4: Apply month-to-date spending corrections
      final spendingCorrection = _calculateSpendingCorrection(
        monthToDateSpending,
        monthlyIncome,
        currentDate.day,
        daysInMonth
      );
      
      // Step 5: Apply seasonal and calendar adjustments
      final seasonalAdjustment = _calculateSeasonalAdjustment(
        currentDate, 
        incomeTier
      );
      
      // Step 6: Apply goal-oriented adjustments
      final goalAdjustment = _calculateGoalBasedAdjustment(
        activeGoals, 
        remainingDays, 
        incomeTier
      );

      // Calculate final daily budget
      final adjustedDailyBudget = baseDailyAmount * 
        behavioralAdjustment * 
        velocityAdjustment * 
        seasonalAdjustment * 
        (1 + spendingCorrection) * 
        (1 + goalAdjustment);

      // Apply safety bounds
      final safeDailyBudget = _applySafetyBounds(
        adjustedDailyBudget, 
        monthlyIncome, 
        incomeTier, 
        remainingDays
      );

      // Generate behavioral insights and recommendations
      final insights = _generateDailyBudgetInsights(
        safeDailyBudget,
        baseDailyAmount,
        dayOfWeek,
        incomeTier,
        currentDate
      );

      return {
        'daily_budget': safeDailyBudget,
        'base_daily_amount': baseDailyAmount,
        'adjustments': {
          'behavioral': behavioralAdjustment,
          'velocity': velocityAdjustment,
          'spending_correction': spendingCorrection,
          'seasonal': seasonalAdjustment,
          'goal_based': goalAdjustment,
        },
        'insights': insights,
        'day_type': _getDayType(dayOfWeek),
        'spending_confidence': _calculateSpendingConfidence(historicalDailySpending, dayOfWeek),
        'behavioral_nudges': _generateDailyNudges(incomeTier, dayOfWeek, safeDailyBudget),
      };

    } catch (e, stackTrace) {
      logError('Error calculating behavioral daily budget: $e', error: e, stackTrace: stackTrace);
      return {
        'daily_budget': monthlyIncome / 30, // Safe fallback
        'base_daily_amount': monthlyIncome / 30,
        'adjustments': {},
        'insights': ['Unable to calculate optimal daily budget - using safe default'],
        'day_type': 'unknown',
        'spending_confidence': 0.5,
        'behavioral_nudges': [],
      };
    }
  }

  // ===========================================================================
  // INTELLIGENT BUDGET REDISTRIBUTION
  // ===========================================================================

  /// Calculate optimal budget redistribution across remaining days
  /// 
  /// Uses advanced algorithms to:
  /// - Identify optimal redistribution opportunities
  /// - Consider behavioral constraints
  /// - Maintain psychological comfort zones
  /// - Predict future spending needs
  Map<String, dynamic> calculateIntelligentRedistribution({
    required Map<int, Map<String, double>> monthlyCalendar, // day -> {spent, limit}
    required double monthlyIncome,
    required IncomeTier incomeTier,
    required DateTime currentDate,
    BehavioralProfile? behavioralProfile,
    Map<String, List<double>>? historicalSpending,
  }) {
    try {
      logInfo('Calculating intelligent budget redistribution');

      final daysInMonth = DateTime(currentDate.year, currentDate.month + 1, 0).day;
      final currentDay = currentDate.day;
      
      // Analyze current state
      final analysis = _analyzeCalendarState(monthlyCalendar, currentDay, daysInMonth);
      
      // Identify redistribution opportunities
      final opportunities = _identifyRedistributionOpportunities(
        monthlyCalendar, 
        analysis, 
        incomeTier,
        behavioralProfile
      );
      
      // Calculate optimal transfers
      final transfers = _calculateOptimalTransfers(
        opportunities, 
        analysis, 
        incomeTier,
        currentDate
      );
      
      // Apply behavioral constraints
      final constrainedTransfers = _applyBehavioralRedistributionConstraints(
        transfers, 
        incomeTier, 
        behavioralProfile
      );
      
      // Generate new calendar with redistribution applied
      final redistributedCalendar = _applyRedistributionToCalendar(
        monthlyCalendar, 
        constrainedTransfers
      );
      
      // Validate redistribution safety
      final validation = _validateRedistribution(
        redistributedCalendar, 
        monthlyIncome, 
        incomeTier
      );

      return {
        'original_calendar': monthlyCalendar,
        'redistributed_calendar': redistributedCalendar,
        'transfers': constrainedTransfers,
        'total_transferred': constrainedTransfers.fold<double>(0, (sum, transfer) => sum + transfer['amount']),
        'analysis': analysis,
        'validation': validation,
        'confidence_score': _calculateRedistributionConfidence(constrainedTransfers, analysis),
        'behavioral_impact': _assessRedistributionBehavioralImpact(constrainedTransfers, incomeTier),
        'recommendations': _generateRedistributionRecommendations(analysis, incomeTier),
      };

    } catch (e, stackTrace) {
      logError('Error calculating intelligent redistribution: $e', error: e, stackTrace: stackTrace);
      return {
        'original_calendar': monthlyCalendar,
        'redistributed_calendar': monthlyCalendar, // No changes on error
        'transfers': [],
        'total_transferred': 0.0,
        'analysis': {},
        'validation': {'is_safe': false, 'warnings': ['Redistribution calculation failed']},
        'confidence_score': 0.0,
        'behavioral_impact': 'unknown',
        'recommendations': ['Review budget manually due to calculation error'],
      };
    }
  }

  // ===========================================================================
  // SPENDING PREDICTION AND PATTERN ANALYSIS
  // ===========================================================================

  /// Predict spending for remaining days in month
  Map<String, dynamic> predictRemainingMonthSpending({
    required Map<int, Map<String, double>> monthlyCalendar,
    required DateTime currentDate,
    required IncomeTier incomeTier,
    Map<String, List<double>>? historicalDailySpending,
    BehavioralProfile? behavioralProfile,
  }) {
    try {
      final daysInMonth = DateTime(currentDate.year, currentDate.month + 1, 0).day;
      final remainingDays = List.generate(
        daysInMonth - currentDate.day, 
        (index) => currentDate.day + index + 1
      );

      final predictions = <int, double>{};
      final confidenceScores = <int, double>{};
      
      for (final day in remainingDays) {
        final dayOfWeek = DateTime(currentDate.year, currentDate.month, day).weekday;
        
        // Base prediction using historical patterns
        final basePrediction = _calculateBaseDayPrediction(
          historicalDailySpending, 
          dayOfWeek, 
          incomeTier
        );
        
        // Apply behavioral adjustments
        final behavioralAdjustment = _calculateBehavioralPredictionAdjustment(
          behavioralProfile, 
          dayOfWeek, 
          incomeTier
        );
        
        // Apply calendar context adjustments
        final calendarAdjustment = _calculateCalendarContextAdjustment(
          DateTime(currentDate.year, currentDate.month, day),
          incomeTier
        );
        
        final finalPrediction = basePrediction * behavioralAdjustment * calendarAdjustment;
        
        predictions[day] = finalPrediction;
        confidenceScores[day] = _calculatePredictionConfidence(
          historicalDailySpending, 
          dayOfWeek, 
          incomeTier
        );
      }

      final totalPredicted = predictions.values.fold(0.0, (sum, value) => sum + value);
      final averageConfidence = confidenceScores.values.fold(0.0, (sum, value) => sum + value) / confidenceScores.length;

      return {
        'daily_predictions': predictions,
        'confidence_scores': confidenceScores,
        'total_predicted': totalPredicted,
        'average_confidence': averageConfidence,
        'risk_factors': _identifySpendingRiskFactors(predictions, incomeTier),
        'recommendations': _generateSpendingPredictionRecommendations(predictions, incomeTier),
      };

    } catch (e, stackTrace) {
      logError('Error predicting remaining month spending: $e', error: e, stackTrace: stackTrace);
      return {
        'daily_predictions': <int, double>{},
        'confidence_scores': <int, double>{},
        'total_predicted': 0.0,
        'average_confidence': 0.0,
        'risk_factors': [],
        'recommendations': ['Unable to generate spending predictions'],
      };
    }
  }

  // ===========================================================================
  // BEHAVIORAL NUDGE GENERATION
  // ===========================================================================

  /// Generate context-aware behavioral nudges
  List<Map<String, dynamic>> generateCalendarNudges({
    required DateTime currentDate,
    required IncomeTier incomeTier,
    required double remainingBudget,
    required int remainingDays,
    Map<String, double>? todaySpending,
    BehavioralProfile? behavioralProfile,
  }) {
    final nudges = <Map<String, dynamic>>[];
    final dayOfWeek = currentDate.weekday;
    final patterns = _incomeService.getBehavioralSpendingPatterns(incomeTier);
    
    try {
      // Time-based nudges
      nudges.addAll(_generateTimeBasedNudges(currentDate, incomeTier, remainingBudget, remainingDays));
      
      // Day-of-week specific nudges
      nudges.addAll(_generateDayOfWeekNudges(dayOfWeek, incomeTier, remainingBudget));
      
      // Budget status nudges
      nudges.addAll(_generateBudgetStatusNudges(remainingBudget, remainingDays, incomeTier));
      
      // Behavioral pattern nudges
      if (behavioralProfile != null) {
        nudges.addAll(_generateBehavioralPatternNudges(behavioralProfile, incomeTier, currentDate));
      }
      
      // Seasonal/contextual nudges
      nudges.addAll(_generateSeasonalNudges(currentDate, incomeTier));

      // Sort by effectiveness and relevance
      nudges.sort((a, b) => (b['effectiveness'] as double).compareTo(a['effectiveness'] as double));
      
      return nudges.take(3).toList(); // Return top 3 most effective nudges

    } catch (e, stackTrace) {
      logError('Error generating calendar nudges: $e', error: e, stackTrace: stackTrace);
      return [];
    }
  }

  // ===========================================================================
  // MILESTONE AND CELEBRATION TRACKING
  // ===========================================================================

  /// Track and celebrate financial milestones
  Map<String, dynamic> trackFinancialMilestones({
    required Map<int, Map<String, double>> monthlyCalendar,
    required DateTime currentDate,
    required IncomeTier incomeTier,
    required double monthlyIncome,
    List<FinancialGoal>? goals,
  }) {
    final milestones = <Map<String, dynamic>>[];
    final celebrations = <Map<String, dynamic>>[];
    
    try {
      // Daily budget adherence milestones
      final adherenceStreak = _calculateBudgetAdherenceStreak(monthlyCalendar, currentDate.day);
      if (adherenceStreak >= _getMilestoneThreshold(incomeTier, 'adherence_streak')) {
        milestones.add({
          'type': 'adherence_streak',
          'value': adherenceStreak,
          'title': '$adherenceStreak Days On Track!',
          'description': 'You\'ve stayed within budget for $adherenceStreak consecutive days',
          'reward_points': adherenceStreak * 10,
          'tier_bonus': _getTierBonusMultiplier(incomeTier),
        });
      }

      // Savings milestones
      final monthToDateSavings = _calculateMonthToDateSavings(monthlyCalendar, monthlyIncome);
      final savingsGoalProgress = monthToDateSavings / (monthlyIncome * 0.20); // 20% savings target
      if (savingsGoalProgress >= 0.5) {
        milestones.add({
          'type': 'savings_progress',
          'value': savingsGoalProgress,
          'title': 'Savings Champion!',
          'description': 'You\'re ${(savingsGoalProgress * 100).toStringAsFixed(0)}% toward your monthly savings goal',
          'reward_points': (savingsGoalProgress * 100).round(),
          'tier_bonus': _getTierBonusMultiplier(incomeTier),
        });
      }

      // Goal-specific milestones
      if (goals != null) {
        for (final goal in goals) {
          final progress = goal.currentAmount / goal.targetAmount;
          if (_isGoalMilestoneReached(goal, progress)) {
            milestones.add({
              'type': 'goal_milestone',
              'goal_id': goal.id,
              'value': progress,
              'title': '${goal.title} Progress!',
              'description': 'You\'re ${(progress * 100).toStringAsFixed(0)}% toward your ${goal.title} goal',
              'reward_points': (progress * 500).round(),
              'tier_bonus': _getTierBonusMultiplier(incomeTier),
            });
          }
        }
      }

      // Generate celebrations for achieved milestones
      for (final milestone in milestones) {
        celebrations.add(_generateCelebration(milestone, incomeTier));
      }

      return {
        'milestones': milestones,
        'celebrations': celebrations,
        'total_reward_points': milestones.fold<int>(0, (sum, m) => sum + (m['reward_points'] as int)),
        'next_milestone': _getNextMilestone(monthlyCalendar, incomeTier, goals),
        'achievement_level': _calculateAchievementLevel(milestones, incomeTier),
      };

    } catch (e, stackTrace) {
      logError('Error tracking financial milestones: $e', error: e, stackTrace: stackTrace);
      return {
        'milestones': [],
        'celebrations': [],
        'total_reward_points': 0,
        'next_milestone': null,
        'achievement_level': 'novice',
      };
    }
  }

  // ===========================================================================
  // PRIVATE HELPER METHODS
  // ===========================================================================

  double _calculateBehavioralDayAdjustment(IncomeTier incomeTier, int dayOfWeek, BehavioralProfile? profile) {
    // Weekend spending patterns
    double weekendMultiplier = 1.0;
    if (dayOfWeek >= 6) { // Weekend
      switch (incomeTier) {
        case IncomeTier.low:
          weekendMultiplier = 0.8; // Lower weekend spending for budget constraints
          break;
        case IncomeTier.lowerMiddle:
          weekendMultiplier = 1.1; // Slightly higher weekend spending
          break;
        case IncomeTier.middle:
        case IncomeTier.upperMiddle:
        case IncomeTier.high:
          weekendMultiplier = 1.3; // Higher weekend spending for entertainment
          break;
      }
    }

    // Behavioral profile adjustments
    double profileAdjustment = 1.0;
    if (profile != null) {
      switch (profile.spendingPersonality) {
        case SpendingPersonality.saver:
          profileAdjustment = 0.9;
          break;
        case SpendingPersonality.spender:
          profileAdjustment = 1.1;
          break;
        case SpendingPersonality.balanced:
          profileAdjustment = 1.0;
          break;
      }
    }

    return weekendMultiplier * profileAdjustment;
  }

  double _calculateSpendingVelocityAdjustment(Map<String, List<double>>? historicalSpending, int dayOfWeek, IncomeTier tier) {
    if (historicalSpending == null) return 1.0;
    
    // Calculate average spending for this day of week
    final dayName = _getDayName(dayOfWeek);
    final historicalForDay = historicalSpending[dayName] ?? [];
    
    if (historicalForDay.isEmpty) return 1.0;
    
    final averageForDay = historicalForDay.fold(0.0, (sum, amount) => sum + amount) / historicalForDay.length;
    final totalAverage = historicalSpending.values
        .expand((list) => list)
        .fold(0.0, (sum, amount) => sum + amount) / 
        historicalSpending.values.expand((list) => list).length;
    
    if (totalAverage == 0) return 1.0;
    
    return (averageForDay / totalAverage).clamp(0.5, 2.0);
  }

  double _calculateSpendingCorrection(Map<String, double>? monthToDateSpending, double monthlyIncome, int currentDay, int daysInMonth) {
    if (monthToDateSpending == null) return 0.0;
    
    final totalSpent = monthToDateSpending.values.fold(0.0, (sum, amount) => sum + amount);
    final expectedSpent = monthlyIncome * (currentDay / daysInMonth);
    final spendingRatio = totalSpent / expectedSpent;
    
    // If overspending, reduce remaining daily budgets
    // If underspending, increase remaining daily budgets
    if (spendingRatio > 1.1) {
      return -0.1; // Reduce by 10%
    } else if (spendingRatio < 0.9) {
      return 0.05; // Increase by 5%
    }
    
    return 0.0;
  }

  double _calculateSeasonalAdjustment(DateTime currentDate, IncomeTier tier) {
    final month = currentDate.month;
    
    // Holiday season adjustments (November-December)
    if (month == 11 || month == 12) {
      switch (tier) {
        case IncomeTier.low:
          return 0.9; // Reduce spending to save for holidays
        case IncomeTier.lowerMiddle:
        case IncomeTier.middle:
          return 1.1; // Slight increase for holiday spending
        case IncomeTier.upperMiddle:
        case IncomeTier.high:
          return 1.2; // Higher holiday spending capacity
      }
    }
    
    // Back-to-school season (August-September)
    if (month == 8 || month == 9) {
      return 1.05; // Slight increase for seasonal needs
    }
    
    return 1.0; // No seasonal adjustment
  }

  double _calculateGoalBasedAdjustment(List<FinancialGoal>? goals, int remainingDays, IncomeTier tier) {
    if (goals == null || goals.isEmpty) return 0.0;
    
    double totalGoalAdjustment = 0.0;
    for (final goal in goals) {
      if (goal.isActive && goal.monthlyContribution > 0) {
        final dailyContribution = goal.monthlyContribution / 30; // Approximate daily contribution
        totalGoalAdjustment += dailyContribution;
      }
    }
    
    // Convert to percentage adjustment
    const baseDaily = 100.0; // Assume $100 base daily budget for calculation
    return totalGoalAdjustment / baseDaily;
  }

  double _applySafetyBounds(double calculatedBudget, double monthlyIncome, IncomeTier tier, int remainingDays) {
    final minDailyBudget = monthlyIncome * 0.01; // Minimum 1% of monthly income
    final maxDailyBudget = monthlyIncome * 0.15; // Maximum 15% of monthly income
    
    return calculatedBudget.clamp(minDailyBudget, maxDailyBudget);
  }

  List<String> _generateDailyBudgetInsights(double dailyBudget, double baseBudget, int dayOfWeek, IncomeTier tier, DateTime date) {
    final insights = <String>[];
    final dayType = _getDayType(dayOfWeek);
    final tierName = _incomeService.getIncomeTierName(tier);
    
    if (dailyBudget > baseBudget * 1.1) {
      insights.add('Your $dayType budget is ${((dailyBudget / baseBudget - 1) * 100).toStringAsFixed(0)}% higher than average');
    } else if (dailyBudget < baseBudget * 0.9) {
      insights.add('Your $dayType budget is ${((1 - dailyBudget / baseBudget) * 100).toStringAsFixed(0)}% lower to help you stay on track');
    }
    
    insights.add('${tierName}s typically spend \$${dailyBudget.toStringAsFixed(0)} on ${dayType}s');
    
    return insights;
  }

  String _getDayType(int dayOfWeek) {
    if (dayOfWeek >= 6) return 'weekend';
    return 'weekday';
  }

  String _getDayName(int dayOfWeek) {
    switch (dayOfWeek) {
      case 1: return 'monday';
      case 2: return 'tuesday';
      case 3: return 'wednesday';
      case 4: return 'thursday';
      case 5: return 'friday';
      case 6: return 'saturday';
      case 7: return 'sunday';
      default: return 'unknown';
    }
  }

  double _calculateSpendingConfidence(Map<String, List<double>>? historicalSpending, int dayOfWeek) {
    if (historicalSpending == null) return 0.5;
    
    final dayName = _getDayName(dayOfWeek);
    final historicalForDay = historicalSpending[dayName] ?? [];
    
    if (historicalForDay.length < 4) return 0.3; // Low confidence with little data
    if (historicalForDay.length < 8) return 0.6; // Medium confidence
    return 0.8; // High confidence with sufficient data
  }

  List<Map<String, dynamic>> _generateDailyNudges(IncomeTier tier, int dayOfWeek, double dailyBudget) {
    final nudges = <Map<String, dynamic>>[];
    final patterns = _incomeService.getBehavioralSpendingPatterns(tier);
    final tierNudges = _incomeService.getTierSpecificNudges(tier, null, dailyBudget * 30);
    
    // Add day-specific nudges
    if (dayOfWeek >= 6) { // Weekend
      nudges.add({
        'type': 'weekend_awareness',
        'message': 'Weekend spending ahead! You have \$${dailyBudget.toStringAsFixed(0)} budgeted for today',
        'effectiveness': 0.7,
        'icon': Icons.weekend,
        'color': Colors.orange,
      });
    }
    
    // Add tier-specific nudges
    for (final nudge in tierNudges.take(2)) {
      nudges.add({
        ...nudge,
        'icon': _getNudgeIcon(nudge['type'] as String),
        'color': _getNudgeColor(nudge['type'] as String),
      });
    }
    
    return nudges;
  }

  IconData _getNudgeIcon(String type) {
    switch (type) {
      case 'loss_framing': return Icons.shield;
      case 'social_proof': return Icons.group;
      case 'progress_framing': return Icons.trending_up;
      case 'opportunity_cost': return Icons.calculate;
      case 'tax_efficiency': return Icons.receipt_long;
      case 'impact_framing': return Icons.favorite;
      default: return Icons.lightbulb;
    }
  }

  Color _getNudgeColor(String type) {
    switch (type) {
      case 'loss_framing': return Colors.red.shade600;
      case 'social_proof': return Colors.blue.shade600;
      case 'progress_framing': return Colors.green.shade600;
      case 'opportunity_cost': return Colors.purple.shade600;
      case 'tax_efficiency': return Colors.orange.shade600;
      case 'impact_framing': return Colors.pink.shade600;
      default: return Colors.grey.shade600;
    }
  }

  // Additional helper methods would be implemented here for:
  // - _analyzeCalendarState
  // - _identifyRedistributionOpportunities
  // - _calculateOptimalTransfers
  // - _applyBehavioralRedistributionConstraints
  // - _applyRedistributionToCalendar
  // - _validateRedistribution
  // - _calculateRedistributionConfidence
  // - _assessRedistributionBehavioralImpact
  // - _generateRedistributionRecommendations
  // - _calculateBaseDayPrediction
  // - _calculateBehavioralPredictionAdjustment
  // - _calculateCalendarContextAdjustment
  // - _calculatePredictionConfidence
  // - _identifySpendingRiskFactors
  // - _generateSpendingPredictionRecommendations
  // - _generateTimeBasedNudges
  // - _generateDayOfWeekNudges
  // - _generateBudgetStatusNudges
  // - _generateBehavioralPatternNudges
  // - _generateSeasonalNudges
  // - _calculateBudgetAdherenceStreak
  // - _getMilestoneThreshold
  // - _calculateMonthToDateSavings
  // - _getTierBonusMultiplier
  // - _isGoalMilestoneReached
  // - _generateCelebration
  // - _getNextMilestone
  // - _calculateAchievementLevel
}