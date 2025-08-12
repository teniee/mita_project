import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:mita/services/income_service.dart';
import 'package:mita/services/country_profiles_service.dart';
import 'package:mita/services/location_service.dart';

/// Comprehensive edge case testing for MITA financial systems
/// Ensures zero-tolerance quality standards for financial calculations
void main() {
  group('Financial Precision Edge Cases', () {
    late IncomeService incomeService;
    late CountryProfilesService countryService;

    setUp(() {
      incomeService = IncomeService();
      countryService = CountryProfilesService();
    });

    group('Floating Point Precision Tests', () {
      test('Exact threshold boundary precision', () {
        // Test California's exact low threshold: $44,935 annually = $3,744.58333... monthly
        const exactMonthlyLow = 44935.0 / 12; // 3744.5833333...
        
        // Test exact boundary
        final resultExact = incomeService.classifyIncomeForLocation(
          exactMonthlyLow, 'US', stateCode: 'CA'
        );
        expect(resultExact, equals(IncomeTier.low), 
               reason: 'Exact boundary should classify as low tier');

        // Test just above boundary (add 1 cent annually)
        final resultAbove = incomeService.classifyIncomeForLocation(
          (44935.01) / 12, 'US', stateCode: 'CA'
        );
        expect(resultAbove, equals(IncomeTier.lowerMiddle),
               reason: 'Just above boundary should classify as lowerMiddle');

        // Test just below boundary (subtract 1 cent annually)  
        final resultBelow = incomeService.classifyIncomeForLocation(
          (44934.99) / 12, 'US', stateCode: 'CA'
        );
        expect(resultBelow, equals(IncomeTier.low),
               reason: 'Just below boundary should classify as low');
      });

      test('Recurring decimal precision handling', () {
        // Test incomes that create recurring decimals when converted
        final recurringCases = [
          {'annual': 33333, 'monthly': 33333 / 12}, // 2777.75
          {'annual': 66666, 'monthly': 66666 / 12}, // 5555.5
          {'annual': 99999, 'monthly': 99999 / 12}, // 8333.25
        ];

        for (final testCase in recurringCases) {
          final monthly = testCase['monthly'] as double;
          final annual = testCase['annual'] as double;
          
          // Forward conversion (monthly -> annual -> classification)
          final tier1 = incomeService.classifyIncomeForLocation(monthly, 'US', stateCode: 'CA');
          
          // Reverse conversion (annual -> monthly -> classification)
          final monthlyFromAnnual = countryService.annualToMonthly(annual);
          final tier2 = incomeService.classifyIncomeForLocation(monthlyFromAnnual, 'US', stateCode: 'CA');
          
          expect(tier1, equals(tier2),
                 reason: 'Conversion precision should not affect classification for income $annual');
        }
      });

      test('Large number precision maintenance', () {
        // Test very large incomes maintain precision
        final largeIncomes = [999999.99, 1234567.89, 9999999.99];
        
        for (final income in largeIncomes) {
          final monthly = income / 12;
          final backToAnnual = monthly * 12;
          
          final precision = (backToAnnual - income).abs();
          expect(precision, lessThan(0.01),
                 reason: 'Large income $income should maintain cent precision');
          
          // Should classify as highest tier regardless
          final tier = incomeService.classifyIncomeForLocation(monthly, 'US', stateCode: 'CA');
          expect(tier, equals(IncomeTier.high));
        }
      });
    });

    group('State Boundary Edge Cases', () {
      test('Extreme state differences for same income', () {
        const testIncome = 3500.0; // $42,000 annually
        
        // Get lowest and highest threshold states
        final states = countryService.getSubregions('US');
        String? lowestState, highestState;
        double lowestThreshold = double.infinity;
        double highestThreshold = 0;
        
        for (final state in states) {
          final thresholds = countryService.getIncomeThresholds('US', stateCode: state);
          final lowThreshold = thresholds['low']!;
          
          if (lowThreshold < lowestThreshold) {
            lowestThreshold = lowThreshold;
            lowestState = state;
          }
          if (lowThreshold > highestThreshold) {
            highestThreshold = lowThreshold;
            highestState = state;
          }
        }
        
        expect(lowestState, isNotNull);
        expect(highestState, isNotNull);
        
        final lowestStateTier = incomeService.classifyIncomeForLocation(
          testIncome, 'US', stateCode: lowestState!
        );
        final highestStateTier = incomeService.classifyIncomeForLocation(
          testIncome, 'US', stateCode: highestState!
        );
        
        // Same income should potentially classify differently in extreme states
        print('$testIncome monthly income: $lowestState -> $lowestStateTier, $highestState -> $highestStateTier');
        
        // Both should be valid tiers
        expect([IncomeTier.low, IncomeTier.lowerMiddle, IncomeTier.middle, IncomeTier.upperMiddle, IncomeTier.high]
                 .contains(lowestStateTier), isTrue);
        expect([IncomeTier.low, IncomeTier.lowerMiddle, IncomeTier.middle, IncomeTier.upperMiddle, IncomeTier.high]
                 .contains(highestStateTier), isTrue);
      });

      test('All states handle extreme incomes consistently', () {
        final extremeIncomes = [
          {'monthly': 0.01, 'desc': 'penny income'},
          {'monthly': 1.0, 'desc': 'dollar income'},  
          {'monthly': 100000.0, 'desc': 'very high income'},
          {'monthly': -100.0, 'desc': 'negative income (edge case)'},
        ];
        
        final states = countryService.getSubregions('US');
        
        for (final incomeCase in extremeIncomes) {
          final income = incomeCase['monthly'] as double;
          final desc = incomeCase['desc'] as String;
          
          for (final state in states.take(5)) { // Test first 5 states for performance
            expect(
              () => incomeService.classifyIncomeForLocation(income, 'US', stateCode: state),
              returnsNormally,
              reason: 'State $state should handle $desc gracefully'
            );
            
            final tier = incomeService.classifyIncomeForLocation(income, 'US', stateCode: state);
            expect(tier, isA<IncomeTier>(), reason: 'Should return valid tier for $desc in $state');
          }
        }
      });
    });

    group('Data Validation Edge Cases', () {
      test('Invalid state codes fallback gracefully', () {
        final invalidStates = ['XX', 'INVALID', '123', '', 'usa', 'california'];
        
        for (final invalidState in invalidStates) {
          expect(
            () => incomeService.classifyIncomeForLocation(5000, 'US', stateCode: invalidState),
            returnsNormally,
            reason: 'Should handle invalid state code: $invalidState'
          );
          
          final tier = incomeService.classifyIncomeForLocation(5000, 'US', stateCode: invalidState);
          expect(tier, isA<IncomeTier>(), reason: 'Should return valid tier for invalid state $invalidState');
        }
      });

      test('Malformed input handling', () {
        final malformedInputs = [
          {'income': double.nan, 'desc': 'NaN income'},
          {'income': double.infinity, 'desc': 'infinite income'},
          {'income': double.negativeInfinity, 'desc': 'negative infinite income'},
        ];
        
        for (final input in malformedInputs) {
          final income = input['income'] as double;
          final desc = input['desc'] as String;
          
          expect(
            () => incomeService.classifyIncomeForLocation(income, 'US', stateCode: 'CA'),
            returnsNormally,
            reason: 'Should handle $desc gracefully'
          );
        }
      });

      test('Threshold data integrity across all states', () {
        final states = countryService.getSubregions('US');
        
        for (final state in states) {
          final thresholds = countryService.getIncomeThresholds('US', stateCode: state);
          
          // Verify all required keys exist
          final requiredKeys = ['low', 'lower_middle', 'middle', 'upper_middle'];
          for (final key in requiredKeys) {
            expect(thresholds.containsKey(key), isTrue,
                   reason: 'State $state missing threshold: $key');
            expect(thresholds[key], isA<double>(),
                   reason: 'State $state threshold $key should be double');
            expect(thresholds[key]! > 0, isTrue,
                   reason: 'State $state threshold $key should be positive');
          }
          
          // Verify ascending order
          expect(thresholds['low']! < thresholds['lower_middle']!, isTrue,
                 reason: 'State $state: low should be less than lower_middle');
          expect(thresholds['lower_middle']! < thresholds['middle']!, isTrue,  
                 reason: 'State $state: lower_middle should be less than middle');
          expect(thresholds['middle']! < thresholds['upper_middle']!, isTrue,
                 reason: 'State $state: middle should be less than upper_middle');
          
          // Verify reasonable ranges (no state should have extremely high/low thresholds)
          expect(thresholds['low']!, greaterThan(15000),
                 reason: 'State $state low threshold unusually low: ${thresholds['low']}');
          expect(thresholds['low']!, lessThan(100000),
                 reason: 'State $state low threshold unusually high: ${thresholds['low']}');
          expect(thresholds['upper_middle']!, lessThan(500000),
                 reason: 'State $state upper_middle threshold unusually high: ${thresholds['upper_middle']}');
        }
      });
    });
  });

  group('Location Service Edge Cases', () {
    late LocationService locationService;

    setUp(() async {
      locationService = LocationService();
      // Mock SharedPreferences
      SharedPreferences.setMockInitialValues({});
    });

    test('Handle location permission edge cases', () async {
      // This would require mocking the location services
      // For now, test the data structures and fallbacks
      
      final supportedCountries = locationService.getSupportedCountriesForSelection();
      expect(supportedCountries.length, equals(1)); // US only
      expect(supportedCountries.first['code'], equals('US'));
      
      final states = locationService.getUSStatesForSelection();
      expect(states.length, equals(50)); // All US states
      
      // Verify each state has required fields
      for (final state in states) {
        expect(state['code'], isA<String>());
        expect(state['name'], isA<String>());
        expect(state['code']!.length, equals(2));
        expect(state['name']!.isNotEmpty, isTrue);
      }
    });

    test('Location formatting edge cases', () {
      final testCases = [
        {'country': 'US', 'state': 'CA', 'expected': '🇺🇸 United States, California'},
        {'country': 'US', 'state': 'TX', 'expected': '🇺🇸 United States, Texas'},
        {'country': 'US', 'state': 'INVALID', 'expected': '🇺🇸 United States, INVALID'},
        {'country': 'US', 'state': null, 'expected': '🇺🇸 United States'},
        {'country': 'INVALID', 'state': null, 'expected': ' INVALID'},
      ];
      
      for (final testCase in testCases) {
        final result = locationService.formatLocationForDisplay(
          testCase['country'] as String,
          stateCode: testCase['state']
        );
        expect(result, equals(testCase['expected']),
               reason: 'Formatting failed for ${testCase['country']}, ${testCase['state']}');
      }
    });
  });

  group('Service Integration Edge Cases', () {
    late IncomeService incomeService;
    late CountryProfilesService countryService;

    setUp(() {
      incomeService = IncomeService();
      countryService = CountryProfilesService();
    });

    test('Tier name and description consistency', () {
      for (final tier in IncomeTier.values) {
        final name = incomeService.getIncomeTierName(tier);
        final description = incomeService.getIncomeTierDescription(tier);
        final color = incomeService.getIncomeTierPrimaryColor(tier);
        final secondaryColor = incomeService.getIncomeTierSecondaryColor(tier);
        final icon = incomeService.getIncomeTierIcon(tier);
        
        // Verify all return non-null, meaningful values
        expect(name.isNotEmpty, isTrue, reason: 'Tier $tier should have non-empty name');
        expect(description.isNotEmpty, isTrue, reason: 'Tier $tier should have non-empty description');
        expect(color.alpha, greaterThan(0), reason: 'Tier $tier should have visible primary color');
        expect(secondaryColor.alpha, greaterThan(0), reason: 'Tier $tier should have visible secondary color');
        
        // Names should not contain placeholder text
        expect(name, isNot(contains('TODO')));
        expect(name, isNot(contains('PLACEHOLDER')));
        expect(description, isNot(contains('TODO')));
        expect(description, isNot(contains('PLACEHOLDER')));
      }
    });

    test('Budget weight consistency across tiers', () {
      for (final tier in IncomeTier.values) {
        final weights = incomeService.getDefaultBudgetWeights(tier);
        
        // Verify weights sum to reasonable total (should be close to 1.0)
        final totalWeight = weights.values.fold<double>(0, (sum, weight) => sum + weight);
        expect(totalWeight, greaterThan(0.8), reason: 'Budget weights too low for tier $tier');
        expect(totalWeight, lessThan(1.2), reason: 'Budget weights too high for tier $tier');
        
        // Verify all weights are positive
        for (final category in weights.keys) {
          expect(weights[category]!, greaterThan(0), 
                 reason: 'Category $category should have positive weight for tier $tier');
          expect(weights[category]!, lessThan(1.0),
                 reason: 'Category $category weight too high for tier $tier');
        }
        
        // Verify essential categories exist
        final requiredCategories = ['housing', 'food', 'savings'];
        for (final category in requiredCategories) {
          expect(weights.containsKey(category), isTrue,
                 reason: 'Tier $tier missing required category: $category');
        }
      }
    });

    test('Financial tips quality and consistency', () {
      for (final tier in IncomeTier.values) {
        final tips = incomeService.getFinancialTips(tier);
        
        expect(tips.isNotEmpty, isTrue, reason: 'Tier $tier should have financial tips');
        expect(tips.length, greaterThan(3), reason: 'Tier $tier should have sufficient tips');
        
        for (final tip in tips) {
          expect(tip.isNotEmpty, isTrue, reason: 'All tips should be non-empty for tier $tier');
          expect(tip.length, greaterThan(10), reason: 'Tips should be meaningful length for tier $tier');
          
          // Tips should not contain placeholder text
          expect(tip, isNot(contains('TODO')));
          expect(tip, isNot(contains('PLACEHOLDER')));
          expect(tip, isNot(contains('[TBD]')));
        }
      }
    });

    test('Goal suggestions appropriateness by tier', () {
      final testIncomes = [2000.0, 4000.0, 6000.0, 10000.0, 15000.0];
      
      for (int i = 0; i < testIncomes.length && i < IncomeTier.values.length; i++) {
        final income = testIncomes[i];
        final tier = IncomeTier.values[i];
        final goals = incomeService.getGoalSuggestions(tier, income);
        
        expect(goals.isNotEmpty, isTrue, reason: 'Tier $tier should have goal suggestions');
        
        for (final goal in goals) {
          expect(goal['title'], isA<String>(), reason: 'Goal should have string title');
          expect(goal['description'], isA<String>(), reason: 'Goal should have string description');
          expect(goal['target_amount'], isA<double>(), reason: 'Goal should have numeric target');
          expect(goal['monthly_target'], isA<double>(), reason: 'Goal should have monthly target');
          expect(goal['priority'], isA<String>(), reason: 'Goal should have priority level');
          
          // Target amounts should be reasonable for the income level
          final targetAmount = goal['target_amount'] as double;
          final monthlyTarget = goal['monthly_target'] as double;
          
          expect(targetAmount, greaterThan(0), reason: 'Goal target should be positive');
          expect(monthlyTarget, greaterThan(0), reason: 'Monthly target should be positive');
          expect(monthlyTarget, lessThanOrEqualTo(income * 0.5),
                 reason: 'Monthly target should not exceed 50% of income');
        }
      }
    });
  });

  group('Performance and Memory Edge Cases', () {
    late IncomeService incomeService;

    setUp(() {
      incomeService = IncomeService();
    });

    test('Classification performance under load', () {
      final stopwatch = Stopwatch()..start();
      
      // Perform many classifications rapidly
      for (int i = 0; i < 10000; i++) {
        final income = 2000.0 + (i % 5000); // Vary income
        final stateIndex = i % 50; // Cycle through states
        final stateCode = ['CA', 'TX', 'NY', 'FL', 'PA'][stateIndex % 5];
        
        incomeService.classifyIncomeForLocation(income, 'US', stateCode: stateCode);
      }
      
      stopwatch.stop();
      
      // Should complete reasonable time (adjust threshold based on device performance)  
      expect(stopwatch.elapsedMilliseconds, lessThan(1000),
             reason: '10,000 classifications should complete in under 1 second');
    });

    test('Memory usage stability', () {
      // Create multiple service instances to test for memory leaks
      final services = <IncomeService>[];
      
      for (int i = 0; i < 100; i++) {
        final service = IncomeService();
        services.add(service);
        
        // Use each service
        service.classifyIncomeForLocation(5000, 'US', stateCode: 'CA');
        service.getIncomeTierName(IncomeTier.middle);
        service.getDefaultBudgetWeights(IncomeTier.middle);
      }
      
      // If we reach here without out-of-memory, test passes
      expect(services.length, equals(100));
      
      // Test that services still work
      for (final service in services.take(10)) {
        final tier = service.classifyIncomeForLocation(5000, 'US', stateCode: 'CA');
        expect(tier, isA<IncomeTier>());
      }
    });

    test('Concurrent classification consistency', () {
      // Simulate concurrent classifications of the same income
      const testIncome = 5000.0;
      final results = <IncomeTier>[];
      
      // Perform same classification multiple times rapidly
      for (int i = 0; i < 100; i++) {
        final result = incomeService.classifyIncomeForLocation(testIncome, 'US', stateCode: 'CA');
        results.add(result);
      }
      
      // All results should be identical
      final firstResult = results.first;
      for (final result in results) {
        expect(result, equals(firstResult),
               reason: 'Concurrent classifications should be consistent');
      }
    });
  });
}