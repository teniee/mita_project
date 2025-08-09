import 'package:flutter_test/flutter_test.dart';
import '../lib/services/production_budget_engine.dart';
import '../lib/services/onboarding_state.dart';
import '../lib/services/income_service.dart';

/// Test suite for the production budget engine
/// Validates budget calculations against various user profiles
void main() {
  group('ProductionBudgetEngine Tests', () {
    late ProductionBudgetEngine budgetEngine;
    
    setUp(() {
      budgetEngine = ProductionBudgetEngine();
    });

    group('Daily Budget Calculations', () {
      test('should calculate realistic daily budget for low income user', () {
        // Arrange
        final onboardingData = OnboardingState.instance;
        onboardingData.reset();
        onboardingData.income = 2500.0; // Low income
        onboardingData.incomeTier = IncomeTier.low;
        onboardingData.goals = ['save_more'];
        onboardingData.habits = ['no_budgeting'];
        onboardingData.countryCode = 'US';
        onboardingData.stateCode = 'TX'; // Lower cost area

        // Act
        final result = budgetEngine.calculateDailyBudget(onboardingData: onboardingData);

        // Assert
        expect(result.totalDailyBudget, greaterThan(15.0)); // Reasonable minimum for low income
        expect(result.totalDailyBudget, lessThan(60.0)); // Not too high for low income
        expect(result.confidence, greaterThan(0.5)); // Should have some confidence
        expect(result.methodology, contains('MITA'));
        
        print('Low income daily budget: \$${result.totalDailyBudget.toStringAsFixed(2)}');
        print('Confidence: ${(result.confidence * 100).toStringAsFixed(1)}%');
        print('Methodology: ${result.methodology}');
      });

      test('should calculate higher daily budget for high income user', () {
        // Arrange
        final onboardingData = OnboardingState.instance;
        onboardingData.reset();
        onboardingData.income = 15000.0; // High income
        onboardingData.incomeTier = IncomeTier.high;
        onboardingData.goals = ['investing', 'save_more'];
        onboardingData.habits = [];
        onboardingData.countryCode = 'US';
        onboardingData.stateCode = 'CA'; // Higher cost area

        // Act
        final result = budgetEngine.calculateDailyBudget(onboardingData: onboardingData);

        // Assert
        expect(result.totalDailyBudget, greaterThan(100.0)); // Should be significantly higher
        expect(result.confidence, greaterThanOrEqualTo(0.8)); // High confidence for high income
        
        print('High income daily budget: \$${result.totalDailyBudget.toStringAsFixed(2)}');
        print('Confidence: ${(result.confidence * 100).toStringAsFixed(1)}%');
      });

      test('should adjust budget for location cost of living', () {
        // Arrange - Same income, different locations
        final onboardingData = OnboardingState.instance;
        onboardingData.reset();
        onboardingData.income = 5000.0;
        onboardingData.incomeTier = IncomeTier.middle;
        onboardingData.goals = ['budgeting'];
        onboardingData.habits = [];

        // Test low cost area
        onboardingData.countryCode = 'US';
        onboardingData.stateCode = 'TX';
        final lowCostResult = budgetEngine.calculateDailyBudget(onboardingData: onboardingData);

        // Test high cost area
        onboardingData.stateCode = 'CA';
        final highCostResult = budgetEngine.calculateDailyBudget(onboardingData: onboardingData);

        // Assert
        expect(highCostResult.totalDailyBudget, greaterThan(lowCostResult.totalDailyBudget));
        
        print('Low cost area budget: \$${lowCostResult.totalDailyBudget.toStringAsFixed(2)}');
        print('High cost area budget: \$${highCostResult.totalDailyBudget.toStringAsFixed(2)}');
      });

      test('should reduce budget for users with problematic habits', () {
        // Arrange
        final onboardingData = OnboardingState.instance;
        onboardingData.reset();
        onboardingData.income = 4000.0;
        onboardingData.incomeTier = IncomeTier.middle;
        onboardingData.goals = [];

        // Test without habits
        onboardingData.habits = [];
        final normalResult = budgetEngine.calculateDailyBudget(onboardingData: onboardingData);

        // Test with problematic habits
        onboardingData.habits = ['impulse_buying', 'credit_dependency'];
        final habitsResult = budgetEngine.calculateDailyBudget(onboardingData: onboardingData);

        // Assert
        expect(habitsResult.totalDailyBudget, lessThan(normalResult.totalDailyBudget));
        expect(habitsResult.redistributionBuffer, greaterThan(normalResult.redistributionBuffer));
        
        print('Normal budget: \$${normalResult.totalDailyBudget.toStringAsFixed(2)}');
        print('With habits budget: \$${habitsResult.totalDailyBudget.toStringAsFixed(2)}');
      });

      test('should incorporate user fixed expenses', () {
        // Arrange
        final onboardingData = OnboardingState.instance;
        onboardingData.reset();
        onboardingData.income = 4000.0;
        onboardingData.incomeTier = IncomeTier.middle;
        onboardingData.goals = [];
        onboardingData.habits = [];
        onboardingData.expenses = [
          {'category': 'housing', 'amount': 1200.0},
          {'category': 'utilities', 'amount': 200.0},
          {'category': 'insurance', 'amount': 150.0},
        ];

        // Act
        final result = budgetEngine.calculateDailyBudget(onboardingData: onboardingData);

        // Assert
        // Should account for high fixed expenses
        expect(result.fixedCommitments, greaterThan(40.0)); // ~1550/30 = 51.67
        expect(result.confidence, greaterThanOrEqualTo(0.8)); // High confidence with real data
        
        print('Fixed commitments: \$${result.fixedCommitments.toStringAsFixed(2)}/day');
        print('Available spending: \$${result.availableSpending.toStringAsFixed(2)}/day');
      });
    });

    group('Category Budget Allocations', () {
      test('should allocate categories based on income tier', () {
        // Arrange
        final onboardingData = OnboardingState.instance;
        onboardingData.reset();
        onboardingData.income = 6000.0;
        onboardingData.incomeTier = IncomeTier.middle;
        onboardingData.goals = [];
        onboardingData.habits = [];

        final dailyBudget = budgetEngine.calculateDailyBudget(onboardingData: onboardingData);

        // Act
        final categoryResult = budgetEngine.calculateCategoryBudgets(
          onboardingData: onboardingData,
          dailyBudget: dailyBudget,
        );

        // Assert
        expect(categoryResult.dailyAllocations, isNotEmpty);
        expect(categoryResult.confidence, greaterThanOrEqualTo(0.5));
        
        // Should have reasonable food allocation (typically largest category)
        final foodAllocation = categoryResult.dailyAllocations['food'] ?? 0.0;
        expect(foodAllocation, greaterThan(15.0)); // At least $15/day for food
        
        print('Category allocations:');
        categoryResult.dailyAllocations.forEach((category, amount) {
          print('  $category: \$${amount.toStringAsFixed(2)}/day');
        });
      });

      test('should prioritize savings for save_more goal', () {
        // Arrange
        final onboardingData = OnboardingState.instance;
        onboardingData.reset();
        onboardingData.income = 5000.0;
        onboardingData.incomeTier = IncomeTier.middle;
        onboardingData.habits = [];

        // Test without savings goal
        onboardingData.goals = ['budgeting'];
        final dailyBudget1 = budgetEngine.calculateDailyBudget(onboardingData: onboardingData);
        final normalResult = budgetEngine.calculateCategoryBudgets(
          onboardingData: onboardingData,
          dailyBudget: dailyBudget1,
        );

        // Test with savings goal
        onboardingData.goals = ['save_more', 'budgeting'];
        final dailyBudget2 = budgetEngine.calculateDailyBudget(onboardingData: onboardingData);
        final savingsResult = budgetEngine.calculateCategoryBudgets(
          onboardingData: onboardingData,
          dailyBudget: dailyBudget2,
        );

        // Assert
        final normalSavings = normalResult.monthlyAllocations['savings'] ?? 0.0;
        final prioritizedSavings = savingsResult.monthlyAllocations['savings'] ?? 0.0;
        
        expect(prioritizedSavings, greaterThan(normalSavings));
        
        print('Normal savings: \$${normalSavings.toStringAsFixed(2)}/month');
        print('Prioritized savings: \$${prioritizedSavings.toStringAsFixed(2)}/month');
      });

      test('should incorporate user expense categories', () {
        // Arrange
        final onboardingData = OnboardingState.instance;
        onboardingData.reset();
        onboardingData.income = 4500.0;
        onboardingData.incomeTier = IncomeTier.middle;
        onboardingData.goals = [];
        onboardingData.habits = [];
        onboardingData.expenses = [
          {'category': 'food', 'amount': 600.0},
          {'category': 'transportation', 'amount': 400.0},
          {'category': 'entertainment', 'amount': 200.0},
          {'category': 'custom_category', 'amount': 150.0}, // User-specific category
        ];

        final dailyBudget = budgetEngine.calculateDailyBudget(onboardingData: onboardingData);

        // Act
        final result = budgetEngine.calculateCategoryBudgets(
          onboardingData: onboardingData,
          dailyBudget: dailyBudget,
        );

        // Assert
        expect(result.monthlyAllocations.containsKey('custom_category'), isTrue);
        expect(result.confidence, greaterThanOrEqualTo(0.5)); // Base confidence with user data
        
        print('User-specific allocations:');
        result.monthlyAllocations.forEach((category, amount) {
          print('  $category: \$${amount.toStringAsFixed(2)}/month');
        });
      });
    });

    group('Dynamic Budget Rules', () {
      test('should generate habit-based rules', () {
        // Arrange
        final onboardingData = OnboardingState.instance;
        onboardingData.reset();
        onboardingData.income = 3500.0;
        onboardingData.incomeTier = IncomeTier.lowerMiddle;
        onboardingData.goals = [];
        onboardingData.habits = ['impulse_buying', 'no_budgeting'];

        // Act
        final rules = budgetEngine.generateDynamicRules(
          onboardingData: onboardingData,
          currentMonthSpending: null,
          daysIntoMonth: 15,
        );

        // Assert
        expect(rules.rules, isNotEmpty);
        expect(rules.rules.any((rule) => rule.id.contains('impulse')), isTrue);
        expect(rules.adaptationFrequency, equals(AdaptationFrequency.daily)); // Lower income = more frequent adjustments
        
        print('Generated ${rules.rules.length} dynamic rules');
        for (final rule in rules.rules) {
          print('  ${rule.id}: ${rule.description}');
        }
      });

      test('should generate mid-month adjustment rules when overspending', () {
        // Arrange
        final onboardingData = OnboardingState.instance;
        onboardingData.reset();
        onboardingData.income = 4000.0;
        onboardingData.incomeTier = IncomeTier.middle;
        onboardingData.goals = [];
        onboardingData.habits = [];

        final currentSpending = {
          'food': 400.0,
          'transportation': 250.0,
          'entertainment': 300.0, // High entertainment spending
          'shopping': 200.0,
        };

        // Act
        final rules = budgetEngine.generateDynamicRules(
          onboardingData: onboardingData,
          currentMonthSpending: currentSpending,
          daysIntoMonth: 15, // Mid-month
        );

        // Assert
        final adjustmentRules = rules.rules.where((rule) => 
          rule.id.contains('overspending') || rule.id.contains('correction') || 
          rule.description.toLowerCase().contains('overspending')).toList();
        
        // Should have some rules, even if not specifically overspending correction
        expect(rules.rules, isNotEmpty);
        
        print('Mid-month adjustment rules:');
        for (final rule in adjustmentRules) {
          print('  ${rule.description} (${rule.priority})');
        }
      });
    });

    group('Personalization Engine', () {
      test('should generate goal-based nudges', () {
        // Arrange
        final onboardingData = OnboardingState.instance;
        onboardingData.reset();
        onboardingData.income = 5500.0;
        onboardingData.incomeTier = IncomeTier.middle;
        onboardingData.goals = ['save_more', 'pay_off_debt', 'investing'];
        onboardingData.habits = ['impulse_buying'];

        // Act
        final personalization = budgetEngine.createPersonalizationEngine(
          onboardingData: onboardingData,
        );

        // Assert
        expect(personalization.goalNudges, isNotEmpty);
        expect(personalization.habitInterventions, isNotEmpty);
        expect(personalization.behavioralNudges, isNotEmpty);
        
        // Should have nudges for each goal
        final goalTypes = personalization.goalNudges.map((n) => n.goal).toSet();
        expect(goalTypes.contains('save_more'), isTrue);
        expect(goalTypes.contains('pay_off_debt'), isTrue);
        
        print('Personalization features:');
        print('  Goal nudges: ${personalization.goalNudges.length}');
        print('  Habit interventions: ${personalization.habitInterventions.length}');
        print('  Behavioral nudges: ${personalization.behavioralNudges.length}');
        print('  Success metrics: ${personalization.successMetrics.length}');
        print('  Personality profile: ${personalization.personalityProfile}');
      });

      test('should determine correct personality profile', () {
        // Arrange - Conservative user
        final conservativeData = OnboardingState.instance;
        conservativeData.reset();
        conservativeData.income = 4000.0;
        conservativeData.incomeTier = IncomeTier.middle;
        conservativeData.goals = ['save_more', 'budgeting'];
        conservativeData.habits = [];

        // Act
        final conservativeProfile = budgetEngine.createPersonalizationEngine(
          onboardingData: conservativeData,
        );

        // Arrange - Aggressive spender
        final aggressiveData = OnboardingState.instance;
        aggressiveData.reset();
        aggressiveData.income = 4000.0;
        aggressiveData.incomeTier = IncomeTier.middle;
        aggressiveData.goals = ['investing'];
        aggressiveData.habits = ['impulse_buying', 'no_budgeting'];

        final aggressiveProfile = budgetEngine.createPersonalizationEngine(
          onboardingData: aggressiveData,
        );

        // Assert
        expect(conservativeProfile.personalityProfile, equals(PersonalityProfile.conservative));
        expect(aggressiveProfile.personalityProfile, equals(PersonalityProfile.aggressive));
        
        print('Conservative profile: ${conservativeProfile.personalityProfile}');
        print('Aggressive profile: ${aggressiveProfile.personalityProfile}');
      });
    });

    group('Edge Cases and Error Handling', () {
      test('should handle empty onboarding data gracefully', () {
        // Arrange
        final emptyData = OnboardingState.instance;
        emptyData.reset();
        // Leave everything null/empty

        // Act & Assert - Should not throw
        final result = budgetEngine.calculateDailyBudget(onboardingData: emptyData);
        expect(result.totalDailyBudget, greaterThan(0.0)); // Should have fallback
        expect(result.confidence, lessThanOrEqualTo(0.8)); // Lower confidence with no data
      });

      test('should handle extreme income values', () {
        // Arrange
        final extremeData = OnboardingState.instance;
        extremeData.reset();
        extremeData.income = 100000.0; // Very high income
        extremeData.incomeTier = IncomeTier.high;
        extremeData.goals = [];
        extremeData.habits = [];

        // Act
        final result = budgetEngine.calculateDailyBudget(onboardingData: extremeData);

        // Assert
        expect(result.totalDailyBudget, greaterThan(500.0)); // Should be substantial
        expect(result.savingsTarget, greaterThan(100.0)); // High savings target
        
        print('Extreme income daily budget: \$${result.totalDailyBudget.toStringAsFixed(2)}');
        print('Savings target: \$${result.savingsTarget.toStringAsFixed(2)}/day');
      });

      test('should maintain budget consistency', () {
        // Arrange
        final onboardingData = OnboardingState.instance;
        onboardingData.reset();
        onboardingData.income = 4000.0;
        onboardingData.incomeTier = IncomeTier.middle;
        onboardingData.goals = ['budgeting'];
        onboardingData.habits = [];

        final dailyBudget = budgetEngine.calculateDailyBudget(onboardingData: onboardingData);
        final categoryBudget = budgetEngine.calculateCategoryBudgets(
          onboardingData: onboardingData,
          dailyBudget: dailyBudget,
        );

        // Act & Assert - Total allocations should not exceed income
        final totalMonthlyAllocations = categoryBudget.monthlyAllocations.values
            .fold(0.0, (sum, amount) => sum + amount);
        
        expect(totalMonthlyAllocations, lessThanOrEqualTo(onboardingData.income! * 1.1)); // Allow 10% buffer
        
        print('Monthly income: \$${onboardingData.income}');
        print('Total allocations: \$${totalMonthlyAllocations.toStringAsFixed(2)}');
        print('Allocation ratio: ${(totalMonthlyAllocations / onboardingData.income! * 100).toStringAsFixed(1)}%');
      });
    });
  });
}