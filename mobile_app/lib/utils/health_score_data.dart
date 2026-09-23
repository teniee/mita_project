/// A Financial Health Score is a measurement, or it is nothing.
///
/// `/api/ai/financial-health-score` used to answer an account with no
/// transactions at all with the income tier's *expectation* threshold — 70
/// plus a tier bonus — as that person's score: $9,000/month got
/// `score: 73, grade: "C"` with the same number copied into four components
/// and a "stable" trend. Nothing had measured any of it.
///
/// The endpoint now sends `score: null`, `grade: null`, `components: {}`,
/// `trend: null` and `status: "insufficient_data"` until there is real
/// spending to score, and the same nulls (with an `error`) when the analysis
/// fails. Both mean the screen has no assessment to show.
///
/// Lives here, not in the screen, so the rule is testable and so a later
/// `?? 75` cannot quietly put a grade back on the card — that default is
/// exactly what this replaced.
bool hasFinancialHealthScore(Map<String, dynamic>? healthData) {
  if (healthData == null) return false;
  // An explicit verdict from the server wins over any figure beside it.
  if (healthData['status'] == 'insufficient_data') return false;
  return healthData['score'] != null && healthData['grade'] != null;
}
