import 'package:flutter_timezone/flutter_timezone.dart';

import '../services/logging_service.dart';

/// Best-effort IANA timezone of the device (e.g. "Europe/Sofia").
///
/// The backend buckets DailyPlan/calendar days and computes "today" per the
/// user's stored timezone, so registration and onboarding must send the real
/// device zone — not the previous hard-coded "UTC", which pushed every
/// non-UTC user's spend onto the wrong calendar day.
Future<String> deviceTimezone() async {
  try {
    final tz = await FlutterTimezone.getLocalTimezone();
    if (tz.isNotEmpty) return tz;
  } catch (e) {
    logWarning('Failed to read device timezone, defaulting to UTC: $e',
        tag: 'DEVICE_TZ');
  }
  return 'UTC';
}
