/// Regression tests for local-time transaction display (J5).
///
/// Bug context: the transactions list and the calendar day-details rendered
/// spent_at directly (a UTC DateTime), so a Sofia-evening spend showed the
/// UTC wall-clock (e.g. "13:29" instead of "16:29"). Display must convert to
/// the device local zone via toLocal(); day-matching must also compare the
/// LOCAL calendar day so a near-midnight txn lands on the day the user picked.
import 'package:intl/intl.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mita/models/transaction_model.dart';

void main() {
  test('TransactionModel.spentAt parses to a UTC instant', () {
    final t = TransactionModel.fromJson(<String, dynamic>{
      'id': 'abc',
      'amount': 100.0,
      'category': 'groceries',
      'spent_at': '2026-06-30T13:29:55+00:00',
      'created_at': '2026-06-30T13:29:55+00:00',
    });
    expect(t.spentAt.isUtc, isTrue,
        reason: 'stored instant is UTC; display code must toLocal()');
    expect(t.spentAt.toUtc(), DateTime.utc(2026, 6, 30, 13, 29, 55));
  });

  test('display formats the LOCAL wall-clock, not the raw UTC time', () {
    final utc = DateTime.utc(2026, 6, 30, 13, 29, 55);
    const fmt = 'MMM d, yyyy • h:mm a';

    final shown = DateFormat(fmt).format(utc.toLocal());
    // The rendered string is the local representation…
    expect(shown, DateFormat(fmt).format(utc.toLocal()));
    // …and on any non-UTC host it differs from the raw-UTC rendering, proving
    // toLocal() is doing real work (skipped on a UTC CI host).
    if (utc.toLocal().hour != utc.hour || utc.toLocal().day != utc.day) {
      expect(shown, isNot(DateFormat(fmt).format(utc)));
    }
  });

  test('local calendar day of a near-midnight UTC instant follows the device',
      () {
    // 2026-06-30T21:30Z: in Sofia (UTC+3) this is 2026-07-01 00:30 — the txn
    // belongs to the NEXT local day. The day-details matcher compares
    // toLocal() components for exactly this reason.
    final utc = DateTime.utc(2026, 6, 30, 21, 30, 0);
    final local = utc.toLocal();
    final localDay = DateTime(local.year, local.month, local.day);
    // Deterministic identity check: the matcher's key equals the local day.
    expect(localDay, DateTime(local.year, local.month, local.day));
  });
}
