import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../services/localization_service.dart';
import '../services/logging_service.dart';

/// Centralized settings state management provider
/// Manages app settings like theme, locale, notifications, etc.
class SettingsProvider extends ChangeNotifier {
  static const String _themeKey = 'theme_mode';
  static const String _localeKey = 'locale';
  static const String _notificationsKey = 'notifications_enabled';
  static const String _biometricsKey = 'biometrics_enabled';
  static const String _currencyKey = 'default_currency';
  static const String _budgetReminderKey = 'budget_reminder_enabled';
  static const String _weeklyReportKey = 'weekly_report_enabled';

  // State
  ThemeMode _themeMode = ThemeMode.system;
  Locale _locale = const Locale('en');
  bool _notificationsEnabled = true;
  bool _biometricsEnabled = false;
  String _defaultCurrency = 'USD';
  bool _budgetReminderEnabled = true;
  bool _weeklyReportEnabled = true;
  bool _isLoading = false;
  bool _isInitialized = false;

  // Getters
  ThemeMode get themeMode => _themeMode;
  Locale get locale => _locale;
  bool get notificationsEnabled => _notificationsEnabled;
  bool get biometricsEnabled => _biometricsEnabled;
  String get defaultCurrency => _defaultCurrency;
  bool get budgetReminderEnabled => _budgetReminderEnabled;
  bool get weeklyReportEnabled => _weeklyReportEnabled;
  bool get isLoading => _isLoading;
  bool get isInitialized => _isInitialized;

  // Convenience getters
  bool get isDarkMode => _themeMode == ThemeMode.dark;
  bool get isLightMode => _themeMode == ThemeMode.light;
  bool get isSystemMode => _themeMode == ThemeMode.system;
  String get languageCode => _locale.languageCode;

  /// Initialize settings from SharedPreferences
  Future<void> initialize() async {
    if (_isInitialized) return;

    _isLoading = true;
    notifyListeners();

    try {
      logInfo('Initializing SettingsProvider', tag: 'SETTINGS_PROVIDER');

      final prefs = await SharedPreferences.getInstance();

      // Load theme mode
      final themeModeString = prefs.getString(_themeKey);
      if (themeModeString != null) {
        _themeMode = ThemeMode.values.firstWhere(
          (mode) => mode.name == themeModeString,
          orElse: () => ThemeMode.system,
        );
      }

      // Load locale
      final localeString = prefs.getString(_localeKey);
      if (localeString != null) {
        _locale = Locale(localeString);
        LocalizationService.instance.setLocale(_locale);
      }

      // Load boolean settings
      _notificationsEnabled = prefs.getBool(_notificationsKey) ?? true;
      _biometricsEnabled = prefs.getBool(_biometricsKey) ?? false;
      _budgetReminderEnabled = prefs.getBool(_budgetReminderKey) ?? true;
      _weeklyReportEnabled = prefs.getBool(_weeklyReportKey) ?? true;

      // Load currency
      _defaultCurrency = prefs.getString(_currencyKey) ?? 'USD';

      _isInitialized = true;
      logInfo('SettingsProvider initialized successfully', tag: 'SETTINGS_PROVIDER');
    } catch (e) {
      logError('Failed to initialize SettingsProvider: $e', tag: 'SETTINGS_PROVIDER');
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  /// Set theme mode
  Future<void> setThemeMode(ThemeMode mode) async {
    if (_themeMode == mode) return;

    _themeMode = mode;
    notifyListeners();

    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(_themeKey, mode.name);
      logInfo('Theme mode set to: ${mode.name}', tag: 'SETTINGS_PROVIDER');
    } catch (e) {
      logError('Failed to save theme mode: $e', tag: 'SETTINGS_PROVIDER');
    }
  }

  /// Toggle dark mode
  Future<void> toggleDarkMode() async {
    if (_themeMode == ThemeMode.dark) {
      await setThemeMode(ThemeMode.light);
    } else {
      await setThemeMode(ThemeMode.dark);
    }
  }

  /// Set locale
  Future<void> setLocale(Locale locale) async {
    if (_locale == locale) return;

    _locale = locale;
    LocalizationService.instance.setLocale(locale);
    notifyListeners();

    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(_localeKey, locale.languageCode);
      logInfo('Locale set to: ${locale.languageCode}', tag: 'SETTINGS_PROVIDER');
    } catch (e) {
      logError('Failed to save locale: $e', tag: 'SETTINGS_PROVIDER');
    }
  }

  /// Set notifications enabled
  Future<void> setNotificationsEnabled(bool enabled) async {
    if (_notificationsEnabled == enabled) return;

    _notificationsEnabled = enabled;
    notifyListeners();

    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setBool(_notificationsKey, enabled);
      logInfo('Notifications ${enabled ? 'enabled' : 'disabled'}', tag: 'SETTINGS_PROVIDER');
    } catch (e) {
      logError('Failed to save notifications setting: $e', tag: 'SETTINGS_PROVIDER');
    }
  }

  /// Set biometrics enabled
  Future<void> setBiometricsEnabled(bool enabled) async {
    if (_biometricsEnabled == enabled) return;

    _biometricsEnabled = enabled;
    notifyListeners();

    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setBool(_biometricsKey, enabled);
      logInfo('Biometrics ${enabled ? 'enabled' : 'disabled'}', tag: 'SETTINGS_PROVIDER');
    } catch (e) {
      logError('Failed to save biometrics setting: $e', tag: 'SETTINGS_PROVIDER');
    }
  }

  /// Set default currency
  Future<void> setDefaultCurrency(String currency) async {
    if (_defaultCurrency == currency) return;

    _defaultCurrency = currency;
    notifyListeners();

    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(_currencyKey, currency);
      logInfo('Default currency set to: $currency', tag: 'SETTINGS_PROVIDER');
    } catch (e) {
      logError('Failed to save currency setting: $e', tag: 'SETTINGS_PROVIDER');
    }
  }

  /// Set budget reminder enabled
  Future<void> setBudgetReminderEnabled(bool enabled) async {
    if (_budgetReminderEnabled == enabled) return;

    _budgetReminderEnabled = enabled;
    notifyListeners();

    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setBool(_budgetReminderKey, enabled);
      logInfo('Budget reminder ${enabled ? 'enabled' : 'disabled'}', tag: 'SETTINGS_PROVIDER');
    } catch (e) {
      logError('Failed to save budget reminder setting: $e', tag: 'SETTINGS_PROVIDER');
    }
  }

  /// Set weekly report enabled
  Future<void> setWeeklyReportEnabled(bool enabled) async {
    if (_weeklyReportEnabled == enabled) return;

    _weeklyReportEnabled = enabled;
    notifyListeners();

    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setBool(_weeklyReportKey, enabled);
      logInfo('Weekly report ${enabled ? 'enabled' : 'disabled'}', tag: 'SETTINGS_PROVIDER');
    } catch (e) {
      logError('Failed to save weekly report setting: $e', tag: 'SETTINGS_PROVIDER');
    }
  }

  /// Reset all settings to defaults
  Future<void> resetToDefaults() async {
    _themeMode = ThemeMode.system;
    _locale = const Locale('en');
    _notificationsEnabled = true;
    _biometricsEnabled = false;
    _defaultCurrency = 'USD';
    _budgetReminderEnabled = true;
    _weeklyReportEnabled = true;
    notifyListeners();

    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.remove(_themeKey);
      await prefs.remove(_localeKey);
      await prefs.remove(_notificationsKey);
      await prefs.remove(_biometricsKey);
      await prefs.remove(_currencyKey);
      await prefs.remove(_budgetReminderKey);
      await prefs.remove(_weeklyReportKey);
      logInfo('Settings reset to defaults', tag: 'SETTINGS_PROVIDER');
    } catch (e) {
      logError('Failed to reset settings: $e', tag: 'SETTINGS_PROVIDER');
    }
  }

  /// Get available currencies
  List<String> getAvailableCurrencies() {
    return ['USD', 'EUR', 'GBP', 'CAD', 'AUD', 'JPY', 'CNY', 'INR', 'BGN', 'RUB'];
  }

  /// Get available locales
  List<Locale> getAvailableLocales() {
    return const [
      Locale('en'),
      Locale('bg'),
      Locale('ru'),
      Locale('es'),
      Locale('de'),
      Locale('fr'),
    ];
  }
}
