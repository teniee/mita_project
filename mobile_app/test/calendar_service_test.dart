import 'package:flutter_test/flutter_test.dart';
import 'package:mita/services/calendar_fallback_service.dart';

/// Income-tier assertions must not depend on today's date.
///
/// A day's limit is `round(monthlyBudget * weekdayWeight / monthWeightSum)`, and
/// `monthWeightSum` depends on how many Mondays/Fridays/weekends the month
/// happens to contain. For income 5500 at a neutral location that moves a
/// mid-week limit between 98 and 111 across the twelve months of 2026, so the
/// old `greaterThan(100)` assertion passed in eight months and failed in four
/// (Jan/May/Aug/Oct) — 99 and 100 are perfectly correct outputs.
///
/// The service already accepts an explicit year/month, so these tests pin one.
/// Tests that are genuinely about "now" (day count, is_today, is_weekend) stay
/// dynamic and derive their expectation from DateTime.now().
const _pinnedYear = 2026;
const _pinnedMonth = 1; // January 2026: 31 days, starts on a Thursday.

void main() {
  group('Calendar Fallback Service Tests', () {
    late CalendarFallbackService fallbackService;

    setUp(() {
      fallbackService = CalendarFallbackService();
    });

    group('Income Tier Classification', () {
      /// Mid-week days (Tue-Thu) carry weight 1.00-1.05, avoiding the Monday
      /// reduction (0.80) and the Friday/weekend ramp (1.30-1.50).
      List<int> midWeekLimits(List<Map<String, dynamic>> days) => days
          .where((d) {
            final dow = d['day_of_week'] as int;
            return dow >= 2 && dow <= 4;
          })
          .map((d) => d['limit'] as int)
          .toList();

      test('should classify low income correctly', () async {
        final result = await fallbackService.generateFallbackCalendarData(
          monthlyIncome: 2000,
          location: 'Rural Iowa',
          year: _pinnedYear,
          month: _pinnedMonth,
        );

        expect(result, isNotEmpty);
        expect(result.length, equals(31)); // January 2026

        final firstDay = result.first;
        expect(firstDay['limit'], isA<int>());
        expect(firstDay['limit'], greaterThan(0));
        // 2000 * 0.65 * 0.75 (rural) spread over the month.
        expect(midWeekLimits(result), everyElement(inInclusiveRange(20, 40)));
      });

      test('should classify mid income correctly', () async {
        final result = await fallbackService.generateFallbackCalendarData(
          monthlyIncome: 5500,
          location: 'Chicago, IL',
          year: _pinnedYear,
          month: _pinnedMonth,
        );

        expect(result, isNotEmpty);
        // 5500 * 0.65 * 1.0 (baseline metro). Bounds sit outside the natural
        // month-to-month spread rather than on top of it.
        expect(midWeekLimits(result), everyElement(inInclusiveRange(90, 130)));
      });

      test('should classify high income correctly', () async {
        final result = await fallbackService.generateFallbackCalendarData(
          monthlyIncome: 15000,
          location: 'San Francisco, CA',
          year: _pinnedYear,
          month: _pinnedMonth,
        );

        expect(result, isNotEmpty);
        // 15000 * 0.65 * 1.30 (high-cost metro).
        expect(midWeekLimits(result), everyElement(greaterThan(300)));
      });

      test('daily budget rises strictly with income at a fixed location',
          () async {
        // The actual contract of "income tier classification": holding location
        // and month constant, a higher income tier must yield a higher daily
        // budget. This is what the absolute thresholds above were reaching for.
        final limits = <int>[];
        for (final income in [2000, 5500, 15000]) {
          final result = await fallbackService.generateFallbackCalendarData(
            monthlyIncome: income,
            location: 'Chicago, IL', // neutral 1.0 multiplier for all three
            year: _pinnedYear,
            month: _pinnedMonth,
          );
          limits.add(result.first['limit'] as int);
        }

        expect(limits[0], lessThan(limits[1]));
        expect(limits[1], lessThan(limits[2]));
      });
    });

    group('Location-Based Adjustments', () {
      test('should apply high-cost location multiplier', () async {
        final highCostResult =
            await fallbackService.generateFallbackCalendarData(
          monthlyIncome: 5000,
          location: 'San Francisco, CA',
        );

        final normalCostResult =
            await fallbackService.generateFallbackCalendarData(
          monthlyIncome: 5000,
          location: 'Austin, TX',
        );

        // San Francisco should have higher daily budgets than Austin
        expect(highCostResult.first['limit'] as int,
            greaterThan(normalCostResult.first['limit'] as int));
      });

      test('should apply low-cost location multiplier', () async {
        final lowCostResult =
            await fallbackService.generateFallbackCalendarData(
          monthlyIncome: 5000,
          location: 'Rural Iowa',
        );

        final normalCostResult =
            await fallbackService.generateFallbackCalendarData(
          monthlyIncome: 5000,
          location: 'Chicago, IL',
        );

        // Rural Iowa should have lower daily budgets than Chicago
        expect(lowCostResult.first['limit'] as int,
            lessThan(normalCostResult.first['limit'] as int));
      });
    });

    group('Calendar Data Structure', () {
      test('should generate correct number of days for current month',
          () async {
        final result = await fallbackService.generateFallbackCalendarData(
          monthlyIncome: 5000,
        );

        final now = DateTime.now();
        final expectedDays = DateTime(now.year, now.month + 1, 0).day;
        expect(result.length, equals(expectedDays));
      });

      test('should include all required fields for each day', () async {
        final result = await fallbackService.generateFallbackCalendarData(
          monthlyIncome: 5000,
        );

        for (final day in result) {
          expect(day, contains('day'));
          expect(day, contains('limit'));
          expect(day, contains('spent'));
          expect(day, contains('status'));
          expect(day, contains('categories'));
          expect(day, contains('is_today'));
          expect(day, contains('is_weekend'));
        }
      });

      test('should mark today correctly', () async {
        final result = await fallbackService.generateFallbackCalendarData(
          monthlyIncome: 5000,
        );

        final today = DateTime.now().day;
        final todayData = result.firstWhere((day) => day['day'] == today);
        expect(todayData['is_today'], isTrue);

        // Other days should not be marked as today
        final otherDays = result.where((day) => day['day'] != today);
        for (final day in otherDays) {
          expect(day['is_today'], isFalse);
        }
      });

      test('should mark weekends correctly', () async {
        final result = await fallbackService.generateFallbackCalendarData(
          monthlyIncome: 5000,
        );

        for (final dayData in result) {
          final dayNumber = dayData['day'] as int;
          final date =
              DateTime(DateTime.now().year, DateTime.now().month, dayNumber);
          final isWeekend = date.weekday >= 6;
          expect(dayData['is_weekend'], equals(isWeekend));
        }
      });
    });

    group('Spending Calculations', () {
      test('should have realistic spending for past days', () async {
        final result = await fallbackService.generateFallbackCalendarData(
          monthlyIncome: 5000,
        );

        final today = DateTime.now().day;
        final pastDays = result.where((day) => (day['day'] as int) < today);

        for (final day in pastDays) {
          final spent = day['spent'] as int;
          final limit = day['limit'] as int;

          expect(spent, greaterThan(0)); // Past days should have some spending
          expect(
              spent,
              lessThanOrEqualTo(limit *
                  1.5)); // Shouldn't exceed 150% of budget (reasonable overspending)
        }
      });

      test('should have no spending for future days', () async {
        final result = await fallbackService.generateFallbackCalendarData(
          monthlyIncome: 5000,
        );

        final today = DateTime.now().day;
        final futureDays = result.where((day) => (day['day'] as int) > today);

        for (final day in futureDays) {
          final spent = day['spent'] as int;
          expect(spent, equals(0)); // Future days should have no spending
        }
      });

      test('a month that is not the current month carries no spend at all',
          () async {
        // The two tests above only exercise their loop bodies for whatever
        // today happens to be: run on the 1st, "past days" is empty and passes
        // vacuously. Spend accrual is only defined for the current month, so
        // pin a different month and assert that directly.
        final result = await fallbackService.generateFallbackCalendarData(
          monthlyIncome: 5000,
          year: _pinnedYear,
          month: _pinnedMonth,
        );
        final now = DateTime.now();
        expect(
          now.year == _pinnedYear && now.month == _pinnedMonth,
          isFalse,
          reason: 'pin a month that is not the current one for this assertion',
        );

        expect(result, isNotEmpty);
        expect(result.map((d) => d['spent'] as int), everyElement(equals(0)));
        expect(result.map((d) => d['status'] as String),
            everyElement(equals('good')));
        expect(result.map((d) => d['is_today'] as bool), everyElement(isFalse));
      });

      test('should calculate status correctly', () async {
        final result = await fallbackService.generateFallbackCalendarData(
          monthlyIncome: 5000,
        );

        for (final day in result) {
          final spent = day['spent'] as int;
          final limit = day['limit'] as int;
          final status = day['status'] as String;

          if (spent == 0) {
            expect(status, equals('good'));
          } else {
            final ratio = spent / limit;
            if (ratio > 1.1) {
              expect(status, equals('over'));
            } else if (ratio > 0.85) {
              expect(status, equals('warning'));
            } else {
              expect(status, equals('good'));
            }
          }
        }
      });
    });

    group('Category Breakdown', () {
      test('should include standard spending categories', () async {
        final result = await fallbackService.generateFallbackCalendarData(
          monthlyIncome: 5000,
        );

        final firstDay = result.first;
        final categories = firstDay['categories'] as Map<String, dynamic>;

        expect(categories, contains('food'));
        expect(categories, contains('transportation'));
        expect(categories, contains('entertainment'));
        expect(categories, contains('shopping'));
      });

      test('should have positive category amounts', () async {
        final result = await fallbackService.generateFallbackCalendarData(
          monthlyIncome: 5000,
        );

        for (final day in result) {
          final categories = day['categories'] as Map<String, dynamic>;
          for (final amount in categories.values) {
            expect(amount, greaterThan(0));
          }
        }
      });

      test('should have category amounts that sum to reasonable daily budget',
          () async {
        final result = await fallbackService.generateFallbackCalendarData(
          monthlyIncome: 5000,
        );

        final firstDay = result.first;
        final categories = firstDay['categories'] as Map<String, dynamic>;
        final limit = firstDay['limit'] as int;

        final categorySum = categories.values
            .fold<int>(0, (sum, amount) => sum + (amount as int));

        // Category sum should be reasonably close to daily limit (within 30% to account for rounding)
        expect(categorySum, greaterThan(limit * 0.7));
        expect(categorySum, lessThan(limit * 1.3));
      });
    });

    group('Weekend and Payday Effects', () {
      test('should have higher budgets on weekends', () async {
        final result = await fallbackService.generateFallbackCalendarData(
          monthlyIncome: 5000,
        );

        // Find weekend and weekday examples
        final weekendDays = result.where((day) => day['is_weekend'] == true);
        final weekdayDays = result.where((day) => day['is_weekend'] == false);

        if (weekendDays.isNotEmpty && weekdayDays.isNotEmpty) {
          final avgWeekendBudget = weekendDays
                  .map((day) => day['limit'] as int)
                  .reduce((a, b) => a + b) /
              weekendDays.length;

          final avgWeekdayBudget = weekdayDays
                  .map((day) => day['limit'] as int)
                  .reduce((a, b) => a + b) /
              weekdayDays.length;

          // Weekend budgets should generally be higher than weekday budgets
          expect(avgWeekendBudget, greaterThan(avgWeekdayBudget * 0.9));
        }
      });
    });

    group('Edge Cases', () {
      test('should handle zero income gracefully', () async {
        final result = await fallbackService.generateFallbackCalendarData(
          monthlyIncome: 0,
        );

        expect(result, isNotEmpty);
        for (final day in result) {
          expect(day['limit'], greaterThanOrEqualTo(0));
        }
      });

      test('should handle extremely high income', () async {
        final result = await fallbackService.generateFallbackCalendarData(
          monthlyIncome: 100000,
        );

        expect(result, isNotEmpty);
        for (final day in result) {
          expect(day['limit'], greaterThan(0));
          expect(day['limit'], lessThan(10000)); // Reasonable upper bound
        }
      });

      test('should handle unknown location', () async {
        final result = await fallbackService.generateFallbackCalendarData(
          monthlyIncome: 5000,
          location: 'Unknown City, ZZ',
        );

        expect(result, isNotEmpty);
        // Should still generate valid data even with unknown location
        for (final day in result) {
          expect(day['limit'], greaterThan(0));
        }
      });
    });

    group('Sample Data Generation', () {
      test('should provide sample incomes for testing', () {
        final sampleIncomes = CalendarFallbackService.getSampleIncomes();

        expect(sampleIncomes, isNotEmpty);
        expect(sampleIncomes, contains('low'));
        expect(sampleIncomes, contains('mid'));
        expect(sampleIncomes, contains('high'));

        for (final income in sampleIncomes.values) {
          expect(income, greaterThan(0));
        }
      });

      test('should provide sample locations for testing', () {
        final sampleLocations = CalendarFallbackService.getSampleLocations();

        expect(sampleLocations, isNotEmpty);
        expect(sampleLocations.length, greaterThan(5));

        // Should include high-cost and low-cost locations
        expect(sampleLocations.any((loc) => loc.contains('San Francisco')),
            isTrue);
        expect(sampleLocations.any((loc) => loc.contains('Rural')), isTrue);
      });
    });
  });
}
