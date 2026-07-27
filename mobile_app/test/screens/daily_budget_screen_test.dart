import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mita/providers/budget_provider.dart';
import 'package:mita/screens/daily_budget_screen.dart';
import 'package:provider/provider.dart';

class _StubBudgetProvider extends BudgetProvider {
  _StubBudgetProvider(this._budgets);

  final List<Map<String, dynamic>> _budgets;

  @override
  BudgetState get state => BudgetState.loaded;

  @override
  bool get isLoading => false;

  @override
  bool get isRedistributing => false;

  @override
  List<Map<String, dynamic>> get dailyBudgets => _budgets;

  @override
  Map<String, dynamic> get liveBudgetStatus => {};

  @override
  Map<String, dynamic> get budgetSuggestions => {};

  @override
  List<Map<String, dynamic>> get redistributionHistory => [];
}

Future<void> _pumpScreen(
  WidgetTester tester,
  List<Map<String, dynamic>> budgets,
) async {
  await tester.pumpWidget(
    ChangeNotifierProvider<BudgetProvider>.value(
      value: _StubBudgetProvider(budgets),
      child: const MaterialApp(home: DailyBudgetScreen()),
    ),
  );
  await tester.pump();
}

/// Every Semantics label rendered anywhere in the tree.
List<String> _semanticLabels(WidgetTester tester) => tester
    .widgetList<Semantics>(find.byType(Semantics))
    .map((s) => s.properties.label)
    .whereType<String>()
    .toList();

void main() {
  testWidgets('renders spending against a zero daily limit without crashing',
      (tester) async {
    await _pumpScreen(tester, [
      {
        'date': '2026-07-25',
        'status': 'warning',
        'spent': 12.34,
        'limit': 0.0,
      },
    ]);

    expect(tester.takeException(), isNull);
    expect(find.text('Spent: \$12.34 / Limit: \$0.00'), findsOneWidget);

    final progress = tester.widget<LinearProgressIndicator>(
      find.byType(LinearProgressIndicator).last,
    );
    expect(progress.value, 0.0);
  });

  testWidgets('zero limit with real spending never announces 0 percent used',
      (tester) async {
    await _pumpScreen(tester, [
      {
        'date': '2026-07-25',
        'status': 'warning',
        'spent': 12.34,
        'limit': 0.0,
      },
    ]);

    final labels = _semanticLabels(tester);

    // The screen must not claim a percentage it cannot compute. Announcing
    // "0 percent of budget used" for a day with $12.34 of real spending
    // states the opposite of the truth.
    expect(
      labels.where((l) => l.contains('percent of budget used')),
      isEmpty,
    );
    expect(
      labels.where((l) => l.contains('no budget limit is set')),
      isNotEmpty,
    );
    // The descriptive label must also stay truthful.
    expect(
      labels.where((l) => l.contains('No budget limit is set')),
      isNotEmpty,
    );
  });

  testWidgets('zero limit and zero spending stays finite and truthful',
      (tester) async {
    await _pumpScreen(tester, [
      {
        'date': '2026-07-25',
        'status': 'good',
        'spent': 0.0,
        'limit': 0.0,
      },
    ]);

    expect(tester.takeException(), isNull);

    final progress = tester.widget<LinearProgressIndicator>(
      find.byType(LinearProgressIndicator).last,
    );
    expect(progress.value, 0.0);
    expect(progress.value!.isFinite, isTrue);

    expect(
      _semanticLabels(tester)
          .where((l) => l.contains('percent of budget used')),
      isEmpty,
    );
  });

  testWidgets('a real limit still reports its true percentage', (tester) async {
    await _pumpScreen(tester, [
      {
        'date': '2026-07-25',
        'status': 'warning',
        'spent': 25.0,
        'limit': 50.0,
      },
    ]);

    final progress = tester.widget<LinearProgressIndicator>(
      find.byType(LinearProgressIndicator).last,
    );
    expect(progress.value, 0.5);

    expect(
      _semanticLabels(tester)
          .where((l) => l.contains('50 percent of budget used')),
      isNotEmpty,
    );
  });

  testWidgets('overspend clamps the bar but reports the true percentage',
      (tester) async {
    await _pumpScreen(tester, [
      {
        'date': '2026-07-25',
        'status': 'over',
        'spent': 150.0,
        'limit': 50.0,
      },
    ]);

    final progress = tester.widget<LinearProgressIndicator>(
      find.byType(LinearProgressIndicator).last,
    );
    // Bar is clamped for layout, but the announcement must not be.
    expect(progress.value, 1.0);
    expect(
      _semanticLabels(tester)
          .where((l) => l.contains('300 percent of budget used')),
      isNotEmpty,
    );
  });
}
