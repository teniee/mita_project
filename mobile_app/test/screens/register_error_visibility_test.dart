/// Registration must tell the user why it refused, where they can see it.
///
/// Device-reproduced during the pre-launch pass: the rejection text rendered
/// at the very bottom of the card, after "Back to login". With the keyboard
/// open — the only state a user is actually in when they tap Register — that
/// sits below the fold, so tapping Register looked like the button did
/// nothing. Users retried, then gave up, at the very first screen of the app.
///
/// The password rule shown on screen also has to be the rule that is enforced:
/// the old hint promised "at least 8 characters" while
/// PasswordValidationService additionally requires upper, lower, digit and
/// symbol.
library;

import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:mita/providers/providers.dart';
import 'package:mita/screens/register_screen.dart';
import 'package:mita/theme/mita_theme.dart';

class _NoNetwork extends HttpOverrides {
  @override
  HttpClient createHttpClient(SecurityContext? context) =>
      throw const SocketException('network disabled in tests');
}

Widget _host({double bottomInset = 0}) => MultiProvider(
      providers: [
        ChangeNotifierProvider<SettingsProvider>(
            create: (_) => SettingsProvider()),
        ChangeNotifierProvider<UserProvider>(create: (_) => UserProvider()),
      ],
      child: MaterialApp(
        theme: MitaTheme.lightTheme,
        home: Builder(
          builder: (context) => MediaQuery(
            data: MediaQuery.of(context).copyWith(
              viewInsets: EdgeInsets.only(bottom: bottomInset),
              padding: const EdgeInsets.only(top: 24, bottom: 16),
            ),
            child: const RegisterScreen(),
          ),
        ),
      ),
    );

Future<void> _submit(
  WidgetTester tester, {
  required String email,
  required String password,
}) async {
  await tester.enterText(find.widgetWithText(TextField, 'Email'), email);
  await tester.enterText(find.widgetWithText(TextField, 'Password'), password);
  final button = find.widgetWithText(ElevatedButton, 'Register');
  // The card scrolls; a user scrolls to the button before tapping it. This
  // also asserts the button is reachable at all — it must never be stranded
  // outside the scrollable area.
  await tester.ensureVisible(button);
  // settle, not pump: ensureVisible animates, and tapping mid-scroll lands
  // where the button no longer is.
  await tester.pumpAndSettle();
  await tester.tap(button);
  await tester.pump();
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  HttpOverrides.global = _NoNetwork();
  SharedPreferences.setMockInitialValues(<String, Object>{});

  testWidgets('states the password rule that is actually enforced',
      (tester) async {
    await tester.pumpWidget(_host());
    await tester.pump();

    final hint = tester.widget<Text>(find.textContaining('at least 8'));
    final text = hint.data!;
    // Naming only the length would send users round a loop of rejections they
    // cannot explain.
    expect(text, contains('upper'));
    expect(text, contains('number'));
    expect(text, contains('symbol'));
  });

  testWidgets('a rejected password is reported above the Register button',
      (tester) async {
    // 300px of keyboard: the state the user is in when they tap Register.
    // (Narrow-phone layout for this screen is covered by
    // small_viewport_overflow_test.dart; what matters here is the order of
    // the error relative to the button, which is viewport-independent.)
    await tester.pumpWidget(_host(bottomInset: 300));
    await tester.pump();

    await _submit(tester, email: 'someone@example.com', password: 'short');

    final error = find.textContaining('at least 8 characters long');
    expect(error, findsOneWidget,
        reason: 'tapping Register with a bad password must say why');

    // Above the button, not after "Back to login" at the bottom of the card.
    final errorY = tester.getTopLeft(error).dy;
    final buttonY =
        tester.getTopLeft(find.widgetWithText(ElevatedButton, 'Register')).dy;
    expect(errorY, lessThan(buttonY),
        reason: 'the reason must sit between the fields and the button, so it '
            'is on screen whenever the button is');
  });

  testWidgets('a rejection clears as soon as the user edits a field',
      (tester) async {
    await tester.pumpWidget(_host());
    await tester.pump();

    await _submit(tester, email: 'someone@example.com', password: 'short');
    expect(find.textContaining('at least 8 characters long'), findsOneWidget);

    await tester.enterText(
        find.widgetWithText(TextField, 'Password'), 'shortE');
    await tester.pump();

    // A stale rejection describing values no longer in the fields is a lie.
    expect(find.textContaining('at least 8 characters long'), findsNothing);
  });

  testWidgets('an empty email is reported, not silently ignored',
      (tester) async {
    await tester.pumpWidget(_host());
    await tester.pump();

    await _submit(tester, email: '', password: 'Kx9#tRw4qz');
    expect(find.textContaining('enter your email'), findsOneWidget);
  });
}
