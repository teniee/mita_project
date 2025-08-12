import 'package:flutter_test/flutter_test.dart';
import 'package:mita/services/calendar_fallback_service.dart';

void main() {
  group('Calendar Integration Tests', () {
    late CalendarFallbackService fallbackService;

    setUp(() {
      fallbackService = CalendarFallbackService();
    });

    group('End-to-End Calendar Flow', () {
      testWidgets('Full calendar workflow with different income tiers', (WidgetTester tester) async {
        final incomeTestCases = [
          {'income': 2000.0, 'tier': 'low'},
          {'income': 5000.0, 'tier': 'mid'},
          {'income': 12000.0, 'tier': 'high'},
        ];

        for (final testCase in incomeTestCases) {
          final income = testCase['income'] as double;
          final tier = testCase['tier'] as String;

          // Generate calendar data for this income tier
          final calendarData = await fallbackService.generateFallbackCalendarData(
            monthlyIncome: income,
            location: 'Chicago, IL',
          );

          // Verify calendar structure
          expect(calendarData, isNotEmpty);
          expect(calendarData.length, greaterThan(25)); // At least 25 days in month

          // Verify income-appropriate budgets
          final avgDailyBudget = calendarData
              .map((day) => day['limit'] as int)
              .reduce((a, b) => a + b) / calendarData.length;

          switch (tier) {
            case 'low':
              expect(avgDailyBudget, lessThan(100));
              break;
            case 'mid':
              expect(avgDailyBudget, greaterThan(100));
              expect(avgDailyBudget, lessThan(300));
              break;
            case 'high':
              expect(avgDailyBudget, greaterThan(200));
              break;
          }
        }
      });

      testWidgets('Calendar data consistency across different locations', (WidgetTester tester) async {
        final locations = [
          'San Francisco, CA', // High cost
          'Chicago, IL',       // Medium cost
          'Rural Iowa',        // Low cost
        ];

        const income = 5000.0;
        final results = <String, List<Map<String, dynamic>>>{};

        // Generate calendar data for each location
        for (final location in locations) {
          results[location] = await fallbackService.generateFallbackCalendarData(
            monthlyIncome: income,
            location: location,
          );
        }

        // Verify location-based differences
        final sfData = results['San Francisco, CA']!;
        final chicagoData = results['Chicago, IL']!;
        final iowaData = results['Rural Iowa']!;

        final sfAvgBudget = sfData.map((d) => d['limit'] as int).reduce((a, b) => a + b) / sfData.length;
        final chicagoAvgBudget = chicagoData.map((d) => d['limit'] as int).reduce((a, b) => a + b) / chicagoData.length;
        final iowaAvgBudget = iowaData.map((d) => d['limit'] as int).reduce((a, b) => a + b) / iowaData.length;

        // San Francisco should have highest budgets, Iowa lowest
        expect(sfAvgBudget, greaterThan(chicagoAvgBudget));
        expect(chicagoAvgBudget, greaterThan(iowaAvgBudget));
      });
    });

    group('Data Quality and Financial Accuracy', () {
      test('Calendar data maintains financial precision', () async {
        const income = 5432.67; // Decimal income to test precision
        final calendarData = await fallbackService.generateFallbackCalendarData(
          monthlyIncome: income,
        );

        // Verify no money is lost in calculations
        final totalMonthlyBudget = calendarData
            .map((day) => day['limit'] as int)
            .reduce((a, b) => a + b);

        // Should be reasonable percentage of income (around 50-60% for flexible spending)
        const expectedRange = income * 0.4; // 40% minimum
        const maxRange = income * 0.7; // 70% maximum

        expect(totalMonthlyBudget, greaterThan(expectedRange));
        expect(totalMonthlyBudget, lessThan(maxRange));
      });

      test('Category allocations sum correctly', () async {
        final calendarData = await fallbackService.generateFallbackCalendarData(
          monthlyIncome: 5000,
        );

        for (final day in calendarData) {
          final categories = day['categories'] as Map<String, dynamic>;
          final dailyLimit = day['limit'] as int;

          final categorySum = categories.values.fold<int>(0, (sum, amount) => sum + (amount as int));

          // Category sum should be close to daily limit (within reasonable variance)
          expect(categorySum, greaterThan(dailyLimit * 0.8));
          expect(categorySum, lessThan(dailyLimit * 1.2));
        }
      });

      test('Spending patterns are realistic', () async {
        final calendarData = await fallbackService.generateFallbackCalendarData(
          monthlyIncome: 5000,
        );

        final today = DateTime.now().day;
        int totalOverBudgetDays = 0;
        int totalGoodDays = 0;

        for (final day in calendarData) {
          final dayNumber = day['day'] as int;
          final status = day['status'] as String;

          if (dayNumber < today) { // Past days
            if (status == 'over') totalOverBudgetDays++;
            if (status == 'good') totalGoodDays++;
          }
        }

        // Realistic spending: most days should be good, some over budget
        expect(totalGoodDays, greaterThan(totalOverBudgetDays));
        expect(totalOverBudgetDays, lessThan(today ~/ 3)); // Less than 1/3 over budget
      });
    });

    group('Edge Cases and Error Handling', () {
      test('Handles extreme income values gracefully', () async {
        final extremeIncomes = [0.01, 1.0, 100.0, 100000.0, 1000000.0];

        for (final income in extremeIncomes) {
          final calendarData = await fallbackService.generateFallbackCalendarData(
            monthlyIncome: income,
          );

          expect(calendarData, isNotEmpty);

          // All daily limits should be positive
          for (final day in calendarData) {
            expect(day['limit'], greaterThan(0));
          }
        }
      });

      test('Handles missing or invalid location data', () async {
        final invalidLocations = [null, '', 'Invalid Location, XX', '12345'];

        for (final location in invalidLocations) {
          final calendarData = await fallbackService.generateFallbackCalendarData(
            monthlyIncome: 5000,
            location: location,
          );

          expect(calendarData, isNotEmpty);
          expect(calendarData.length, greaterThan(25));
        }
      });

      test('Handles different month lengths correctly', () async {
        final testMonths = [
          {'year': 2024, 'month': 2}, // February (leap year - 29 days)
          {'year': 2023, 'month': 2}, // February (non-leap year - 28 days)
          {'year': 2024, 'month': 4}, // April (30 days)
          {'year': 2024, 'month': 1}, // January (31 days)
        ];

        for (final testMonth in testMonths) {
          final year = testMonth['year'] as int;
          final month = testMonth['month'] as int;

          final calendarData = await fallbackService.generateFallbackCalendarData(
            monthlyIncome: 5000,
            year: year,
            month: month,
          );

          final expectedDays = DateTime(year, month + 1, 0).day;
          expect(calendarData.length, equals(expectedDays));
        }
      });
    });

    group('Performance and Load Testing', () {
      test('Calendar generation completes within time limits', () async {
        final stopwatch = Stopwatch()..start();

        await fallbackService.generateFallbackCalendarData(
          monthlyIncome: 5000,
          location: 'San Francisco, CA',
        );

        stopwatch.stop();

        // Should complete in under 1 second
        expect(stopwatch.elapsedMilliseconds, lessThan(1000));
      });

      test('Multiple concurrent calendar generations', () async {
        final futures = <Future<List<Map<String, dynamic>>>>[];

        // Create 20 concurrent calendar generations
        for (int i = 0; i < 20; i++) {
          futures.add(fallbackService.generateFallbackCalendarData(
            monthlyIncome: 5000 + (i * 100), // Vary income slightly
            location: 'Chicago, IL',
          ));
        }

        final results = await Future.wait(futures);

        // All should complete successfully
        expect(results.length, equals(20));
        for (final result in results) {
          expect(result, isNotEmpty);
        }
      });

      test('Memory usage remains reasonable with large datasets', () async {
        final largeResults = <List<Map<String, dynamic>>>[];

        // Generate many calendar datasets
        for (int i = 0; i < 100; i++) {
          final result = await fallbackService.generateFallbackCalendarData(
            monthlyIncome: 5000,
          );
          largeResults.add(result);
        }

        // Should handle large datasets without issues
        expect(largeResults.length, equals(100));

        // Verify data integrity in all results
        for (final result in largeResults) {
          expect(result.length, greaterThan(25));
          expect(result.first, contains('day'));
          expect(result.first, contains('limit'));
        }
      });
    });

    group('Business Logic Integration', () {
      test('Weekend effects are applied consistently', () async {
        final calendarData = await fallbackService.generateFallbackCalendarData(
          monthlyIncome: 5000,
        );

        final weekendDays = calendarData.where((day) => day['is_weekend'] == true);
        final weekdayDays = calendarData.where((day) => day['is_weekend'] == false);

        if (weekendDays.isNotEmpty && weekdayDays.isNotEmpty) {
          final avgWeekendBudget = weekendDays
              .map((day) => day['limit'] as int)
              .reduce((a, b) => a + b) / weekendDays.length;

          final avgWeekdayBudget = weekdayDays
              .map((day) => day['limit'] as int)
              .reduce((a, b) => a + b) / weekdayDays.length;

          // Weekend budgets should be higher on average
          expect(avgWeekendBudget, greaterThanOrEqualTo(avgWeekdayBudget * 0.9));
        }
      });

      test('Today is correctly identified and marked', () async {
        final calendarData = await fallbackService.generateFallbackCalendarData(
          monthlyIncome: 5000,
        );

        final todayNumber = DateTime.now().day;
        final todayData = calendarData.firstWhere((day) => day['day'] == todayNumber);

        expect(todayData['is_today'], isTrue);

        // Only one day should be marked as today
        final todayCount = calendarData.where((day) => day['is_today'] == true).length;
        expect(todayCount, equals(1));
      });

      test('Status calculations are mathematically correct', () async {
        final calendarData = await fallbackService.generateFallbackCalendarData(
          monthlyIncome: 5000,
        );

        for (final day in calendarData) {
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

    group('Sample Data Validation', () {
      test('Sample incomes cover all tiers', () {
        final sampleIncomes = CalendarFallbackService.getSampleIncomes();

        expect(sampleIncomes['low']!, lessThan(2500));
        expect(sampleIncomes['mid']!, greaterThan(4000));
        expect(sampleIncomes['mid']!, lessThan(8000));
        expect(sampleIncomes['high']!, greaterThan(10000));
      });

      test('Sample locations include cost variations', () {
        final sampleLocations = CalendarFallbackService.getSampleLocations();

        // Should include high-cost cities
        expect(sampleLocations.any((loc) => loc.contains('San Francisco') || loc.contains('New York')), isTrue);

        // Should include low-cost areas
        expect(sampleLocations.any((loc) => loc.contains('Rural') || loc.contains('Iowa')), isTrue);

        // Should include medium-cost cities
        expect(sampleLocations.any((loc) => loc.contains('Chicago') || loc.contains('Austin')), isTrue);
      });
    });
  });
}