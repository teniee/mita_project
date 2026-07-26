import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mita/services/api_service.dart';
import 'package:shared_preferences/shared_preferences.dart';

class _Route {
  _Route({
    required this.status,
    required this.body,
    this.gate,
    this.started,
  });

  final int status;
  final String body;
  final Future<void>? gate;
  final Completer<void>? started;
}

class _EpochHttpOverrides extends HttpOverrides {
  final routes = <String, _Route>{};
  final calls = <String, int>{};

  @override
  HttpClient createHttpClient(SecurityContext? context) =>
      _EpochHttpClient(this);

  _Route routeFor(Uri uri) {
    final path = uri.path;
    calls[path] = (calls[path] ?? 0) + 1;
    final route =
        routes[path] ?? _Route(status: 200, body: '{"success":true,"data":{}}');
    if (route.started != null && !route.started!.isCompleted) {
      route.started!.complete();
    }
    return route;
  }
}

class _EpochHttpClient implements HttpClient {
  _EpochHttpClient(this.overrides);

  final _EpochHttpOverrides overrides;

  @override
  bool autoUncompress = true;
  @override
  Duration? connectionTimeout;
  @override
  Duration idleTimeout = const Duration(seconds: 15);
  @override
  int? maxConnectionsPerHost;
  @override
  String? userAgent;

  @override
  Future<HttpClientRequest> openUrl(String method, Uri url) async =>
      _EpochHttpRequest(method, url, overrides.routeFor(url));

  @override
  Future<HttpClientRequest> getUrl(Uri url) => openUrl('GET', url);
  @override
  Future<HttpClientRequest> postUrl(Uri url) => openUrl('POST', url);
  @override
  Future<HttpClientRequest> patchUrl(Uri url) => openUrl('PATCH', url);
  @override
  Future<HttpClientRequest> putUrl(Uri url) => openUrl('PUT', url);
  @override
  Future<HttpClientRequest> deleteUrl(Uri url) => openUrl('DELETE', url);
  @override
  void close({bool force = false}) {}
  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

class _EpochHttpRequest implements HttpClientRequest {
  _EpochHttpRequest(this.method, this.uri, this.route);

  @override
  final String method;
  @override
  final Uri uri;
  final _Route route;

  @override
  final HttpHeaders headers = _EpochHeaders();
  @override
  bool followRedirects = true;
  @override
  int maxRedirects = 5;
  @override
  bool persistentConnection = true;
  @override
  bool bufferOutput = true;
  @override
  int contentLength = -1;
  @override
  Encoding encoding = utf8;

  @override
  void add(List<int> data) {}
  @override
  Future<void> addStream(Stream<List<int>> stream) async {
    await stream.drain<void>();
  }

  @override
  void write(Object? object) {}

  @override
  void abort([Object? exception, StackTrace? stackTrace]) {}

  @override
  Future<HttpClientResponse> close() async {
    await route.gate;
    return _EpochHttpResponse(route.status, route.body);
  }

  @override
  Future<HttpClientResponse> get done => close();
  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

class _EpochHttpResponse extends Stream<List<int>>
    implements HttpClientResponse {
  _EpochHttpResponse(this.statusCode, String body) : _bytes = utf8.encode(body);

  @override
  final int statusCode;
  final List<int> _bytes;

  @override
  String get reasonPhrase => statusCode >= 400 ? 'Error' : 'OK';
  @override
  int get contentLength => _bytes.length;
  @override
  HttpClientResponseCompressionState get compressionState =>
      HttpClientResponseCompressionState.notCompressed;
  @override
  HttpHeaders get headers =>
      _EpochHeaders()..set('content-type', 'application/json');
  @override
  bool get isRedirect => false;
  @override
  bool get persistentConnection => false;
  @override
  List<Cookie> get cookies => const [];
  @override
  List<RedirectInfo> get redirects => const [];
  @override
  X509Certificate? get certificate => null;

  @override
  StreamSubscription<List<int>> listen(
    void Function(List<int> event)? onData, {
    Function? onError,
    void Function()? onDone,
    bool? cancelOnError,
  }) {
    return Stream<List<int>>.fromIterable([_bytes]).listen(
      onData,
      onError: onError,
      onDone: onDone,
      cancelOnError: cancelOnError,
    );
  }

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

class _EpochHeaders implements HttpHeaders {
  final Map<String, List<String>> values = {};

  @override
  void set(String name, Object value, {bool preserveHeaderCase = false}) {
    values[name.toLowerCase()] = ['$value'];
  }

  @override
  void add(String name, Object value, {bool preserveHeaderCase = false}) {
    values.putIfAbsent(name.toLowerCase(), () => []).add('$value');
  }

  @override
  List<String>? operator [](String name) => values[name.toLowerCase()];
  @override
  String? value(String name) => values[name.toLowerCase()]?.join(', ');
  @override
  void remove(String name, Object value) =>
      values[name.toLowerCase()]?.remove('$value');
  @override
  void removeAll(String name) => values.remove(name.toLowerCase());
  @override
  void forEach(void Function(String name, List<String> values) action) =>
      values.forEach(action);
  @override
  void clear() => values.clear();
  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

String _jwtFor(String userId, String label) {
  final payload = base64Url
      .encode(utf8.encode(jsonEncode({'sub': userId})))
      .split('=')
      .first;
  return '$label.$payload.signature';
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  final http = _EpochHttpOverrides();
  final secureStore = <String, String>{};
  Completer<void>? blockedWriteGate;
  Completer<void>? blockedWriteStarted;
  String? blockedWriteValue;
  String? failingWriteKey;

  setUpAll(() {
    HttpOverrides.global = http;
  });

  setUp(() async {
    http.routes.clear();
    http.calls.clear();
    secureStore.clear();
    blockedWriteGate = null;
    blockedWriteStarted = null;
    blockedWriteValue = null;
    failingWriteKey = null;
    SharedPreferences.setMockInitialValues(<String, Object>{});

    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(
      const MethodChannel('plugins.it_nomads.com/flutter_secure_storage'),
      (call) async {
        final args = (call.arguments as Map?) ?? const {};
        final key = args['key'] as String?;
        switch (call.method) {
          case 'write':
            final value = args['value'] as String;
            if (key == failingWriteKey) {
              throw PlatformException(
                code: 'WRITE_FAILED',
                message: 'Injected secure-storage write failure',
              );
            }
            if (value == blockedWriteValue) {
              if (blockedWriteStarted != null &&
                  !blockedWriteStarted!.isCompleted) {
                blockedWriteStarted!.complete();
              }
              await blockedWriteGate?.future;
            }
            secureStore[key!] = value;
            return null;
          case 'read':
            return secureStore[key];
          case 'delete':
            secureStore.remove(key);
            return null;
          case 'readAll':
            return Map<String, String>.from(secureStore);
          case 'deleteAll':
            secureStore.clear();
            return null;
          case 'containsKey':
            return secureStore.containsKey(key);
          default:
            return null;
        }
      },
    );
  });

  tearDownAll(() {
    HttpOverrides.global = null;
  });

  test('latest token boundary wins over an older blocked token save', () async {
    final api = ApiService();
    await api.clearTokens();

    blockedWriteGate = Completer<void>();
    blockedWriteStarted = Completer<void>();
    blockedWriteValue = _jwtFor('account-a', 'access-a');

    final oldSave = api.saveTokens(
      blockedWriteValue!,
      _jwtFor('account-a', 'refresh-a'),
    );
    await blockedWriteStarted!.future;

    final newAccess = _jwtFor('account-b', 'access-b');
    final newRefresh = _jwtFor('account-b', 'refresh-b');
    final newSave = api.saveTokens(newAccess, newRefresh);

    blockedWriteGate!.complete();
    await Future.wait([oldSave, newSave]);

    expect(await api.getToken(), newAccess);
    expect(await api.getRefreshToken(), newRefresh);
    expect(await api.getUserId(), 'account-b');
    expect(api.hasActiveSession, isTrue);
  });

  test('secure-store failure can use newer complete legacy fallback', () async {
    final api = ApiService();
    await api.clearTokens();

    // SecureTokenStorage fail-closes and leaves its tombstone set. ApiService
    // must still accept the independently complete legacy pair written by
    // this newer login after it clears the legacy tombstone.
    failingWriteKey = 'mita_access_token_v2';
    final access = _jwtFor('legacy-account', 'legacy-access');
    final refresh = _jwtFor('legacy-account', 'legacy-refresh');
    await api.saveTokens(access, refresh);
    failingWriteKey = null;

    expect(secureStore['mita_logout_tombstone_v1'], 'true');
    expect(secureStore['access_token'], access);
    expect(secureStore.containsKey('mita_logout_tombstone_v1'), isTrue);
    expect(await api.getToken(), access);
    expect(await api.getRefreshToken(), refresh);
    expect(await api.getUserId(), 'legacy-account');
  });

  test('old refresh response cannot overwrite a newer login', () async {
    final api = ApiService();
    await api.clearTokens();
    await api.saveTokens(
      _jwtFor('account-a', 'access-a'),
      _jwtFor('account-a', 'refresh-a'),
    );

    final refreshGate = Completer<void>();
    final refreshStarted = Completer<void>();
    http.routes['/api/auth/refresh-token'] = _Route(
      status: 200,
      body: jsonEncode({
        'access_token': _jwtFor('account-a', 'access-a-rotated'),
        'refresh_token': _jwtFor('account-a', 'refresh-a-rotated'),
      }),
      gate: refreshGate.future,
      started: refreshStarted,
    );

    final staleRefresh = api.refreshAccessToken();
    await refreshStarted.future;

    final newAccess = _jwtFor('account-b', 'access-b');
    final newRefresh = _jwtFor('account-b', 'refresh-b');
    await api.saveTokens(newAccess, newRefresh);
    refreshGate.complete();

    expect(await staleRefresh, isNull);
    expect(await api.getToken(), newAccess);
    expect(await api.getRefreshToken(), newRefresh);
  });

  test('stale 401 does not refresh or replay under the new identity', () async {
    final api = ApiService();
    await api.clearTokens();
    await api.saveTokens(
      _jwtFor('account-a', 'access-a'),
      _jwtFor('account-a', 'refresh-a'),
    );

    final protectedGate = Completer<void>();
    final protectedStarted = Completer<void>();
    http.routes['/api/protected'] = _Route(
      status: 401,
      body: '{"detail":"expired"}',
      gate: protectedGate.future,
      started: protectedStarted,
    );
    http.routes['/api/auth/refresh-token'] = _Route(
      status: 200,
      body: '{}',
    );

    final staleRequest = api.authedDio.get<dynamic>('/protected');
    await protectedStarted.future;

    await api.saveTokens(
      _jwtFor('account-b', 'access-b'),
      _jwtFor('account-b', 'refresh-b'),
    );
    protectedGate.complete();

    await expectLater(staleRequest, throwsA(isA<Exception>()));
    expect(http.calls['/api/protected'], 1);
    expect(http.calls['/api/auth/refresh-token'] ?? 0, 0);
  });

  test('late account-A logout cannot clear account-B credentials', () async {
    final api = ApiService();
    await api.clearTokens();
    await api.saveTokens(
      _jwtFor('account-a', 'access-a'),
      _jwtFor('account-a', 'refresh-a'),
    );

    final logoutGate = Completer<void>();
    final logoutStarted = Completer<void>();
    http.routes['/api/auth/logout'] = _Route(
      status: 200,
      body: '{"success":true}',
      gate: logoutGate.future,
      started: logoutStarted,
    );

    final oldLogout = api.logout();
    await logoutStarted.future;

    final newAccess = _jwtFor('account-b', 'access-b');
    final newRefresh = _jwtFor('account-b', 'refresh-b');
    await api.saveTokens(newAccess, newRefresh);
    logoutGate.complete();
    await oldLogout;

    expect(await api.getToken(), newAccess);
    expect(await api.getRefreshToken(), newRefresh);
    expect(await api.getUserId(), 'account-b');
  });

  test('stale users-me future cannot repopulate the profile cache', () async {
    final api = ApiService();
    await api.clearTokens();
    await api.saveTokens(
      _jwtFor('account-a', 'access-a'),
      _jwtFor('account-a', 'refresh-a'),
    );

    final oldGate = Completer<void>();
    final oldStarted = Completer<void>();
    http.routes['/api/users/me'] = _Route(
      status: 200,
      body: '{"success":true,"data":{"id":"account-a"}}',
      gate: oldGate.future,
      started: oldStarted,
    );
    final oldProfile = api.getUserProfile(forceRefresh: true);
    await oldStarted.future;

    await api.saveTokens(
      _jwtFor('account-b', 'access-b'),
      _jwtFor('account-b', 'refresh-b'),
    );
    http.routes['/api/users/me'] = _Route(
      status: 200,
      body: '{"success":true,"data":{"id":"account-b"}}',
    );
    oldGate.complete();

    await expectLater(oldProfile, throwsA(isA<Exception>()));
    final current = await api.getUserProfile();
    expect((current['data'] as Map<String, dynamic>)['id'], 'account-b');
    expect(http.calls['/api/users/me'], 2);

    await api.getUserProfile();
    expect(http.calls['/api/users/me'], 2,
        reason: 'only account B may populate the TTL cache');
  });
}
