import 'dart:ui' as ui;
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

/// Comprehensive localization service for MITA financial app
/// Handles currency, number, date formatting with locale-aware behavior
class LocalizationService {
  static LocalizationService? _instance;
  
  LocalizationService._internal();
  
  static LocalizationService get instance {
    _instance ??= LocalizationService._internal();
    return _instance!;
  }

  /// Current locale being used by the app
  Locale _currentLocale = const Locale('en', 'US');
  
  /// Currency codes and symbols by locale
  static const Map<String, Map<String, String>> _currencyData = {
    'en_US': {'code': 'USD', 'symbol': r'$', 'name': 'US Dollar'},
    'en_GB': {'code': 'GBP', 'symbol': '£', 'name': 'British Pound'},
    'es_ES': {'code': 'EUR', 'symbol': '€', 'name': 'Euro'},
    'es_MX': {'code': 'MXN', 'symbol': r'$', 'name': 'Mexican Peso'},
    'es_AR': {'code': 'ARS', 'symbol': r'$', 'name': 'Argentine Peso'},
  };

  /// Set the current locale and notify listeners if needed
  void setLocale(Locale locale) {
    _currentLocale = locale;
  }

  /// Get the current locale
  Locale get currentLocale => _currentLocale;

  /// Get currency data for current locale
  Map<String, String> get currentCurrencyData {
    final localeKey = '${_currentLocale.languageCode}_${_currentLocale.countryCode ?? 'US'}';
    return _currencyData[localeKey] ?? _currencyData['en_US']!;
  }

  /// Get currency code for current locale (e.g., 'USD', 'EUR')
  String get currencyCode => currentCurrencyData['code']!;

  /// Get currency symbol for current locale (e.g., '$', '€')
  String get currencySymbol => currentCurrencyData['symbol']!;

  /// Get currency name for current locale (e.g., 'US Dollar', 'Euro')
  String get currencyName => currentCurrencyData['name']!;

  /// Format currency amount with proper locale-specific formatting
  /// 
  /// Examples:
  /// - US: formatCurrency(1234.56) → "$1,234.56"
  /// - ES: formatCurrency(1234.56) → "1.234,56 €"
  /// - MX: formatCurrency(1234.56) → "$1,234.56"
  String formatCurrency(double amount, {
    bool showSymbol = true,
    int decimalDigits = 2,
    bool compact = false,
  }) {
    try {
      final formatter = NumberFormat.currency(
        locale: _currentLocale.toString(),
        symbol: showSymbol ? currencySymbol : '',
        decimalDigits: decimalDigits,
      );
      
      if (compact && amount.abs() >= 1000) {
        return _formatCompactCurrency(amount, showSymbol: showSymbol);
      }
      
      return formatter.format(amount);
    } catch (e) {
      // Fallback to basic formatting if locale is not supported
      return _formatCurrencyFallback(amount, showSymbol: showSymbol, decimalDigits: decimalDigits);
    }
  }

  /// Format currency in compact form (e.g., $1.2K, $2.5M)
  String _formatCompactCurrency(double amount, {bool showSymbol = true}) {
    final absAmount = amount.abs();
    final symbol = showSymbol ? currencySymbol : '';
    final sign = amount < 0 ? '-' : '';
    
    if (absAmount >= 1000000000) {
      return '$sign$symbol${(absAmount / 1000000000).toStringAsFixed(1)}B';
    } else if (absAmount >= 1000000) {
      return '$sign$symbol${(absAmount / 1000000).toStringAsFixed(1)}M';
    } else if (absAmount >= 1000) {
      return '$sign$symbol${(absAmount / 1000).toStringAsFixed(1)}K';
    } else {
      return formatCurrency(amount, showSymbol: showSymbol, compact: false);
    }
  }

  /// Fallback currency formatting when locale is not supported
  String _formatCurrencyFallback(double amount, {bool showSymbol = true, int decimalDigits = 2}) {
    final symbol = showSymbol ? currencySymbol : '';
    final absAmount = amount.abs();
    final sign = amount < 0 ? '-' : '';
    
    // Use US-style formatting as fallback
    final formatter = NumberFormat('#,##0.${'0' * decimalDigits}');
    return '$sign$symbol${formatter.format(absAmount)}';
  }

  /// Format number with proper locale-specific thousands separators
  /// 
  /// Examples:
  /// - US: formatNumber(1234.56) → "1,234.56"
  /// - ES: formatNumber(1234.56) → "1.234,56"
  String formatNumber(double number, {int decimalDigits = 2}) {
    try {
      final formatter = NumberFormat('#,##0.${'0' * decimalDigits}', _currentLocale.toString());
      return formatter.format(number);
    } catch (e) {
      // Fallback to US formatting
      final formatter = NumberFormat('#,##0.${'0' * decimalDigits}');
      return formatter.format(number);
    }
  }

  /// Format percentage with locale-specific formatting
  /// 
  /// Examples:
  /// - US: formatPercentage(0.1256) → "12.56%"
  /// - ES: formatPercentage(0.1256) → "12,56 %"
  String formatPercentage(double ratio, {int decimalDigits = 1}) {
    try {
      final formatter = NumberFormat.percentPattern(_currentLocale.toString());
      if (decimalDigits != formatter.minimumFractionDigits) {
        formatter.minimumFractionDigits = decimalDigits;
        formatter.maximumFractionDigits = decimalDigits;
      }
      return formatter.format(ratio);
    } catch (e) {
      // Fallback formatting
      final percentage = (ratio * 100).toStringAsFixed(decimalDigits);
      return '$percentage%';
    }
  }

  /// Format date with locale-specific formatting
  /// 
  /// Examples:
  /// - US: formatDate(date) → "12/31/2024"
  /// - ES: formatDate(date) → "31/12/2024"
  String formatDate(DateTime date, {DateFormat? customFormat}) {
    try {
      final formatter = customFormat ?? DateFormat.yMd(_currentLocale.toString());
      return formatter.format(date);
    } catch (e) {
      // Fallback to ISO format
      return DateFormat.yMd().format(date);
    }
  }

  /// Format date and time with locale-specific formatting
  String formatDateTime(DateTime dateTime) {
    try {
      final formatter = DateFormat.yMd(_currentLocale.toString()).add_Hm();
      return formatter.format(dateTime);
    } catch (e) {
      // Fallback formatting
      return DateFormat.yMd().add_Hm().format(dateTime);
    }
  }

  /// Format date in a user-friendly way (Today, Yesterday, etc.)
  String formatRelativeDate(DateTime date, String todayLabel, String yesterdayLabel) {
    final now = DateTime.now();
    final today = DateTime(now.year, now.month, now.day);
    final dateOnly = DateTime(date.year, date.month, date.day);
    
    final difference = today.difference(dateOnly).inDays;
    
    switch (difference) {
      case 0:
        return todayLabel;
      case 1:
        return yesterdayLabel;
      default:
        return formatDate(date);
    }
  }

  /// Format time with locale-specific formatting
  String formatTime(DateTime time) {
    try {
      final formatter = DateFormat.Hm(_currentLocale.toString());
      return formatter.format(time);
    } catch (e) {
      return DateFormat.Hm().format(time);
    }
  }

  /// Format month and year (e.g., "January 2024", "enero 2024")
  String formatMonthYear(DateTime date) {
    try {
      final formatter = DateFormat.yMMM(_currentLocale.toString());
      return formatter.format(date);
    } catch (e) {
      return DateFormat.yMMM().format(date);
    }
  }

  /// Check if current locale uses right-to-left text direction
  bool get isRTL {
    return ui.Directionality.of != null && 
           Directionality.of(ui.window.locale as BuildContext) == TextDirection.rtl;
  }

  /// Get text direction for current locale
  TextDirection get textDirection {
    // Add RTL language codes as needed
    const rtlLanguages = ['ar', 'he', 'fa', 'ur'];
    return rtlLanguages.contains(_currentLocale.languageCode) 
        ? TextDirection.rtl 
        : TextDirection.ltr;
  }

  /// Parse currency string back to double
  /// Useful for handling user input in different locales
  double? parseCurrency(String currencyString) {
    try {
      // Remove currency symbols and spaces
      String cleanString = currencyString
          .replaceAll(currencySymbol, '')
          .replaceAll(' ', '')
          .trim();
      
      // Handle different decimal separators
      if (_currentLocale.toString().startsWith('es')) {
        // European format: 1.234,56
        cleanString = cleanString.replaceAll('.', '').replaceAll(',', '.');
      }
      
      return double.tryParse(cleanString);
    } catch (e) {
      return null;
    }
  }

  /// Get list of supported currencies for the current locale
  List<Map<String, String>> getSupportedCurrencies() {
    return _currencyData.values.toList();
  }

  /// Check if a currency is supported
  bool isCurrencySupported(String currencyCode) {
    return _currencyData.values.any((currency) => currency['code'] == currencyCode);
  }

  /// Format budget progress percentage with visual context
  String formatBudgetProgress(double spent, double budget) {
    if (budget <= 0) return '0%';
    
    final percentage = spent / budget;
    return formatPercentage(percentage);
  }

  /// Format budget status message with amount
  String formatBudgetStatus(double spent, double budget, 
      String overBudgetText, String underBudgetText, String onTrackText) {
    if (budget <= 0) return formatCurrency(spent);
    
    final percentage = spent / budget;
    
    if (percentage > 1.1) {
      final excess = spent - budget;
      return '$overBudgetText ${formatCurrency(excess)}';
    } else if (percentage < 0.9) {
      return underBudgetText;
    } else {
      return onTrackText;
    }
  }

  /// Format large numbers in a readable way (K, M, B abbreviations)
  String formatLargeNumber(double number) {
    final absNumber = number.abs();
    final sign = number < 0 ? '-' : '';
    
    if (absNumber >= 1000000000) {
      return '$sign${(absNumber / 1000000000).toStringAsFixed(1)}B';
    } else if (absNumber >= 1000000) {
      return '$sign${(absNumber / 1000000).toStringAsFixed(1)}M';
    } else if (absNumber >= 1000) {
      return '$sign${(absNumber / 1000).toStringAsFixed(1)}K';
    } else {
      return formatNumber(number, decimalDigits: 0);
    }
  }
}

/// Extension to easily access localization from BuildContext
extension LocalizationExtension on BuildContext {
  LocalizationService get l10n => LocalizationService.instance;
}