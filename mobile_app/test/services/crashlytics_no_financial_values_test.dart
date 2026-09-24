// What an error-level log entry sends to Crashlytics must not contain the
// user's money.
//
// Reproduced on efbde78: three call sites put the user's data into `extra` on
// realistic failures, and LoggingService forwarded every `extra` value to
// Crashlytics with toString() in release builds — which, with Firebase
// configured (it is what enables push), is the shipped app.
//
//   add_expense_screen      'amount': 42.17 (double), 'category' on any
//                            failed save (offline, timeout, 5xx)
//   expense_state_service   'expenseData': the whole expense Map
//   api_service interceptor 'errorData': every error response body — the
//                            422 for an amount over the cap echoes
//                            provided_amount
//
// Each case logs the exact shape its call site logs through the real
// LoggingService and checks what crashReportFor — the only thing the
// Crashlytics sink receives — would send.

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mita/services/logging_service.dart';
import 'package:mita/utils/crash_report_sanitizer.dart';

/// Every value the sink would put on the wire for this entry.
String _wire(LogEntry e) {
  final CrashReport r = LoggingService.instance.crashReportFor(e);
  return [
    ...r.customKeys.entries.map((k) => '${k.key}=${k.value}'),
    r.reason,
    r.exception ?? '',
  ].join('\n');
}

List<LogEntry> _errors({String? tag}) => LoggingService.instance
    .getRecentLogs()
    .where((e) => e.level == LogLevel.error || e.level == LogLevel.critical)
    .where((e) => tag == null || e.tag == tag)
    .toList();

void main() {
  setUp(LoggingService.instance.clearHistory);

  test('a failed expense save does not send its amount or category', () {
    // add_expense_screen.dart, the catch around the submit.
    logError('Failed to submit expense',
        tag: 'ADD_EXPENSE',
        error: Exception('Failed to create transaction'),
        extra: {
          'stackTrace': StackTrace.current.toString(),
          'amount': 42.17,
          'category': 'Food & Dining',
        });

    final wire = _errors(tag: 'ADD_EXPENSE').map(_wire).join('\n');
    expect(wire, isNot(contains('42.17')));
    expect(wire, isNot(contains('Food & Dining')));
    expect(wire, contains('ADD_EXPENSE: Failed to submit expense'));
    expect(wire, contains('extra_redacted_count=2'));
  });

  test('an error response body with an amount does not reach Crashlytics', () {
    // The exact body the backend returns for an amount over the cap, logged
    // with the exact extra ApiService's Dio interceptor builds for every
    // failed request (api_service.dart, onError).
    const body = {
      'success': false,
      'error': {
        'code': 'VALIDATION_2003',
        'message': r'Amount cannot exceed $100,000.00',
        'details': {'max_amount': 100000.0, 'provided_amount': 150000.55},
      },
    };
    final options = RequestOptions(
      baseUrl: 'https://api.example.test/api',
      path: '/transactions/?note=landlordq3',
      method: 'POST',
      data: {'amount': 150000.55, 'category': 'rent'},
    );
    final e = DioException.badResponse(
      statusCode: 422,
      requestOptions: options,
      response: Response<dynamic>(
          requestOptions: options, statusCode: 422, data: body),
    );
    logError(
      'API Error: ${e.response?.statusCode} ${e.requestOptions.uri}',
      tag: 'API',
      extra: {
        'statusCode': e.response?.statusCode,
        'url': e.requestOptions.uri.toString(),
        'errorMessage': e.message,
        'errorData': e.response?.data,
      },
      error: e,
    );

    final wire = _errors(tag: 'API').map(_wire).join('\n');
    expect(wire, isNot(contains('150000')));
    expect(wire, isNot(contains('100,000')));
    expect(wire, isNot(contains('landlordq3')));
    // The failure is still diagnosable.
    expect(wire, contains('extra_statusCode=422'));
    expect(wire, contains('extra_url=/api/transactions/'));
    expect(wire, contains('API Error: 422'));
  });

  test('an expense map in extra does not reach Crashlytics', () {
    // The shape expense_state_service logs when an optimistic update fails.
    logError('Failed to add expense optimistically',
        tag: 'EXPENSE_STATE',
        error: StateError('calendar day missing'),
        extra: {
          'stackTrace': StackTrace.current.toString(),
          'expenseData': {
            'amount': 42.17,
            'category': 'food',
            'description': 'Starbucks Reserve',
            'date': '2026-09-24',
          },
        });

    final wire = _errors(tag: 'EXPENSE_STATE').map(_wire).join('\n');
    expect(wire, isNot(contains('42.17')));
    expect(wire, isNot(contains('Starbucks')));
    expect(wire, contains('calendar day missing'));
  });
}
