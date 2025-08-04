import 'dart:math' as math;
import 'package:flutter/material.dart';
import 'income_service.dart';

/// Behavioral Calendar Engine Helper Methods
/// 
/// Contains implementation of helper methods for the Behavioral Calendar Engine:
/// - Calendar state analysis
/// - Redistribution opportunity identification
/// - Behavioral constraint application
/// - Spending prediction calculations
/// - Nudge generation
/// - Milestone tracking
class BehavioralCalendarHelpers {
  static final BehavioralCalendarHelpers _instance = BehavioralCalendarHelpers._internal();
  factory BehavioralCalendarHelpers() => _instance;
  BehavioralCalendarHelpers._internal();

  final IncomeService _incomeService = IncomeService();

  /// Analyze current calendar state for redistribution opportunities
  Map<String, dynamic> analyzeCalendarState(
    Map<int, Map<String, double>> monthlyCalendar,
    int currentDay,
    int daysInMonth,
  ) {
    final analysis = <String, dynamic>{};
    
    // Calculate overall spending velocity
    final pastDays = monthlyCalendar.keys.where((day) => day < currentDay).toList();
    final totalSpent = pastDays.fold<double>(0, (sum, day) {
      return sum + (monthlyCalendar[day]?['spent'] ?? 0.0);
    });
    
    final totalBudgeted = pastDays.fold<double>(0, (sum, day) {
      return sum + (monthlyCalendar[day]?['limit'] ?? 0.0);
    });
    
    analysis['total_spent'] = totalSpent;
    analysis['total_budgeted'] = totalBudgeted;
    analysis['spending_ratio'] = totalBudgeted > 0 ? totalSpent / totalBudgeted : 0.0;
    analysis['days_analyzed'] = pastDays.length;
    analysis['remaining_days'] = daysInMonth - currentDay;
    
    // Identify patterns
    final overspentDays = pastDays.where((day) {
      final spent = monthlyCalendar[day]?['spent'] ?? 0.0;
      final limit = monthlyCalendar[day]?['limit'] ?? 0.0;
      return spent > limit;
    }).length;
    
    final underspentDays = pastDays.where((day) {
      final spent = monthlyCalendar[day]?['spent'] ?? 0.0;
      final limit = monthlyCalendar[day]?['limit'] ?? 0.0;
      return spent < limit * 0.8; // Under 80% of budget
    }).length;
    
    analysis['overspent_days'] = overspentDays;
    analysis['underspent_days'] = underspentDays;
    analysis['budget_adherence_rate'] = pastDays.isNotEmpty 
      ? (pastDays.length - overspentDays) / pastDays.length 
      : 1.0;
    
    // Calculate surplus/deficit
    analysis['current_surplus'] = totalBudgeted - totalSpent;
    analysis['needs_redistribution'] = analysis['current_surplus'].abs() > 50.0; // $50 threshold
    
    return analysis;
  }

  /// Identify optimal redistribution opportunities
  List<Map<String, dynamic>> identifyRedistributionOpportunities(
    Map<int, Map<String, double>> monthlyCalendar,
    Map<String, dynamic> analysis,
    IncomeTier tier,
    BehavioralProfile? profile,
  ) {
    final opportunities = <Map<String, dynamic>>[];
    final currentDay = DateTime.now().day;
    final remainingDays = analysis['remaining_days'] as int;
    final surplus = analysis['current_surplus'] as double;
    
    if (surplus.abs() < 20.0) return opportunities; // Not worth redistributing small amounts
    
    if (surplus > 0) {
      // We have extra money to redistribute to future days
      final futureDays = monthlyCalendar.keys.where((day) => day > currentDay).toList()..sort();
      final redistributionPerDay = surplus / futureDays.length;
      
      // Prioritize upcoming high-spending days (weekends, etc.)
      for (final day in futureDays) {
        final dayOfWeek = DateTime(DateTime.now().year, DateTime.now().month, day).weekday;
        var priority = 0.5;
        
        if (dayOfWeek >= 6) priority = 0.8; // Weekend
        if (dayOfWeek == 5) priority = 0.7; // Friday
        
        opportunities.add({
          'type': 'increase_budget',
          'day': day,
          'amount': redistributionPerDay * priority,
          'reason': 'Surplus from underspending in previous days',
          'priority': priority,
        });
      }
    } else {
      // We're overspent - need to reduce future budgets
      final futureDays = monthlyCalendar.keys.where((day) => day > currentDay).toList()..sort();
      final reductionPerDay = surplus.abs() / futureDays.length;
      
      // Reduce budgets more on discretionary days
      for (final day in futureDays) {
        final dayOfWeek = DateTime(DateTime.now().year, DateTime.now().month, day).weekday;
        var reduction = reductionPerDay;
        
        if (dayOfWeek >= 6) reduction *= 1.2; // Reduce weekend spending more
        
        opportunities.add({
          'type': 'decrease_budget',
          'day': day,\n          'amount': -reduction,
          'reason': 'Compensation for previous overspending',
          'priority': 0.8,
        });
      }
    }
    
    return opportunities;
  }

  /// Apply behavioral constraints to redistribution
  List<Map<String, dynamic>> applyBehavioralRedistributionConstraints(
    List<Map<String, dynamic>> opportunities,
    IncomeTier tier,
    BehavioralProfile? profile,
  ) {
    final constrainedOpportunities = <Map<String, dynamic>>[];
    
    for (final opportunity in opportunities) {
      var amount = opportunity['amount'] as double;
      var priority = opportunity['priority'] as double;
      
      // Apply tier-specific constraints
      switch (tier) {
        case IncomeTier.low:
          // Low tier users need smaller, less dramatic changes
          amount *= 0.7;
          break;
        case IncomeTier.lowerMiddle:
          amount *= 0.8;
          break;
        case IncomeTier.middle:
          // No adjustment needed
          break;
        case IncomeTier.upperMiddle:
        case IncomeTier.high:
          // Higher tiers can handle larger adjustments
          amount *= 1.1;
          break;
      }
      
      // Apply behavioral profile constraints
      if (profile != null) {
        switch (profile.riskTolerance) {
          case RiskTolerance.low:
            amount *= 0.8;
            break;
          case RiskTolerance.high:
            amount *= 1.2;
            break;
          case RiskTolerance.moderate:
            break;
        }
        
        // Spenders need more conservative adjustments
        if (profile.spendingPersonality == SpendingPersonality.spender) {
          amount *= 0.9;
        }
      }
      
      // Only include opportunities above minimum threshold
      if (amount.abs() >= 10.0) {
        constrainedOpportunities.add({
          ...opportunity,
          'amount': amount,
          'priority': priority,
        });
      }
    }
    
    return constrainedOpportunities;
  }

  /// Calculate base day spending prediction
  double calculateBaseDayPrediction(
    Map<String, List<double>>? historicalSpending,
    int dayOfWeek,
    IncomeTier tier,
  ) {
    if (historicalSpending == null) {
      // Fallback to tier-based estimates
      return _getTierBaseDailySpending(tier, dayOfWeek);
    }
    
    final dayName = _getDayName(dayOfWeek);
    final historicalForDay = historicalSpending[dayName] ?? [];
    
    if (historicalForDay.isEmpty) {
      return _getTierBaseDailySpending(tier, dayOfWeek);
    }
    
    // Use median for more robust prediction
    final sorted = [...historicalForDay]..sort();
    final median = sorted.length % 2 == 0
        ? (sorted[sorted.length ~/ 2 - 1] + sorted[sorted.length ~/ 2]) / 2
        : sorted[sorted.length ~/ 2];
    
    return median;
  }

  /// Calculate behavioral prediction adjustment
  double calculateBehavioralPredictionAdjustment(
    BehavioralProfile? profile,
    int dayOfWeek,
    IncomeTier tier,
  ) {
    if (profile == null) return 1.0;
    
    var adjustment = 1.0;
    
    // Weekend adjustments based on personality
    if (dayOfWeek >= 6) {
      switch (profile.spendingPersonality) {
        case SpendingPersonality.saver:
          adjustment *= 0.9; // Savers spend less on weekends
          break;
        case SpendingPersonality.spender:
          adjustment *= 1.3; // Spenders increase weekend spending
          break;
        case SpendingPersonality.balanced:
          adjustment *= 1.1; // Moderate increase
          break;
      }
    }
    
    // Impulsivity adjustments
    if (profile.impulsivityScore > 0.7) {
      adjustment *= 1.1; // High impulsivity increases spending
    } else if (profile.impulsivityScore < 0.3) {
      adjustment *= 0.95; // Low impulsivity decreases spending
    }
    
    return adjustment;
  }

  /// Calculate calendar context adjustment (holidays, paydays, etc.)
  double calculateCalendarContextAdjustment(DateTime date, IncomeTier tier) {
    var adjustment = 1.0;
    
    // Payday effects (assume bi-weekly paydays on Fridays)
    final dayOfMonth = date.day;
    final dayOfWeek = date.weekday;
    
    if (dayOfWeek == 5 && (dayOfMonth <= 7 || (dayOfMonth >= 15 && dayOfMonth <= 21))) {
      // Payday Friday
      adjustment *= 1.2;
    }
    
    // Month-end effects
    if (dayOfMonth >= 28) {
      adjustment *= 0.9; // People tend to spend less at month-end
    }
    
    // Holiday proximity effects
    final month = date.month;
    if (month == 12) {
      adjustment *= 1.4; // December holiday spending
    } else if (month == 11) {
      adjustment *= 1.2; // November holiday preparation
    } else if (month == 1) {
      adjustment *= 0.8; // January recovery
    }
    
    return adjustment;
  }

  /// Generate time-based nudges
  List<Map<String, dynamic>> generateTimeBasedNudges(
    DateTime currentDate,
    IncomeTier tier,
    double remainingBudget,
    int remainingDays,
  ) {
    final nudges = <Map<String, dynamic>>[];
    final dayOfWeek = currentDate.weekday;
    final dayOfMonth = currentDate.day;
    
    // Monday motivation
    if (dayOfWeek == 1) {
      nudges.add({
        'type': 'weekly_start',
        'message': 'New week, fresh budget! You have \$${remainingBudget.toStringAsFixed(0)} to work with.',
        'effectiveness': 0.8,
        'icon': Icons.wb_sunny,
        'color': Colors.green,
      });
    }
    
    // Friday warning
    if (dayOfWeek == 5) {
      final dailyAverage = remainingDays > 0 ? remainingBudget / remainingDays : 0.0;
      nudges.add({
        'type': 'weekend_preparation',
        'message': 'Weekend ahead! Your daily average for the rest of the month: \$${dailyAverage.toStringAsFixed(0)}',
        'effectiveness': 0.9,
        'icon': Icons.weekend,
        'color': Colors.orange,
      });
    }
    
    // Month-end urgency
    if (dayOfMonth >= 25) {
      nudges.add({
        'type': 'month_end',
        'message': 'Month-end approaching! Stay strong with your remaining \$${remainingBudget.toStringAsFixed(0)}.',
        'effectiveness': 0.7,
        'icon': Icons.flag,
        'color': Colors.red,
      });
    }
    
    return nudges;
  }

  /// Generate day-of-week specific nudges
  List<Map<String, dynamic>> generateDayOfWeekNudges(
    int dayOfWeek,
    IncomeTier tier,
    double remainingBudget,
  ) {
    final nudges = <Map<String, dynamic>>[];
    final patterns = _incomeService.getBehavioralSpendingPatterns(tier);
    
    // Weekend nudges
    if (dayOfWeek >= 6) {
      nudges.add({
        'type': 'weekend_awareness',
        'message': 'Weekend spending tends to be 30% higher. Budget accordingly!',
        'effectiveness': 0.8,
        'icon': Icons.weekend,
        'color': Colors.blue,
      });
    }
    
    // Midweek momentum
    if (dayOfWeek == 3) {
      nudges.add({
        'type': 'midweek_check',
        'message': 'Midweek check-in: How are you tracking against your budget?',
        'effectiveness': 0.6,
        'icon': Icons.trending_up,
        'color': Colors.purple,
      });
    }
    
    return nudges;
  }

  /// Generate budget status nudges
  List<Map<String, dynamic>> generateBudgetStatusNudges(
    double remainingBudget,
    int remainingDays,
    IncomeTier tier,
  ) {
    final nudges = <Map<String, dynamic>>[];
    final dailyAverage = remainingDays > 0 ? remainingBudget / remainingDays : 0.0;
    
    if (remainingBudget < 0) {
      nudges.add({
        'type': 'overspent_alert',
        'message': 'You\\'re over budget by \$${remainingBudget.abs().toStringAsFixed(0)}. Time to tighten up!',
        'effectiveness': 0.9,
        'icon': Icons.warning,
        'color': Colors.red,
      });
    } else if (dailyAverage < 20) {
      nudges.add({
        'type': 'low_budget_warning',
        'message': 'Only \$${dailyAverage.toStringAsFixed(0)}/day remaining. Consider meal prep and free activities.',
        'effectiveness': 0.8,
        'icon': Icons.savings,
        'color': Colors.orange,
      });
    } else if (remainingBudget > dailyAverage * remainingDays * 1.5) {
      nudges.add({
        'type': 'surplus_opportunity',
        'message': 'You\\'re doing great! Consider saving the extra or treating yourself mindfully.',
        'effectiveness': 0.7,
        'icon': Icons.celebration,
        'color': Colors.green,
      });
    }
    
    return nudges;
  }

  // Helper methods
  double _getTierBaseDailySpending(IncomeTier tier, int dayOfWeek) {
    var base = 0.0;
    switch (tier) {
      case IncomeTier.low: base = 30.0; break;
      case IncomeTier.lowerMiddle: base = 45.0; break;
      case IncomeTier.middle: base = 75.0; break;
      case IncomeTier.upperMiddle: base = 120.0; break;
      case IncomeTier.high: base = 200.0; break;
    }
    
    // Weekend multiplier
    if (dayOfWeek >= 6) {
      base *= 1.3;
    }
    
    return base;
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
}