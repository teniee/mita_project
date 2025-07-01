import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('sample integration test', (WidgetTester tester) async {
    await tester.pumpWidget(const MaterialApp(home: Text('Integration Test')));
    expect(find.text('Integration Test'), findsOneWidget);
  });
}
