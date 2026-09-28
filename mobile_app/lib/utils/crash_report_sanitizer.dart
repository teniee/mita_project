/// What one error-level log entry is allowed to tell Crashlytics.
///
/// `LoggingService._sendToCrashlytics` used to copy every `extra` entry into a
/// Crashlytics custom key with `value.toString()`. The PII mask it relied on
/// only rewrote *String* values, so numbers went out untouched and a nested
/// Map was stringified whole. With Firebase configured (the intended release
/// build — it is what enables push), tapping "Save Expense" while offline
/// sent `extra_amount = 42.17` and `extra_category = Food & Dining` off the
/// device; `expense_state_service` sent the whole expense map, and the Dio
/// interceptor sent every error response body as `extra_errorData` (a
/// transaction over the cap echoes `provided_amount`).
///
/// The rule now: structured context is ALLOW-LISTED — only keys that describe
/// the failure (status code, operation, counts, flags) leave the device, and
/// only as `bool`, `int` or scrubbed `String`. A `double`, a Map, a List or any
/// other object is dropped even under an allowed key, because none of the
/// allowed keys should ever carry one. Free text that cannot be allow-listed
/// (the message, the exception string, allowed String values) is scrubbed of
/// money-like numbers, sensitive key/value pairs, URL query strings, e-mail
/// addresses and tokens. No user identifier is ever attached.
///
/// Lives here, not inside `LoggingService`, so the rule is testable without a
/// Firebase app.
library;

/// Crashlytics custom-key values are capped at 1 KB.
const int kCrashTextLimit = 1000;

/// `extra` keys that describe a failure rather than the user's data.
///
/// Adding a key here is a privacy decision: it must never hold an amount,
/// merchant, description, note, category, e-mail, name, id of a person, token
/// or a request/response body.
const Set<String> kCrashSafeExtraKeys = {
  'statusCode',
  'status_code',
  'operation',
  'operation_id',
  'error_type',
  'errorMessage',
  'final_error',
  'severity',
  'has_retry',
  'attempt',
  'total_attempts',
  'remaining_attempts',
  'max_timeout_seconds',
  'active_operations',
  'reason',
  'type',
  'detail',
  'instance',
  'url',
  'endpoint',
  'method',
  'screen',
  'stackTrace',
};

/// The sanitized form of one log entry, ready for Crashlytics.
class CrashReport {
  const CrashReport({
    required this.customKeys,
    required this.reason,
    this.exception,
  });

  /// Custom keys to set. Values are only `String`, `int` or `bool`.
  final Map<String, Object> customKeys;

  /// `"<tag>: <message>"`, scrubbed.
  final String reason;

  /// The error's text, scrubbed; null when the entry had no error.
  final String? exception;
}

/// Builds what Crashlytics may receive for one entry.
CrashReport buildCrashReport({
  required String? tag,
  required String level,
  required String message,
  Map<String, dynamic>? extra,
  Object? error,
  DateTime? timestamp,
}) {
  final keys = <String, Object>{
    'log_tag': tag ?? 'UNKNOWN',
    'log_level': level.toUpperCase(),
    'timestamp': (timestamp ?? DateTime.now()).toIso8601String(),
  };

  var redacted = 0;
  extra?.forEach((key, value) {
    if (value == null) return;
    final safe =
        kCrashSafeExtraKeys.contains(key) ? _safeValue(key, value) : null;
    if (safe == null) {
      redacted++;
    } else {
      keys['extra_$key'] = safe;
    }
  });
  if (redacted > 0) keys['extra_redacted_count'] = redacted;

  return CrashReport(
    customKeys: keys,
    reason: scrubCrashText('${tag ?? 'UNKNOWN'}: $message'),
    exception: error == null ? null : scrubCrashText(error.toString()),
  );
}

Object? _safeValue(String key, Object? value) {
  if (value is bool) return value;
  // A double under an allowed key is a bug at the call site, not a count.
  if (value is int) return value;
  if (value is String) {
    return key == 'url' || key == 'endpoint'
        ? scrubCrashText(_pathOnly(value))
        : scrubCrashText(value);
  }
  return null;
}

String _pathOnly(String url) {
  final uri = Uri.tryParse(url);
  if (uri == null) return url;
  return uri.path.isEmpty ? '/' : uri.path;
}

// Values of these keys are the user's data wherever they appear in a JSON
// body or a Dart `Map.toString()` dump (`provided_amount`, `daily_budget`,
// `merchant_name`, ...).
const String _sensitiveKey =
    r'[A-Za-z_]*(?:amount|income|salary|balance|budget|spent|spending|total|'
    r'price|cost|saving|limit|value|merchant|description|note|category|'
    r'email|name|title|phone|address|token|password)[A-Za-z_]*';

final RegExp _jsonPair = RegExp(
  '"($_sensitiveKey)"\\s*:\\s*("(?:[^"\\\\]|\\\\.)*"|[^,}\\]\\s]+)',
  caseSensitive: false,
);
final RegExp _dartMapPair = RegExp(
  '\\b($_sensitiveKey):\\s*([^,}\\]]+)',
  caseSensitive: false,
);
final RegExp _email = RegExp(
  r'[A-Za-z0-9._%+*-]*[A-Za-z0-9*]@[A-Za-z0-9.-]+\.[A-Za-z]{2,}',
);
final RegExp _bearer = RegExp(r'Bearer\s+\S+', caseSensitive: false);
// JWTs, and long random strings (refresh tokens, API keys, UUIDs). The digit
// look-ahead keeps long Dart class names in stack traces readable.
final RegExp _token = RegExp(
  r'eyJ[A-Za-z0-9_-]*\.[A-Za-z0-9_-]*\.[A-Za-z0-9_-]*'
  r'|\b(?=[A-Za-z0-9_-]*\d)[A-Za-z0-9_-]{32,}\b',
);
// A query string after a URL or path (`?search=...&month=...`); a bare "?"
// in prose is left alone.
final RegExp _query = RegExp(r'''(?<=[A-Za-z0-9/_.-])\?[^\s"']+''');
final RegExp _currency = RegExp(r'[$€£¥₹₽]\s?\d[\d,]*(?:\.\d+)?');
final RegExp _decimal = RegExp(r'\b\d+[.,]\d+\b');
final RegExp _grouped = RegExp(r'\b\d{1,3}(?:,\d{3})+\b');
final RegExp _longInt = RegExp(r'\b\d{4,}\b');

/// Scrubs free text before it leaves the device.
///
/// Keeps what diagnoses a failure — words, HTTP status codes, small counts,
/// paths — and removes amounts, sensitive key/value pairs, query strings,
/// e-mail addresses and tokens. Order matters: pairs first so a quoted value
/// is removed whole, numbers last so they cannot split a token.
String scrubCrashText(String text) {
  var out = text
      .replaceAllMapped(_jsonPair, (m) => '"${m[1]}":"<redacted>"')
      .replaceAllMapped(_dartMapPair, (m) => '${m[1]}: <redacted>')
      .replaceAll(_email, '<email>')
      .replaceAll(_bearer, 'Bearer <redacted>')
      .replaceAll(_token, '<redacted>')
      .replaceAll(_query, '')
      .replaceAll(_currency, '<amount>')
      .replaceAll(_grouped, '<number>')
      .replaceAll(_decimal, '<number>')
      .replaceAll(_longInt, '<number>');
  if (out.length > kCrashTextLimit) {
    out = '${out.substring(0, kCrashTextLimit)}…';
  }
  return out;
}
