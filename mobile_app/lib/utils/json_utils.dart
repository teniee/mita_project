/// Runtime-safe coercion helpers for JSON / API boundary data.
///
/// Backend responses are not guaranteed to keep a stable shape (numbers may
/// arrive as `int`, `double` or `String`; objects may be flat or nested under
/// `data`). These helpers validate the runtime type and normalize the value
/// instead of casting, so a shape change degrades to a fallback value rather
/// than a runtime `TypeError`.
library;

String? asStringOrNull(Object? value) => value is String ? value : null;

String asString(Object? value, {String fallback = ''}) =>
    value is String ? value : fallback;

int? asIntOrNull(Object? value) {
  if (value is int) return value;
  if (value is num) return value.toInt();
  if (value is String) return int.tryParse(value);
  return null;
}

int asInt(Object? value, {int fallback = 0}) => asIntOrNull(value) ?? fallback;

double? asDoubleOrNull(Object? value) {
  if (value is double) return value;
  if (value is num) return value.toDouble();
  if (value is String) return double.tryParse(value);
  return null;
}

double asDouble(Object? value, {double fallback = 0.0}) =>
    asDoubleOrNull(value) ?? fallback;

bool asBool(Object? value, {bool fallback = false}) {
  if (value is bool) return value;
  if (value is num) return value != 0;
  if (value is String) {
    final lower = value.toLowerCase();
    if (lower == 'true' || lower == '1' || lower == 'yes') return true;
    if (lower == 'false' || lower == '0' || lower == 'no') return false;
  }
  return fallback;
}

/// Normalizes any map into a string-keyed map; empty map for non-map input.
Map<String, dynamic> asStringKeyedMap(Object? value) =>
    asStringKeyedMapOrNull(value) ?? <String, dynamic>{};

Map<String, dynamic>? asStringKeyedMapOrNull(Object? value) {
  if (value is Map<String, dynamic>) return value;
  if (value is Map) {
    return value.map((key, dynamic v) => MapEntry(key.toString(), v));
  }
  return null;
}

List<dynamic> asList(Object? value) => value is List ? value : <dynamic>[];

/// Normalizes a JSON array of objects into `List<Map<String, dynamic>>`,
/// dropping entries that are not maps.
List<Map<String, dynamic>> asMapList(Object? value) {
  if (value is! List) return <Map<String, dynamic>>[];
  return [
    for (final entry in value)
      if (entry is Map) asStringKeyedMap(entry),
  ];
}

List<String> asStringList(Object? value) {
  if (value is! List) return <String>[];
  return [
    for (final entry in value)
      if (entry is String) entry else if (entry != null) entry.toString(),
  ];
}

DateTime? asDateTimeOrNull(Object? value) {
  if (value is DateTime) return value;
  if (value is String) return DateTime.tryParse(value);
  return null;
}
