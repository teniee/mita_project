/// Regression tests for the saved-calendar fallback decision (Fix B).
///
/// Bug context (session-6 device journey): after deleting the only June
/// transaction and refreshing, the June calendar re-rendered as a full
/// generated shell preview ($5379 / 31 days) instead of the saved 1-day data.
/// Root cause: loadCalendarData replaced real saved data with the shell
/// preview whenever the saved response came back empty — including the
/// transient empty right after a mutation, and cross-month reload races.
///
/// Invariant under test (calendarLoadAction):
///   - a non-empty saved response is always used (source of truth);
///   - an empty response for the SAME month we already hold saved data for is
///     ignored (keep saved) — a transient blip must not downgrade to shell;
///   - an empty response for a different month (or with no saved data yet)
///     falls back to the shell preview.
import 'package:flutter_test/flutter_test.dart';
import 'package:mita/providers/budget_provider.dart';

void main() {
  group('calendarLoadAction', () {
    test('non-empty saved response is always used as source of truth', () {
      expect(
        calendarLoadAction(
            savedIsEmpty: false, hasSavedData: false, sameMonth: false),
        CalendarLoadAction.useSaved,
      );
      // Even if we already had saved data for the same month, fresh saved wins.
      expect(
        calendarLoadAction(
            savedIsEmpty: false, hasSavedData: true, sameMonth: true),
        CalendarLoadAction.useSaved,
      );
    });

    test('empty response for the SAME month keeps existing saved data', () {
      // This is the post-delete case: June saved data is present, a refresh
      // momentarily returns empty — must NOT swap in the shell preview.
      expect(
        calendarLoadAction(
            savedIsEmpty: true, hasSavedData: true, sameMonth: true),
        CalendarLoadAction.keepExisting,
      );
    });

    test('empty response for a DIFFERENT month falls back to shell', () {
      // Navigating from a month with data to a month that has none should show
      // that month's (empty) shell preview, not the previous month's data.
      expect(
        calendarLoadAction(
            savedIsEmpty: true, hasSavedData: true, sameMonth: false),
        CalendarLoadAction.useShell,
      );
    });

    test('empty response with no saved data yet uses shell', () {
      expect(
        calendarLoadAction(
            savedIsEmpty: true, hasSavedData: false, sameMonth: false),
        CalendarLoadAction.useShell,
      );
      expect(
        calendarLoadAction(
            savedIsEmpty: true, hasSavedData: false, sameMonth: true),
        CalendarLoadAction.useShell,
      );
    });
  });
}
