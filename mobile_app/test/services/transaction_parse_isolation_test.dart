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
}
