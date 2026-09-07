/// True only when the API actually returned peers to compare against.
///
/// `/api/cohort/peer_comparison` is explicit when it cannot compare: it sends
/// `peer_count: 0`, `comparison: "insufficient_peer_data"` and null averages.
/// Widgets used to paper over that with `?? 0.0`, `?? 50` or
/// `userAmount * 1.15`, so a first-day user was shown a peer average, a
/// percentile and a verdict derived from a cohort of nobody.
///
/// Lives here rather than in the widget layer so services can apply the same
/// test without importing Flutter. `peer_comparison_widgets.dart` re-exports
/// it, so existing widget-side imports keep working.
bool hasSufficientPeerData(Map<String, dynamic>? peerData) {
  if (peerData == null) return false;
  if (peerData['comparison'] == 'insufficient_peer_data') return false;
  final count = peerData['peer_count'];
  if (count is num && count <= 0) return false;
  return peerData['peer_average'] != null;
}
