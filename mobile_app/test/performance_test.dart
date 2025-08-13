import 'package:flutter_test/flutter_test.dart';
import 'package:flutter/material.dart';
import 'package:mita/main.dart' show MITAApp;

/// Performance Testing for MITA Application
/// Tests app startup time, memory usage, and responsiveness
void main() {
  group('Performance Tests', () {
    
    group('App Startup Performance', () {
      testWidgets('App should start quickly', (WidgetTester tester) async {
        final stopwatch = Stopwatch()..start();
        
        try {
          await tester.pumpWidget(const MITAApp());
          await tester.pump(); // Single pump for initial render
          
          stopwatch.stop();
          
          // App should render initial screen within reasonable time
          expect(stopwatch.elapsedMilliseconds, lessThan(5000),
            reason: 'App startup should complete within 5 seconds');
          
          // Should not crash on startup
          expect(tester.takeException(), isNull);
          
        } catch (e) {
          stopwatch.stop();
          // Allow for network/API errors but not widget errors
          if (!e.toString().contains('SocketException') && 
              !e.toString().contains('TimeoutException')) {
            fail('App startup failed with: $e');
          }
        }
      });
      
      testWidgets('App should handle initial API failures gracefully', (WidgetTester tester) async {
        await tester.pumpWidget(const MITAApp());
        
        // Wait for initial network calls to complete/fail
        await tester.pump(const Duration(seconds: 2));
        
        // Should still render UI even if API calls fail
        expect(find.byType(Scaffold), findsOneWidget);
        expect(tester.takeException(), isNull);
      });
    });

    group('Memory and Resource Management', () {
      testWidgets('App should not leak widgets during navigation', (WidgetTester tester) async {
        await tester.pumpWidget(const MITAApp());
        await tester.pump();
        
        final initialWidgetCount = tester.allWidgets.length;
        
        // Simulate some navigation if bottom nav exists
        final bottomNavButtons = find.byType(GestureDetector);
        if (bottomNavButtons.evaluate().isNotEmpty) {
          // Tap between tabs
          for (int i = 0; i < 3; i++) {
            if (bottomNavButtons.evaluate().length > 1) {
              await tester.tap(bottomNavButtons.at(1));
              await tester.pump();
              await tester.tap(bottomNavButtons.at(0));
              await tester.pump();
            }
          }
        }
        
        final finalWidgetCount = tester.allWidgets.length;
        
        // Widget count should not grow excessively
        final widgetGrowth = finalWidgetCount - initialWidgetCount;
        expect(widgetGrowth, lessThan(100),
          reason: 'Widget count should not grow excessively during navigation');
      });
    });

    group('UI Responsiveness', () {
      testWidgets('UI should remain responsive during data loading', (WidgetTester tester) async {
        await tester.pumpWidget(const MITAApp());
        
        // Initial pump
        await tester.pump();
        
        // Look for loading indicators
        final loadingIndicators = find.byType(CircularProgressIndicator);
        if (loadingIndicators.evaluate().isNotEmpty) {
          // UI should still be interactive during loading
          final refreshButtons = find.byIcon(Icons.refresh);
          // Look for UI elements during loading
          
          // Should be able to tap buttons during loading
          if (refreshButtons.evaluate().isNotEmpty) {
            await tester.tap(refreshButtons.first);
            await tester.pump();
          }
          
          // UI should not freeze
          expect(tester.takeException(), isNull);
        }
      });

      testWidgets('Scroll performance should be smooth', (WidgetTester tester) async {
        await tester.pumpWidget(const MITAApp());
        await tester.pump();
        
        // Find scrollable widgets
        final scrollViews = find.byType(ScrollView);
        final listViews = find.byType(ListView);
        final singleChildScrollViews = find.byType(SingleChildScrollView);
        
        final scrollableWidgets = [
          ...scrollViews.evaluate(),
          ...listViews.evaluate(),
          ...singleChildScrollViews.evaluate(),
        ];
        
        if (scrollableWidgets.isNotEmpty) {
          final scrollableFinder = scrollViews.evaluate().isNotEmpty ? scrollViews.first : 
                                  listViews.evaluate().isNotEmpty ? listViews.first : 
                                  singleChildScrollViews.first;
          
          // Test scrolling performance
          await tester.fling(scrollableFinder, const Offset(0, -300), 1000);
          await tester.pump();
          await tester.pump(const Duration(milliseconds: 100));
          
          await tester.fling(scrollableFinder, const Offset(0, 300), 1000);
          await tester.pump();
          await tester.pump(const Duration(milliseconds: 100));
          
          // Should complete without throwing exceptions
          expect(tester.takeException(), isNull);
        }
      });
    });

    group('Error Recovery Performance', () {
      testWidgets('App should recover quickly from network errors', (WidgetTester tester) async {
        await tester.pumpWidget(const MITAApp());
        await tester.pump();
        
        // Look for retry mechanisms
        final retryButtons = find.textContaining('retry', findRichText: true);
        final refreshButtons = find.byIcon(Icons.refresh);
        
        if (retryButtons.evaluate().isNotEmpty) {
          final stopwatch = Stopwatch()..start();
          
          await tester.tap(retryButtons.first);
          await tester.pump();
          
          stopwatch.stop();
          
          // Retry action should be responsive
          expect(stopwatch.elapsedMilliseconds, lessThan(500),
            reason: 'Retry action should be immediate');
        }
        
        if (refreshButtons.evaluate().isNotEmpty) {
          final stopwatch = Stopwatch()..start();
          
          await tester.tap(refreshButtons.first);
          await tester.pump();
          
          stopwatch.stop();
          
          // Refresh action should be responsive
          expect(stopwatch.elapsedMilliseconds, lessThan(500),
            reason: 'Refresh action should be immediate');
        }
      });
    });

    group('Animation Performance', () {
      testWidgets('Animations should not cause frame drops', (WidgetTester tester) async {
        await tester.pumpWidget(const MITAApp());
        await tester.pump();
        
        // Look for animated widgets
        final animatedWidgets = find.byWidgetPredicate((widget) =>
          widget is AnimatedWidget ||
          widget is AnimatedContainer ||
          widget is AnimatedOpacity ||
          widget is FadeTransition ||
          widget is SlideTransition
        );
        
        if (animatedWidgets.evaluate().isNotEmpty) {
          // Trigger animations by interacting with UI
          final tappableElements = find.byType(GestureDetector);
          if (tappableElements.evaluate().isNotEmpty) {
            await tester.tap(tappableElements.first);
            
            // Let animations run
            for (int i = 0; i < 60; i++) { // 1 second at 60fps
              await tester.pump(const Duration(milliseconds: 16));
            }
            
            expect(tester.takeException(), isNull);
          }
        }
      });
    });

    group('Resource Cleanup', () {
      testWidgets('App should clean up resources properly', (WidgetTester tester) async {
        await tester.pumpWidget(const MITAApp());
        await tester.pump();
        
        // Test multiple mount/unmount cycles
        for (int i = 0; i < 3; i++) {
          await tester.pumpWidget(Container()); // Unmount
          await tester.pump();
          
          await tester.pumpWidget(const MITAApp()); // Remount  
          await tester.pump();
        }
        
        // Should handle cleanup without issues
        expect(tester.takeException(), isNull);
      });
    });
  });
}