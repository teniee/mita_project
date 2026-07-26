import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mita/providers/budget_provider.dart';
import 'package:mita/screens/daily_budget_screen.dart';
import 'package:provider/provider.dart';

class _ZeroLimitBudgetProvider extends BudgetProvider {
  @override
  BudgetState get state => BudgetState.loaded;

  @override
  bool get isLoading => false;

  @override
  bool get isRedistributing => false;

  @override
  List<Map<String, dynamic>> get dailyBudgets => [
        {
          'date': '2026-07-25',
          'status': 'warning',
          'spent': 12.34,
          'limit': 0.0,
        },
      ];

  @override
  Map<String, dynamic> get liveBudgetStatus => {};

  @override
  Map<String, dynamic> get budgetSuggestions => {};

  @override
  List<Map<String, dynamic>> get redistributionHistory => [];
}

void main() {
  testWidgets('renders spending against a zero daily limit without crashing',
      (tester) async {
    final provider = _ZeroLimitBudgetProvider();

    await tester.pumpWidget(
      ChangeNotifierProvider<BudgetProvider>.value(
        value: provider,
        child: const MaterialApp(home: DailyBudgetScreen()),
      ),
    );
    await tester.pump();

    expect(tester.takeException(), isNull);
    expect(find.text('Spent: \$12.34 / Limit: \$0.00'), findsOneWidget);

    final progress = tester.widget<LinearProgressIndicator>(
      find.byType(LinearProgressIndicator).last,
    );
    expect(progress.value, 0.0);
  });
}
