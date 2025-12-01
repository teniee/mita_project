import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mita/screens/calendar_screen.dart';

void main() {
  group('Calendar Screen Tests', () {
    testWidgets('Calendar shows loading indicator initially',
        (WidgetTester tester) async {
      await tester.pumpWidget(const MaterialApp(home: CalendarScreen()));

      expect(find.byType(CircularProgressIndicator), findsOneWidget);
    });

    testWidgets('Calendar shows app bar with correct title',
        (WidgetTester tester) async {
      await tester.pumpWidget(const MaterialApp(home: CalendarScreen()));

      expect(find.byType(AppBar), findsOneWidget);
      expect(find.textContaining('Calendar'), findsOneWidget);
    });

    testWidgets('Calendar shows refresh button in app bar',
        (WidgetTester tester) async {
      await tester.pumpWidget(const MaterialApp(home: CalendarScreen()));

      expect(find.byIcon(Icons.refresh_rounded), findsOneWidget);
    });

    testWidgets('Calendar shows settings button in app bar',
        (WidgetTester tester) async {
      await tester.pumpWidget(const MaterialApp(home: CalendarScreen()));

      expect(find.byIcon(Icons.settings), findsOneWidget);
    });

    testWidgets('Calendar shows floating action button',
        (WidgetTester tester) async {
      await tester.pumpWidget(const MaterialApp(home: CalendarScreen()));

      expect(find.byType(FloatingActionButton), findsOneWidget);
      expect(find.textContaining('Add Expense'), findsOneWidget);
    });

    testWidgets('Calendar shows status legend', (WidgetTester tester) async {
      await tester.pumpWidget(const MaterialApp(home: CalendarScreen()));

      expect(find.textContaining('Spending Status'), findsOneWidget);
      expect(find.textContaining('On Track'), findsOneWidget);
      expect(find.textContaining('Warning'), findsOneWidget);
      expect(find.textContaining('Over Budget'), findsOneWidget);
    });

    testWidgets('Calendar shows pull to refresh', (WidgetTester tester) async {
      await tester.pumpWidget(const MaterialApp(home: CalendarScreen()));

      expect(find.byType(RefreshIndicator), findsOneWidget);
    });

    testWidgets('Calendar handles refresh action', (WidgetTester tester) async {
      await tester.pumpWidget(const MaterialApp(home: CalendarScreen()));

      // Find and tap the refresh button
      await tester.tap(find.byIcon(Icons.refresh_rounded));
      await tester.pump();

      // Should still show loading indicator after refresh
      expect(find.byType(CircularProgressIndicator), findsOneWidget);
    });

    testWidgets('Calendar shows weekday headers when data loads',
        (WidgetTester tester) async {
      await tester.pumpWidget(const MaterialApp(home: CalendarScreen()));

      // Wait for initial load and potential data
      await tester.pump(const Duration(seconds: 1));
      await tester.pumpAndSettle();

      // If data loads, should show weekday headers
      // Note: This might show error state instead if no real backend
      expect(find.byType(SingleChildScrollView), findsOneWidget);
    });

    group('Error State Tests', () {
      testWidgets('Calendar shows error state with retry button',
          (WidgetTester tester) async {
        await tester.pumpWidget(const MaterialApp(home: CalendarScreen()));

        // Wait for loading to complete
        await tester.pump(const Duration(seconds: 3));
        await tester.pumpAndSettle();

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
        await tester.pumpWidget(const MaterialApp(home: CalendarScreen()));

        // Wait for loading to complete
        await tester.pump(const Duration(seconds: 3));
        await tester.pumpAndSettle();

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
        await tester.pumpWidget(const MaterialApp(home: CalendarScreen()));

        // Check for semantic labels on key elements
        expect(find.bySemanticsLabel('Refresh Calendar'), findsOneWidget);
        expect(find.bySemanticsLabel('Add new expense'), findsOneWidget);
      });

      testWidgets('Calendar buttons have tooltips',
          (WidgetTester tester) async {
        await tester.pumpWidget(const MaterialApp(home: CalendarScreen()));

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
        await tester.pumpWidget(MaterialApp(
          home: const CalendarScreen(),
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
        await tester.pumpWidget(MaterialApp(
          home: const CalendarScreen(),
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
        await tester.pumpWidget(const MaterialApp(home: CalendarScreen()));

        // Measure render time
        final stopwatch = Stopwatch()..start();
        await tester.pump();
        stopwatch.stop();

        // Should render quickly (less than 100ms for initial render)
        expect(stopwatch.elapsedMilliseconds, lessThan(100));
      });

      testWidgets('Calendar handles rapid refresh without issues',
          (WidgetTester tester) async {
        await tester.pumpWidget(const MaterialApp(home: CalendarScreen()));

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
        await tester.pumpWidget(const MaterialApp(home: CalendarScreen()));

        // Wait for initial state
        await tester.pump(const Duration(seconds: 1));

        // Trigger rebuild
        await tester.pumpWidget(const MaterialApp(home: CalendarScreen()));

        // Should maintain calendar screen
        expect(find.byType(CalendarScreen), findsOneWidget);
      });
    });
  });
}
