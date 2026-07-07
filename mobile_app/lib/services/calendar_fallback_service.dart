/// Offline calendar generator.
///
/// When the backend calendar cannot be reached, the app still needs a
/// plausible daily-budget calendar so the calendar screen renders instead
/// of showing an empty/error state. This produces a deterministic month of
/// daily budgets derived purely from income + location — no network, no
/// persistence — so it is safe to call in any offline situation.
///
/// The output shape matches what the calendar UI consumes:
///   {
///     'day': int, 'day_of_week': int (Mon=1..Sun=7),
///     'limit': int, 'spent': int, 'status': 'good'|'warning'|'over',
///     'categories': { 'food': int, 'transportation': int,
///                     'entertainment': int, 'shopping': int },
///     'is_today': bool, 'is_weekend': bool,
///   }
class CalendarFallbackService {
  /// Share of monthly income treated as flexible daily spending.
  static const double _budgetRatio = 0.65;

  /// Per-weekday spending-pattern weights (DateTime.weekday: Mon=1..Sun=7).
  /// Mondays are lean; spending ramps into the weekend.
  static const Map<int, double> _weekdayWeights = {
    1: 0.80, // Monday
    2: 1.00, // Tuesday
    3: 1.05, // Wednesday
    4: 1.00, // Thursday
    5: 1.30, // Friday
    6: 1.50, // Saturday
    7: 1.40, // Sunday
  };

  static const List<String> _categories = [
    'food',
    'transportation',
    'entertainment',
    'shopping',
  ];

  /// Category shares of a day's budget (sum = 1.0).
  static const Map<String, double> _categoryShares = {
    'food': 0.35,
    'transportation': 0.25,
    'entertainment': 0.20,
    'shopping': 0.20,
  };

  /// Generate a month of fallback daily-budget data.
  ///
  /// [year]/[month] default to the current month.
  Future<List<Map<String, dynamic>>> generateFallbackCalendarData({
    required num monthlyIncome,
    String? location,
    int? year,
    int? month,
  }) async {
    final now = DateTime.now();
    final targetYear = year ?? now.year;
    final targetMonth = month ?? now.month;
    final daysInMonth = DateTime(targetYear, targetMonth + 1, 0).day;

    final income = monthlyIncome < 0 ? 0.0 : monthlyIncome.toDouble();
    final locationMultiplier = _locationMultiplier(location);
    final monthlyBudget = income * _budgetRatio * locationMultiplier;

    // Sum of weekday weights across the whole month, used to normalize so
    // the month's limits sum to (approximately) the monthly budget.
    double weightSum = 0;
    for (var day = 1; day <= daysInMonth; day++) {
      final weekday = DateTime(targetYear, targetMonth, day).weekday;
      weightSum += _weekdayWeights[weekday]!;
    }
    if (weightSum == 0) weightSum = daysInMonth.toDouble();

    final isCurrentMonth = targetYear == now.year && targetMonth == now.month;
    final today = now.day;

    final result = <Map<String, dynamic>>[];
    for (var day = 1; day <= daysInMonth; day++) {
      final date = DateTime(targetYear, targetMonth, day);
      final weekday = date.weekday; // Mon=1..Sun=7
      final isWeekend = weekday >= 6;

      var limit =
          (monthlyBudget * _weekdayWeights[weekday]! / weightSum).round();
      // Positive income must always yield a spendable amount; only a truly
      // zero income produces a zero limit.
      if (income > 0 && limit < 1) limit = 1;
      if (income <= 0) limit = 0;

      final isToday = isCurrentMonth && day == today;
      final isPast = isCurrentMonth && day < today;

      final spent = isPast ? _spentForDay(limit, day) : 0;
      final status = _statusFor(spent, limit);

      result.add({
        'day': day,
        'day_of_week': weekday,
        'limit': limit,
        'spent': spent,
        'status': status,
        'categories': _categoriesFor(limit),
        'is_today': isToday,
        'is_weekend': isWeekend,
      });
    }

    return result;
  }

  int _spentForDay(int limit, int day) {
    if (limit <= 0) return 0;
    // Deterministic factor: mostly at/under budget, exactly one bucket per
    // 7-day cycle overspends. No bucket sits on the 1.1 'over' boundary —
    // a factor of exactly 1.1 flipped between warning/over depending on how
    // the integer limit rounded, so day statuses varied with income.
    const factors = [0.6, 0.7, 0.8, 0.9, 1.0, 1.05, 1.2];
    final spent = (limit * factors[day % 7]).round();
    return spent < 1 ? 1 : spent;
  }

  String _statusFor(int spent, int limit) {
    if (spent == 0 || limit <= 0) return 'good';
    final ratio = spent / limit;
    if (ratio > 1.1) return 'over';
    if (ratio > 0.85) return 'warning';
    return 'good';
  }

  Map<String, dynamic> _categoriesFor(int limit) {
    if (limit <= 0) {
      return {for (final c in _categories) c: 0};
    }
    final food = (limit * _categoryShares['food']!).round();
    final transportation = (limit * _categoryShares['transportation']!).round();
    final entertainment = (limit * _categoryShares['entertainment']!).round();
    // Assign the remainder to shopping so categories sum exactly to limit.
    var shopping = limit - food - transportation - entertainment;
    if (shopping < 1) shopping = 1;
    return {
      'food': food < 1 ? 1 : food,
      'transportation': transportation < 1 ? 1 : transportation,
      'entertainment': entertainment < 1 ? 1 : entertainment,
      'shopping': shopping,
    };
  }

  /// Cost-of-living multiplier inferred from a free-text location.
  double _locationMultiplier(String? location) {
    if (location == null || location.trim().isEmpty) return 1.0;
    final loc = location.toLowerCase();

    const highCost = [
      'san francisco',
      'new york',
      'boston',
      'seattle',
      'san jose',
      'washington',
    ];
    for (final city in highCost) {
      if (loc.contains(city)) return 1.30;
    }
    if (loc.contains('los angeles') || loc.contains('miami')) return 1.15;
    if (loc.contains('rural')) return 0.75;

    // Known medium-cost metros stay at baseline; everything else (unknown
    // locations) also falls back to the neutral 1.0 multiplier.
    return 1.0;
  }

  /// Sample incomes for manual testing / previews.
  static Map<String, int> getSampleIncomes() {
    return const {
      'low': 2000,
      'mid': 5000,
      'high': 12000,
    };
  }

  /// Sample locations spanning cost-of-living tiers.
  static List<String> getSampleLocations() {
    return const [
      'San Francisco, CA',
      'New York, NY',
      'Chicago, IL',
      'Austin, TX',
      'Denver, CO',
      'Rural Iowa',
      'Rural Montana',
    ];
  }
}
