/// Tests for deviceTimezone() (J3): registration/onboarding must send the
/// device's real IANA zone so the backend buckets DailyPlan/calendar days by
/// the user's local date instead of the old hard-coded "UTC".
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mita/utils/device_timezone.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  const channel = MethodChannel('flutter_timezone');
  final messenger =
      TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger;

  tearDown(() {
    messenger.setMockMethodCallHandler(channel, null);
  });

  test('returns the device IANA timezone from the platform', () async {
    messenger.setMockMethodCallHandler(channel, (call) async {
      if (call.method == 'getLocalTimezone') return 'Europe/Sofia';
      return null;
    });

    expect(await deviceTimezone(), 'Europe/Sofia');
  });

  test('falls back to UTC when the platform call throws', () async {
    messenger.setMockMethodCallHandler(channel, (call) async {
      throw PlatformException(code: 'UNAVAILABLE');
    });

    expect(await deviceTimezone(), 'UTC');
  });

  test('falls back to UTC on an empty platform response', () async {
    messenger.setMockMethodCallHandler(channel, (call) async => '');
    expect(await deviceTimezone(), 'UTC');
  });
}
