/// Crashlytics must never receive the user's money, text or identity.
///
/// `LoggingService._sendToCrashlytics` copied every `extra` value into a
/// Crashlytics custom key with `toString()`. Its PII mask only rewrote String
/// values, so `'amount': 42.17` (a double) and a nested expense Map went out
/// as-is. These cases pin the replacement: an allow-list for structured
/// context, a scrubber for free text, and no user identifier at all.
library;

import 'package:flutter_test/flutter_test.dart';
import 'package:mita/utils/crash_report_sanitizer.dart';

/// Every value the report would put on the wire, as one string.
String _wire(CrashReport r) => [
      ...r.customKeys.entries.map((e) => '${e.key}=${e.value}'),
      r.reason,
      r.exception ?? '',
    ].join('\n');

CrashReport _report(Map<String, dynamic> extra,
        {String message = 'Failed', Object? error}) =>
    buildCrashReport(
      tag: 'TEST',
      level: 'error',
      message: message,
      extra: extra,
      error: error,
      timestamp: DateTime.utc(2026, 9, 24),
    );

void main() {
  group('structured extra is allow-listed', () {
    test('a double amount does not survive, under any key', () {
      final r = _report({
        'amount': 42.17,
        'monthly_income': 5000.0,
        'balance': 1234.56,
        // Even an allowed key may not carry a double.
        'statusCode': 42.17,
      });
      expect(_wire(r), isNot(contains('42.17')));
      expect(_wire(r), isNot(contains('5000')));
      expect(_wire(r), isNot(contains('1234.56')));
      expect(r.customKeys['extra_redacted_count'], 4);
    });

    test('an int or num amount under a non-allowed key does not survive', () {
      const num income = 7250;
      final r = _report({'income': income, 'spent': 88, 'total': 9999});
      expect(_wire(r), isNot(contains('7250')));
      expect(_wire(r), isNot(contains('88')));
      expect(_wire(r), isNot(contains('9999')));
    });

    test('merchant, description, note, category and email are dropped', () {
      final r = _report({
        'merchant': 'Starbucks Reserve',
        'description': 'Dinner with Anna',
        'note': 'rent share',
        'category': 'Food & Dining',
        'email': 'dana@example.com',
      });
      for (final v in [
        'Starbucks',
        'Anna',
        'rent share',
        'Food',
        'dana',
        'example.com',
      ]) {
        expect(_wire(r), isNot(contains(v)), reason: v);
      }
    });

    test('a nested Map or List is dropped whole, even under an allowed key',
        () {
      final r = _report({
        'expenseData': {
          'amount': 42.17,
          'category': 'food',
          'description': 'Starbucks',
          'items': [
            {'price': 3.5}
          ],
        },
        'detail': {'provided_amount': 150000.55},
        'reason': [42.17, 'Starbucks'],
      });
      expect(_wire(r), isNot(contains('42.17')));
      expect(_wire(r), isNot(contains('Starbucks')));
      expect(_wire(r), isNot(contains('150000')));
      expect(_wire(r), isNot(contains('3.5')));
      expect(r.customKeys['extra_redacted_count'], 3);
    });

    test('a user identifier is never attached', () {
      final r = _report({
        'user_id': '2d3a4f33-8b0f-4abe-bb59-76da3d2eaed4',
        'userId': 'u-123',
      });
      expect(_wire(r), isNot(contains('2d3a4f33')));
      expect(_wire(r), isNot(contains('u-123')));
    });

    test('tokens and headers are dropped', () {
      final r = _report({
        'access_token': 'eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ4In0.sig',
        'headers': {'Authorization': 'Bearer abc.def.ghi'},
        'refresh_token': 'r' * 40,
      });
      expect(_wire(r), isNot(contains('eyJ')));
      expect(_wire(r), isNot(contains('Bearer abc')));
      expect(_wire(r), isNot(contains('rrrrrrrr')));
    });

    test('failure-describing context still gets through', () {
      final r = _report({
        'statusCode': 500,
        'operation': 'createTransaction',
        'has_retry': true,
        'total_attempts': 3,
        'url':
            'https://api.example.test/api/transactions/?search=starbucks&month=2026-09',
      });
      expect(r.customKeys['extra_statusCode'], 500);
      expect(r.customKeys['extra_operation'], 'createTransaction');
      expect(r.customKeys['extra_has_retry'], true);
      expect(r.customKeys['extra_total_attempts'], 3);
      // The endpoint, without host or query.
      expect(r.customKeys['extra_url'], '/api/transactions/');
      expect(r.customKeys['log_tag'], 'TEST');
      expect(r.customKeys['log_level'], 'ERROR');
      expect(r.customKeys.containsKey('extra_redacted_count'), isFalse);
    });
  });

  group('free text is scrubbed', () {
    test('an exception carrying a serialized expense loses its values', () {
      final r = _report(
        const {},
        message: 'Failed to add expense optimistically',
        error: Exception(
            'Invalid expense {amount: 42.17, category: food, description: '
            'Starbucks Reserve, day: 24}'),
      );
      expect(r.exception, isNot(contains('42.17')));
      expect(r.exception, isNot(contains('Starbucks')));
      expect(r.exception, isNot(contains('food')));
      expect(r.exception, contains('Invalid expense'));
    });

    test('a JSON error body loses its values', () {
      // The exact 422 the backend returns for an amount over the cap, and the
      // 422 for a duplicate registration.
      const overCap = '{"success":false,"error":{"code":"VALIDATION_2003",'
          '"message":"Amount cannot exceed \$100,000.00","details":'
          '{"max_amount":100000.0,"provided_amount":150000.55}}}';
      const duplicate = '{"error":{"code":"RESOURCE_3002","details":'
          '{"email":"dana.rga@example.com"}}}';
      final text = scrubCrashText('$overCap $duplicate');
      expect(text, isNot(contains('150000')));
      expect(text, isNot(contains('100,000')));
      expect(text, isNot(contains('dana')));
      expect(text, isNot(contains('example.com')));
      expect(text, contains('VALIDATION_2003'));
      expect(text, contains('RESOURCE_3002'));
    });

    test('money-like numbers in a message are removed', () {
      final text = scrubCrashText(
          'Budget exceeded: spent \$1,234.50 of 1500 (overshoot 12.5) €80');
      for (final v in ['1,234', '1234', '1500', '12.5', '80']) {
        expect(text, isNot(contains(v)), reason: v);
      }
    });

    test('query strings, e-mails and tokens are removed', () {
      final text = scrubCrashText(
          'GET https://api.example.test/api/transactions/?search=starbucks '
          'for dana@example.com with Bearer eyJhbGciOiJIUzI1NiJ9.eyJ4In0.s1g '
          'refresh 0123456789abcdef0123456789abcdef');
      expect(text, isNot(contains('starbucks')));
      expect(text, isNot(contains('dana')));
      expect(text, isNot(contains('eyJ')));
      expect(text, isNot(contains('0123456789abcdef')));
      expect(text, contains('/api/transactions/'));
    });

    test('a partially masked e-mail from the local mask is removed too', () {
      expect(scrubCrashText('user da***@example.com'), isNot(contains('da*')));
    });

    test('status codes and stack-trace structure survive', () {
      final text =
          scrubCrashText('DioException [bad response]: status code of 500\n'
              '#0      _AddExpenseScreenStateWithTickerProviderMixin._submit '
              '(package:mita/screens/add_expense_screen.dart:512:7)');
      expect(text, contains('500'));
      expect(text, contains('#0'));
      expect(text, contains('_AddExpenseScreenStateWithTickerProviderMixin'));
      expect(text, contains('add_expense_screen.dart:512:7'));
    });

    test('long text is bounded', () {
      expect(scrubCrashText('x' * 5000).length,
          lessThanOrEqualTo(kCrashTextLimit + 1));
    });
  });
}
