/// True only when the API actually returned peers to compare against.
///
/// `/api/cohort/peer_comparison` is explicit when it cannot compare: it sends
/// `peer_count: 0`, `comparison: "insufficient_peer_data"` and null averages.
/// Widgets used to paper over that with `?? 0.0`, `?? 50` or
/// `userAmount * 1.15`, so a first-day user was shown a peer average, a
/// percentile and a verdict derived from a cohort of nobody.
///
/// When it CAN compare, the only peer statistic it publishes is `peer_median`
/// (rounded to $100). `peer_average` and `percentile` are always null — a
/// mean and a rank both let a caller work out individual members' spending —
/// and `peer_count` is a floor ("at least 10"), not a cohort size. So the
/// median is what this checks for; a payload carrying only a mean is not the
/// contract and gets no comparison.
///
/// Lives here rather than in the widget layer so services can apply the same
/// test without importing Flutter. `peer_comparison_widgets.dart` re-exports
/// it, so existing widget-side imports keep working.
bool hasSufficientPeerData(Map<String, dynamic>? peerData) {
  if (peerData == null) return false;
  if (peerData['comparison'] == 'insufficient_peer_data') return false;
  final count = peerData['peer_count'];
  if (count is num && count <= 0) return false;
  return peerData['peer_median'] is num;
}
