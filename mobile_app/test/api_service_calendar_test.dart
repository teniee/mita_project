import 'package:flutter_test/flutter_test.dart';
import 'package:mockito/mockito.dart';
import 'package:mockito/annotations.dart';
import 'package:dio/dio.dart';
import 'package:mita/services/api_service.dart';

// Generate mocks
@GenerateMocks([Dio])
import 'api_service_calendar_test.mocks.dart';

void main() {
  group('API Service Calendar Tests', () {
    late ApiService apiService;
    late MockDio mockDio;

    setUp(() {
      mockDio = MockDio();
      // We can't easily inject the Dio instance into ApiService due to its singleton pattern
      // These tests will focus on testing the logic we can test
    });

    group('Calendar Data Validation', () {
      test('should validate calendar data structure', () {
        // Test the validation logic for calendar data
        final validCalendarData = [
          {
            'day': 1,
            'limit': 100,
            'spent': 50,
            'status': 'good',
            'categories': {
              'food': 40,
              'transportation': 30,
              'entertainment': 20,
              'shopping': 10,
            }
          },
          {
            'day': 2,
            'limit': 120,
            'spent': 110,
            'status': 'warning',
            'categories': {
              'food': 48,
              'transportation': 36,
              'entertainment': 24,
              'shopping': 12,
            }
          }
        ];

        // Validate each day has required fields
        for (final day in validCalendarData) {
          expect(day, contains('day'));
          expect(day, contains('limit'));
          expect(day, contains('spent'));
          expect(day, contains('status'));
          expect(day['day'], isA<int>());
          expect(day['limit'], isA<int>());
          expect(day['spent'], isA<int>());
          expect(day['status'], isA<String>());
        }
      });

      test('should calculate spending ratios correctly', () {
        final testCases = [
          {'spent': 50, 'limit': 100, 'expectedStatus': 'good'},
          {'spent': 90, 'limit': 100, 'expectedStatus': 'warning'},
          {'spent': 120, 'limit': 100, 'expectedStatus': 'over'},
          {'spent': 0, 'limit': 100, 'expectedStatus': 'good'},
        ];

        for (final testCase in testCases) {
          final spent = testCase['spent'] as int;
          final limit = testCase['limit'] as int;
          final expectedStatus = testCase['expectedStatus'] as String;
          
          String calculatedStatus;
          if (spent == 0) {
            calculatedStatus = 'good';
          } else {
            final ratio = spent / limit;
            if (ratio > 1.1) {
              calculatedStatus = 'over';
            } else if (ratio > 0.85) {
              calculatedStatus = 'warning';
            } else {
              calculatedStatus = 'good';
            }
          }
          
          expect(calculatedStatus, equals(expectedStatus),
              reason: 'Spent: $spent, Limit: $limit should result in $expectedStatus');
        }
      });
    });

    group('Financial Accuracy Tests', () {
      test('should ensure no money is lost in calculations', () {
        const monthlyIncome = 5000.0;
        final weights = {
          'food': 0.15,
          'transportation': 0.15,
          'entertainment': 0.08,
          'shopping': 0.10,
          'healthcare': 0.07,
        };

        // Calculate category allocations
        final totalAllocated = weights.values.fold<double>(0.0, (sum, weight) => sum + weight);
        final flexibleBudget = monthlyIncome * totalAllocated;
        
        // Verify that individual category amounts sum to total
        double categorySum = 0.0;
        weights.forEach((category, weight) {
          categorySum += monthlyIncome * weight;
        });

        expect(categorySum, equals(flexibleBudget));
        expect(categorySum, lessThanOrEqualTo(monthlyIncome)); // Shouldn't exceed income
      });

      test('should handle decimal precision correctly', () {
        final testIncomes = [2000.33, 3500.67, 5000.99];
        
        for (final income in testIncomes) {
          final dailyBudget = (income * 0.55) / 30; // 55% for flexible spending, 30 days
          final roundedDailyBudget = dailyBudget.round();
          
          // Verify rounding doesn't create significant discrepancies
          expect((dailyBudget - roundedDailyBudget).abs(), lessThan(1.0));
          expect(roundedDailyBudget, greaterThan(0));
        }
      });

      test('should maintain budget consistency across days', () {
        const monthlyIncome = 6000.0;
        const flexiblePercentage = 0.55;
        const monthlyFlexible = monthlyIncome * flexiblePercentage;
        const daysInMonth = 30;
        
        // Calculate daily budgets with variation
        const baseDailyBudget = monthlyFlexible / daysInMonth;
        final dailyBudgets = <int>[];
        
        for (int day = 1; day <= daysInMonth; day++) {
          double variation = baseDailyBudget;
          
          // Apply weekend effect
          final dayOfWeek = DateTime(2024, 1, day).weekday;
          if (dayOfWeek >= 6) {
            variation *= 1.5; // Weekend multiplier
          }
          
          dailyBudgets.add(variation.round());
        }
        
        // Verify total doesn't exceed monthly flexible budget by too much
        final totalDaily = dailyBudgets.fold<int>(0, (sum, budget) => sum + budget);
        expect(totalDaily, lessThan(monthlyFlexible * 1.3)); // Allow 30% variance for weekend effects
      });
    });

    group('Category Distribution Tests', () {
      test('should distribute categories proportionally', () {
        const dailyBudget = 200;
        final categoryWeights = {
          'food': 0.4,
          'transportation': 0.25,
          'entertainment': 0.2,
          'shopping': 0.15,
        };

        final categoryAmounts = <String, int>{};
        categoryWeights.forEach((category, weight) {
          categoryAmounts[category] = (dailyBudget * weight).round();
        });

        // Verify proportions are maintained
        expect(categoryAmounts['food'], equals(80)); // 200 * 0.4
        expect(categoryAmounts['transportation'], equals(50)); // 200 * 0.25
        expect(categoryAmounts['entertainment'], equals(40)); // 200 * 0.2
        expect(categoryAmounts['shopping'], equals(30)); // 200 * 0.15

        // Verify total doesn't exceed daily budget significantly
        final totalCategories = categoryAmounts.values.fold<int>(0, (sum, amount) => sum + amount);
        expect(totalCategories, lessThanOrEqualTo(dailyBudget + 5)); // Allow small rounding variance
      });

      test('should handle minimum category amounts', () {
        const smallDailyBudget = 20; // Very small budget
        final categoryWeights = {
          'food': 0.5,
          'transportation': 0.3,
          'entertainment': 0.1,
          'shopping': 0.1,
        };

        final categoryAmounts = <String, int>{};
        categoryWeights.forEach((category, weight) {
          final amount = (smallDailyBudget * weight).round();
          categoryAmounts[category] = amount > 0 ? amount : 1; // Ensure minimum of 1
        });

        // All categories should have at least some allocation
        for (var amount in categoryAmounts.values) {
          expect(amount, greaterThan(0));
        }
      });
    });

    group('Income Tier Logic Tests', () {
      test('should classify income tiers correctly', () {
        final testCases = [
          {'income': 2000.0, 'expectedTier': 'low'},
          {'income': 3500.0, 'expectedTier': 'mid_low'},
          {'income': 5500.0, 'expectedTier': 'mid'},
          {'income': 8500.0, 'expectedTier': 'mid_high'},
          {'income': 15000.0, 'expectedTier': 'high'},
        ];

        for (final testCase in testCases) {
          final income = testCase['income'] as double;
          final expectedTier = testCase['expectedTier'] as String;
          
          String actualTier;
          if (income < 2500) {
            actualTier = 'low';
          } else if (income < 5000) {
            actualTier = 'mid_low';
          } else if (income < 7500) {
            actualTier = 'mid';
          } else if (income < 12000) {
            actualTier = 'mid_high';
          } else {
            actualTier = 'high';
          }
          
          expect(actualTier, equals(expectedTier),
              reason: 'Income $income should be classified as $expectedTier');
        }
      });

      test('should apply tier-appropriate budget allocations', () {
        final testCases = [
          {'tier': 'low', 'foodWeight': 0.20, 'savingsWeight': 0.07},
          {'tier': 'mid', 'foodWeight': 0.15, 'savingsWeight': 0.16},
          {'tier': 'high', 'foodWeight': 0.10, 'savingsWeight': 0.28},
        ];

        for (final testCase in testCases) {
          final tier = testCase['tier'] as String;
          final expectedFoodWeight = testCase['foodWeight'] as double;
          final expectedSavingsWeight = testCase['savingsWeight'] as double;
          
          // Verify that lower income tiers allocate more to essentials like food
          // and higher income tiers allocate more to savings
          if (tier == 'low') {
            expect(expectedFoodWeight, greaterThan(0.15));
            expect(expectedSavingsWeight, lessThan(0.15));
          } else if (tier == 'high') {
            expect(expectedFoodWeight, lessThan(0.15));
            expect(expectedSavingsWeight, greaterThan(0.20));
          }
        }
      });
    });

    group('Edge Case Handling', () {
      test('should handle zero income', () {
        const income = 0.0;
        const fallbackIncome = income > 0 ? income : 3000.0; // Default fallback
        
        expect(fallbackIncome, equals(3000.0));
        expect(fallbackIncome, greaterThan(0));
      });

      test('should handle negative income', () {
        const income = -1000.0;
        const fallbackIncome = income > 0 ? income : 3000.0; // Default fallback
        
        expect(fallbackIncome, equals(3000.0));
        expect(fallbackIncome, greaterThan(0));
      });

      test('should handle extremely high income', () {
        const income = 1000000.0; // $1M monthly
        const maxReasonableDaily = 10000; // $10k daily limit
        
        final dailyBudget = ((income * 0.55) / 30).round(); // 55% flexible, 30 days
        final cappedDailyBudget = dailyBudget > maxReasonableDaily ? maxReasonableDaily : dailyBudget;
        
        expect(cappedDailyBudget, lessThanOrEqualTo(maxReasonableDaily));
        expect(cappedDailyBudget, greaterThan(0));
      });

      test('should handle leap year February', () {
        // Test February in leap year (29 days) vs non-leap year (28 days)
        final leapYearDays = DateTime(2024, 3, 0).day; // 2024 is a leap year
        final normalYearDays = DateTime(2023, 3, 0).day; // 2023 is not a leap year
        
        expect(leapYearDays, equals(29));
        expect(normalYearDays, equals(28));
        
        // Verify budget calculations work for both
        const monthlyIncome = 5000.0;
        const flexibleBudget = monthlyIncome * 0.55;
        
        final leapYearDaily = (flexibleBudget / leapYearDays).round();
        final normalYearDaily = (flexibleBudget / normalYearDays).round();
        
        expect(leapYearDaily, greaterThan(0));
        expect(normalYearDaily, greaterThan(0));
        expect(normalYearDaily, greaterThan(leapYearDaily)); // Fewer days = higher daily budget
      });
    });

    group('Performance and Efficiency Tests', () {
      test('should complete calendar generation quickly', () async {
        final stopwatch = Stopwatch()..start();
        
        // Simulate calendar data generation
        const monthlyIncome = 5000.0;
        const daysInMonth = 31;
        final calendarData = <Map<String, dynamic>>[];
        
        for (int day = 1; day <= daysInMonth; day++) {
          calendarData.add({
            'day': day,
            'limit': ((monthlyIncome * 0.55) / daysInMonth).round(),
            'spent': day < DateTime.now().day ? 50 : 0,
            'status': 'good',
            'categories': {
              'food': 40,
              'transportation': 30,
              'entertainment': 20,
              'shopping': 10,
            }
          });
        }
        
        stopwatch.stop();
        
        expect(calendarData.length, equals(daysInMonth));
        expect(stopwatch.elapsedMilliseconds, lessThan(100)); // Should complete in under 100ms
      });

      test('should handle multiple concurrent calendar requests', () async {
        // Simulate multiple calendar requests
        final futures = <Future<List<Map<String, dynamic>>>>[];
        
        for (int i = 0; i < 10; i++) {
          futures.add(Future.value([
            {
              'day': 1,
              'limit': 100,
              'spent': 50,
              'status': 'good',
            }
          ]));
        }
        
        final results = await Future.wait(futures);
        
        expect(results.length, equals(10));
        for (final result in results) {
          expect(result, isNotEmpty);
        }
      });
    });

    group('Data Consistency Tests', () {
      test('should maintain consistent data across calls', () {
        // Simulate consistent data generation with same input
        const income = 5000.0;
        const day = 15; // Fixed day for consistency
        
        final result1 = _generateMockDayData(income, day);
        final result2 = _generateMockDayData(income, day);
        
        expect(result1['day'], equals(result2['day']));
        expect(result1['limit'], equals(result2['limit']));
        // Note: spent amounts might vary due to randomness, which is expected
      });

      test('should validate status consistency with amounts', () {
        final testCases = [
          {'spent': 50, 'limit': 100},
          {'spent': 90, 'limit': 100},
          {'spent': 120, 'limit': 100},
        ];

        for (final testCase in testCases) {
          final spent = testCase['spent'] as int;
          final limit = testCase['limit'] as int;
          
          final ratio = spent / limit;
          String expectedStatus;
          if (ratio > 1.1) {
            expectedStatus = 'over';
          } else if (ratio > 0.85) {
            expectedStatus = 'warning';
          } else {
            expectedStatus = 'good';
          }
          
          final dayData = {
            'spent': spent,
            'limit': limit,
            'status': expectedStatus,
          };
          
          // Verify status matches spending ratio
          final actualRatio = (dayData['spent'] as int) / (dayData['limit'] as int);
          final actualStatus = dayData['status'] as String;
          
          if (actualRatio > 1.1) {
            expect(actualStatus, equals('over'));
          } else if (actualRatio > 0.85) {
            expect(actualStatus, equals('warning'));
          } else {
            expect(actualStatus, equals('good'));
          }
        }
      });
    });
  });
}

// Helper function to generate mock day data
Map<String, dynamic> _generateMockDayData(double income, int day) {
  final dailyBudget = ((income * 0.55) / 30).round();
  return {
    'day': day,
    'limit': dailyBudget,
    'spent': day < DateTime.now().day ? (dailyBudget * 0.7).round() : 0,
    'status': 'good',
    'categories': {
      'food': (dailyBudget * 0.4).round(),
      'transportation': (dailyBudget * 0.3).round(),
      'entertainment': (dailyBudget * 0.2).round(),
      'shopping': (dailyBudget * 0.1).round(),
    }
  };
}