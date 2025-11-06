import 'package:flutter/material.dart';

/// Budget Warning Dialog Widget
/// Shows real-time budget warnings when user tries to exceed budget
/// Part of MITA's core differentiator: preventive overspending protection
class BudgetWarningDialog extends StatelessWidget {
  final String warningLevel; // safe, caution, danger, blocked
  final String category;
  final double amount;
  final double dailyBudget;
  final double remaining;
  final double overage;
  final double percentageUsed;
  final String impactMessage;
  final List<dynamic> alternativeCategories;
  final List<dynamic> suggestions;
  final VoidCallback onProceed;
  final Function(String)? onUseAlternative;

  const BudgetWarningDialog({
    super.key,
    required this.warningLevel,
    required this.category,
    required this.amount,
    required this.dailyBudget,
    required this.remaining,
    required this.overage,
    required this.percentageUsed,
    required this.impactMessage,
    required this.alternativeCategories,
    required this.suggestions,
    required this.onProceed,
    this.onUseAlternative,
  });

  Color _getWarningColor() {
    switch (warningLevel) {
      case 'safe':
        return Colors.green;
      case 'caution':
        return Colors.orange;
      case 'danger':
        return Colors.deepOrange;
      case 'blocked':
        return Colors.red;
      default:
        return Colors.grey;
    }
  }

  IconData _getWarningIcon() {
    switch (warningLevel) {
      case 'safe':
        return Icons.check_circle;
      case 'caution':
        return Icons.warning;
      case 'danger':
        return Icons.error;
      case 'blocked':
        return Icons.block;
      default:
        return Icons.info;
    }
  }

  String _getTitle() {
    switch (warningLevel) {
      case 'safe':
        return 'Budget Check';
      case 'caution':
        return 'Budget Warning';
      case 'danger':
        return 'Budget Alert!';
      case 'blocked':
        return 'Budget Exceeded!';
      default:
        return 'Budget Status';
    }
  }

  @override
  Widget build(BuildContext context) {
    final warningColor = _getWarningColor();

    return Dialog(
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(20),
      ),
      child: Container(
        padding: const EdgeInsets.all(24),
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(20),
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [
              Colors.white,
              warningColor.withOpacity(0.05),
            ],
          ),
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            // Icon and title
            Icon(
              _getWarningIcon(),
              size: 60,
              color: warningColor,
            ),
            const SizedBox(height: 16),
            Text(
              _getTitle(),
              style: TextStyle(
                fontFamily: 'Sora',
                fontSize: 22,
                fontWeight: FontWeight.w700,
                color: warningColor,
              ),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 16),

            // Impact message
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: warningColor.withOpacity(0.1),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: warningColor.withOpacity(0.3)),
              ),
              child: Text(
                impactMessage,
                style: TextStyle(
                  fontFamily: 'Manrope',
                  fontSize: 15,
                  color: warningColor.withOpacity(0.9),
                  fontWeight: FontWeight.w600,
                ),
                textAlign: TextAlign.center,
              ),
            ),
            const SizedBox(height: 20),

            // Budget details
            _buildBudgetBar(context, warningColor),
            const SizedBox(height: 20),

            // Suggestions
            if (suggestions.isNotEmpty) ...[
              Align(
                alignment: Alignment.centerLeft,
                child: Text(
                  'Suggestions:',
                  style: TextStyle(
                    fontFamily: 'Sora',
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                    color: Colors.grey.shade700,
                  ),
                ),
              ),
              const SizedBox(height: 8),
              ...suggestions.take(3).map((suggestion) => Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Icon(Icons.lightbulb_outline, size: 16, color: Colors.amber.shade700),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        suggestion.toString(),
                        style: const TextStyle(
                          fontFamily: 'Manrope',
                          fontSize: 13,
                          color: Colors.black87,
                        ),
                      ),
                    ),
                  ],
                ),
              )),
              const SizedBox(height: 16),
            ],

            // Alternative categories chips
            if (alternativeCategories.isNotEmpty && onUseAlternative != null) ...[
              Align(
                alignment: Alignment.centerLeft,
                child: Text(
                  'Use different category:',
                  style: TextStyle(
                    fontFamily: 'Sora',
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                    color: Colors.grey.shade700,
                  ),
                ),
              ),
              const SizedBox(height: 8),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: alternativeCategories.take(3).map((alt) {
                  final categoryName = alt['category'] ?? '';
                  final available = alt['available'] ?? 0.0;
                  return ActionChip(
                    label: Text(
                      '$categoryName (\$${available.toStringAsFixed(0)} free)',
                      style: const TextStyle(
                        fontFamily: 'Manrope',
                        fontSize: 12,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    backgroundColor: Colors.green.shade50,
                    side: BorderSide(color: Colors.green.shade300),
                    onPressed: () {
                      onUseAlternative!(categoryName); // This will close the dialog and handle category switch
                    },
                  );
                }).toList(),
              ),
              const SizedBox(height: 16),
            ],

            // Action buttons
            Row(
              children: [
                Expanded(
                  child: OutlinedButton(
                    onPressed: () {
                      Navigator.of(context).pop(false); // Return false to indicate cancellation
                    },
                    style: OutlinedButton.styleFrom(
                      padding: const EdgeInsets.symmetric(vertical: 14),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(12),
                      ),
                      side: BorderSide(color: Colors.grey.shade400),
                    ),
                    child: const Text(
                      'Cancel',
                      style: TextStyle(
                        fontFamily: 'Sora',
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: ElevatedButton(
                    onPressed: () {
                      onProceed(); // This will call Navigator.pop(true) from the callback
                    },
                    style: ElevatedButton.styleFrom(
                      padding: const EdgeInsets.symmetric(vertical: 14),
                      backgroundColor: warningLevel == 'blocked'
                          ? Colors.red
                          : const Color(0xFF193C57),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(12),
                      ),
                    ),
                    child: Text(
                      warningLevel == 'blocked' ? 'Proceed Anyway' : 'Continue',
                      style: const TextStyle(
                        fontFamily: 'Sora',
                        fontWeight: FontWeight.w600,
                        color: Colors.white,
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildBudgetBar(BuildContext context, Color warningColor) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(
              'Daily Budget',
              style: TextStyle(
                fontFamily: 'Manrope',
                fontSize: 12,
                color: Colors.grey.shade600,
              ),
            ),
            Text(
              '\$${dailyBudget.toStringAsFixed(2)}',
              style: const TextStyle(
                fontFamily: 'Manrope',
                fontSize: 12,
                fontWeight: FontWeight.w600,
                color: Colors.black87,
              ),
            ),
          ],
        ),
        const SizedBox(height: 8),
        // Progress bar
        ClipRRect(
          borderRadius: BorderRadius.circular(10),
          child: LinearProgressIndicator(
            value: (percentageUsed / 100).clamp(0.0, 1.0),
            minHeight: 12,
            backgroundColor: Colors.grey.shade200,
            valueColor: AlwaysStoppedAnimation<Color>(warningColor),
          ),
        ),
        const SizedBox(height: 8),
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(
              '${percentageUsed.toStringAsFixed(0)}% used',
              style: TextStyle(
                fontFamily: 'Manrope',
                fontSize: 12,
                color: warningColor,
                fontWeight: FontWeight.w600,
              ),
            ),
            Text(
              overage > 0
                  ? 'Over by \$${overage.toStringAsFixed(2)}'
                  : '\$${remaining.toStringAsFixed(2)} left',
              style: TextStyle(
                fontFamily: 'Manrope',
                fontSize: 12,
                color: overage > 0 ? Colors.red : Colors.green,
                fontWeight: FontWeight.w600,
              ),
            ),
          ],
        ),
      ],
    );
  }
}

/// Helper function to show budget warning dialog
Future<bool?> showBudgetWarningDialog({
  required BuildContext context,
  required Map<String, dynamic> affordabilityCheck,
  required VoidCallback onProceed,
  Function(String)? onUseAlternative,
}) {
  return showDialog<bool>(
    context: context,
    barrierDismissible: false,
    builder: (BuildContext context) {
      return BudgetWarningDialog(
        warningLevel: affordabilityCheck['warning_level'] ?? 'caution',
        category: affordabilityCheck['category'] ?? '',
        amount: (affordabilityCheck['amount'] ?? 0.0).toDouble(),
        dailyBudget: (affordabilityCheck['daily_budget'] ?? 0.0).toDouble(),
        remaining: (affordabilityCheck['remaining_budget'] ?? 0.0).toDouble(),
        overage: (affordabilityCheck['overage'] ?? 0.0).toDouble(),
        percentageUsed: (affordabilityCheck['percentage_used'] ?? 0.0).toDouble(),
        impactMessage: affordabilityCheck['impact_message'] ?? '',
        alternativeCategories: affordabilityCheck['alternative_categories'] ?? [],
        suggestions: affordabilityCheck['suggestions'] ?? [],
        onProceed: onProceed,
        onUseAlternative: onUseAlternative,
      );
    },
  );
}
