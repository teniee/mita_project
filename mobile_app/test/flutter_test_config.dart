import 'dart:async';
import 'dart:io';

/// Suite-wide guard: a unit or widget test must never open a real socket.
///
/// Flutter runs this wrapper once per test file, before `main()`. It installs
/// an [HttpOverrides] whose client refuses every connection, so a test that
/// reaches for the live MITA backend fails loudly and immediately instead of
/// silently depending on production being up, on network latency, or on
/// whatever data happens to be in the production database that day.
///
/// Tests that need HTTP install their own [HttpOverrides] (or a Dio adapter)
/// in `setUpAll` and thereby replace this guard for their own scope. That is
/// the intended way to opt in: mock the transport, never dial out.
///
/// Live end-to-end coverage belongs in `integration_test/`, which does not
/// load this file and is gated behind `--dart-define=RUN_LIVE_E2E=true`.
Future<void> testExecutable(FutureOr<void> Function() testMain) async {
  HttpOverrides.global = _NoNetworkHttpOverrides();
  await testMain();
}

class _NoNetworkHttpOverrides extends HttpOverrides {
  @override
  HttpClient createHttpClient(SecurityContext? context) =>
      _NoNetworkHttpClient();
}

class BlockedTestNetworkAccess extends Error {
  BlockedTestNetworkAccess(this.method, this.url);

  final String method;
  final Uri url;

  @override
  String toString() =>
      'BlockedTestNetworkAccess: a test tried to $method $url over the real '
      'network.\n'
      'Unit and widget tests must not contact a live host - least of all the '
      'production MITA API.\n'
      'Install an HttpOverrides or a Dio HttpClientAdapter in setUpAll and '
      'serve the response from memory, or move the case to integration_test/.';
}

class _NoNetworkHttpClient implements HttpClient {
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

  Never _block(String method, Uri url) => throw BlockedTestNetworkAccess(
        method,
        url,
      );

  @override
  Future<HttpClientRequest> openUrl(String method, Uri url) =>
      _block(method, url);

  @override
  Future<HttpClientRequest> open(
    String method,
    String host,
    int port,
    String path,
  ) =>
      _block(method, Uri(scheme: 'http', host: host, port: port, path: path));

  @override
  Future<HttpClientRequest> getUrl(Uri url) => _block('GET', url);
  @override
  Future<HttpClientRequest> postUrl(Uri url) => _block('POST', url);
  @override
  Future<HttpClientRequest> putUrl(Uri url) => _block('PUT', url);
  @override
  Future<HttpClientRequest> patchUrl(Uri url) => _block('PATCH', url);
  @override
  Future<HttpClientRequest> deleteUrl(Uri url) => _block('DELETE', url);
  @override
  Future<HttpClientRequest> headUrl(Uri url) => _block('HEAD', url);

  @override
  Future<HttpClientRequest> get(String host, int port, String path) =>
      _block('GET', Uri(scheme: 'http', host: host, port: port, path: path));
  @override
  Future<HttpClientRequest> post(String host, int port, String path) =>
      _block('POST', Uri(scheme: 'http', host: host, port: port, path: path));
  @override
  Future<HttpClientRequest> put(String host, int port, String path) =>
      _block('PUT', Uri(scheme: 'http', host: host, port: port, path: path));
  @override
  Future<HttpClientRequest> patch(String host, int port, String path) =>
      _block('PATCH', Uri(scheme: 'http', host: host, port: port, path: path));
  @override
  Future<HttpClientRequest> delete(String host, int port, String path) =>
      _block('DELETE', Uri(scheme: 'http', host: host, port: port, path: path));
  @override
  Future<HttpClientRequest> head(String host, int port, String path) =>
      _block('HEAD', Uri(scheme: 'http', host: host, port: port, path: path));

  @override
  void close({bool force = false}) {}

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}
