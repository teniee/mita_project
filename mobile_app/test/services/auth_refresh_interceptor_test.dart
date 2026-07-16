// Tests for the Dio auth refresh-and-retry contract that ApiService's
// onError interceptor implements (api_service.dart ~L120-182) plus the
// single-flight refresh guard (_refreshTokens).
//
// Root cause these pin: TransactionService used the raw `http` package and
// bypassed this interceptor, so an expired access token failed every
// create/edit/delete with "Unauthorized" and no refresh. TransactionService
// now goes through ApiService.authedDio, so the interceptor below is exactly
// what runs for a transaction edit.
//
// A faithful copy of the interceptor wiring is exercised against a fake
// HttpClientAdapter — there is no live network and no mock-adapter package
// in the project.

import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';

/// Programmable adapter: each entry is (statusCode, jsonBody). Records every
/// request path so tests can assert replay/refresh counts.
class _FakeAdapter implements HttpClientAdapter {
  _FakeAdapter(this.responder);

  final ResponseBody Function(RequestOptions options) responder;
  final List<String> requests = [];

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    requests.add('${options.method} ${options.path}');
    return responder(options);
  }

  @override
  void close({bool force = false}) {}
}

ResponseBody _json(int status, Map<String, dynamic> body) {
  return ResponseBody.fromString(
    jsonEncode(body),
    status,
    headers: {
      Headers.contentTypeHeader: [Headers.jsonContentType],
    },
  );
}

/// Wires a Dio with the same refresh-and-retry + single-flight behavior as
/// ApiService. `refresh` returns true on success and (in the real service)
/// stores the rotated tokens; here it just flips `currentToken` and counts.
class _AuthHarness {
  _AuthHarness({required this.refresh});

  final Future<bool> Function() refresh;
  late final Dio dio;
  late final _FakeAdapter adapter;

  Future<bool>? _inFlight;
  int refreshCalls = 0;

  Future<bool> _singleFlightRefresh() {
    final inFlight = _inFlight;
    if (inFlight != null) return inFlight;
    final future = () async {
      refreshCalls++;
      return refresh();
    }();
    _inFlight = future.whenComplete(() => _inFlight = null);
    return future;
  }

  void build(ResponseBody Function(RequestOptions) responder) {
    dio = Dio(BaseOptions(baseUrl: 'https://test.local'));
    adapter = _FakeAdapter(responder);
    dio.httpClientAdapter = adapter;
    dio.interceptors.add(InterceptorsWrapper(
      onError: (e, handler) async {
        if (e.response?.statusCode == 401) {
          final path = e.requestOptions.path;
          final isRefresh = path.contains('refresh');
          if (isRefresh) return handler.next(e);
          final ok = await _singleFlightRefresh();
          if (ok) {
            final clone = await dio.fetch<dynamic>(e.requestOptions);
            return handler.resolve(clone);
          }
        }
        handler.next(e);
      },
    ));
  }
}

void main() {
  test('expired access token: one refresh, request replayed once, succeeds',
      () async {
    var accessExpired = true;
    late _AuthHarness h;
    h = _AuthHarness(refresh: () async {
      accessExpired = false; // rotation succeeded
      return true;
    });
    h.build((options) {
      if (options.path.contains('transactions')) {
        return accessExpired
            ? _json(401, {'detail': 'expired'})
            : _json(200, {'data': {'id': 'txn1', 'amount': 100}});
      }
      return _json(200, {});
    });

    final resp = await h.dio.put<dynamic>('/transactions/txn1',
        data: {'amount': 100});

    expect(resp.statusCode, 200);
    expect(resp.data['data']['amount'], 100);
    expect(h.refreshCalls, 1, reason: 'exactly one refresh');
    // original 401 + replay = 2 transaction hits.
    final txnHits =
        h.adapter.requests.where((r) => r.contains('transactions')).length;
    expect(txnHits, 2, reason: 'replayed exactly once, no duplicate write');
  });

  test('concurrent 401s trigger only ONE refresh (single-flight)', () async {
    var accessExpired = true;
    late _AuthHarness h;
    h = _AuthHarness(refresh: () async {
      await Future<void>.delayed(const Duration(milliseconds: 20));
      accessExpired = false;
      return true;
    });
    h.build((options) {
      if (options.path.contains('dashboard') ||
          options.path.contains('calendar') ||
          options.path.contains('budget')) {
        return accessExpired
            ? _json(401, {'detail': 'expired'})
            : _json(200, {'ok': true});
      }
      return _json(200, {});
    });

    // Three concurrent authenticated calls all get 401 at once.
    final results = await Future.wait([
      h.dio.get<dynamic>('/dashboard'),
      h.dio.get<dynamic>('/calendar/saved/2026/7'),
      h.dio.get<dynamic>('/budget/daily'),
    ]);

    for (final r in results) {
      expect(r.statusCode, 200);
    }
    expect(h.refreshCalls, 1,
        reason: 'rotation invalidates the token — must refresh once, '
            'then all queued requests retry with the new token');
  });

  test('refresh failure does NOT retry (routes to login exactly once)',
      () async {
    late _AuthHarness h;
    h = _AuthHarness(refresh: () async => false); // refresh token expired
    h.build((options) {
      return _json(401, {'detail': 'expired'});
    });

    await expectLater(
      h.dio.get<dynamic>('/dashboard'),
      throwsA(isA<DioException>()),
    );
    expect(h.refreshCalls, 1, reason: 'one refresh attempt');
    // one dashboard hit; no replay after failed refresh.
    final dashHits =
        h.adapter.requests.where((r) => r.contains('dashboard')).length;
    expect(dashHits, 1);
  });

  test('a 401 on the refresh request itself never recurses', () async {
    late _AuthHarness h;
    h = _AuthHarness(refresh: () async => true);
    h.build((options) => _json(401, {'detail': 'expired'}));

    // Hitting the refresh endpoint directly must not trigger another refresh.
    await expectLater(
      h.dio.post<dynamic>('/auth/refresh-token', data: {'refresh_token': 'x'}),
      throwsA(isA<DioException>()),
    );
    expect(h.refreshCalls, 0, reason: 'refresh endpoint 401 must not recurse');
  });
}
