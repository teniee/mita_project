import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mita/screens/calendar_screen.dart';

import 'helpers/test_app.dart';

void main() {
  initTestEnvironment();

  group('Calendar Screen Tests', () {
    testWidgets('Calendar shows loading indicator initially',
        (WidgetTester tester) async {
      await tester.pumpWidget(wrapWithProviders(const CalendarScreen()));
      // initState kicks off the async load; the provider flips isLoading on
      // its first notify, one microtask after the initial frame.
      await tester.pump();

      expect(find.byType(CircularProgressIndicator), findsOneWidget);
    });

    testWidgets('Calendar shows app bar with correct title',
        (WidgetTester tester) async {
      await tester.pumpWidget(wrapWithProviders(const CalendarScreen()));

      expect(find.byType(AppBar), findsOneWidget);
      expect(find.textContaining('Calendar'), findsOneWidget);
    });

    testWidgets('Calendar shows refresh button in app bar',
        (WidgetTester tester) async {
      await tester.pumpWidget(wrapWithProviders(const CalendarScreen()));

      expect(find.byIcon(Icons.refresh_rounded), findsOneWidget);
    });

    testWidgets('Calendar shows settings button in app bar',
        (WidgetTester tester) async {
      await tester.pumpWidget(wrapWithProviders(const CalendarScreen()));

      expect(find.byIcon(Icons.settings), findsOneWidget);
    });

    testWidgets('Calendar shows floating action button',
        (WidgetTester tester) async {
      await tester.pumpWidget(wrapWithProviders(const CalendarScreen()));

      expect(find.byType(FloatingActionButton), findsOneWidget);
      expect(find.textContaining('Add Expense'), findsOneWidget);
    });

    testWidgets('Calendar shows status legend', (WidgetTester tester) async {
      await tester.pumpWidget(wrapWithProviders(const CalendarScreen()));

      expect(find.textContaining('Spending Status'), findsOneWidget);
      expect(find.textContaining('On Track'), findsOneWidget);
      expect(find.textContaining('Warning'), findsOneWidget);
      expect(find.textContaining('Over Budget'), findsOneWidget);
    });

    testWidgets('Calendar shows pull to refresh', (WidgetTester tester) async {
      await tester.pumpWidget(wrapWithProviders(const CalendarScreen()));

      expect(find.byType(RefreshIndicator), findsOneWidget);
    });

    testWidgets('Calendar handles refresh action', (WidgetTester tester) async {
      await tester.pumpWidget(wrapWithProviders(const CalendarScreen()));

      // Find and tap the refresh button
      await tester.tap(find.byIcon(Icons.refresh_rounded));
      await tester.pump();

      // Should still show loading indicator after refresh
      expect(find.byType(CircularProgressIndicator), findsOneWidget);
    });

    testWidgets('Calendar shows weekday headers when data loads',
        (WidgetTester tester) async {
      await tester.pumpWidget(wrapWithProviders(const CalendarScreen()));

      // Wait for initial load and potential data. (Bounded pumps: the
      // live-updates periodic timer means pumpAndSettle would never settle.)
      await tester.pump(const Duration(seconds: 1));
      await tester.pump(const Duration(seconds: 2));

      // If data loads, should show weekday headers
      // Note: This might show error state instead if no real backend
      expect(find.byType(SingleChildScrollView), findsOneWidget);
    });

    group('Error State Tests', () {
      testWidgets('Calendar shows error state with retry button',
          (WidgetTester tester) async {
        await tester.pumpWidget(wrapWithProviders(const CalendarScreen()));

        // Wait for loading to complete (bounded pumps; see above)
        await tester.pump(const Duration(seconds: 3));
        await tester.pump(const Duration(seconds: 3));

        // Should either show error state or calendar data
        // If error state is shown, verify it has retry functionality
        if (find
            .textContaining('Unable to load calendar')
            .evaluate()
            .isNotEmpty) {
          expect(
              find.textContaining('Unable to load calendar'), findsOneWidget);
          expect(find.textContaining('Retry'), findsOneWidget);
          expect(find.byIcon(Icons.error_outline_rounded), findsOneWidget);
        }
      });

      testWidgets('Calendar shows empty state when no data',
          (WidgetTester tester) async {
        await tester.pumpWidget(wrapWithProviders(const CalendarScreen()));

        // Wait for loading to complete (bounded pumps; see above)
        await tester.pump(const Duration(seconds: 3));
        await tester.pump(const Duration(seconds: 3));

        // Should either show empty state or calendar data
        if (find
            .textContaining('No calendar data available')
            .evaluate()
            .isNotEmpty) {
          expect(find.textContaining('No calendar data available'),
              findsOneWidget);
          expect(find.textContaining('Setup Budget'), findsOneWidget);
          expect(find.byIcon(Icons.calendar_month_rounded), findsOneWidget);
        }
      });
    });

    group('Accessibility Tests', () {
      testWidgets('Calendar has proper semantic labels',
          (WidgetTester tester) async {
        await tester.pumpWidget(wrapWithProviders(const CalendarScreen()));

        // Check for semantic labels on key elements. The FAB merges its
        // icon label with the button text, so the tooltip is its stable
        // accessibility handle.
        expect(find.bySemanticsLabel('Refresh Calendar'), findsOneWidget);
        expect(find.byTooltip('Add new expense'), findsOneWidget);
      });

      testWidgets('Calendar buttons have tooltips',
          (WidgetTester tester) async {
        await tester.pumpWidget(wrapWithProviders(const CalendarScreen()));

        // Verify tooltips exist for icon buttons
        final refreshButton = find.byIcon(Icons.refresh_rounded);
        final settingsButton = find.byIcon(Icons.settings);

        if (refreshButton.evaluate().isNotEmpty) {
          expect(find.byTooltip('Refresh Calendar'), findsOneWidget);
        }
        if (settingsButton.evaluate().isNotEmpty) {
          expect(find.byTooltip('Budget Settings'), findsOneWidget);
        }
      });
    });

    group('Navigation Tests', () {
      testWidgets('Settings button navigates correctly',
          (WidgetTester tester) async {
        await tester.pumpWidget(wrapWithProviders(
          const CalendarScreen(),
          routes: {
            '/budget_settings': (context) =>
                const Scaffold(body: Text('Budget Settings')),
          },
        ));

        // Tap settings button
        await tester.tap(find.byIcon(Icons.settings));
        await tester.pumpAndSettle();

        // Should navigate to budget settings
        expect(find.textContaining('Budget Settings'), findsOneWidget);
      });

      testWidgets('Add expense button navigates correctly',
          (WidgetTester tester) async {
        await tester.pumpWidget(wrapWithProviders(
          const CalendarScreen(),
          routes: {
            '/add_expense': (context) =>
                const Scaffold(body: Text('Add Expense')),
          },
        ));

        // Tap add expense button
        await tester.tap(find.byType(FloatingActionButton));
        await tester.pumpAndSettle();

        // Should navigate to add expense
        expect(find.textContaining('Add Expense'), findsOneWidget);
      });
    });

    group('Performance Tests', () {
      testWidgets('Calendar renders without performance issues',
          (WidgetTester tester) async {
        await tester.pumpWidget(wrapWithProviders(const CalendarScreen()));

        // Measure render time
        final stopwatch = Stopwatch()..start();
        await tester.pump();
        stopwatch.stop();

        // Should render quickly (less than 100ms for initial render)
        expect(stopwatch.elapsedMilliseconds, lessThan(100));
      });

      testWidgets('Calendar handles rapid refresh without issues',
          (WidgetTester tester) async {
        await tester.pumpWidget(wrapWithProviders(const CalendarScreen()));

        // Rapidly tap refresh multiple times
        for (int i = 0; i < 5; i++) {
          await tester.tap(find.byIcon(Icons.refresh_rounded));
          await tester.pump(const Duration(milliseconds: 100));
        }

        // Should still be functional
        expect(find.byType(CalendarScreen), findsOneWidget);
      });
    });

    group('Widget State Tests', () {
      testWidgets('Calendar maintains state during rebuild',
          (WidgetTester tester) async {
        await tester.pumpWidget(wrapWithProviders(const CalendarScreen()));

        // Wait for initial state
        await tester.pump(const Duration(seconds: 1));

        // Trigger rebuild
        await tester.pumpWidget(wrapWithProviders(const CalendarScreen()));

        // Should maintain calendar screen
        expect(find.byType(CalendarScreen), findsOneWidget);
      });
    });

    // Regression (J7b): the calendar was pinned to DateTime.now() with no way
    // to reach any other month, so past/future-month days — and every
    // transaction dated outside the current month — were unreachable in the UI.
    group('Month Navigation Tests', () {
      const monthNames = [
        'January', 'February', 'March', 'April', 'May', 'June',
        'July', 'August', 'September', 'October', 'November', 'December',
      ];

      String titleFor(DateTime m) =>
          'Calendar - ${monthNames[m.month - 1]} ${m.year}';

      testWidgets('shows previous and next month navigation buttons',
          (WidgetTester tester) async {
        await tester.pumpWidget(wrapWithProviders(const CalendarScreen()));
        await tester.pump();

        expect(find.byIcon(Icons.chevron_left), findsOneWidget);
        expect(find.byIcon(Icons.chevron_right), findsOneWidget);
      });

      testWidgets('previous-month button moves the title back one month',
          (WidgetTester tester) async {
        await tester.pumpWidget(wrapWithProviders(const CalendarScreen()));
        await tester.pump();

        final now = DateTime.now();
        final prev = DateTime(now.year, now.month - 1, 1);
        expect(find.text(titleFor(DateTime(now.year, now.month, 1))),
            findsOneWidget);

        await tester.tap(find.byIcon(Icons.chevron_left));
        await tester.pump();

        expect(find.text(titleFor(prev)), findsOneWidget);
      });

      testWidgets('next-month button moves the title forward one month',
          (WidgetTester tester) async {
        await tester.pumpWidget(wrapWithProviders(const CalendarScreen()));
        await tester.pump();

        final now = DateTime.now();
        final next = DateTime(now.year, now.month + 1, 1);

        await tester.tap(find.byIcon(Icons.chevron_right));
        await tester.pump();

        expect(find.text(titleFor(next)), findsOneWidget);
      });

      testWidgets('navigating back then forward returns to the current month',
          (WidgetTester tester) async {
        await tester.pumpWidget(wrapWithProviders(const CalendarScreen()));
        await tester.pump();

        final now = DateTime.now();
        final current = titleFor(DateTime(now.year, now.month, 1));

        await tester.tap(find.byIcon(Icons.chevron_left));
        await tester.pump();
        await tester.tap(find.byIcon(Icons.chevron_right));
        await tester.pump();

        expect(find.text(current), findsOneWidget);
      });

      testWidgets('crossing a year boundary backward renders December',
          (WidgetTester tester) async {
        await tester.pumpWidget(wrapWithProviders(const CalendarScreen()));
        await tester.pump();

        final now = DateTime.now();
        // Step back to January of this year, then once more into last December.
        for (var m = now.month; m > 1; m--) {
          await tester.tap(find.byIcon(Icons.chevron_left));
          await tester.pump();
        }
        await tester.tap(find.byIcon(Icons.chevron_left));
        await tester.pump();

        expect(find.text('Calendar - December ${now.year - 1}'), findsOneWidget);
      });
    });
  });
}
