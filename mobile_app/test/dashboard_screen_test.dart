import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mita/screens/main_screen.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'helpers/test_app.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  SharedPreferences.setMockInitialValues(<String, Object>{});

  testWidgets('Dashboard shows loading indicator initially',
      (WidgetTester tester) async {
    // MainScreen reads app state through the provider tree (see lib/main.dart).
    await tester.pumpWidget(wrapWithProviders(const MainScreen()));
    await tester.pump();

    expect(find.byType(CircularProgressIndicator), findsWidgets);
  });
}
