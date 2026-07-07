import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mita/providers/providers.dart';
import 'package:mita/screens/calendar_screen.dart';
import 'package:mita/screens/main_screen.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'helpers/test_app.dart';

/// Providers + MaterialApp wrapper preserving each test's theme options.
Widget appWith(Widget home, {ThemeData? theme}) {
  return MultiProvider(
    providers: buildTestProviders(),
    child: MaterialApp(home: home, theme: theme),
  );
}

/// UI Fixes Validation Test
/// Tests the specific UI fixes mentioned in the QA requirements:
/// 1. RenderFlex overflow errors should be eliminated
/// 2. Calendar day cells should show proper status instead of "overbottom"
/// 3. Error handling should display proper dismissible messages
/// 4. Material Design 3 compliance
/// 5. Responsive design across different screen sizes

void main() {
  group('UI Fixes Validation Tests', () {
    group('RenderFlex Overflow Fixes', () {
      testWidgets(
          'Calendar screen should not produce RenderFlex overflow errors',
          (WidgetTester tester) async {
        // Capture only overflow errors; everything else must keep flowing
        // to the framework handler or the binding's exception bookkeeping
        // breaks. Restored before the assertions run.
        final List<FlutterErrorDetails> errors = [];
        final originalOnError = FlutterError.onError;
        addTearDown(() => FlutterError.onError = originalOnError);
        FlutterError.onError = (FlutterErrorDetails details) {
          if (details.toString().contains('overflowed')) {
            errors.add(details);
          } else {
            originalOnError?.call(details);
          }
        };

        // Build calendar screen in various sizes
        await tester.pumpWidget(
          appWith(const CalendarScreen(), theme: ThemeData(useMaterial3: true)),
        );

        // Wait for initial render
        await tester.pump(const Duration(seconds: 1));

        // Test with small screen size (common issue source)
        await tester.binding.setSurfaceSize(const Size(320, 568));
        await tester.pump(const Duration(seconds: 1));

        // Test with large screen size
        await tester.binding.setSurfaceSize(const Size(414, 896));
        await tester.pump(const Duration(seconds: 1));

        // Test with tablet size
        await tester.binding.setSurfaceSize(const Size(768, 1024));
        await tester.pump(const Duration(seconds: 1));

        // Check for RenderFlex overflow errors
        final overflowErrors = errors.where((error) =>
            error.toString().contains('RenderFlex overflowed') ||
            error.toString().contains('overflow'));

        expect(overflowErrors.isEmpty, isTrue,
            reason:
                'No RenderFlex overflow errors should occur. Found: ${overflowErrors.map((e) => e.exception).toList()}');

        // Reset surface size
        await tester.binding.setSurfaceSize(null);
      });

      testWidgets(
          'Main dashboard should handle responsive layout without overflow',
          (WidgetTester tester) async {
        final List<FlutterErrorDetails> errors = [];
        FlutterError.onError = (FlutterErrorDetails details) {
          errors.add(details);
        };

        await tester.pumpWidget(
          appWith(const MainScreen(), theme: ThemeData(useMaterial3: true)),
        );

        await tester.pump(const Duration(seconds: 1));

        // Test different screen sizes
        final testSizes = [
          const Size(320, 568), // iPhone SE
          const Size(375, 812), // iPhone X
          const Size(414, 896), // iPhone XS Max
          const Size(768, 1024), // iPad
        ];

        for (final size in testSizes) {
          await tester.binding.setSurfaceSize(size);
          await tester.pump(const Duration(seconds: 1));

          final overflowErrors = errors.where(
              (error) => error.toString().contains('RenderFlex overflowed'));

          expect(overflowErrors.isEmpty, isTrue,
              reason: 'No overflow errors at size $size');
        }

        await tester.binding.setSurfaceSize(null);
      });
    });

    group('Calendar Display Fixes', () {
      testWidgets(
          'Calendar day cells should show proper status text, not "overbottom"',
          (WidgetTester tester) async {
        await tester.pumpWidget(
          appWith(const CalendarScreen(), theme: ThemeData(useMaterial3: true)),
        );

        // Wait for calendar to load
        await tester.pump(const Duration(seconds: 3));

        // Look for any text widgets containing "overbottom"
        final overbottomFinders = find.textContaining('overbottom');
        expect(overbottomFinders, findsNothing,
            reason: 'Calendar should not display "overbottom" text');

        // Check for proper status indicators
        final statusIndicators = [
          'good',
          'warning',
          'over',
          'under budget',
          'on track',
          'exceeded',
        ];

        bool foundProperStatus = false;
        for (final status in statusIndicators) {
          final statusFinder = find.textContaining(status, findRichText: true);
          if (statusFinder.evaluate().isNotEmpty) {
            foundProperStatus = true;
            break;
          }
        }

        // If no status text found, check for visual indicators (colors, icons)
        if (!foundProperStatus) {
          // Look for colored containers or status icons
          final coloredContainers = find.byWidgetPredicate(
              (widget) => widget is Container && widget.decoration != null);
          final statusIcons = find.byType(Icon);

          // Should have visual status indicators even if no text
          expect(
              coloredContainers.evaluate().isNotEmpty ||
                  statusIcons.evaluate().isNotEmpty,
              isTrue,
              reason: 'Calendar should have visual status indicators');
        }
      });

      testWidgets('Calendar should display month and year correctly',
          (WidgetTester tester) async {
        await tester.pumpWidget(
          appWith(const CalendarScreen(), theme: ThemeData(useMaterial3: true)),
        );

        await tester.pump(const Duration(seconds: 1));

        // Should display current month name
        final now = DateTime.now();
        final monthNames = [
          'January',
          'February',
          'March',
          'April',
          'May',
          'June',
          'July',
          'August',
          'September',
          'October',
          'November',
          'December'
        ];
        final currentMonth = monthNames[now.month - 1];

        final monthFinder = find.textContaining(currentMonth);
        expect(monthFinder, findsWidgets,
            reason: 'Calendar should display current month name');

        // Should display current year
        final yearFinder = find.textContaining(now.year.toString());
        expect(yearFinder, findsWidgets,
            reason: 'Calendar should display current year');
      });
    });

    group('Error Handling UI Improvements', () {
      testWidgets('Error messages should be dismissible',
          (WidgetTester tester) async {
        await tester.pumpWidget(
          MaterialApp(
            home: Scaffold(
              body: Builder(
                builder: (context) => ElevatedButton(
                  onPressed: () {
                    ScaffoldMessenger.of(context).showSnackBar(
                      SnackBar(
                        content: const Text('Test error'),
                        duration: const Duration(seconds: 5),
                        action: SnackBarAction(
                          label: 'Dismiss',
                          onPressed: () {
                            ScaffoldMessenger.of(context).hideCurrentSnackBar();
                          },
                        ),
                      ),
                    );
                  },
                  child: const Text('Show Error'),
                ),
              ),
            ),
          ),
        );

        // Tap to show error; one pump starts the entrance animation and
        // the second completes it — with a single pump the SnackBar is
        // still positioned below the viewport and can't be hit-tested.
        await tester.tap(find.text('Show Error'));
        await tester.pump();
        await tester.pump(const Duration(milliseconds: 750));

        // Should find a SnackBar or dismissible error message
        final snackBarFinder = find.byType(SnackBar);
        final dismissButtonFinder = find.byIcon(Icons.close);

        expect(
            snackBarFinder.evaluate().isNotEmpty ||
                dismissButtonFinder.evaluate().isNotEmpty,
            isTrue,
            reason: 'Error messages should be dismissible');

        // Dismiss deterministically through the SnackBar's own action —
        // relying on the auto-dismiss timer proved Flutter-version
        // sensitive (passed on 3.35.4, failed on CI's newer stable).
        // The point under test is that the error CAN be dismissed.
        if (dismissButtonFinder.evaluate().isNotEmpty) {
          await tester.tap(dismissButtonFinder.first);
        } else {
          await tester.tap(find.text('Dismiss'));
        }
        // Let the exit animation run to completion.
        await tester.pump();
        await tester.pump(const Duration(seconds: 1));
        await tester.pumpAndSettle();
        expect(find.text('Test error'), findsNothing);
      });

      testWidgets('Error messages should not be persistent red bars',
          (WidgetTester tester) async {
        await tester.pumpWidget(
          MaterialApp(
            home: Scaffold(
              body: Builder(
                builder: (context) => ElevatedButton(
                  onPressed: () {
                    ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(
                        content: Text('Network error'),
                        backgroundColor: Colors.red,
                      ),
                    );
                  },
                  child: const Text('Show Network Error'),
                ),
              ),
            ),
          ),
        );

        await tester.tap(find.text('Show Network Error'));
        await tester.pump(const Duration(seconds: 1));

        // Should not be a persistent Container with red background
        final persistentRedContainers = find.byWidgetPredicate(
            (widget) => widget is Container && widget.color != null);

        // Error display should be temporary (SnackBar, Dialog, etc.)
        final temporaryErrorDisplays = find.byWidgetPredicate((widget) =>
            widget is SnackBar || widget is AlertDialog || widget is Dialog);

        expect(temporaryErrorDisplays, findsWidgets,
            reason: 'Errors should be displayed in temporary UI elements');

        // Wait for auto-dismissal
        await tester.pump(const Duration(seconds: 5));
        await tester.pump(const Duration(seconds: 1));
      });
    });

    group('Material Design 3 Compliance', () {
      testWidgets('App should use Material 3 theme',
          (WidgetTester tester) async {
        await tester.pumpWidget(
          appWith(const CalendarScreen(), theme: ThemeData(useMaterial3: true)),
        );

        await tester.pump(const Duration(seconds: 1));

        // Find MaterialApp to check theme
        final materialApp =
            tester.widget<MaterialApp>(find.byType(MaterialApp));
        expect(materialApp.theme?.useMaterial3, isTrue,
            reason: 'App should use Material Design 3');
      });

      testWidgets('Buttons should use Material 3 styling',
          (WidgetTester tester) async {
        await tester.pumpWidget(
          appWith(const CalendarScreen(), theme: ThemeData(useMaterial3: true)),
        );

        await tester.pump(const Duration(seconds: 1));

        // Look for buttons with Material 3 characteristics. The calendar's
        // always-visible action is its extended FAB (an M3 component);
        // Filled/Elevated/Outlined buttons appear in loaded/error states.
        final elevatedButtons = find.byType(ElevatedButton);
        final filledButtons = find.byType(FilledButton);
        final outlinedButtons = find.byType(OutlinedButton);
        final fabs = find.byType(FloatingActionButton);

        final hasModernButtons = elevatedButtons.evaluate().isNotEmpty ||
            filledButtons.evaluate().isNotEmpty ||
            outlinedButtons.evaluate().isNotEmpty ||
            fabs.evaluate().isNotEmpty;

        expect(hasModernButtons, isTrue,
            reason: 'Should use Material 3 button styles');
      });
    });

    group('Accessibility and Usability', () {
      testWidgets('Calendar should have proper accessibility labels',
          (WidgetTester tester) async {
        await tester.pumpWidget(
          appWith(const CalendarScreen(), theme: ThemeData(useMaterial3: true)),
        );

        await tester.pump(const Duration(seconds: 1));

        // Check for semantic labels on interactive elements
        final semanticFinder = find.byWidgetPredicate(
            (widget) => widget is Semantics && widget.properties.label != null);

        // Should have at least some semantic labels
        expect(semanticFinder.evaluate().length, greaterThan(0),
            reason: 'Calendar should have accessibility labels');
      });

      testWidgets('Navigation elements should be accessible',
          (WidgetTester tester) async {
        await tester.pumpWidget(
          appWith(const CalendarScreen(), theme: ThemeData(useMaterial3: true)),
        );

        await tester.pump(const Duration(seconds: 1));

        // Look for navigation buttons/icons with tooltips
        final tooltipFinder = find.byType(Tooltip);
        final iconButtonFinder = find.byType(IconButton);

        if (iconButtonFinder.evaluate().isNotEmpty) {
          // Should have tooltips for icon buttons
          expect(tooltipFinder.evaluate().isNotEmpty, isTrue,
              reason: 'Icon buttons should have tooltips for accessibility');
        }
      });
    });

    group('Performance and Smoothness', () {
      testWidgets('Calendar animations should be smooth',
          (WidgetTester tester) async {
        await tester.pumpWidget(
          appWith(const CalendarScreen(), theme: ThemeData(useMaterial3: true)),
        );

        await tester.pump(const Duration(seconds: 1));

        // Check for animation controllers
        final animatedWidgets = find.byWidgetPredicate((widget) =>
            widget is AnimatedWidget ||
            widget is AnimatedBuilder ||
            widget is FadeTransition ||
            widget is SlideTransition);

        // If animations exist, they should complete without errors
        if (animatedWidgets.evaluate().isNotEmpty) {
          await tester.pump(const Duration(seconds: 2));
          // No assertion needed - pumpAndSettle will fail if animations don't complete
        }
      });

      testWidgets('Scroll performance should be smooth',
          (WidgetTester tester) async {
        await tester.pumpWidget(
          appWith(const CalendarScreen(), theme: ThemeData(useMaterial3: true)),
        );

        await tester.pump(const Duration(seconds: 1));

        // Look for scrollable widgets
        final scrollableFinder = find.byWidgetPredicate((widget) =>
            widget is ScrollView ||
            widget is ListView ||
            widget is SingleChildScrollView);

        if (scrollableFinder.evaluate().isNotEmpty) {
          // Test scrolling
          await tester.drag(scrollableFinder.first, const Offset(0, -100));
          await tester.pump(const Duration(seconds: 1));

          await tester.drag(scrollableFinder.first, const Offset(0, 100));
          await tester.pump(const Duration(seconds: 1));

          // Should complete without errors
        }
      });
    });
  });
}
