import 'dart:math';
import '../models/budget_intelligence_models.dart';

/// Advanced temporal intelligence service with ML-based spending predictions
class TemporalIntelligenceService {
  static final TemporalIntelligenceService _instance =
      TemporalIntelligenceService._internal();
  factory TemporalIntelligenceService() => _instance;
  TemporalIntelligenceService._internal();

  /// Learn spending patterns from historical transaction data
  Future<TemporalSpendingPattern> learnSpendingPatterns(
    List<Map<String, dynamic>> transactionHistory,
  ) async {
    // Initialize pattern maps
    final dayOfWeekSpending = <int, List<double>>{};
    final dayOfMonthSpending = <int, List<double>>{};
    final monthOfYearSpending = <int, List<double>>{};

    // Analyze historical transactions
    for (final transaction in transactionHistory) {
      final date = DateTime.tryParse(transaction['date']?.toString() ?? '') ??
          DateTime.now();
      final amount = (transaction['amount'] as num?)?.toDouble() ?? 0.0;

      // Group by day of week (1 = Monday, 7 = Sunday)
      dayOfWeekSpending.putIfAbsent(date.weekday, () => []).add(amount);

      // Group by day of month
      dayOfMonthSpending.putIfAbsent(date.day, () => []).add(amount);

      // Group by month of year
      monthOfYearSpending.putIfAbsent(date.month, () => []).add(amount);
    }

    // Calculate multipliers based on average spending patterns
    final baselineSpending = _calculateBaseline(transactionHistory);

    return TemporalSpendingPattern(
      dayOfWeekMultipliers:
          _calculateMultipliers(dayOfWeekSpending, baselineSpending),
      dayOfMonthMultipliers:
          _calculateMultipliers(dayOfMonthSpending, baselineSpending),
      monthOfYearMultipliers:
          _calculateMultipliers(monthOfYearSpending, baselineSpending),
      holidayMultipliers: _detectHolidayPatterns(transactionHistory),
      seasonalMultipliers: _detectSeasonalPatterns(transactionHistory),
      paydayEffect: _calculatePaydayEffect(transactionHistory),
      weekendEffect: _calculateWeekendEffect(transactionHistory),
      monthEndEffect: _calculateMonthEndEffect(transactionHistory),
      confidenceScore: _calculateConfidenceScore(transactionHistory),
    );
  }

  /// Calculate temporal adjustment for a specific target date
  Future<TemporalBudgetResult> calculateTemporalAdjustment(
    double baseDailyBudget,
    DateTime targetDate,
    TemporalSpendingPattern? patterns,
  ) async {
    if (patterns == null) {
      // Return base budget with minimal adjustment
      return TemporalBudgetResult(
        baseDailyBudget: baseDailyBudget,
        adjustedDailyBudget: baseDailyBudget,
        temporalMultiplier: 1.0,
        primaryReason: 'No historical patterns available',
        contributingFactors: <String>[],
        confidenceLevel: 0.5,
        factorBreakdown: <String, double>{},
      );
    }

    var multiplier = 1.0;
    final factors = <String>[];
    final factorBreakdown = <String, double>{};
    var primaryReason = 'Standard daily budget';

    // Day of week adjustment
    final dayOfWeekMultiplier =
        patterns.dayOfWeekMultipliers[targetDate.weekday] ?? 1.0;
    if (dayOfWeekMultiplier != 1.0) {
      multiplier *= dayOfWeekMultiplier;
      factors.add('${_getDayName(targetDate.weekday)} spending pattern');
      factorBreakdown['day_of_week'] = dayOfWeekMultiplier;
    }

    // Weekend effect
    if (targetDate.weekday >= 6 && patterns.weekendEffect != 1.0) {
      multiplier *= patterns.weekendEffect;
      factors.add('Weekend spending increase');
      factorBreakdown['weekend_effect'] = patterns.weekendEffect;
      primaryReason = 'Weekend spending adjustment';
    }

    // Month-end effect
    if (targetDate.day > 25 && patterns.monthEndEffect != 1.0) {
      multiplier *= patterns.monthEndEffect;
      factors.add('Month-end spending pattern');
      factorBreakdown['month_end_effect'] = patterns.monthEndEffect;
      if (patterns.monthEndEffect < 1.0) {
        primaryReason = 'Month-end conservation';
      }
    }

    // Holiday effects
    final holidayKey = _getHolidayKey(targetDate);
    if (holidayKey != null) {
      final holidayMultiplier = patterns.holidayMultipliers[holidayKey] ?? 1.0;
      if (holidayMultiplier != 1.0) {
        multiplier *= holidayMultiplier;
        factors.add('Holiday spending adjustment');
        factorBreakdown['holiday_effect'] = holidayMultiplier;
        primaryReason = 'Holiday spending pattern';
      }
    }

    // Seasonal adjustments
    final season = _getSeason(targetDate);
    final seasonalMultiplier = patterns.seasonalMultipliers[season] ?? 1.0;
    if (seasonalMultiplier != 1.0) {
      multiplier *= seasonalMultiplier;
      factors.add('$season seasonal adjustment');
      factorBreakdown['seasonal_effect'] = seasonalMultiplier;
    }

    // Payday effect (if within 3 days of typical payday)
    if (_isNearPayday(targetDate) && patterns.paydayEffect != 1.0) {
      multiplier *= patterns.paydayEffect;
      factors.add('Payday spending increase');
      factorBreakdown['payday_effect'] = patterns.paydayEffect;
    }

    // Clamp multiplier to reasonable bounds
    multiplier = multiplier.clamp(0.5, 2.0);

    return TemporalBudgetResult(
      baseDailyBudget: baseDailyBudget,
      adjustedDailyBudget: baseDailyBudget * multiplier,
      temporalMultiplier: multiplier,
      primaryReason: primaryReason,
      contributingFactors: factors,
      confidenceLevel: patterns.confidenceScore,
      factorBreakdown: factorBreakdown,
    );
  }

  /// Get temporal insights for budget optimization
  Future<List<String>> generateTemporalInsights(
    TemporalSpendingPattern patterns,
    DateTime targetDate,
  ) async {
    final insights = <String>[];

    // Analyze day-of-week patterns
    final highSpendingDays = patterns.dayOfWeekMultipliers.entries
        .where((entry) => entry.value > 1.2)
        .map((entry) => _getDayName(entry.key))
        .toList();

    if (highSpendingDays.isNotEmpty) {
      insights.add(
          'You tend to spend ${((patterns.dayOfWeekMultipliers.values.reduce(max) - 1) * 100).round()}% more on ${highSpendingDays.join(', ')}');
    }

    // Weekend spending patterns
    if (patterns.weekendEffect > 1.15) {
      insights.add(
          'Weekend spending is ${((patterns.weekendEffect - 1) * 100).round()}% higher than weekdays');
    }

    // Month-end patterns
    if (patterns.monthEndEffect < 0.9) {
      insights.add(
          'You typically reduce spending by ${((1 - patterns.monthEndEffect) * 100).round()}% at month-end');
    }

    // Seasonal patterns
    final currentSeason = _getSeason(targetDate);
    final seasonalMultiplier =
        patterns.seasonalMultipliers[currentSeason] ?? 1.0;
    if (seasonalMultiplier > 1.1) {
      insights.add(
          '$currentSeason season typically increases spending by ${((seasonalMultiplier - 1) * 100).round()}%');
    }

    // Confidence assessment
    if (patterns.confidenceScore > 0.8) {
      insights.add(
          'High confidence predictions based on ${patterns.confidenceScore > 0.9 ? 'extensive' : 'good'} historical data');
    } else if (patterns.confidenceScore < 0.6) {
      insights.add(
          'Predictions have moderate confidence - more spending history will improve accuracy');
    }

    return insights.take(3).toList(); // Return top 3 insights
  }

  // Helper methods

  double _calculateBaseline(List<Map<String, dynamic>> transactions) {
    if (transactions.isEmpty) return 0.0;

    final totalSpending = transactions.fold(
        0.0, (sum, t) => sum + ((t['amount'] as num?)?.toDouble() ?? 0.0));
    return totalSpending / transactions.length;
  }

  Map<int, double> _calculateMultipliers(
    Map<int, List<double>> spendingByPeriod,
    double baseline,
  ) {
    final multipliers = <int, double>{};

    for (final entry in spendingByPeriod.entries) {
      final periodAverage = entry.value.isEmpty
          ? 0.0
          : entry.value.reduce((a, b) => a + b) / entry.value.length;
      multipliers[entry.key] = baseline > 0 ? periodAverage / baseline : 1.0;
    }

    return multipliers;
  }

  Map<String, double> _detectHolidayPatterns(
      List<Map<String, dynamic>> transactions) {
    final holidaySpending = <String, List<double>>{};

    for (final transaction in transactions) {
      final date = DateTime.tryParse(transaction['date']?.toString() ?? '') ??
          DateTime.now();
      final amount = (transaction['amount'] as num?)?.toDouble() ?? 0.0;
      final holidayKey = _getHolidayKey(date);

      if (holidayKey != null) {
        holidaySpending.putIfAbsent(holidayKey, () => []).add(amount);
      }
    }

    final baseline = _calculateBaseline(transactions);
    final holidayMultipliers = <String, double>{};

    for (final entry in holidaySpending.entries) {
      final holidayAverage = entry.value.isEmpty
          ? 0.0
          : entry.value.reduce((a, b) => a + b) / entry.value.length;
      holidayMultipliers[entry.key] =
          baseline > 0 ? holidayAverage / baseline : 1.0;
    }

    return holidayMultipliers;
  }

  Map<String, double> _detectSeasonalPatterns(
      List<Map<String, dynamic>> transactions) {
    final seasonalSpending = <String, List<double>>{
      'spring': [],
      'summer': [],
      'fall': [],
      'winter': [],
    };

    for (final transaction in transactions) {
      final date = DateTime.tryParse(transaction['date']?.toString() ?? '') ??
          DateTime.now();
      final amount = (transaction['amount'] as num?)?.toDouble() ?? 0.0;
      final season = _getSeason(date);

      seasonalSpending[season]!.add(amount);
    }

    final baseline = _calculateBaseline(transactions);
    final seasonalMultipliers = <String, double>{};

    for (final entry in seasonalSpending.entries) {
      final seasonalAverage = entry.value.isEmpty
          ? 0.0
          : entry.value.reduce((a, b) => a + b) / entry.value.length;
      seasonalMultipliers[entry.key] =
          baseline > 0 ? seasonalAverage / baseline : 1.0;
    }

    return seasonalMultipliers;
  }

  double _calculatePaydayEffect(List<Map<String, dynamic>> transactions) {
    final paydaySpending = <double>[];
    final regularSpending = <double>[];

    for (final transaction in transactions) {
      final date = DateTime.tryParse(transaction['date']?.toString() ?? '') ??
          DateTime.now();
      final amount = (transaction['amount'] as num?)?.toDouble() ?? 0.0;

      if (_isNearPayday(date)) {
        paydaySpending.add(amount);
      } else {
        regularSpending.add(amount);
      }
    }

    if (paydaySpending.isEmpty || regularSpending.isEmpty) return 1.0;

    final paydayAverage =
        paydaySpending.reduce((a, b) => a + b) / paydaySpending.length;
    final regularAverage =
        regularSpending.reduce((a, b) => a + b) / regularSpending.length;

    return regularAverage > 0 ? paydayAverage / regularAverage : 1.0;
  }

  double _calculateWeekendEffect(List<Map<String, dynamic>> transactions) {
    final weekendSpending = <double>[];
    final weekdaySpending = <double>[];

    for (final transaction in transactions) {
      final date = DateTime.tryParse(transaction['date']?.toString() ?? '') ??
          DateTime.now();
      final amount = (transaction['amount'] as num?)?.toDouble() ?? 0.0;

      if (date.weekday >= 6) {
        weekendSpending.add(amount);
      } else {
        weekdaySpending.add(amount);
      }
    }

    if (weekendSpending.isEmpty || weekdaySpending.isEmpty) return 1.0;

    final weekendAverage =
        weekendSpending.reduce((a, b) => a + b) / weekendSpending.length;
    final weekdayAverage =
        weekdaySpending.reduce((a, b) => a + b) / weekdaySpending.length;

    return weekdayAverage > 0 ? weekendAverage / weekdayAverage : 1.0;
  }

  double _calculateMonthEndEffect(List<Map<String, dynamic>> transactions) {
    final monthEndSpending = <double>[];
    final regularSpending = <double>[];

    for (final transaction in transactions) {
      final date = DateTime.tryParse(transaction['date']?.toString() ?? '') ??
          DateTime.now();
      final amount = (transaction['amount'] as num?)?.toDouble() ?? 0.0;

      if (date.day > 25) {
        monthEndSpending.add(amount);
      } else {
        regularSpending.add(amount);
      }
    }

    if (monthEndSpending.isEmpty || regularSpending.isEmpty) return 1.0;

    final monthEndAverage =
        monthEndSpending.reduce((a, b) => a + b) / monthEndSpending.length;
    final regularAverage =
        regularSpending.reduce((a, b) => a + b) / regularSpending.length;

    return regularAverage > 0 ? monthEndAverage / regularAverage : 1.0;
  }

  double _calculateConfidenceScore(List<Map<String, dynamic>> transactions) {
    if (transactions.isEmpty) return 0.0;
    if (transactions.length < 10) return 0.3;
    if (transactions.length < 30) return 0.6;
    if (transactions.length < 90) return 0.8;
    return 0.95;
  }

  String _getDayName(int weekday) {
    switch (weekday) {
      case 1:
        return 'Monday';
      case 2:
        return 'Tuesday';
      case 3:
        return 'Wednesday';
      case 4:
        return 'Thursday';
      case 5:
        return 'Friday';
      case 6:
        return 'Saturday';
      case 7:
        return 'Sunday';
      default:
        return 'Unknown';
    }
  }

  String? _getHolidayKey(DateTime date) {
    // Simple holiday detection - would be enhanced with actual holiday data
    if (date.month == 12 && date.day >= 20 && date.day <= 31) {
      return 'christmas_season';
    }
    if (date.month == 11 && date.day >= 20 && date.day <= 30) {
      return 'thanksgiving';
    }
    if (date.month == 1 && date.day == 1) {
      return 'new_year';
    }
    return null;
  }

  String _getSeason(DateTime date) {
    switch (date.month) {
      case 3:
      case 4:
      case 5:
        return 'spring';
      case 6:
      case 7:
      case 8:
        return 'summer';
      case 9:
      case 10:
      case 11:
        return 'fall';
      case 12:
      case 1:
      case 2:
        return 'winter';
      default:
        return 'unknown';
    }
  }

  bool _isNearPayday(DateTime date) {
    // Assume typical payday is 1st and 15th of month
    return (date.day >= 1 && date.day <= 3) ||
        (date.day >= 15 && date.day <= 17);
  }
}
