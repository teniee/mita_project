// One unparseable transaction must not blank the whole history.
//
// TransactionService.getTransactions() mapped every row through
// TransactionModel.fromJson inside a single .map(), and fromJson hard-casts
// id/category/amount and DateTime.parses spent_at/created_at. A row missing
// any of those threw out of the map, the surrounding catch rethrew, and the
// user lost their entire transaction list rather than one row.
//
// That payload is reachable: the transactions table permits NULL spent_at and
// created_at — alembic 0001_initial declares them with neither
// nullable=False nor a server_default, so only SQLAlchemy's Python-side
// `default=` fills them, and TxnOut declares both as non-Optional datetime.
//
// Drives the real Dio through a fake adapter, the same technique as
// auth_refresh_interceptor_test.dart (no mock-adapter package in this repo).

import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mita/services/api_service.dart';
import 'package:mita/services/logging_service.dart';
import 'package:mita/services/transaction_service.dart';

class _PayloadAdapter implements HttpClientAdapter {
  _PayloadAdapter(this.body);

  final Object body;

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    return ResponseBody.fromString(
      jsonEncode(body),
      200,
      headers: {
        Headers.contentTypeHeader: [Headers.jsonContentType],
      },
    );
  }

  @override
  void close({bool force = false}) {}
}

Map<String, dynamic> _goodRow(String id) => {
      'id': id,
      'category': 'food',
      'amount': '12.34',
      'currency': 'USD',
      'spent_at': '2026-09-01T10:00:00Z',
      'created_at': '2026-09-01T10:00:00Z',
    };

void main() {
  late Dio dio;
  late HttpClientAdapter original;

  setUp(() {
    dio = ApiService().authedDio;
    original = dio.httpClientAdapter;
    LoggingService.instance.clearHistory();
  });

  tearDown(() {
    dio.httpClientAdapter = original;
  });

  test('a row with a null spent_at does not blank the history', () async {
    final bad = _goodRow('bad')..['spent_at'] = null;
    dio.httpClientAdapter = _PayloadAdapter({
      'data': [_goodRow('a'), bad, _goodRow('b')],
    });

    final result = await TransactionService().getTransactions();

    expect(result.map((t) => t.id), ['a', 'b'],
        reason: 'the two intact rows must survive the one broken row');
  });

  test('a row missing category does not blank the history', () async {
    final bad = Map<String, dynamic>.from(_goodRow('bad'))..remove('category');
    dio.httpClientAdapter = _PayloadAdapter({
      'data': [_goodRow('a'), bad],
    });

    final result = await TransactionService().getTransactions();

    expect(result.map((t) => t.id), ['a']);
  });

  test('an entirely unparseable list yields empty, not a throw', () async {
    dio.httpClientAdapter = _PayloadAdapter({
      'data': [
        {'nonsense': true},
        {'also': 'nonsense'},
      ],
    });

    final result = await TransactionService().getTransactions();

    expect(result, isEmpty);
  });

  test('a fully valid list is unaffected', () async {
    dio.httpClientAdapter = _PayloadAdapter({
      'data': [_goodRow('a'), _goodRow('b'), _goodRow('c')],
    });

    final result = await TransactionService().getTransactions();

    expect(result.map((t) => t.id), ['a', 'b', 'c']);
    expect(result.first.amount, 12.34);
  });

  // The diagnostic must not leak the row's data.
  //
  // Dart's FormatException embeds its input in toString(): double.parse on
  // '1234.56USD' throws "Invalid double\n1234.56USD", and DateTime.parse does
  // the same with the offending date string. logError forwards to Crashlytics
  // in release builds and LoggingService._maskPII only masks emails, cards,
  // phones, IBANs and tokens — an amount, a merchant or a note is not matched
  // by any of those patterns and would be reported verbatim. So the earlier
  // `logError('Skipping unparseable transaction: $e')` sent the user's money
  // off the device.

  /// Everything the log pipeline would carry off the device for one entry.
  String surface(LogEntry e) =>
      '${e.message} | ${e.error ?? ''} | ${e.extra ?? ''}';

  String allLoggedText() =>
      LoggingService.instance.getRecentLogs().map(surface).join('\n');

  test('a malformed amount never reaches the log', () async {
    final bad = _goodRow('bad')
      ..['amount'] = '1234.56USD'
      ..['merchant'] = 'Kaufland Varna'
      ..['description'] = 'weekly groceries'
      ..['notes'] = 'split with flatmate';
    dio.httpClientAdapter = _PayloadAdapter({
      'data': [_goodRow('a'), bad],
    });

    final result = await TransactionService().getTransactions();
    expect(result.map((t) => t.id), ['a'],
        reason: 'the valid row must still be visible');

    final logged = allLoggedText();
    expect(logged, isNot(contains('1234.56USD')));
    expect(logged, isNot(contains('1234.56')));
    expect(logged, isNot(contains('Kaufland')));
    expect(logged, isNot(contains('weekly groceries')));
    expect(logged, isNot(contains('flatmate')));
    expect(logged, isNot(contains('Invalid double')),
        reason: 'the FormatException message carries its input with it');
  });

  test('a malformed date never reaches the log', () async {
    final bad = _goodRow('bad')..['spent_at'] = '2026-13-99 not-a-date';
    dio.httpClientAdapter = _PayloadAdapter({
      'data': [_goodRow('a'), bad],
    });

    final result = await TransactionService().getTransactions();
    expect(result.map((t) => t.id), ['a']);

    final logged = allLoggedText();
    expect(logged, isNot(contains('2026-13-99')));
    expect(logged, isNot(contains('not-a-date')));
    expect(logged, isNot(contains('Invalid date format')));
  });

  test('the drop is reported, not silent, and names the field', () async {
    final bad = _goodRow('bad')..['amount'] = '1234.56USD';
    dio.httpClientAdapter = _PayloadAdapter({
      'data': [_goodRow('a'), bad, _goodRow('b')],
    });

    await TransactionService().getTransactions();

    final reports = LoggingService.instance
        .getRecentLogs()
        .where((e) => e.tag == 'TRANSACTION_SERVICE')
        .toList();

    expect(reports, hasLength(1),
        reason: 'one report per load, not one per malformed row — a fully '
            'malformed page would otherwise emit up to `limit` non-fatals');

    final report = reports.single;
    expect(report.level, LogLevel.error,
        reason: 'an operator must see that a malformed payload occurred');
    expect(report.message, contains('Dropped 1 of 3'));
    expect(report.message, contains('amount'),
        reason: 'the failing field is schema, not data, and is the diagnostic');
    expect(report.message, contains('#1'),
        reason: 'the row position locates the failure without identifying it');
    expect(report.stackTrace, isNotNull,
        reason: 'stack is preserved even though the exception is not');
    // LoggingService.log() stores `_maskPII(error.toString())`, so whatever
    // object is handed to it is stringified and shipped — which is exactly
    // how the real FormatException would have carried the amount off the
    // device. The stand-in's toString() is counts only.
    expect(report.error, const TransactionParseException(1, 3).toString(),
        reason: 'a value-free stand-in, never the real parse exception');
  });

  test('the transaction id is not used as the diagnostic key', () async {
    final bad = _goodRow('7f3a9c02-user-linked-id')..['spent_at'] = null;
    dio.httpClientAdapter = _PayloadAdapter({
      'data': [_goodRow('a'), bad],
    });

    await TransactionService().getTransactions();

    expect(allLoggedText(), isNot(contains('7f3a9c02-user-linked-id')),
        reason: 'the row id is user-linked and the index already locates it');
  });

  test('a page of malformed rows yields one report, not one per row', () async {
    dio.httpClientAdapter = _PayloadAdapter({
      'data': List.generate(50,
          (i) => Map<String, dynamic>.from(_goodRow('r$i'))..['amount'] = 'x'),
    });

    final result = await TransactionService().getTransactions();

    expect(result, isEmpty);
    expect(
        LoggingService.instance
            .getRecentLogs()
            .where((e) => e.tag == 'TRANSACTION_SERVICE'),
        hasLength(1));
  });
}
