import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mita/l10n/generated/app_localizations.dart';
import 'package:mita/screens/login_screen.dart';

void main() {
  testWidgets('Login screen displays sign in button',
      (WidgetTester tester) async {
    // LoginScreen resolves its strings through AppLocalizations, so the
    // harness must provide the delegates the real app configures.
    await tester.pumpWidget(
      const MaterialApp(
        locale: Locale('en'),
        localizationsDelegates: [
          AppLocalizations.delegate,
          GlobalMaterialLocalizations.delegate,
          GlobalWidgetsLocalizations.delegate,
          GlobalCupertinoLocalizations.delegate,
        ],
        supportedLocales: AppLocalizations.supportedLocales,
        home: LoginScreen(),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Sign In'), findsOneWidget);
    expect(find.text('Continue with Google'), findsOneWidget);
  });
}
