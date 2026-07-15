/// Money display formatting.
///
/// `(-remaining).toStringAsFixed(0)` and friends render IEEE negative zero
/// as "-0" (the dashboard showed "Over budget: $-0" when spent == limit).
/// Route every user-visible money string through [formatMoney] so any value
/// that ROUNDS to zero at the chosen precision displays as plain zero.
String formatMoney(num value, {int decimals = 2}) {
  final text = value.toDouble().toStringAsFixed(decimals);
  final zero = (0.0).toStringAsFixed(decimals);
  if (text == '-$zero') {
    return zero;
  }
  return text;
}
