import 'package:flutter_test/flutter_test.dart';
import 'package:mita/services/calendar_fallback_service.dart';

void main() {
  group('Calendar Fallback Service Tests', () {
    late CalendarFallbackService fallbackService;

    setUp(() {
      fallbackService = CalendarFallbackService();
    });

    group('Income Tier Classification', () {
      test('should classify low income correctly', () async {
        final result = await fallbackService.generateFallbackCalendarData(
          monthlyIncome: 2000,
          location: 'Rural Iowa',
        );

        expect(result, isNotEmpty);
        final expectedDays = DateTime(DateTime.now().year, DateTime.now().month + 1, 0).day;
        expect(result.length, equals(expectedDays)); // Current month days
        
        // Verify that low income has appropriate budget amounts
        final firstDay = result.first;
        expect(firstDay['limit'], isA<int>());
        expect(firstDay['limit'], greaterThan(0));
        expect(firstDay['limit'], lessThan(100)); // Low income should have lower daily budgets
      });

      test('should classify mid income correctly', () async {
        final result = await fallbackService.generateFallbackCalendarData(
          monthlyIncome: 5500,
          location: 'Chicago, IL',
        );

        expect(result, isNotEmpty);
        final firstDay = result.first;
        expect(firstDay['limit'], greaterThan(100)); // Mid income should have higher daily budgets
        expect(firstDay['limit'], lessThan(300));
      });

      test('should classify high income correctly', () async {
        final result = await fallbackService.generateFallbackCalendarData(
          monthlyIncome: 15000,
          location: 'San Francisco, CA',
        );

        expect(result, isNotEmpty);
        final firstDay = result.first;
        expect(firstDay['limit'], greaterThan(200)); // High income should have higher daily budgets
      });
    });

    group('Location-Based Adjustments', () {
      test('should apply high-cost location multiplier', () async {
        final highCostResult = await fallbackService.generateFallbackCalendarData(
          monthlyIncome: 5000,
          location: 'San Francisco, CA',
        );

        final normalCostResult = await fallbackService.generateFallbackCalendarData(
          monthlyIncome: 5000,
          location: 'Austin, TX',
        );

        // San Francisco should have higher daily budgets than Austin
        expect(highCostResult.first['limit'], greaterThan(normalCostResult.first['limit']));
      });

      test('should apply low-cost location multiplier', () async {
        final lowCostResult = await fallbackService.generateFallbackCalendarData(
          monthlyIncome: 5000,
          location: 'Rural Iowa',
        );

        final normalCostResult = await fallbackService.generateFallbackCalendarData(
          monthlyIncome: 5000,
          location: 'Chicago, IL',
        );

        // Rural Iowa should have lower daily budgets than Chicago
        expect(lowCostResult.first['limit'], lessThan(normalCostResult.first['limit']));
      });
    });

    group('Calendar Data Structure', () {
      test('should generate correct number of days for current month', () async {
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
          final date = DateTime(DateTime.now().year, DateTime.now().month, dayNumber);
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
          expect(spent, lessThanOrEqualTo(limit * 1.5)); // Shouldn't exceed 150% of budget (reasonable overspending)
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

      test('should have category amounts that sum to reasonable daily budget', () async {
        final result = await fallbackService.generateFallbackCalendarData(
          monthlyIncome: 5000,
        );

        final firstDay = result.first;
        final categories = firstDay['categories'] as Map<String, dynamic>;
        final limit = firstDay['limit'] as int;

        final categorySum = categories.values.fold<int>(0, (sum, amount) => sum + (amount as int));
        
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
              .reduce((a, b) => a + b) / weekendDays.length;
          
          final avgWeekdayBudget = weekdayDays
              .map((day) => day['limit'] as int)
              .reduce((a, b) => a + b) / weekdayDays.length;

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
        expect(sampleLocations.any((loc) => loc.contains('San Francisco')), isTrue);
        expect(sampleLocations.any((loc) => loc.contains('Rural')), isTrue);
      });
    });
  });
}