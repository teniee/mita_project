// Regression for the "Get User Profile for Calendar ~18s" P2
// (docs/end-to-end-test-matrix.md, C-bis): /users/me was requested
// independently by the dashboard, calendar, budget engines and
// live-updates during one screen load. ApiService.getUserProfile() must
// collapse concurrent callers into ONE network request and serve immediate
// repeats from a short-TTL cache; token changes and profile updates drop
// the cache.

import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mita/services/api_service.dart';
import 'package:shared_preferences/shared_preferences.dart';

const _profileJson =
    '{"success": true, "data": {"id": "u1", "email": "dedupe@mita.app", '
    '"income": 6000.0, "location": "US"}}';

class _CountingHttpOverrides extends HttpOverrides {
  int userMeGets = 0;

  @override
  HttpClient createHttpClient(SecurityContext? context) =>
      _FakeHttpClient(this);
}

class _FakeHttpClient implements HttpClient {
  _FakeHttpClient(this.overrides);

  final _CountingHttpOverrides overrides;

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
  Future<HttpClientRequest> openUrl(String method, Uri url) async {
    if (method.toUpperCase() == 'GET' && url.path.endsWith('/users/me')) {
      overrides.userMeGets++;
    }
    return _FakeHttpClientRequest(method, url);
  }

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

class _FakeHttpClientRequest implements HttpClientRequest {
  _FakeHttpClientRequest(this.method, this.uri);

  @override
  final String method;

  @override
  final Uri uri;

  @override
  final HttpHeaders headers = _FakeHttpHeaders();

  final _body = BytesBuilder();

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
  void add(List<int> data) => _body.add(data);

  @override
  Future addStream(Stream<List<int>> stream) async {
    await for (final chunk in stream) {
      _body.add(chunk);
    }
  }

  @override
  void write(Object? object) => add(utf8.encode(object.toString()));

  @override
  Future<HttpClientResponse> close() async =>
      _FakeHttpClientResponse(_profileJson);

  @override
  Future<HttpClientResponse> get done => close();

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

class _FakeHttpClientResponse extends Stream<List<int>>
    implements HttpClientResponse {
  _FakeHttpClientResponse(String body) : _bytes = utf8.encode(body);

  final List<int> _bytes;

  @override
  int get statusCode => 200;

  @override
  String get reasonPhrase => 'OK';

  @override
  int get contentLength => _bytes.length;

  @override
  HttpClientResponseCompressionState get compressionState =>
      HttpClientResponseCompressionState.notCompressed;

  @override
  HttpHeaders get headers =>
      _FakeHttpHeaders()..set('content-type', 'application/json');

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

class _FakeHttpHeaders implements HttpHeaders {
  final Map<String, List<String>> _headers = {};

  @override
  void set(String name, Object value, {bool preserveHeaderCase = false}) {
    _headers[name.toLowerCase()] = ['$value'];
  }

  @override
  void add(String name, Object value, {bool preserveHeaderCase = false}) {
    _headers.putIfAbsent(name.toLowerCase(), () => []).add('$value');
  }

  @override
  List<String>? operator [](String name) => _headers[name.toLowerCase()];

  @override
  String? value(String name) => _headers[name.toLowerCase()]?.join(', ');

  @override
  void remove(String name, Object value) =>
      _headers[name.toLowerCase()]?.remove('$value');

  @override
  void removeAll(String name) => _headers.remove(name.toLowerCase());

  @override
  void forEach(void Function(String name, List<String> values) action) {
    _headers.forEach(action);
  }

  @override
  void clear() => _headers.clear();

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  // ONE overrides instance for the whole file: ApiService is a singleton and
  // its Dio adapter creates the underlying HttpClient once — under whichever
  // overrides are active at first use. Per-test instances would count only
  // the first test's requests.
  final overrides = _CountingHttpOverrides();

  setUp(() {
    overrides.userMeGets = 0;
    HttpOverrides.global = overrides;
    SharedPreferences.setMockInitialValues(<String, Object>{});

    // In-memory secure storage so getToken() works without a device.
    final Map<String, String> secureStore = {};
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(
            const MethodChannel('plugins.it_nomads.com/flutter_secure_storage'),
            (call) async {
      final args = (call.arguments as Map?) ?? const {};
      switch (call.method) {
        case 'write':
          secureStore[args['key'] as String] = args['value'] as String;
          return null;
        case 'read':
          return secureStore[args['key'] as String];
        case 'readAll':
          return Map<String, String>.from(secureStore);
        case 'delete':
          secureStore.remove(args['key'] as String);
          return null;
        case 'deleteAll':
          secureStore.clear();
          return null;
        case 'containsKey':
          return secureStore.containsKey(args['key'] as String);
        default:
          return null;
      }
    });
  });

  tearDown(() {
    HttpOverrides.global = null;
  });

  test('concurrent getUserProfile calls share one network request', () async {
    final api = ApiService();
    await api.clearTokens(); // also resets the profile cache

    final results = await Future.wait(
      List.generate(6, (_) => api.getUserProfile()),
    );

    expect(overrides.userMeGets, 1,
        reason: 'six concurrent callers must share a single /users/me GET');
    for (final profile in results) {
      expect(profile['data']?['income'], 6000.0);
    }

    // An immediate repeat is served from the TTL cache — still one request.
    final again = await api.getUserProfile();
    expect(again['data']?['income'], 6000.0);
    expect(overrides.userMeGets, 1);
  });

  test('forceRefresh bypasses the cache', () async {
    final api = ApiService();
    await api.clearTokens();

    await api.getUserProfile();
    await api.getUserProfile(forceRefresh: true);

    expect(overrides.userMeGets, 2);
  });

  test('token changes drop the cached profile', () async {
    final api = ApiService();
    await api.clearTokens();

    await api.getUserProfile();
    expect(overrides.userMeGets, 1);

    // A new session may belong to a different user.
    await api.saveTokens('new-access-token', 'new-refresh-token');
    await api.getUserProfile();
    expect(overrides.userMeGets, 2);
  });
}
