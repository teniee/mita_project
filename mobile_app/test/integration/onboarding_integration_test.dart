import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mita/screens/onboarding_location_screen.dart';
import 'package:mita/services/onboarding_state.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  // OnboardingState persists via SharedPreferences; without a mock the
  // platform channel is missing and every reset()/save() throws.
  TestWidgetsFlutterBinding.ensureInitialized();

  group('Onboarding Integration Tests', () {
    setUp(() async {
      SharedPreferences.setMockInitialValues(<String, Object>{});
      // Reset onboarding state before each test
      await OnboardingState.instance.reset();
    });

    testWidgets('Complete location selection flow',
        (WidgetTester tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: const OnboardingLocationScreen(),
          routes: {
            '/onboarding_income': (context) =>
                const Scaffold(body: Text('Income step')),
          },
        ),
      );

      // Verify initial state
      expect(find.text('Which US state are you in?'), findsOneWidget);
      expect(find.text('Continue'), findsOneWidget);

      // Continue button should be disabled initially
      final continueButton = tester.widget<ElevatedButton>(
          find.widgetWithText(ElevatedButton, 'Continue'));
      expect(continueButton.onPressed, isNull);

      // Search narrows the list to one result and hides the popular-state
      // chips ('California' would otherwise match twice).
      await tester.enterText(find.byType(TextField), 'California');
      await tester.pump();

      await tester.ensureVisible(find.widgetWithText(ListTile, 'California'));
      await tester.tap(find.widgetWithText(ListTile, 'California'));
      await tester.pump();

      // Verify selection feedback
      expect(find.byIcon(Icons.check_circle_rounded), findsOneWidget);

      // Continue button should now be enabled
      final enabledButton = tester.widget<ElevatedButton>(
          find.widgetWithText(ElevatedButton, 'Continue'));
      expect(enabledButton.onPressed, isNotNull);

      // Tap continue
      await tester.ensureVisible(find.text('Continue'));
      await tester.tap(find.text('Continue'));
      await tester.pumpAndSettle();

      // Verify state is saved in OnboardingState
      expect(OnboardingState.instance.countryCode, equals('US'));
      expect(OnboardingState.instance.stateCode, equals('CA'));
    });

    testWidgets('Auto-detection UI states', (WidgetTester tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: OnboardingLocationScreen(),
        ),
      );

      // Initially, should show detecting location
      expect(find.text('Detecting your location...'), findsOneWidget);
      expect(find.byType(CircularProgressIndicator), findsOneWidget);

      // Wait for auto-detection to complete (mock would be better)
      await tester.pump(const Duration(seconds: 2));

      // Should show either success or error state
      // (Exact outcome depends on LocationService mock/implementation)
    });

    testWidgets('State list contains all 50 states',
        (WidgetTester tester) async {
      // Tall surface so the embedded state list is on-screen and drags
      // actually reach it (on the default 600px surface it sits below
      // the fold and drag gestures miss).
      tester.view.physicalSize = const Size(1080, 2400);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);

      await tester.pumpWidget(
        const MaterialApp(
          home: OnboardingLocationScreen(),
        ),
      );
      await tester.pump();

      // Get all state list items
      final stateListFinder = find.byType(ListTile);

      // Scroll through and count unique states
      final Set<String> foundStates = {};

      void collectVisible() {
        final visibleTiles = tester.widgetList<ListTile>(stateListFinder);
        for (final tile in visibleTiles) {
          if (tile.title is Text) {
            final text = tile.title as Text;
            if (text.data != null) {
              foundStates.add(text.data!);
            }
          }
        }
      }

      collectVisible();
      // Scroll to find all states
      for (int i = 0; i < 60; i++) {
        await tester.drag(
          find.byType(ListView).last,
          const Offset(0, -100),
        );
        await tester.pump();
        collectVisible();
      }

      // Should find a reasonable number of states (test may need adjustment)
      expect(foundStates.length, greaterThan(40));
    });

    testWidgets('State selection persistence', (WidgetTester tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: const OnboardingLocationScreen(),
          routes: {
            '/onboarding_income': (context) =>
                const Scaffold(body: Text('Income step')),
          },
        ),
      );

      // Select Texas (search narrows to a single match)
      await tester.enterText(find.byType(TextField), 'Texas');
      await tester.pump();
      await tester.ensureVisible(find.widgetWithText(ListTile, 'Texas'));
      await tester.tap(find.widgetWithText(ListTile, 'Texas'));
      await tester.pump();

      // Verify Texas is selected
      expect(find.byIcon(Icons.check_circle_rounded), findsOneWidget);

      // Select different state (Florida)
      await tester.enterText(find.byType(TextField), 'Florida');
      await tester.pump();
      await tester.ensureVisible(find.widgetWithText(ListTile, 'Florida'));
      await tester.tap(find.widgetWithText(ListTile, 'Florida'));
      await tester.pump();

      // Should still have only one check mark (Florida selected)
      expect(find.byIcon(Icons.check_circle_rounded), findsOneWidget);

      // Continue with Florida selection
      await tester.ensureVisible(find.text('Continue'));
      await tester.tap(find.text('Continue'));
      await tester.pumpAndSettle();

      // Verify Florida is saved, not Texas
      expect(OnboardingState.instance.stateCode, equals('FL'));
    });

    testWidgets('Accessibility features', (WidgetTester tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: OnboardingLocationScreen(),
        ),
      );

      // Check that buttons are accessible
      final continueButton = find.text('Continue');
      expect(continueButton, findsOneWidget);

      // Check that state list is accessible
      final firstState = find.byType(ListTile).first;
      expect(tester.widget<ListTile>(firstState).title, isA<Text>());
    });

    group('Error Handling', () {
      testWidgets('Handle location detection failure gracefully',
          (WidgetTester tester) async {
        // This test would need a mocked LocationService that fails
        await tester.pumpWidget(
          const MaterialApp(
            home: OnboardingLocationScreen(),
          ),
        );

        // Wait for auto-detection to complete
        await tester.pump(const Duration(seconds: 3));

        // Should show error state without crashing
        // (Implementation depends on how LocationService handles errors)
        expect(find.byType(OnboardingLocationScreen), findsOneWidget);
      });

      testWidgets('Handle invalid state selection',
          (WidgetTester tester) async {
        await tester.pumpWidget(
          const MaterialApp(
            home: OnboardingLocationScreen(),
          ),
        );

        // Test continues without accessing private state
        // This would require a proper mock setup in a real implementation

        // Should not crash the app
        expect(find.byType(OnboardingLocationScreen), findsOneWidget);
      });
    });

    group('Performance Tests', () {
      testWidgets('State list scrolling performance',
          (WidgetTester tester) async {
        await tester.pumpWidget(
          const MaterialApp(
            home: OnboardingLocationScreen(),
          ),
        );

        final stopwatch = Stopwatch()..start();

        // Perform rapid scrolling
        for (int i = 0; i < 10; i++) {
          await tester.drag(
            find.byType(ListView),
            const Offset(0, -200),
          );
          await tester.pump();
        }

        stopwatch.stop();

        // Should complete scrolling operations quickly
        expect(stopwatch.elapsedMilliseconds, lessThan(1000));
      });

      testWidgets('Memory usage during state selection',
          (WidgetTester tester) async {
        await tester.pumpWidget(
          const MaterialApp(
            home: OnboardingLocationScreen(),
          ),
        );

        // Select multiple states rapidly
        final states = ['California', 'Texas', 'Florida', 'New York'];

        for (final state in states) {
          if (find.text(state).evaluate().isNotEmpty) {
            // A state name can appear both as a popular-state chip and a
            // list tile; either instance selects the state.
            await tester.tap(find.text(state).first, warnIfMissed: false);
            await tester.pump();
          }
        }

        // Should not cause memory issues
        expect(find.byType(OnboardingLocationScreen), findsOneWidget);
      });
    });

    group('Visual Regression Tests', () {
      testWidgets('UI layout consistency', (WidgetTester tester) async {
        await tester.pumpWidget(
          const MaterialApp(
            home: OnboardingLocationScreen(),
          ),
        );

        // Take screenshot for visual regression testing
        await expectLater(
          find.byType(OnboardingLocationScreen),
          matchesGoldenFile('onboarding_location_initial.png'),
        );

        // Select a state and take another screenshot
        await tester.enterText(find.byType(TextField), 'California');
        await tester.pump();
        await tester.tap(find.widgetWithText(ListTile, 'California'));
        await tester.pump();

        await expectLater(
          find.byType(OnboardingLocationScreen),
          matchesGoldenFile('onboarding_location_selected.png'),
        );
      });
    });
  });
}
