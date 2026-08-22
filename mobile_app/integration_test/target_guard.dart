/// Fail-closed target guard for live end-to-end tests.
///
/// These suites register accounts and write financial data through the real
/// backend. Production accumulated 78+ synthetic accounts and irreversible
/// daily_plan drift because automated suites could reach the live host, so a
/// live run must name a disposable target explicitly and production is refused
/// outright. Kept in step with `scripts/_target_guard.py` — add new aliases to
/// both.
library;

/// Exact production hostnames. Matched on the parsed host, not by substring:
/// `contains()` both over-matches (a staging host containing the string) and
/// under-matches (an alias that does not).
const Set<String> kProductionHosts = {
  'mita-production-production.up.railway.app',
  'mita-production.up.railway.app',
  'mitafinance.com',
  'www.mitafinance.com',
  'api.mitafinance.com',
};

/// `--dart-define=E2E_BASE_URL=...`. Deliberately has no default.
const String kE2eBaseUrl = String.fromEnvironment('E2E_BASE_URL');

String? _hostOf(String url) {
  final trimmed = url.trim();
  if (trimmed.isEmpty) return null;
  final uri = Uri.tryParse(trimmed);
  if (uri == null) return null;
  if (uri.scheme != 'http' && uri.scheme != 'https') return null;
  if (uri.host.isEmpty) return null;
  return uri.host.replaceAll(RegExp(r'\.$'), '').toLowerCase();
}

/// True when [url] names a known production host.
bool isProductionTarget(String url) {
  final host = _hostOf(url);
  return host != null && kProductionHosts.contains(host);
}

/// True only when E2E_BASE_URL is set, parseable, and not production.
bool get e2eTargetIsSafe {
  final host = _hostOf(kE2eBaseUrl);
  return host != null && !kProductionHosts.contains(host);
}

/// Why the current target was refused. Empty when the target is safe.
String get e2eTargetProblem {
  if (kE2eBaseUrl.trim().isEmpty) {
    return 'E2E_BASE_URL is not set — refusing to fall back to production. '
        'Pass --dart-define=E2E_BASE_URL=https://<disposable-host>';
  }
  final host = _hostOf(kE2eBaseUrl);
  if (host == null) {
    return 'E2E_BASE_URL is not a usable http(s) URL: "$kE2eBaseUrl"';
  }
  if (kProductionHosts.contains(host)) {
    return 'E2E_BASE_URL points at production ($host) — refused. '
        'This suite registers accounts and writes financial data. '
        'There is no override by design.';
  }
  return '';
}
