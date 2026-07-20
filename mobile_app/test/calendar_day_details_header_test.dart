/// Regression test for the stale day-details header (Fix A).
///
/// Bug context (session-6 device journey): after deleting the only June 30
/// transaction, the transaction list emptied and backend spent became 0, but
/// the day-details modal header kept showing "Spent $100". Root cause: the
/// header rendered the immutable route arguments (widget.spent/widget.limit)
/// instead of the refreshable day entry, so it could not reflect a mutation
/// without closing and reopening the sheet.
///
/// Invariant under test: the header renders the (mutable) day entry's
/// spent/limit — refreshed after mutations — not the route-argument snapshot.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mita/screens/calendar_day_details_screen.dart';

import 'helpers/test_app.dart';

void main() {
  initTestEnvironment();

  testWidgets(
      'day-details header reflects the day entry, not the route-arg snapshot',
      (WidgetTester tester) async {
    // A tall surface so the full 85%-height sheet lays out without a RenderFlex
    // overflow (unrelated to the header source under test).
    tester.view.physicalSize = const Size(1200, 3200);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    // Route args carry the pre-mutation snapshot (spent 100 / limit 200);
    // the day entry carries fresh values (spent 42 / limit 99). The header
    // must render the fresh values and never the stale snapshot.
    await tester.pumpWidget(wrapWithProviders(
      CalendarDayDetailsScreen(
        dayNumber: 30,
        limit: 200,
        spent: 100,
        status: 'over',
        date: DateTime(2026, 6, 30),
        dayData: <String, dynamic>{
          'day': 30,
          'date': '2026-06-30',
          'limit': 99,
          'spent': 42,
          'status': 'good',
          'categories': <String, dynamic>{
            'groceries': <String, dynamic>{'planned': 99.0, 'spent': 42.0},
          },
        },
      ),
    ));

    // Let the entry/fade settle a couple of frames (network loads are guarded
    // and irrelevant to the header source).
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 700));

    // Fresh day-entry values are shown, with consistent 2-decimal money
    // formatting (Budget/Spent/Remaining all via formatMoney).
    expect(find.text('\$42.00'), findsWidgets,
        reason: 'header spent from entry, 2-decimal');
    expect(find.text('\$99.00'), findsWidgets,
        reason: 'header budget from entry, 2-decimal');
    expect(find.text('\$57.00'), findsWidgets,
        reason: 'remaining = budget 99 - spent 42 = 57, 2-decimal');
    // …and the stale route-argument snapshot never appears (any formatting).
    expect(find.text('\$100'), findsNothing,
        reason: 'stale route-arg spent must not render');
    expect(find.text('\$100.00'), findsNothing,
        reason: 'stale route-arg spent must not render (2-decimal)');
    expect(find.text('\$200'), findsNothing,
        reason: 'stale route-arg limit must not render');
    expect(find.text('\$200.00'), findsNothing,
        reason: 'stale route-arg limit must not render (2-decimal)');
  });
}
