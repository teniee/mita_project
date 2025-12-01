import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_localizations/flutter_localizations.dart';

import 'package:mita/l10n/generated/app_localizations.dart';
import 'package:mita/services/localization_service.dart';
import 'package:mita/utils/financial_formatters.dart';
import 'package:mita/screens/login_screen.dart';
import 'package:mita/screens/welcome_screen.dart';

void main() {
  group('MITA i18n Integration Tests', () {
    testWidgets('Login screen displays English strings correctly',
        (tester) async {
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

      // Check for English strings
      expect(find.text('Welcome back'), findsOneWidget);
      expect(find.text('Sign in to continue managing your finances'),
          findsOneWidget);
      expect(find.text('Email address'), findsOneWidget);
      expect(find.text('Password'), findsOneWidget);
      expect(find.text('Remember me'), findsOneWidget);
      expect(find.text('Continue with Google'), findsOneWidget);
      expect(find.text('Sign In'), findsOneWidget);
    });

    testWidgets('Login screen displays Spanish strings correctly',
        (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          locale: Locale('es'),
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

      // Check for Spanish strings
      expect(find.text('Bienvenido de nuevo'), findsOneWidget);
      expect(find.text('Inicia sesión para continuar gestionando tus finanzas'),
          findsOneWidget);
      expect(find.text('Dirección de correo electrónico'), findsOneWidget);
      expect(find.text('Contraseña'), findsOneWidget);
      expect(find.text('Recordarme'), findsOneWidget);
      expect(find.text('Continuar con Google'), findsOneWidget);
      expect(find.text('Iniciar Sesión'), findsOneWidget);
    });

    testWidgets('Welcome screen displays localized status messages',
        (tester) async {
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
          home: WelcomeScreen(),
        ),
      );

      await tester.pump();

      // The initial text should appear
      expect(find.text('Initializing...'), findsOneWidget);
    });

    test('LocalizationService formats currency correctly for different locales',
        () {
      // Test USD formatting
      LocalizationService.instance.setLocale(const Locale('en', 'US'));

      String formatted = LocalizationService.instance.formatCurrency(1234.56);
      expect(formatted, contains('\$'));
      expect(formatted, contains('1,234.56'));

      // Test EUR formatting (Spanish locale)
      LocalizationService.instance.setLocale(const Locale('es', 'ES'));

      formatted = LocalizationService.instance.formatCurrency(1234.56);
      expect(formatted, contains('€'));
      // Note: Exact formatting may vary based on system locale support
    });

    test('FinancialFormatters work with BuildContext-aware methods', () {
      // Create a test widget to provide context
      testWidgets('Currency formatting with context', (tester) async {
        late BuildContext testContext;

        await tester.pumpWidget(
          MaterialApp(
            locale: const Locale('en', 'US'),
            localizationsDelegates: const [
              AppLocalizations.delegate,
              GlobalMaterialLocalizations.delegate,
              GlobalWidgetsLocalizations.delegate,
              GlobalCupertinoLocalizations.delegate,
            ],
            supportedLocales: AppLocalizations.supportedLocales,
            home: Builder(
              builder: (context) {
                testContext = context;
                return Container();
              },
            ),
          ),
        );

        await tester.pump();

        // Test currency formatting
        final currencyFormatted =
            FinancialFormatters.formatCurrency(testContext, 1234.56);
        expect(currencyFormatted, contains('\$'));
        expect(currencyFormatted, contains('1,234.56'));

        // Test compact formatting
        final compactFormatted =
            FinancialFormatters.formatCompactCurrency(testContext, 1234567);
        expect(compactFormatted, contains('1.2M'));

        // Test category formatting
        final categoryFormatted =
            FinancialFormatters.formatCategory(testContext, 'food');
        expect(categoryFormatted, 'Food');
      });
    });

    test('LocalizationService provides correct currency data', () {
      // Test USD
      LocalizationService.instance.setLocale(const Locale('en', 'US'));
      expect(LocalizationService.instance.currencyCode, 'USD');
      expect(LocalizationService.instance.currencySymbol, '\$');

      // Test EUR (Spanish)
      LocalizationService.instance.setLocale(const Locale('es', 'ES'));
      expect(LocalizationService.instance.currencyCode, 'EUR');
      expect(LocalizationService.instance.currencySymbol, '€');

      // Test GBP
      LocalizationService.instance.setLocale(const Locale('en', 'GB'));
      expect(LocalizationService.instance.currencyCode, 'GBP');
      expect(LocalizationService.instance.currencySymbol, '£');
    });

    test('LocalizationService handles number parsing correctly', () {
      // Test US format parsing
      LocalizationService.instance.setLocale(const Locale('en', 'US'));

      double? parsed = LocalizationService.instance.parseCurrency('\$1,234.56');
      expect(parsed, 1234.56);

      parsed = LocalizationService.instance.parseCurrency('1234.56');
      expect(parsed, 1234.56);

      // Test invalid input
      parsed = LocalizationService.instance.parseCurrency('invalid');
      expect(parsed, null);
    });

    test('LocalizationService formats dates correctly', () {
      final testDate = DateTime(2024, 12, 25);

      // Test US format
      LocalizationService.instance.setLocale(const Locale('en', 'US'));
      String dateFormatted = LocalizationService.instance.formatDate(testDate);
      expect(dateFormatted, contains('12'));
      expect(dateFormatted, contains('25'));
      expect(dateFormatted, contains('2024'));

      // Test Spanish format
      LocalizationService.instance.setLocale(const Locale('es', 'ES'));
      dateFormatted = LocalizationService.instance.formatDate(testDate);
      expect(dateFormatted, contains('25'));
      expect(dateFormatted, contains('12'));
      expect(dateFormatted, contains('2024'));
    });

    test('LocalizationService handles percentage formatting', () {
      LocalizationService.instance.setLocale(const Locale('en', 'US'));

      String percentage = LocalizationService.instance.formatPercentage(0.1256);
      expect(percentage, contains('12.6'));
      expect(percentage, contains('%'));

      percentage = LocalizationService.instance.formatPercentage(1.0);
      expect(percentage, contains('100'));
    });

    test('LocalizationService detects text direction correctly', () {
      // LTR languages
      LocalizationService.instance.setLocale(const Locale('en', 'US'));
      expect(LocalizationService.instance.textDirection, TextDirection.ltr);

      LocalizationService.instance.setLocale(const Locale('es', 'ES'));
      expect(LocalizationService.instance.textDirection, TextDirection.ltr);

      // Note: RTL would be tested with Arabic/Hebrew locales when added
      // Example: LocalizationService.instance.setLocale(const Locale('ar'));
      // expect(LocalizationService.instance.textDirection, TextDirection.rtl);
    });

    testWidgets('App handles unsupported locale gracefully', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          locale: const Locale('fr'), // Unsupported locale
          localizationsDelegates: const [
            AppLocalizations.delegate,
            GlobalMaterialLocalizations.delegate,
            GlobalWidgetsLocalizations.delegate,
            GlobalCupertinoLocalizations.delegate,
          ],
          supportedLocales: AppLocalizations.supportedLocales,
          localeResolutionCallback: (locale, supportedLocales) {
            // Should fall back to English
            return const Locale('en');
          },
          home: const Scaffold(
            body: Text('Test'),
          ),
        ),
      );

      await tester.pumpAndSettle();

      // App should not crash and should default to English
      expect(find.text('Test'), findsOneWidget);
    });

    test('FinancialFormatters budget status formatting works', () {
      testWidgets('Budget status with context', (tester) async {
        late BuildContext testContext;

        await tester.pumpWidget(
          MaterialApp(
            locale: const Locale('en'),
            localizationsDelegates: const [
              AppLocalizations.delegate,
              GlobalMaterialLocalizations.delegate,
              GlobalWidgetsLocalizations.delegate,
              GlobalCupertinoLocalizations.delegate,
            ],
            supportedLocales: AppLocalizations.supportedLocales,
            home: Builder(
              builder: (context) {
                testContext = context;
                return Container();
              },
            ),
          ),
        );

        await tester.pump();

        // Test over budget
        String status =
            FinancialFormatters.formatBudgetStatus(testContext, 1200.0, 1000.0);
        expect(status, contains('Over Budget'));

        // Test under budget
        status =
            FinancialFormatters.formatBudgetStatus(testContext, 800.0, 1000.0);
        expect(status, contains('Under Budget'));

        // Test on track
        status =
            FinancialFormatters.formatBudgetStatus(testContext, 950.0, 1000.0);
        expect(status, contains('On Track'));
      });
    });

    test('Large amount detection works correctly', () {
      LocalizationService.instance.setLocale(const Locale('en', 'US'));

      // Test USD thresholds
      expect(FinancialFormatters.isLargeAmount(500.0), false);
      expect(FinancialFormatters.isLargeAmount(1000.0), true);
      expect(FinancialFormatters.isLargeAmount(1500.0), true);
    });

    test('Input validation works correctly', () {
      // Valid inputs
      expect(FinancialFormatters.isValidCurrencyInput('123.45'), true);
      expect(FinancialFormatters.isValidCurrencyInput('0'), true);
      expect(FinancialFormatters.isValidCurrencyInput('1000'), true);

      // Invalid inputs
      expect(FinancialFormatters.isValidCurrencyInput('-50'), false);
      expect(FinancialFormatters.isValidCurrencyInput('abc'), false);
      expect(FinancialFormatters.isValidCurrencyInput(''), false);
    });
  });

  group('Error Handling Tests', () {
    test('LocalizationService handles missing locale gracefully', () {
      // Set an unsupported locale
      LocalizationService.instance.setLocale(const Locale('xx', 'XX'));

      // Should fall back to default formatting
      String formatted = LocalizationService.instance.formatCurrency(1234.56);
      expect(formatted, isNotNull);
      expect(formatted, isNotEmpty);
    });

    test('FinancialFormatters handle edge cases', () {
      testWidgets('Edge case handling', (tester) async {
        late BuildContext testContext;

        await tester.pumpWidget(
          MaterialApp(
            locale: const Locale('en'),
            localizationsDelegates: const [
              AppLocalizations.delegate,
              GlobalMaterialLocalizations.delegate,
              GlobalWidgetsLocalizations.delegate,
              GlobalCupertinoLocalizations.delegate,
            ],
            supportedLocales: AppLocalizations.supportedLocales,
            home: Builder(
              builder: (context) {
                testContext = context;
                return Container();
              },
            ),
          ),
        );

        await tester.pump();

        // Test zero amounts
        String result = FinancialFormatters.formatCurrency(testContext, 0.0);
        expect(result, contains('0.00'));

        // Test negative amounts
        result = FinancialFormatters.formatCurrency(testContext, -100.0);
        expect(result, contains('-'));

        // Test very large amounts
        result =
            FinancialFormatters.formatCompactCurrency(testContext, 1000000000);
        expect(result, contains('1.0B'));
      });
    });
  });
}
