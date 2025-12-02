import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mita/screens/main_screen.dart';

void main() {
  testWidgets('Dashboard shows loading indicator initially',
      (WidgetTester tester) async {
    await tester.pumpWidget(const MaterialApp(home: MainScreen()));

    expect(find.byType(CircularProgressIndicator), findsOneWidget);
  });
}
