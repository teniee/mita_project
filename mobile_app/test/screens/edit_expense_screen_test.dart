import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mita/screens/edit_expense_screen.dart';

void main() {
  // Regression: EditExpenseScreen used to do
  //   widget.expense['amount']?.toDouble()   (NoSuchMethodError on String)
  //   DateTime.parse(widget.expense['date']) (TypeError/FormatException on
  //                                           missing or malformed date)
  // A transaction fetched from the API with a drifted shape crashed the
  // screen before the first frame. It must now open and show a usable form.
  group('EditExpenseScreen shape-drift regression', () {
    Future<void> pump(WidgetTester tester, Map<String, dynamic> expense) {
      return tester.pumpWidget(
        MaterialApp(home: EditExpenseScreen(expense: expense)),
      );
    }

    testWidgets('opens with a well-formed expense', (tester) async {
      await pump(tester, {
        'id': 'tx-1',
        'amount': 42.5,
        'action': 'Food',
        'date': '2026-07-01T10:00:00Z',
      });
      expect(tester.takeException(), isNull);
      expect(find.byType(Form), findsOneWidget);
      expect(find.text('42.5'), findsOneWidget);
    });

    testWidgets('string amount, int id and missing date do not crash',
        (tester) async {
      await pump(tester, {
        'id': 12345, // int instead of String
        'amount': '19.99', // string instead of num
        // 'date' missing entirely
        'action': null,
      });
      expect(tester.takeException(), isNull);
      expect(find.byType(Form), findsOneWidget);
      // string amount is parsed, not zeroed
      expect(find.text('19.99'), findsOneWidget);
    });

    testWidgets('nested-map amount degrades to 0.0 instead of crashing',
        (tester) async {
      await pump(tester, {
        'id': 'tx-3',
        'amount': {'value': 7.0}, // nested map shape
        'date': 'not-a-date',
        'action': 'Unknown Category',
      });
      expect(tester.takeException(), isNull);
      expect(find.byType(Form), findsOneWidget);
      expect(find.text('0.0'), findsOneWidget);
    });
  });
}
