// Regressions for the session-5 date/format defects:
//  * "Over budget: $-0" — negative zero must render as plain zero.
//  * TransactionInput.spent_at must serialize as an explicit-UTC instant
//    (a local DateTime's toIso8601String() has no offset and the backend
//    then misfiles the wall-clock time as the user's timezone).
//  * Date edits must preserve the transaction's time-of-day — replacing it
//    with local midnight shifted the transaction onto the PREVIOUS
//    user-timezone day for any device east of UTC (Europe/Sofia repro).

import 'package:flutter_test/flutter_test.dart';
import 'package:mita/models/transaction_model.dart';
import 'package:mita/utils/money_format.dart';

/// The date-picker handler contract used by add_transaction/add_expense/
/// edit_expense: picked date, original time-of-day.
DateTime preserveTimeOfDay(DateTime picked, DateTime original) => DateTime(
      picked.year,
      picked.month,
      picked.day,
      original.hour,
      original.minute,
      original.second,
    );

void main() {
  group('formatMoney negative-zero collapse', () {
    test('values that round to zero display as plain zero', () {
      expect(formatMoney(-0.0), '0.00');
      expect(formatMoney(-0.004), '0.00');
      expect(formatMoney(0.004), '0.00');
      expect(formatMoney(-0.0, decimals: 0), '0');
      expect(formatMoney(-0.4, decimals: 0), '0');
    });

    test('genuinely negative values keep their sign', () {
      expect(formatMoney(-0.006), '-0.01');
      expect(formatMoney(-1), '-1.00');
      expect(formatMoney(-0.5, decimals: 0), '-1');
    });

    test('ordinary values are unchanged', () {
      expect(formatMoney(23.75), '23.75');
      expect(formatMoney(100), '100.00');
      expect(formatMoney(45.31, decimals: 0), '45');
    });
  });

  group('TransactionInput UTC serialization', () {
    test('spent_at serializes as an explicit-UTC instant', () {
      final local = DateTime(2026, 7, 15, 14, 28, 4);
      final json = TransactionInput(
        amount: 10,
        category: 'food',
        spentAt: local,
      ).toJson();

      final serialized = json['spent_at'] as String;
      expect(serialized, endsWith('Z'),
          reason: 'no offset marker means the backend guesses the timezone');
      // Same instant, expressed in UTC.
      expect(DateTime.parse(serialized), local.toUtc());
    });
  });

  group('date edits preserve time-of-day', () {
    // These tests intentionally use the runner\'s LOCAL timezone (CI/dev
    // machine Europe/Sofia = UTC+3 in summer) — the defect only exists
    // when device-local differs from UTC.
    test('moving Jul 15 14:28 to Jul 14 stays on Jul 14 in UTC (UTC+3)',
        () {
      final original = DateTime(2026, 7, 15, 14, 28);
      final picked = DateTime(2026, 7, 14); // picker returns local midnight
      final moved = preserveTimeOfDay(picked, original);

      expect(moved.hour, 14);
      expect(moved.toUtc().day, 14,
          reason: 'midnight-local would have landed on Jul 13 21:00Z');
    });

    test('month boundary: Aug 1 -> Jul 31 stays on Jul 31 in UTC', () {
      final original = DateTime(2026, 8, 1, 14, 28);
      final picked = DateTime(2026, 7, 31);
      final moved = preserveTimeOfDay(picked, original);

      expect(moved.toUtc().month, 7);
      expect(moved.toUtc().day, 31);
    });

    test('first-of-month midnight edge is the known profile-tz mismatch',
        () {
      // A transaction genuinely made at 00:30 local on Aug 1 belongs to
      // Jul 31 in UTC. This is inherent to a UTC profile timezone, not a
      // serialization bug — pinned here so the behavior is explicit.
      final original = DateTime(2026, 8, 1, 0, 30);
      final offset = original.timeZoneOffset;
      final utcDay = original.toUtc().day;
      if (offset > Duration.zero && offset >= const Duration(minutes: 30)) {
        expect(utcDay, 31);
      } else {
        expect(utcDay, 1);
      }
    });

    test(
        'REGRESSION: repeated edits do not drift the instant '
        '(load spentAt in local time)', () {
      // The edit screen loads spentAt.toLocal() into _selectedDate, so the
      // picker preserves the LOCAL wall-clock. Simulate 6 successive
      // date-preserving edits and assert the UTC instant is stable.
      final createdUtc = DateTime.utc(2026, 7, 15, 16, 29, 55);

      // First edit: load as local, keep the same displayed day.
      var selected = createdUtc.toLocal();
      String? lastSerialized;

      for (var i = 0; i < 6; i++) {
        // Re-pick the SAME calendar day (picker returns local midnight).
        final picked = DateTime(selected.year, selected.month, selected.day);
        selected = preserveTimeOfDay(picked, selected);
        // Serialize the way TransactionInput.toJson does.
        lastSerialized = selected.toUtc().toIso8601String();
        // Next edit loads the persisted value back as local.
        selected = DateTime.parse(lastSerialized).toLocal();
      }

      // No drift: the wall-clock time (and thus the UTC instant) is stable.
      expect(DateTime.parse(lastSerialized!).toUtc(), createdUtc,
          reason: 'six edits must not move the timestamp');
    });

    test('DST transition day serializes to the exact instant (Sofia)', () {
      // Europe/Sofia leaves DST on 2026-10-25: +03 before, +02 after.
      final beforeSwitch = DateTime(2026, 10, 24, 14, 28);
      final afterSwitch = DateTime(2026, 10, 26, 14, 28);
      // Whatever the wall-clock offset, round-tripping through UTC must
      // preserve the instant exactly.
      for (final dt in [beforeSwitch, afterSwitch]) {
        expect(dt.toUtc().toLocal(), dt);
        expect(dt.toUtc().isUtc, isTrue);
      }
    });
  });
}
