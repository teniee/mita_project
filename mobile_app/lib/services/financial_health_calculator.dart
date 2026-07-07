import 'dart:math' as math;

/// Standard personal-finance health metrics.
///
/// Pure, synchronous arithmetic — safe to call from budget screens and
/// insights without awaiting network. All ratios clamp to sane ranges so
/// degenerate input (zero income, negative balances) can never produce
/// NaN/Infinity in the UI.
class FinancialHealthCalculator {
  /// Budget health score in [0, 1]: how sustainably expenses fit income.
  ///
  /// 1.0 = spending well under income; 0.0 = spending at/over income with
  /// no margin. Uses the spending ratio with a soft knee at the common
  /// 50/30/20 guidance (spending <= 80% of income scores >= 0.5).
  double calculateBudgetHealthByIncome(double income, double expenses) {
    if (income <= 0) return 0.0;
    final spendRatio = (expenses / income).clamp(0.0, 2.0);
    // <=0.5 → excellent (1.0..0.9), 0.5..0.8 → good (0.9..0.5),
    // 0.8..1.0 → strained (0.5..0.1), >1.0 → failing (0.1..0.0).
    if (spendRatio <= 0.5) {
      return 1.0 - spendRatio * 0.2;
    } else if (spendRatio <= 0.8) {
      return 0.9 - (spendRatio - 0.5) * (0.4 / 0.3);
    } else if (spendRatio <= 1.0) {
      return 0.5 - (spendRatio - 0.8) * 2.0;
    }
    return math.max(0.0, 0.1 - (spendRatio - 1.0) * 0.1);
  }

  /// Savings rate = savings / income, clamped to [0, 1]. 0 when income <= 0.
  double calculateSavingsRate(double income, double savings) {
    if (income <= 0) return 0.0;
    return (savings / income).clamp(0.0, 1.0);
  }

  /// Debt-to-income ratio (monthly debt payments / monthly income).
  /// Returns 0 for non-positive income and never goes negative.
  double calculateDebtToIncomeRatio(double debt, double income) {
    if (income <= 0) return 0.0;
    return math.max(0.0, debt / income);
  }

  /// How many months of expenses the emergency fund covers.
  /// Returns 0 for non-positive expenses/savings.
  double calculateEmergencyFundMonths(double savings, double monthlyExpenses) {
    if (monthlyExpenses <= 0 || savings <= 0) return 0.0;
    return savings / monthlyExpenses;
  }
}
