// Regression guard: the shipped Android app must not request device location.
//
// FINE location was dropped in TASK-16, but COARSE location remained and
// surfaced an unwanted "approximate location" prompt during onboarding. The
// only consumer (onboarding US-state auto-detect) has a full manual fallback,
// and requesting location in a finance app is a Play Data-safety / review risk.
// Both permissions — and geolocator's foreground-service-location component,
// which are merged in from the plugin manifest — are now stripped with
// tools:node="remove".
//
// This test fails if a bare (granted) location permission or the
// foreground-location service reappears in the app manifest, whether hand-added
// or by dropping the tools:node="remove" guard.

import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

void main() {
  final manifest =
      File('android/app/src/main/AndroidManifest.xml').readAsStringSync();

  // Collapse whitespace so multi-line <uses-permission .../> blocks match.
  final flat = manifest.replaceAll(RegExp(r'\s+'), ' ');

  Match? permissionBlock(String name) => RegExp(
        '<uses-permission[^>]*android:name="android.permission.$name"[^>]*/>',
      ).firstMatch(flat);

  group('Android manifest never grants location', () {
    for (final perm in ['ACCESS_FINE_LOCATION', 'ACCESS_COARSE_LOCATION']) {
      test('$perm is not granted', () {
        final block = permissionBlock(perm);
        // Absent entirely is fine. If declared, it must be a removal directive.
        if (block != null) {
          expect(
            block.group(0),
            contains('tools:node="remove"'),
            reason: '$perm must carry tools:node="remove" — a finance app must '
                'not request device location, and the geolocator plugin '
                'manifest re-adds it on merge unless explicitly stripped.',
          );
        }
      });
    }

    test('geolocator foreground-location service is stripped', () {
      final svc = RegExp(
        '<service[^>]*android:name="com.baseflow.geolocator.'
        'GeolocatorLocationService"[^>]*>',
      ).firstMatch(flat);
      if (svc != null) {
        expect(
          svc.group(0),
          contains('tools:node="remove"'),
          reason: 'A shipped foregroundServiceType="location" service triggers '
              'a Play foreground-location review form; it must stay removed.',
        );
      }
    });
  });
}
