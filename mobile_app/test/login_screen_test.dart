import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mita/screens/login_screen.dart';

void main() {
  testWidgets('Login screen displays sign in button', (WidgetTester tester) async {
    await tester.pumpWidget(const MaterialApp(home: LoginScreen()));

    expect(find.text('Sign in to MITA'), findsOneWidget);
    expect(find.text('Sign in with Google'), findsOneWidget);
  });
}
