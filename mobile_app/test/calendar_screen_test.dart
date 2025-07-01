import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mobile_app/screens/calendar_screen.dart';

void main() {
  testWidgets('Calendar shows loading indicator initially', (WidgetTester tester) async {
    await tester.pumpWidget(const MaterialApp(home: CalendarScreen()));

    expect(find.byType(CircularProgressIndicator), findsOneWidget);
  });
}
