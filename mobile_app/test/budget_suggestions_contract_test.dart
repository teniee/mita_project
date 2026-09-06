/// The `budgetSuggestions` map has exactly two producers. Consumers must read
/// only keys those producers actually emit.
///
/// Producers (see BudgetProvider.loadBudgetSuggestions):
///   1. BudgetAdapterService.getEnhancedBudgetSuggestions() ->
///        suggestions, total_count, enhanced_features_active,
///        confidence_level, methodology, last_updated
///   2. ApiService.getBudgetSuggestions() -> GET /budget/suggestions ->
///        suggestions, total_potential_savings, priority_areas
///
/// insights_screen and main_screen used to read `confidence`,
/// `intelligent_insights` and `category_insights`. No producer emits any of
/// them, so an entire enhanced-insights block and a dashboard health-score
/// block never executed.
///
/// The tempting "fix" — mapping confidence_level onto confidence — would have
/// been worse than the dead code: both blocks derived a financial-health
/// score and a letter grade from budget-engine confidence:
///     'score': (confidence * 100).round()
///     'grade': _getGradeFromConfidence(confidence)   // 0.75 -> "B+"
/// Engine confidence describes how sure the allocator is about its own
/// arithmetic. It is not a measurement of the user's financial health, and
/// rendering it as a B+ is the fabrication class already removed from
/// Insights, Mood and the cohort/challenge fallbacks. Both blocks were
/// deleted instead.
///
/// Item shape also differs between producers: the adapter emits 'message',
/// the backend emits 'text'. daily_budget_screen read only 'message' and fell
/// back to suggestion.toString(), rendering the raw Dart map
/// "{id: 1, text: Keep tracking expenses..., category: general, ...}" inside
/// the "AI Budget Suggestions" card.

import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

void main() {
  final adapter =
      File('lib/services/budget_adapter_service.dart').readAsStringSync();
  final insights = File('lib/screens/insights_screen.dart').readAsStringSync();
  final main = File('lib/screens/main_screen.dart').readAsStringSync();
  final dailyBudget =
      File('lib/screens/daily_budget_screen.dart').readAsStringSync();

  /// Strip `//` comments so the guards match real code, not the explanatory
  /// comments left where the dead blocks used to be.
  String code(String source) => source
      .split('\n')
      .where((l) => !l.trimLeft().startsWith('//'))
      .join('\n');

  group('producers still emit the documented keys', () {
    test('the adapter emits confidence_level, not confidence', () {
      expect(adapter, contains("'confidence_level':"));
    });

    test('the adapter emits a suggestions list', () {
      expect(adapter, contains("'suggestions': suggestions"));
    });
  });

  group('consumers read no key that no producer emits', () {
    test("nothing reads budgetSuggestions['confidence']", () {
      for (final source in [code(insights), code(main)]) {
        expect(
          source,
          isNot(contains("budgetSuggestions['confidence']")),
          reason: "No producer emits 'confidence'. Do not map "
              "'confidence_level' onto it either: that value drove a "
              'fabricated financial-health score and letter grade.',
        );
      }
    });

    test("nothing reads 'intelligent_insights' or 'category_insights'", () {
      for (final key in ['intelligent_insights', 'category_insights']) {
        expect(
          code(insights),
          isNot(contains("budgetSuggestions['$key']")),
          reason: "No producer emits '$key'.",
        );
      }
    });
  });

  group('no financial-health score is derived from engine confidence', () {
    test('_getGradeFromConfidence is gone from both screens', () {
      for (final source in [code(insights), code(main)]) {
        expect(source, isNot(contains('_getGradeFromConfidence(')));
      }
    });

    test('no confidence-to-percentage score survives', () {
      for (final source in [code(insights), code(main)]) {
        expect(source, isNot(contains('(confidence * 100).round()')));
      }
    });

    test('no hardcoded score/grade fallbacks survive on the dashboard', () {
      expect(code(main), isNot(contains("fallback: 75")));
      expect(code(main), isNot(contains("fallback: 'B'")));
    });
  });

  group('suggestion items render real copy from either producer', () {
    test('daily_budget_screen never renders a raw map', () {
      expect(
        code(dailyBudget),
        isNot(contains('suggestion.toString()')),
        reason: 'Backend items carry \'text\', not \'message\'; falling back '
            'to toString() printed the raw Dart map to the user.',
      );
    });

    test('daily_budget_screen reads both message and text', () {
      expect(dailyBudget, contains("suggestion['message']"));
      expect(dailyBudget, contains("suggestion['text']"));
    });
  });
}
