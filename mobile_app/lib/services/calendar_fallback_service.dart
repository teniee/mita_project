import 'dart:math';
import 'logging_service.dart';
import 'income_service.dart';

/// Service that provides realistic fallback calendar data when backend is unavailable
class CalendarFallbackService {
  static final CalendarFallbackService _instance = CalendarFallbackService._internal();
  factory CalendarFallbackService() => _instance;
  CalendarFallbackService._internal();

  /// Generate realistic calendar data based on user income and location
  Future<List<Map<String, dynamic>>> generateFallbackCalendarData({
    required double monthlyIncome,
    String? location,
    int? year,
    int? month,
  }) async {
    try {
      final currentYear = year ?? DateTime.now().year;
      final currentMonth = month ?? DateTime.now().month;
      final today = DateTime.now();

      // Calculate income tier and appropriate allocations
      final incomeTier = _getIncomeTier(monthlyIncome);
      final locationMultiplier = _getLocationMultiplier(location);
      final categoryAllocations =
          _getCategoryAllocations(incomeTier, monthlyIncome, locationMultiplier);

      // Calculate daily flexible budget
      final totalFlexibleBudget =
          categoryAllocations.values.fold<double>(0.0, (sum, amount) => sum + amount);

      // Get number of days in the month
      final daysInMonth = DateTime(currentYear, currentMonth + 1, 0).day;
      final baseDailyBudget = (totalFlexibleBudget / daysInMonth).round();

      List<Map<String, dynamic>> calendarDays = [];

      for (int day = 1; day <= daysInMonth; day++) {
        final currentDate = DateTime(currentYear, currentMonth, day);
        final isToday = currentDate.year == today.year &&
            currentDate.month == today.month &&
            currentDate.day == today.day;
        final isPastDay = currentDate.isBefore(today);

        // Apply realistic daily budget variations
        final dailyBudgetVariation = _getDailyBudgetVariation(
          day: day,
          dayOfWeek: currentDate.weekday,
          baseBudget: baseDailyBudget,
          incomeTier: incomeTier,
        );

        final dailyLimit = dailyBudgetVariation.round();

        // Calculate realistic spending for past days
        int spent = 0;
        String status = 'good';

        if (isPastDay) {
          spent = _calculateRealisticSpending(
            dailyLimit: dailyLimit,
            day: day,
            dayOfWeek: currentDate.weekday,
            incomeTier: incomeTier,
            isWeekend: currentDate.weekday >= 6,
          );
          status = _calculateDayStatus(spent, dailyLimit);
        } else if (isToday) {
          // For today, show some spending progress
          spent = _calculateTodaySpending(dailyLimit, incomeTier);
          status = _calculateDayStatus(spent, dailyLimit);
        }

        calendarDays.add({
          'day': day,
          'limit': dailyLimit,
          'spent': spent,
          'status': status,
          'categories': _generateDailyCategoryBreakdown(dailyLimit, categoryAllocations),
          'is_today': isToday,
          'is_weekend': currentDate.weekday >= 6,
          'day_of_week': currentDate.weekday,
        });
      }

      logDebug('Generated fallback calendar data for $currentMonth/$currentYear',
          tag: 'CALENDAR_FALLBACK',
          extra: {
            'monthly_income': monthlyIncome,
            'income_tier': incomeTier,
            'location': location,
            'days_generated': calendarDays.length,
            'total_budget': totalFlexibleBudget,
            'avg_daily_budget': baseDailyBudget,
          });

      return calendarDays;
    } catch (e) {
      logError('Failed to generate fallback calendar data', tag: 'CALENDAR_FALLBACK', error: e);
      return _generateMinimalFallbackData();
    }
  }

  /// Determine income tier for budget calculations
  String _getIncomeTier(double monthlyIncome) {
    final incomeService = IncomeService();
    final tier = incomeService.classifyIncome(monthlyIncome);
    return incomeService.getTierString(tier);
  }

  /// Get location-based cost multiplier
  double _getLocationMultiplier(String? location) {
    if (location == null) return 1.0;

    final locationLower = location.toLowerCase();

    // High-cost cities
    if (locationLower.contains('san francisco') ||
        locationLower.contains('new york') ||
        locationLower.contains('seattle') ||
        locationLower.contains('los angeles') ||
        locationLower.contains('boston')) {
      return 1.4;
    }

    // Medium-cost cities
    if (locationLower.contains('chicago') ||
        locationLower.contains('austin') ||
        locationLower.contains('denver') ||
        locationLower.contains('miami') ||
        locationLower.contains('portland')) {
      return 1.2;
    }

    // Low-cost areas
    if (locationLower.contains('midwest') ||
        locationLower.contains('south') ||
        locationLower.contains('rural')) {
      return 0.8;
    }

    return 1.0; // Default for unknown locations
  }

  /// Get category allocations based on income tier
  Map<String, double> _getCategoryAllocations(
      String incomeTier, double monthlyIncome, double locationMultiplier) {
    late Map<String, double> baseWeights;

    switch (incomeTier) {
      case 'low':
        baseWeights = {
          'food': 0.20, // Higher percentage for essentials
          'transportation': 0.18,
          'entertainment': 0.05,
          'shopping': 0.08,
          'healthcare': 0.06,
        };
        break;
      case 'mid_low':
        baseWeights = {
          'food': 0.18,
          'transportation': 0.16,
          'entertainment': 0.07,
          'shopping': 0.10,
          'healthcare': 0.05,
        };
        break;
      case 'mid':
        baseWeights = {
          'food': 0.15,
          'transportation': 0.15,
          'entertainment': 0.08,
          'shopping': 0.12,
          'healthcare': 0.05,
        };
        break;
      case 'mid_high':
        baseWeights = {
          'food': 0.12,
          'transportation': 0.12,
          'entertainment': 0.10,
          'shopping': 0.15,
          'healthcare': 0.04,
        };
        break;
      case 'high':
        baseWeights = {
          'food': 0.10,
          'transportation': 0.10,
          'entertainment': 0.12,
          'shopping': 0.18,
          'healthcare': 0.03,
        };
        break;
      default:
        baseWeights = {
          'food': 0.15,
          'transportation': 0.15,
          'entertainment': 0.08,
          'shopping': 0.12,
          'healthcare': 0.05,
        };
    }

    // Apply location multiplier and calculate actual amounts
    final Map<String, double> allocations = {};
    baseWeights.forEach((category, weight) {
      double multiplier = locationMultiplier;

      // Different categories affected differently by location
      if (category == 'food' || category == 'transportation') {
        multiplier = locationMultiplier; // Full impact
      } else if (category == 'entertainment') {
        multiplier = 1.0 + ((locationMultiplier - 1.0) * 0.7); // 70% impact
      } else {
        multiplier = 1.0 + ((locationMultiplier - 1.0) * 0.5); // 50% impact
      }

      allocations[category] = (monthlyIncome * weight * multiplier).roundToDouble();
    });

    return allocations;
  }

  /// Calculate daily budget variation based on patterns
  double _getDailyBudgetVariation({
    required int day,
    required int dayOfWeek,
    required int baseBudget,
    required String incomeTier,
  }) {
    double variation = baseBudget.toDouble();

    // Weekend effect (Friday, Saturday, Sunday typically higher spending)
    if (dayOfWeek == 5) {
      // Friday
      variation *= 1.3;
    } else if (dayOfWeek == 6 || dayOfWeek == 7) {
      // Weekend
      variation *= 1.5;
    } else if (dayOfWeek == 1) {
      // Monday (lower after weekend)
      variation *= 0.8;
    }

    // Payday effect (assuming mid-month and end-of-month paydays)
    if (day == 15 || day == 30 || day == 31) {
      variation *= 1.2;
    }

    // End of month tightening
    if (day > 25) {
      final dayFromEnd = DateTime(DateTime.now().year, DateTime.now().month + 1, 0).day - day;
      if (dayFromEnd < 3) {
        variation *= 0.7; // Tighten budget near month end
      }
    }

    // Income tier adjustments
    switch (incomeTier) {
      case 'low':
        // More consistent spending, less variation
        variation = baseBudget + (variation - baseBudget) * 0.5;
        break;
      case 'high':
        // More flexible, higher variation allowed
        variation = baseBudget + (variation - baseBudget) * 1.2;
        break;
    }

    return variation;
  }

  /// Calculate realistic spending for past days
  int _calculateRealisticSpending({
    required int dailyLimit,
    required int day,
    required int dayOfWeek,
    required String incomeTier,
    required bool isWeekend,
  }) {
    final random = Random(day); // Consistent randomness for same day

    // Base spending percentage (most people spend 70-90% of daily budget)
    double spendingRatio = 0.7 + (random.nextDouble() * 0.3);

    // Weekend adjustment
    if (isWeekend) {
      spendingRatio = 0.8 + (random.nextDouble() * 0.4); // 80-120%
    }

    // Income tier behavior
    switch (incomeTier) {
      case 'low':
        // More cautious spending, rarely exceed budget
        spendingRatio = 0.6 + (random.nextDouble() * 0.3); // 60-90%
        break;
      case 'high':
        // More flexible, occasional overspending
        spendingRatio = 0.7 + (random.nextDouble() * 0.5); // 70-120%
        break;
    }

    // Occasional overspending (10% chance)
    if (random.nextDouble() < 0.1) {
      spendingRatio *= 1.3;
    }

    return (dailyLimit * spendingRatio).round();
  }

  /// Calculate today's spending (partial day)
  int _calculateTodaySpending(int dailyLimit, String incomeTier) {
    final now = DateTime.now();
    final hourOfDay = now.hour;

    // Progress through the day (assuming most spending by 8 PM)
    double dayProgress = (hourOfDay / 20.0).clamp(0.0, 1.0);

    // Random factor for realism
    final random = Random();
    double spendingRatio = dayProgress * (0.6 + (random.nextDouble() * 0.4));

    return (dailyLimit * spendingRatio).round();
  }

  /// Calculate day status based on spending vs limit
  String _calculateDayStatus(int spent, int limit) {
    final ratio = spent / limit;

    if (ratio > 1.1) return 'over'; // >110%
    if (ratio > 0.85) return 'warning'; // 85-110%
    return 'good'; // <85%
  }

  /// Generate daily category breakdown
  Map<String, int> _generateDailyCategoryBreakdown(
      int dailyLimit, Map<String, double> monthlyAllocations) {
    final breakdown = <String, int>{};

    monthlyAllocations.forEach((category, monthlyAmount) {
      final dailyAmount = (monthlyAmount / 30).round(); // Use 30 as average
      breakdown[category] = dailyAmount;
    });

    return breakdown;
  }

  /// Generate minimal fallback data when everything fails
  List<Map<String, dynamic>> _generateMinimalFallbackData() {
    final today = DateTime.now();
    final daysInMonth = DateTime(today.year, today.month + 1, 0).day;
    final List<Map<String, dynamic>> calendarDays = [];

    for (int day = 1; day <= daysInMonth; day++) {
      calendarDays.add({
        'day': day,
        'limit': 50, // Minimal daily budget
        'spent': day < today.day ? 35 : 0,
        'status': 'good',
        'categories': {
          'food': 20,
          'transportation': 15,
          'entertainment': 10,
          'shopping': 5,
        },
        'is_today': day == today.day,
        'is_weekend': DateTime(today.year, today.month, day).weekday >= 6,
      });
    }

    return calendarDays;
  }

  /// Get sample income tiers for testing
  static Map<String, double> getSampleIncomes() {
    return {
      'low': 2000,
      'mid_low': 3500,
      'mid': 5500,
      'mid_high': 8500,
      'high': 15000,
    };
  }

  /// Get sample locations for testing
  static List<String> getSampleLocations() {
    return [
      'San Francisco, CA',
      'New York, NY',
      'Chicago, IL',
      'Austin, TX',
      'Rural Iowa',
      'Denver, CO',
      'Miami, FL',
    ];
  }
}
