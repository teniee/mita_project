import 'package:flutter/material.dart';
import '../services/localization_service.dart';
import '../l10n/generated/app_localizations.dart';

/// Comprehensive financial formatting utilities for MITA app
/// Provides locale-aware formatting for all financial UI components
class FinancialFormatters {
  static LocalizationService get _localizationService => LocalizationService.instance;

  /// Format currency amount for display in UI components
  ///
  /// Uses the current app locale for proper formatting
  /// Examples:
  /// - US: formatCurrency(context, 1234.56) → "$1,234.56"
  /// - ES: formatCurrency(context, 1234.56) → "1.234,56 €"
  static String formatCurrency(
    BuildContext context,
    double amount, {
    bool showSymbol = true,
    bool compact = false,
    int decimalDigits = 2,
  }) {
    return _localizationService.formatCurrency(
      amount,
      showSymbol: showSymbol,
      compact: compact,
      decimalDigits: decimalDigits,
    );
  }

  /// Format budget status with proper localized messaging
  /// Returns appropriate message based on spending vs budget ratio
  static String formatBudgetStatus(BuildContext context, double spent, double budget) {
    final l10n = AppLocalizations.of(context);

    return _localizationService.formatBudgetStatus(
      spent,
      budget,
      l10n.overBudget,
      l10n.underBudget,
      l10n.onTrack,
    );
  }

  /// Format budget progress as percentage
  /// Used in progress indicators and charts
  static String formatBudgetProgress(BuildContext context, double spent, double budget) {
    return _localizationService.formatBudgetProgress(spent, budget);
  }

  /// Format large currency amounts with abbreviated suffixes (K, M, B)
  /// Useful for charts and summary displays
  static String formatCompactCurrency(BuildContext context, double amount) {
    return _localizationService.formatCurrency(amount, compact: true);
  }

  /// Format percentage with proper locale formatting
  /// Used for interest rates, progress indicators, etc.
  static String formatPercentage(double ratio, {int decimalDigits = 1}) {
    return _localizationService.formatPercentage(ratio, decimalDigits: decimalDigits);
  }

  /// Format financial ratios (debt-to-income, savings rate, etc.)
  static String formatRatio(BuildContext context, double numerator, double denominator) {
    if (denominator == 0) return '0%';

    final ratio = numerator / denominator;
    return formatPercentage(ratio);
  }

  /// Format date for financial transactions and reports
  static String formatTransactionDate(BuildContext context, DateTime date) {
    final l10n = AppLocalizations.of(context);
    return _localizationService.formatRelativeDate(date, l10n.today, l10n.yesterday);
  }

  /// Format date range for financial reports
  static String formatDateRange(BuildContext context, DateTime start, DateTime end) {
    final startFormatted = _localizationService.formatDate(start);
    final endFormatted = _localizationService.formatDate(end);
    return '$startFormatted - $endFormatted';
  }

  /// Format month and year for budget periods
  static String formatBudgetPeriod(DateTime date) {
    return _localizationService.formatMonthYear(date);
  }

  /// Parse user input currency string to double
  /// Handles different locale formats and currency symbols
  static double? parseCurrencyInput(String input) {
    return _localizationService.parseCurrency(input);
  }

  /// Format expense categories with proper capitalization
  static String formatCategory(BuildContext context, String categoryKey) {
    final l10n = AppLocalizations.of(context);

    switch (categoryKey.toLowerCase()) {
      case 'food':
        return l10n.food;
      case 'transportation':
        return l10n.transportation;
      case 'entertainment':
        return l10n.entertainment;
      case 'shopping':
        return l10n.shopping;
      case 'utilities':
        return l10n.utilities;
      case 'health':
        return l10n.health;
      case 'other':
        return l10n.other;
      default:
        return categoryKey;
    }
  }

  /// Format savings goal progress
  static String formatGoalProgress(BuildContext context, double current, double target) {
    if (target <= 0) return formatCurrency(context, current);

    final percentage = (current / target).clamp(0.0, 1.0);
    final percentageText = formatPercentage(percentage);
    final amountText = formatCurrency(context, current);

    return '$amountText ($percentageText)';
  }

  /// Format spending trend description
  static String formatSpendingTrend(
      BuildContext context, double currentPeriod, double previousPeriod) {
    final l10n = AppLocalizations.of(context);

    if (previousPeriod == 0) {
      return formatCurrency(context, currentPeriod);
    }

    final change = ((currentPeriod - previousPeriod) / previousPeriod) * 100;
    final changeText = formatPercentage(change / 100);

    if (change > 5) {
      return '↗ $changeText ${l10n.thisMonth}';
    } else if (change < -5) {
      return '↘ $changeText ${l10n.thisMonth}';
    } else {
      return '→ ${l10n.onTrack}';
    }
  }

  /// Format daily allowance with budget context
  static String formatDailyAllowance(BuildContext context, double allowance, double spent) {
    final remaining = allowance - spent;
    final l10n = AppLocalizations.of(context);

    if (remaining > 0) {
      return '${l10n.remaining}: ${formatCurrency(context, remaining)}';
    } else if (remaining < 0) {
      return '${l10n.overBudget}: ${formatCurrency(context, remaining.abs())}';
    } else {
      return l10n.onTrack;
    }
  }

  /// Format installment payment schedule
  static String formatInstallment(
      BuildContext context, double amount, int installmentNumber, int totalInstallments) {
    final formattedAmount = formatCurrency(context, amount);
    return '$formattedAmount ($installmentNumber/$totalInstallments)';
  }

  /// Format financial account balance
  static String formatAccountBalance(BuildContext context, double balance, {bool showSign = true}) {
    if (balance >= 0) {
      return formatCurrency(context, balance);
    } else {
      final absBalance = balance.abs();
      return showSign
          ? '-${formatCurrency(context, absBalance, showSymbol: true)}'
          : formatCurrency(context, absBalance);
    }
  }

  /// Format budget variance (difference between budgeted and actual)
  static String formatBudgetVariance(BuildContext context, double budgeted, double actual) {
    final variance = actual - budgeted;
    final l10n = AppLocalizations.of(context);

    if (variance > 0) {
      return '+${formatCurrency(context, variance)} ${l10n.overBudget}';
    } else if (variance < 0) {
      return '${formatCurrency(context, variance)} ${l10n.underBudget}';
    } else {
      return l10n.onTrack;
    }
  }

  /// Get formatted currency symbol for the current locale
  static String getCurrencySymbol() {
    return _localizationService.currencySymbol;
  }

  /// Get currency code for the current locale (USD, EUR, etc.)
  static String getCurrencyCode() {
    return _localizationService.currencyCode;
  }

  /// Check if amount is considered "large" for the current locale
  /// Used for UI decisions like showing confirmation dialogs
  static bool isLargeAmount(double amount) {
    const thresholds = {
      'USD': 1000.0,
      'EUR': 900.0,
      'GBP': 800.0,
      'MXN': 20000.0,
      'ARS': 100000.0,
    };

    final currencyCode = getCurrencyCode();
    final threshold = thresholds[currencyCode] ?? 1000.0;

    return amount.abs() >= threshold;
  }

  /// Format amount for input fields with proper decimal places
  static String formatForInput(double amount) {
    // Always use 2 decimal places for input consistency
    return amount.toStringAsFixed(2);
  }

  /// Validate currency input format
  static bool isValidCurrencyInput(String input) {
    final parsed = parseCurrencyInput(input);
    return parsed != null && parsed >= 0;
  }

  /// Format spending velocity (spending per day/week/month)
  static String formatSpendingVelocity(BuildContext context, double amount, String period) {
    final formattedAmount = formatCurrency(context, amount);
    return '$formattedAmount/$period';
  }

  /// Format time until financial goal
  static String formatTimeToGoal(
      BuildContext context, double currentSaved, double targetAmount, double monthlyContribution) {
    if (monthlyContribution <= 0 || currentSaved >= targetAmount) {
      return '-';
    }

    final remaining = targetAmount - currentSaved;
    final months = (remaining / monthlyContribution).ceil();

    if (months <= 1) {
      return '< 1 month';
    } else if (months <= 12) {
      return '$months months';
    } else {
      final years = (months / 12).floor();
      final remainingMonths = months % 12;
      if (remainingMonths == 0) {
        return '$years ${years == 1 ? 'year' : 'years'}';
      } else {
        return '$years ${years == 1 ? 'year' : 'years'}, $remainingMonths ${remainingMonths == 1 ? 'month' : 'months'}';
      }
    }
  }

  /// Format financial health score (0-100)
  static String formatHealthScore(int score) {
    if (score >= 80) {
      return '$score - Excellent';
    } else if (score >= 60) {
      return '$score - Good';
    } else if (score >= 40) {
      return '$score - Fair';
    } else {
      return '$score - Needs Improvement';
    }
  }

  /// Get appropriate color for financial amount based on context
  static Color getAmountColor(BuildContext context, double amount, {bool isExpense = true}) {
    final theme = Theme.of(context);

    if (isExpense) {
      return amount > 0 ? theme.colorScheme.error : theme.colorScheme.onSurface;
    } else {
      return amount > 0 ? Colors.green : theme.colorScheme.error;
    }
  }

  /// Get appropriate color for budget status
  static Color getBudgetStatusColor(BuildContext context, double spent, double budget) {
    final theme = Theme.of(context);

    if (budget <= 0) return theme.colorScheme.onSurface;

    final percentage = spent / budget;

    if (percentage > 1.1) {
      return theme.colorScheme.error;
    } else if (percentage > 0.9) {
      return Colors.orange;
    } else {
      return Colors.green;
    }
  }
}

/// Extension to provide easy access to financial formatters from any widget
extension FinancialFormattingExtension on BuildContext {
  /// Quick access to currency formatting
  String formatMoney(double amount, {bool compact = false}) {
    return FinancialFormatters.formatCurrency(this, amount, compact: compact);
  }

  /// Quick access to percentage formatting
  String formatPercent(double ratio) {
    return FinancialFormatters.formatPercentage(ratio);
  }

  /// Quick access to category formatting
  String formatExpenseCategory(String categoryKey) {
    return FinancialFormatters.formatCategory(this, categoryKey);
  }
}
