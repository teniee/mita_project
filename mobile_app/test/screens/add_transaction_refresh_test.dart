// Regression: a successful CREATE must refresh the budget ledger data
// unconditionally. The screens only called onTransactionCreated inside the
// `rebalanced == true` branch, so a plain create left the dashboard showing
// pre-mutation numbers until restart (device-reproduced, Phase-2 journey).

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';
import 'package:mita/models/transaction_model.dart';
import 'package:mita/providers/budget_provider.dart';
import 'package:mita/providers/transaction_provider.dart';
import 'package:mita/screens/add_transaction_screen.dart';

class _FakeTransactionProvider extends TransactionProvider {
  @override
  Future<TransactionModel?> createTransaction(TransactionInput input) async {
    // No network: return a plain (NOT rebalanced) transaction.
    final nowIso = DateTime.now().toUtc().toIso8601String();
    return TransactionModel.fromJson({
      'id': 'txn-refresh-regression',
      'amount': input.amount,
      'category': input.category,
      'spent_at': nowIso,
      'created_at': nowIso,
    });
  }
}

class _RecordingBudgetProvider extends BudgetProvider {
  int onTransactionCreatedCalls = 0;
  bool? lastRebalanced;

  @override
  Future<void> onTransactionCreated({bool rebalanced = false}) async {
    onTransactionCreatedCalls += 1;
    lastRebalanced = rebalanced;
    // Do NOT call super — the real one fans out network loads.
  }
}

void main() {
  testWidgets(
      'successful non-rebalanced create still triggers a budget refresh',
      (tester) async {
    final txnProvider = _FakeTransactionProvider();
    final budgetProvider = _RecordingBudgetProvider();

    await tester.pumpWidget(
      MultiProvider(
        providers: [
          ChangeNotifierProvider<TransactionProvider>.value(value: txnProvider),
          ChangeNotifierProvider<BudgetProvider>.value(value: budgetProvider),
        ],
        child: const MaterialApp(home: AddTransactionScreen()),
      ),
    );
    await tester.pumpAndSettle();

    // Fill the only required field (amount); category defaults to 'food'.
    await tester.enterText(find.byType(TextFormField).first, '5.00');

    // Submit via the save button.
    final saveButton = find.widgetWithText(ElevatedButton, 'Add Transaction');
    expect(saveButton, findsOneWidget);
    await tester.ensureVisible(saveButton);
    await tester.tap(saveButton);
    await tester.pumpAndSettle();

    expect(budgetProvider.onTransactionCreatedCalls, 1,
        reason: 'a successful create must refresh budget data even when '
            'the backend did not rebalance');
    expect(budgetProvider.lastRebalanced, isFalse);
  });
}
