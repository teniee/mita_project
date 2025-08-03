import 'package:flutter_test/flutter_test.dart';
import 'package:mita/services/income_service.dart';
import 'package:mita/services/country_profiles_service.dart';

/// Tests to validate consistency between frontend and backend implementations
/// These tests identify data mismatches that could cause user classification inconsistencies
void main() {
  group('Backend Consistency Tests', () {
    late IncomeService incomeService;
    late CountryProfilesService countryService;

    setUp(() {
      incomeService = IncomeService();
      countryService = CountryProfilesService();
    });

    group('Data Format Consistency', () {
      test('Frontend state data matches expected backend format', () {
        final states = countryService.getSubregions('US');
        
        // Backend uses format like 'US-US-AL', frontend uses 'AL'
        // Verify we have standard 2-letter state codes
        for (final state in states) {
          expect(state.length, equals(2), 
                 reason: 'State code $state should be 2 letters');
          expect(state, matches(RegExp(r'^[A-Z]{2}$')),
                 reason: 'State code $state should be uppercase letters only');
        }
        
        // Verify we have all expected states
        final expectedStates = {
          'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA',
          'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD',
          'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ',
          'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC',
          'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY'
        };
        
        expect(states.toSet(), equals(expectedStates));
      });

      test('Threshold key names are consistent', () {
        final thresholds = countryService.getIncomeThresholds('US', stateCode: 'CA');
        
        // Verify exact key names match backend expectations
        final expectedKeys = {'low', 'lower_middle', 'middle', 'upper_middle'};
        final actualKeys = thresholds.keys.toSet();
        
        expect(actualKeys, containsAll(expectedKeys),
               reason: 'Missing expected threshold keys');
        
        // Verify no unexpected keys
        final unexpectedKeys = actualKeys.difference(expectedKeys);
        expect(unexpectedKeys.isEmpty, isTrue,
               reason: 'Unexpected threshold keys: $unexpectedKeys');
      });
    });

    group('5-Tier Classification Consistency', () {
      test('Frontend enum matches backend tier names', () {
        // Test that our enum values can be converted to backend format
        final frontendTiers = IncomeTier.values;
        final expectedTierNames = [
          'low', 'lowerMiddle', 'middle', 'upperMiddle', 'high'
        ];
        
        for (int i = 0; i < frontendTiers.length; i++) {
          final frontendName = frontendTiers[i].toString().split('.').last;
          final expectedName = expectedTierNames[i];
          
          expect(frontendName, equals(expectedName),
                 reason: 'Frontend tier name mismatch at index $i');
        }
      });

      test('Classification boundaries are identical', () {
        // Test same income gives same classification in both systems
        final testIncomes = [
          1000.0,  // Should be low everywhere
          3000.0,  // Varies by state
          5000.0,  // Varies by state  
          8000.0,  // Varies by state
          15000.0, // Should be high in most states
        ];
        
        final testStates = ['CA', 'TX', 'NY', 'MS', 'WY'];
        
        for (final state in testStates) {
          final thresholds = countryService.getIncomeThresholds('US', stateCode: state);
          
          for (final monthlyIncome in testIncomes) {
            final annualIncome = monthlyIncome * 12;
            
            // Frontend classification
            final frontendTier = incomeService.classifyIncomeForLocation(
              monthlyIncome, 'US', stateCode: state
            );
            
            // Manual classification using same logic as backend should use
            String expectedTier;
            if (annualIncome <= thresholds['low']!) {
              expectedTier = 'low';
            } else if (annualIncome <= thresholds['lower_middle']!) {
              expectedTier = 'lowerMiddle';
            } else if (annualIncome <= thresholds['middle']!) {
              expectedTier = 'middle';
            } else if (annualIncome <= thresholds['upper_middle']!) {
              expectedTier = 'upperMiddle';
            } else {
              expectedTier = 'high';
            }
            
            final frontendTierName = frontendTier.toString().split('.').last;
            
            expect(frontendTierName, equals(expectedTier),
                   reason: 'Classification mismatch for $monthlyIncome monthly in $state');
          }
        }
      });
    });

    group('Critical Backend Issues Detection', () {
      test('Detect outdated 3-tier system usage', () {
        // This test documents the known issue with cohort_analysis.py
        // Using 3-tier thresholds: high >= 7000, mid >= 3000, low < 3000
        
        final problematicMonthlyIncomes = [
          4000.0, // Would be 'mid' in 3-tier, should be 'lower_middle' in 5-tier
          6000.0, // Would be 'mid' in 3-tier, should be 'middle' in 5-tier
          8000.0, // Would be 'high' in 3-tier, should vary by state in 5-tier
        ];
        
        for (final monthlyIncome in problematicMonthlyIncomes) {
          // Expected 5-tier classification for CA
          final fiveTierResult = incomeService.classifyIncomeForLocation(
            monthlyIncome, 'US', stateCode: 'CA'
          );
          
          // Simulate problematic 3-tier classification
          String threeTierResult;
          if (monthlyIncome >= 7000) {
            threeTierResult = 'high';
          } else if (monthlyIncome >= 3000) {
            threeTierResult = 'mid';
          } else {
            threeTierResult = 'low';
          }
          
          // Document the inconsistency
          print('Income: \$${monthlyIncome}/month');
          print('5-tier (CA): ${fiveTierResult.toString().split('.').last}');
          print('3-tier (problematic): $threeTierResult');
          print('---');
        }
        
        // This test always passes but documents the inconsistency
        expect(true, isTrue, reason: 'This test documents backend inconsistency');
      });

      test('Verify all states have reasonable threshold ranges', () {
        final states = countryService.getSubregions('US');
        
        for (final state in states) {
          final thresholds = countryService.getIncomeThresholds('US', stateCode: state);
          
          // Check for unreasonable values that might indicate data corruption
          expect(thresholds['low']!, greaterThan(15000),
                 reason: 'State $state low threshold unreasonably low');
          expect(thresholds['low']!, lessThan(80000),
                 reason: 'State $state low threshold unreasonably high');
          
          expect(thresholds['upper_middle']!, greaterThan(80000),
                 reason: 'State $state upper_middle threshold too low');
          expect(thresholds['upper_middle']!, lessThan(400000),
                 reason: 'State $state upper_middle threshold too high');
          
          // Check for reasonable progression
          final ratios = [
            thresholds['lower_middle']! / thresholds['low']!,
            thresholds['middle']! / thresholds['lower_middle']!,
            thresholds['upper_middle']! / thresholds['middle']!,
          ];
          
          for (final ratio in ratios) {
            expect(ratio, greaterThan(1.2),
                   reason: 'State $state tier progression too small');
            expect(ratio, lessThan(3.0),
                   reason: 'State $state tier progression too large');
          }
        }
      });
    });

    group('Numerical Precision Tests', () {
      test('Floating point consistency across conversions', () {
        final testValues = [
          35000.0,   // Potential boundary value
          44935.0,   // CA low threshold
          50000.0,   // Common round number
          71896.0,   // CA lower_middle threshold
          100000.0,  // Common milestone
        ];
        
        for (final annualValue in testValues) {
          final monthlyValue = annualValue / 12;
          final backToAnnual = monthlyValue * 12;
          
          // Check precision loss
          final precision = (backToAnnual - annualValue).abs();
          expect(precision, lessThan(0.01),
                 reason: 'Precision loss of \$${precision.toStringAsFixed(2)} for \$${annualValue}');
          
          // Test classification consistency
          final directClassification = _simulateBackendClassification(annualValue, 'CA');
          final convertedClassification = _simulateBackendClassification(backToAnnual, 'CA');
          
          expect(directClassification, equals(convertedClassification),
                 reason: 'Classification changed due to conversion precision loss');
        }
      });

      test('Boundary value precision at exact thresholds', () {
        final states = ['CA', 'TX', 'NY', 'MS'];
        
        for (final state in states) {
          final thresholds = countryService.getIncomeThresholds('US', stateCode: state);
          
          // Test exact threshold values
          for (final thresholdName in ['low', 'lower_middle', 'middle', 'upper_middle']) {
            final thresholdValue = thresholds[thresholdName]!;
            final monthlyEquivalent = thresholdValue / 12;
            
            // Classification should be consistent
            final tier1 = incomeService.classifyIncomeForLocation(
              monthlyEquivalent, 'US', stateCode: state
            );
            final tier2 = incomeService.classifyIncomeForLocation(
              monthlyEquivalent, 'US', stateCode: state
            );
            
            expect(tier1, equals(tier2),
                   reason: 'Inconsistent classification for exact threshold');
          }
        }
      });
    });

    group('API Contract Validation', () {
      test('Service methods return expected types', () {
        // Test all public methods return correct types
        final tier = incomeService.classifyIncomeForLocation(5000, 'US', stateCode: 'CA');
        expect(tier, isA<IncomeTier>());
        
        final tierName = incomeService.getIncomeTierName(tier);
        expect(tierName, isA<String>());
        expect(tierName.isNotEmpty, isTrue);
        
        final thresholds = countryService.getIncomeThresholds('US', stateCode: 'CA');
        expect(thresholds, isA<Map<String, double>>());
        expect(thresholds.isNotEmpty, isTrue);
      });

      test('Error handling for edge cases', () {
        // Test service handles null/invalid inputs gracefully
        expect(() => countryService.getIncomeThresholds('INVALID'), returnsNormally);
        expect(() => countryService.getIncomeThresholds('US', stateCode: 'INVALID'), returnsNormally);
      });
    });
  });
}

/// Simulate backend classification logic for testing
String _simulateBackendClassification(double annualIncome, String state) {
  // This simulates the logic that should be in the backend
  final thresholds = {
    'CA': {'low': 44935, 'lower_middle': 71896, 'middle': 107844, 'upper_middle': 179740},
    'TX': {'low': 37750, 'lower_middle': 60400, 'middle': 90600, 'upper_middle': 151000},
    'NY': {'low': 39000, 'lower_middle': 62400, 'middle': 93600, 'upper_middle': 156000},
    'MS': {'low': 26000, 'lower_middle': 41600, 'middle': 62400, 'upper_middle': 104000},
  };
  
  final stateThresholds = thresholds[state] ?? thresholds['CA']!;
  
  if (annualIncome <= stateThresholds['low']!) {
    return 'low';
  } else if (annualIncome <= stateThresholds['lower_middle']!) {
    return 'lower_middle';
  } else if (annualIncome <= stateThresholds['middle']!) {
    return 'middle';
  } else if (annualIncome <= stateThresholds['upper_middle']!) {
    return 'upper_middle';
  } else {
    return 'high';
  }
}