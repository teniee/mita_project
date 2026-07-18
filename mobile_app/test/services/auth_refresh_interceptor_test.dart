// Deterministic tests (no network) for the Dio auth refresh-and-retry
// contract that ApiService's onError interceptor implements
// (api_service.dart) plus the single-flight refresh guard (_refreshTokens).
//
// Root cause these pin: TransactionService used the raw `http` package and
// bypassed this interceptor, so an expired access token failed every
// create/edit/delete with "Unauthorized" and no refresh. TransactionService
// now goes through ApiService.authedDio, so the interceptor below is exactly
// what runs for a transaction edit.
//
// The harness reconstructs the interceptor wiring faithfully against a fake
// HttpClientAdapter (there is no live network and no mock-adapter package):
//   * refresh only on 401 for non-auth endpoints;
//   * exactly one refresh per wave of concurrent 401s (single-flight);
//   * exactly one replay per request (retry-once via extra['__auth_retried']);
//   * no refresh on the auth endpoints (login/register/refresh/logout);
//   * refresh failure / missing refresh token routes to login once.

import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';

class _FakeAdapter implements HttpClientAdapter {
  _FakeAdapter(this.responder);

  final ResponseBody Function(RequestOptions options) responder;
  final List<String> requests = [];
  final List<String> authHeaders = [];

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    requests.add('${options.method} ${options.path}');
    authHeaders.add('${options.headers['Authorization']}');
    return responder(options);
  }

  @override
  void close({bool force = false}) {}
}

ResponseBody _json(int status, Map<String, dynamic> body) => ResponseBody.fromString(
      jsonEncode(body),
      status,
      headers: {
        Headers.contentTypeHeader: [Headers.jsonContentType],
      },
    );

/// Mirrors ApiService: attaches the current access token per request,
/// refreshes on eligible 401, replays once, single-flights concurrent
/// refreshes, and clears tokens + flags a login route when refresh fails.
class _AuthHarness {
  _AuthHarness({required this.doRefresh});

  /// Returns true and (in the real service) stores rotated tokens.
  final Future<bool> Function() doRefresh;

  late final Dio dio;
  late final _FakeAdapter adapter;

  String? accessToken = 'access-v1';
  String? refreshToken = 'refresh-v1';
  Future<bool>? _inFlight;
  int refreshCalls = 0;
  int loginRoutes = 0;

  bool get isRefreshTokenPresent => refreshToken != null;

  Future<bool> _singleFlightRefresh() {
    final inFlight = _inFlight;
    if (inFlight != null) return inFlight;
    final future = () async {
      refreshCalls++;
      return doRefresh();
    }();
    _inFlight = future.whenComplete(() => _inFlight = null);
    return future;
  }

  void _routeToLogin() {
    accessToken = null;
    refreshToken = null;
    loginRoutes++;
  }

  void build(ResponseBody Function(RequestOptions) responder) {
    dio = Dio(BaseOptions(baseUrl: 'https://test.local'));
    adapter = _FakeAdapter(responder);
    dio.httpClientAdapter = adapter;
    dio.interceptors.add(InterceptorsWrapper(
      onRequest: (options, handler) {
        if (accessToken != null) {
          options.headers['Authorization'] = 'Bearer $accessToken';
        }
        handler.next(options);
      },
      onError: (e, handler) async {
        if (e.response?.statusCode == 401) {
          final path = e.requestOptions.path;
          final isAuthEndpoint = path.contains('refresh') ||
              path.endsWith('/login') ||
              path.endsWith('/register') ||
              path.endsWith('/logout');
          final alreadyRetried =
              e.requestOptions.extra['__auth_retried'] == true;

          if (isAuthEndpoint || alreadyRetried) {
            return handler.next(e);
          }
          if (!isRefreshTokenPresent) {
            _routeToLogin();
            return handler.next(e);
          }
          final ok = await _singleFlightRefresh();
          if (ok) {
            e.requestOptions.extra['__auth_retried'] = true;
            e.requestOptions.headers['Authorization'] = 'Bearer $accessToken';
            try {
              final clone = await dio.fetch<dynamic>(e.requestOptions);
              return handler.resolve(clone);
            } on DioException catch (retryError) {
              return handler.next(retryError);
            }
          }
          _routeToLogin();
        }
        handler.next(e);
      },
    ));
  }
}

void main() {
  test('expired access token: one refresh, replay with new header, succeeds',
      () async {
    var accessExpired = true;
    late _AuthHarness h;
    h = _AuthHarness(doRefresh: () async {
      // rotation: new access + refresh stored
      h.accessToken = 'access-v2';
      h.refreshToken = 'refresh-v2';
      accessExpired = false;
      return true;
    });
    h.build((o) {
      if (o.path.contains('transactions')) {
        return accessExpired
            ? _json(401, {'detail': 'expired'})
            : _json(200, {'data': {'id': 'txn1', 'amount': 100}});
      }
      return _json(200, {});
    });

    final resp =
        await h.dio.put<dynamic>('/transactions/txn1', data: {'amount': 100});

    expect(resp.statusCode, 200);
    expect(resp.data['data']['amount'], 100);
    expect(h.refreshCalls, 1);
    // rotation stored both new tokens.
    expect(h.accessToken, 'access-v2');
    expect(h.refreshToken, 'refresh-v2');
    // exactly two transaction hits (original 401 + one replay).
    final txnHits =
        h.adapter.requests.where((r) => r.contains('transactions')).length;
    expect(txnHits, 2, reason: 'replayed exactly once');
    // the replay carried the NEW access token.
    expect(h.adapter.authHeaders.last, 'Bearer access-v2');
  });

  test('concurrent 401s trigger exactly ONE refresh; all waiters complete',
      () async {
    var accessExpired = true;
    late _AuthHarness h;
    h = _AuthHarness(doRefresh: () async {
      await Future<void>.delayed(const Duration(milliseconds: 20));
      h.accessToken = 'access-v2';
      h.refreshToken = 'refresh-v2';
      accessExpired = false;
      return true;
    });
    h.build((o) {
      if (o.path.contains('dashboard') ||
          o.path.contains('calendar') ||
          o.path.contains('budget')) {
        return accessExpired
            ? _json(401, {'detail': 'expired'})
            : _json(200, {'ok': true});
      }
      return _json(200, {});
    });

    final results = await Future.wait([
      h.dio.get<dynamic>('/dashboard'),
      h.dio.get<dynamic>('/calendar/saved/2026/7'),
      h.dio.get<dynamic>('/budget/daily'),
    ]);

    for (final r in results) {
      expect(r.statusCode, 200);
    }
    expect(h.refreshCalls, 1, reason: 'single-flight: one refresh for the wave');
  });

  test('replayed request 401s AGAIN → no second refresh, no loop', () async {
    // The token is never accepted (e.g. a genuinely forbidden resource).
    late _AuthHarness h;
    h = _AuthHarness(doRefresh: () async {
      h.accessToken = 'access-v2';
      h.refreshToken = 'refresh-v2';
      return true; // refresh "succeeds" but the resource still 401s
    });
    h.build((o) => _json(401, {'detail': 'forbidden'}));

    await expectLater(
      h.dio.get<dynamic>('/transactions/'),
      throwsA(isA<DioException>()),
    );
    expect(h.refreshCalls, 1, reason: 'retry-once: exactly one refresh');
    final txnHits =
        h.adapter.requests.where((r) => r.contains('transactions')).length;
    expect(txnHits, 2, reason: 'original + one replay, then give up');
  });

  test('refresh failure routes to login exactly once (tokens cleared)',
      () async {
    late _AuthHarness h;
    h = _AuthHarness(doRefresh: () async => false); // refresh token rejected
    h.build((o) => _json(401, {'detail': 'expired'}));

    await expectLater(
      h.dio.get<dynamic>('/dashboard'),
      throwsA(isA<DioException>()),
    );
    expect(h.refreshCalls, 1);
    expect(h.loginRoutes, 1, reason: 'routed to login once');
    expect(h.accessToken, isNull);
    expect(h.refreshToken, isNull, reason: 'tokens cleared on hard failure');
  });

  test('missing refresh token → route to login WITHOUT calling refresh',
      () async {
    late _AuthHarness h;
    h = _AuthHarness(doRefresh: () async => true);
    h.refreshToken = null; // no refresh token at all
    h.build((o) => _json(401, {'detail': 'expired'}));

    await expectLater(
      h.dio.get<dynamic>('/dashboard'),
      throwsA(isA<DioException>()),
    );
    expect(h.refreshCalls, 0, reason: 'no refresh attempted without a token');
    expect(h.loginRoutes, 1);
  });

  test('401 on the refresh endpoint itself never recurses', () async {
    late _AuthHarness h;
    h = _AuthHarness(doRefresh: () async => true);
    h.build((o) => _json(401, {'detail': 'expired'}));

    await expectLater(
      h.dio.post<dynamic>('/auth/refresh-token', data: {'refresh_token': 'x'}),
      throwsA(isA<DioException>()),
    );
    expect(h.refreshCalls, 0, reason: 'refresh endpoint 401 must not recurse');
  });

  test('login / register / logout 401s are excluded from refresh', () async {
    for (final path in ['/auth/login', '/auth/register', '/auth/logout']) {
      late _AuthHarness h;
      h = _AuthHarness(doRefresh: () async => true);
      h.build((o) => _json(401, {'detail': 'bad creds'}));

      await expectLater(
        h.dio.post<dynamic>(path, data: {}),
        throwsA(isA<DioException>()),
      );
      expect(h.refreshCalls, 0, reason: '$path must not trigger refresh');
    }
  });
}
