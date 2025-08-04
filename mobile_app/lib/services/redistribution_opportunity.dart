class RedistributionOpportunity {
  final String fromCategory;
  final String toCategory;
  final double amount;
  final double confidence;

  RedistributionOpportunity({
    required this.fromCategory,
    required this.toCategory,
    required this.amount,
    required this.confidence,
  });
}