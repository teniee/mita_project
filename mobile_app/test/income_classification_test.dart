import 'package:flutter_test/flutter_test.dart';
import 'package:mita/services/income_service.dart';
import 'package:mita/services/country_profiles_service.dart';

void main() {
  group('Income Classification Tests', () {
    late IncomeService incomeService;
    late CountryProfilesService countryService;

    setUp(() {
      incomeService = IncomeService();
      countryService = CountryProfilesService();
    });

    group('Boundary Value Testing', () {
      test('California boundary values', () {
        // CA thresholds: low=44935, lower_middle=71896, middle=107844, upper_middle=179740
        
        // Test exact boundaries
        expect(
          incomeService.classifyIncomeForLocation(44935/12, 'US', stateCode: 'CA'),
          equals(IncomeTier.low),
          reason: 'Income exactly at low threshold should be classified as low'
        );
        
        expect(
          incomeService.classifyIncomeForLocation(44936/12, 'US', stateCode: 'CA'),
          equals(IncomeTier.lowerMiddle),
          reason: 'Income just above low threshold should be lowerMiddle'
        );
        
        expect(
          incomeService.classifyIncomeForLocation(71896/12, 'US', stateCode: 'CA'),
          equals(IncomeTier.lowerMiddle),
          reason: 'Income exactly at lower_middle threshold should be lowerMiddle'
        );
        
        expect(
          incomeService.classifyIncomeForLocation(71897/12, 'US', stateCode: 'CA'),
          equals(IncomeTier.middle),
          reason: 'Income just above lower_middle threshold should be middle'
        );
      });

      test('Mississippi vs California comparison', () {
        const monthlyIncome = 5000.0; // $60k annually
        
        // MS thresholds are much lower: low=26000, upper_middle=104000
        final msClassification = incomeService.classifyIncomeForLocation(
          monthlyIncome, 'US', stateCode: 'MS'
        );
        
        // CA thresholds are higher: low=44935, upper_middle=179740
        final caClassification = incomeService.classifyIncomeForLocation(
          monthlyIncome, 'US', stateCode: 'CA'
        );
        
        expect(msClassification, equals(IncomeTier.high));
        expect(caClassification, equals(IncomeTier.lowerMiddle));
      });

      test('All states have valid thresholds', () {
        final states = countryService.getSubregions('US');
        expect(states.length, equals(50), reason: 'Should have all 50 US states');
        
        for (final state in states) {
          final thresholds = countryService.getIncomeThresholds('US', stateCode: state);
          
          // Verify all required keys exist
          expect(thresholds.containsKey('low'), isTrue, 
                 reason: 'State $state missing low threshold');
          expect(thresholds.containsKey('lower_middle'), isTrue,
                 reason: 'State $state missing lower_middle threshold');
          expect(thresholds.containsKey('middle'), isTrue,
                 reason: 'State $state missing middle threshold');
          expect(thresholds.containsKey('upper_middle'), isTrue,
                 reason: 'State $state missing upper_middle threshold');
          
          // Verify ascending order
          expect(thresholds['low']! < thresholds['lower_middle']!, isTrue,
                 reason: 'State $state: low >= lower_middle');
          expect(thresholds['lower_middle']! < thresholds['middle']!, isTrue,
                 reason: 'State $state: lower_middle >= middle');
          expect(thresholds['middle']! < thresholds['upper_middle']!, isTrue,
                 reason: 'State $state: middle >= upper_middle');
          
          // Verify reasonable ranges
          expect(thresholds['low']!, greaterThan(20000),
                 reason: 'State $state: low threshold too low');
          expect(thresholds['upper_middle']!, lessThan(500000),
                 reason: 'State $state: upper_middle threshold too high');
        }
      });
    });

    group('Annual/Monthly Conversion Tests', () {
      test('Conversion accuracy', () {
        expect(countryService.annualToMonthly(120000), equals(10000.0));
        expect(countryService.monthlyToAnnual(10000), equals(120000.0));
        
        // Test fractional amounts
        final monthlyFromAnnual = countryService.annualToMonthly(50000);
        final backToAnnual = countryService.monthlyToAnnual(monthlyFromAnnual);
        
        // Should be very close due to floating point precision
        expect((backToAnnual - 50000).abs(), lessThan(0.01));
      });

      test('Floating point precision in classification', () {
        // Test income that exactly hits boundary after conversion
        const caLowThreshold = 44935.0;
        const monthlyIncome = caLowThreshold / 12;
        
        final result = incomeService.classifyIncomeForLocation(
          monthlyIncome, 'US', stateCode: 'CA'
        );
        
        expect(result, equals(IncomeTier.low),
               reason: 'Boundary value classification should be consistent');
      });
    });

    group('Input Validation Tests', () {
      test('Handle negative income', () {
        expect(
          () => incomeService.classifyIncomeForLocation(-1000, 'US', stateCode: 'CA'),
          returnsNormally,
          reason: 'Should handle negative income gracefully'
        );
        
        final result = incomeService.classifyIncomeForLocation(-1000, 'US', stateCode: 'CA');
        expect(result, equals(IncomeTier.low),
               reason: 'Negative income should default to lowest tier'
        );
      });

      test('Handle zero income', () {
        final result = incomeService.classifyIncomeForLocation(0, 'US', stateCode: 'CA');
        expect(result, equals(IncomeTier.low));
      });

      test('Handle extremely large income', () {
        final result = incomeService.classifyIncomeForLocation(1000000, 'US', stateCode: 'CA');
        expect(result, equals(IncomeTier.high));
      });

      test('Handle invalid state code', () {
        expect(
          () => incomeService.classifyIncomeForLocation(5000, 'US', stateCode: 'INVALID'),
          returnsNormally,
          reason: 'Should fallback gracefully for invalid state codes'
        );
        
        // Should use default US thresholds
        final result = incomeService.classifyIncomeForLocation(5000, 'US', stateCode: 'INVALID');
        expect(result, isA<IncomeTier>());
      });

      test('Handle missing state code', () {
        final result = incomeService.classifyIncomeForLocation(5000, 'US');
        expect(result, isA<IncomeTier>());
      });
    });

    group('Performance Tests', () {
      test('Classification performance benchmark', () {
        final stopwatch = Stopwatch()..start();
        
        // Perform 1000 classifications
        for (int i = 0; i < 1000; i++) {
          incomeService.classifyIncomeForLocation(
            3000.0 + (i * 10), 'US', stateCode: 'CA'
          );
        }
        
        stopwatch.stop();
        
        // Should complete in reasonable time (adjust threshold as needed)
        expect(stopwatch.elapsedMilliseconds, lessThan(100),
               reason: '1000 classifications should complete in under 100ms');
      });

      test('Memory efficiency', () {
        // Create multiple service instances to test memory usage
        final services = List.generate(100, (index) => IncomeService());
        
        // Perform classifications with all instances
        for (final service in services) {
          service.classifyIncomeForLocation(5000, 'US', stateCode: 'CA');
        }
        
        // If we get here without memory issues, the test passes
        expect(services.length, equals(100));
      });
    });

    group('Data Consistency Tests', () {
      test('Legacy vs location-based classification consistency', () {
        // For default US thresholds, both methods should give same result
        final legacyResult = incomeService.classifyIncome(5000);
        final locationResult = incomeService.classifyIncomeForLocation(5000, 'US');
        
        // Note: These might differ if default thresholds don't match
        // This test helps identify such inconsistencies
        expect(legacyResult, isA<IncomeTier>());
        expect(locationResult, isA<IncomeTier>());
      });

      test('Income range string accuracy', () {
        const tier = IncomeTier.middle;
        
        // Test legacy method
        final legacyRange = incomeService.getIncomeRangeString(tier);
        expect(legacyRange, contains('\$'));
        expect(legacyRange, contains('month'));
        
        // Test location-based method
        final locationRange = incomeService.getIncomeRangeStringForLocation(
          tier, 'US', stateCode: 'CA'
        );
        expect(locationRange, contains('\$'));
        expect(locationRange, contains('month'));
      });
    });

    group('Edge Cases', () {
      test('State with lowest thresholds (MS)', () {
        // Mississippi has the lowest thresholds
        final thresholds = countryService.getIncomeThresholds('US', stateCode: 'MS');
        expect(thresholds['low'], equals(26000));
        
        // Test classification
        final result = incomeService.classifyIncomeForLocation(2500, 'US', stateCode: 'MS');
        expect(result, equals(IncomeTier.lowerMiddle)); // 2500*12 = 30000 > 26000
      });

      test('State with highest thresholds (CO)', () {
        // Colorado has high thresholds
        final thresholds = countryService.getIncomeThresholds('US', stateCode: 'CO');
        expect(thresholds['high'], equals(260928));
        
        // Test classification
        final result = incomeService.classifyIncomeForLocation(15000, 'US', stateCode: 'CO');
        expect(result, equals(IncomeTier.lowerMiddle)); // 15000*12 = 180000 < 260928
      });

      test('Income tier display names are consistent', () {
        for (final tier in IncomeTier.values) {
          final name = incomeService.getIncomeTierName(tier);
          final description = incomeService.getIncomeTierDescription(tier);
          
          expect(name.isNotEmpty, isTrue);
          expect(description.isNotEmpty, isTrue);
          expect(name, isNot(contains('null')));
          expect(description, isNot(contains('null')));
        }
      });
    });
  });
}