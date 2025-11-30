import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter/semantics.dart';
import 'logging_service.dart';

/// Comprehensive accessibility service for MITA financial app
/// Handles screen reader support, high contrast modes, focus management,
/// and financial data announcements for regulatory compliance
class AccessibilityService {
  static final AccessibilityService _instance = AccessibilityService._internal();
  factory AccessibilityService() => _instance;
  AccessibilityService._internal();

  static AccessibilityService get instance => _instance;

  /// Current accessibility preferences
  bool _screenReaderEnabled = false;
  bool _highContrastEnabled = false;
  bool _reducedMotionEnabled = false;
  double _textScaleFactor = 1.0;

  /// Focus management
  FocusNode? _currentFocus;
  final List<FocusNode> _focusHistory = [];

  /// Announcements queue for screen readers
  final List<String> _announcementQueue = [];
  bool _isAnnouncing = false;

  /// Initialize accessibility service with system settings
  Future<void> initialize() async {
    await _loadSystemAccessibilitySettings();
    _setupAccessibilityListeners();
  }

  /// Load current system accessibility settings
  Future<void> _loadSystemAccessibilitySettings() async {
    try {
      final binding = WidgetsBinding.instance;
      final mediaQuery = MediaQueryData.fromView(binding.platformDispatcher.views.first);

      _screenReaderEnabled = mediaQuery.accessibleNavigation;
      _highContrastEnabled = mediaQuery.highContrast;
      _reducedMotionEnabled = mediaQuery.disableAnimations;
      _textScaleFactor = mediaQuery.textScaler.scale(14) / 14;

      logInfo(
          'Accessibility settings loaded: screenReader=$_screenReaderEnabled, '
          'highContrast=$_highContrastEnabled, reducedMotion=$_reducedMotionEnabled, '
          'textScale=$_textScaleFactor',
          tag: 'ACCESSIBILITY');
    } catch (e) {
      logError('Error loading accessibility settings: $e', tag: 'ACCESSIBILITY');
    }
  }

  /// Set up listeners for system accessibility changes
  void _setupAccessibilityListeners() {
    WidgetsBinding.instance.platformDispatcher.onAccessibilityFeaturesChanged = () {
      _loadSystemAccessibilitySettings();
    };
  }

  // Getters for current accessibility state
  bool get isScreenReaderEnabled => _screenReaderEnabled;
  bool get isHighContrastEnabled => _highContrastEnabled;
  bool get isReducedMotionEnabled => _reducedMotionEnabled;
  double get textScaleFactor => _textScaleFactor;

  /// Announce text to screen readers with financial context
  Future<void> announceToScreenReader(
    String message, {
    String? financialContext,
    bool isImportant = false,
  }) async {
    if (!_screenReaderEnabled) return;

    String fullMessage = message;
    if (financialContext != null) {
      fullMessage = '$financialContext: $message';
    }

    _announcementQueue.add(fullMessage);

    if (!_isAnnouncing) {
      await _processAnnouncementQueue();
    }

    // Provide haptic feedback for important announcements
    if (isImportant) {
      HapticFeedback.mediumImpact();
    }
  }

  /// Process queued announcements
  Future<void> _processAnnouncementQueue() async {
    _isAnnouncing = true;

    while (_announcementQueue.isNotEmpty) {
      final message = _announcementQueue.removeAt(0);

      try {
        SemanticsService.announce(message, TextDirection.ltr);
        // Wait between announcements to avoid overwhelming screen readers
        await Future.delayed(const Duration(milliseconds: 1000));
      } catch (e) {
        logError('Error announcing to screen reader: $e', tag: 'ACCESSIBILITY');
      }
    }

    _isAnnouncing = false;
  }

  /// Announce financial data changes with currency formatting
  Future<void> announceFinancialUpdate(
    String type,
    double amount, {
    String? category,
    String? context,
  }) async {
    final formattedAmount = formatCurrency(amount);
    final categoryText = category != null ? ' in $category' : '';
    final contextText = context != null ? ' $context' : '';

    final message = '$type of $formattedAmount$categoryText$contextText';

    await announceToScreenReader(
      message,
      financialContext: 'Financial Update',
      isImportant: true,
    );
  }

  /// Format currency for accessibility announcements
  String formatCurrency(double amount) {
    if (amount == amount.roundToDouble()) {
      return '\$${amount.toStringAsFixed(0)} dollars';
    } else {
      final dollars = amount.floor();
      final cents = ((amount - dollars) * 100).round();
      return '\$$dollars dollars and $cents cents';
    }
  }

  /// Announce navigation changes
  Future<void> announceNavigation(String screenName, {String? description}) async {
    final message =
        description != null ? 'Navigated to $screenName. $description' : 'Navigated to $screenName';

    await announceToScreenReader(
      message,
      financialContext: 'Navigation',
    );
  }

  /// Focus management for keyboard navigation
  void manageFocus(FocusNode focusNode, {bool addToHistory = true}) {
    if (addToHistory && _currentFocus != null) {
      _focusHistory.add(_currentFocus!);
    }

    _currentFocus = focusNode;
    focusNode.requestFocus();
  }

  /// Navigate to previous focus
  bool navigateToPreviousFocus() {
    if (_focusHistory.isNotEmpty) {
      final previousFocus = _focusHistory.removeLast();
      if (previousFocus.canRequestFocus) {
        previousFocus.requestFocus();
        _currentFocus = previousFocus;
        return true;
      }
    }
    return false;
  }

  /// Clear focus history (call when navigating to new screen)
  void clearFocusHistory() {
    _focusHistory.clear();
    _currentFocus = null;
  }

  /// Create semantic label for financial amounts with context
  String createFinancialSemanticLabel({
    required String label,
    required double amount,
    String? category,
    String? status,
    bool isBalance = false,
  }) {
    final formattedAmount = formatCurrency(amount);
    final categoryText = category != null ? ' for $category' : '';
    final statusText = status != null ? '. Status: $status' : '';

    if (isBalance) {
      return '$label: $formattedAmount$categoryText$statusText. Available balance.';
    } else {
      return '$label: $formattedAmount$categoryText$statusText. Expense amount.';
    }
  }

  /// Create semantic label for progress indicators
  String createProgressSemanticLabel({
    required String category,
    required double spent,
    required double limit,
    String? status,
  }) {
    final percentage = (spent / limit * 100).round();
    final spentFormatted = formatCurrency(spent);
    final limitFormatted = formatCurrency(limit);
    final remaining = limit - spent;
    final remainingFormatted = formatCurrency(remaining.abs());

    String progressText;
    if (remaining >= 0) {
      progressText = '$spentFormatted spent of $limitFormatted budget. '
          '$remainingFormatted remaining. $percentage percent used.';
    } else {
      progressText = '$spentFormatted spent of $limitFormatted budget. '
          'Over budget by $remainingFormatted. $percentage percent used.';
    }

    final statusText = status != null ? ' Status: $status.' : '';
    return '$category budget progress. $progressText$statusText';
  }

  /// Create accessible button label with action context
  String createButtonSemanticLabel({
    required String action,
    String? context,
    bool isDestructive = false,
    bool isDisabled = false,
  }) {
    final contextText = context != null ? ' $context' : '';
    final destructiveText = isDestructive ? ' Warning: This action cannot be undone.' : '';
    final disabledText = isDisabled ? ' Button is currently disabled.' : '';

    return '$action$contextText$destructiveText$disabledText';
  }

  /// Get appropriate minimum touch target size
  Size getMinimumTouchTarget() {
    // Material Design accessibility guidelines: minimum 48x48 dp
    return const Size(48.0, 48.0);
  }

  /// Check if widget meets minimum touch target requirements
  bool meetsMinimumTouchTarget(Size widgetSize) {
    final minSize = getMinimumTouchTarget();
    return widgetSize.width >= minSize.width && widgetSize.height >= minSize.height;
  }

  /// Create accessible text field label with validation context
  String createTextFieldSemanticLabel({
    required String label,
    bool isRequired = false,
    bool hasError = false,
    String? errorMessage,
    String? helperText,
  }) {
    final requiredText = isRequired ? ' Required field.' : '';
    final errorText = hasError && errorMessage != null ? ' Error: $errorMessage' : '';
    final helperTextFormatted = helperText != null ? ' $helperText' : '';

    return '$label$requiredText$errorText$helperTextFormatted';
  }

  /// Announce form validation errors
  Future<void> announceFormErrors(List<String> errors) async {
    if (errors.isEmpty) return;

    final errorCount = errors.length;
    final pluralText = errorCount == 1 ? 'error' : 'errors';
    final summary = '$errorCount form $pluralText found.';

    await announceToScreenReader(
      '$summary ${errors.join('. ')}',
      financialContext: 'Form Validation',
      isImportant: true,
    );
  }

  /// Get high contrast color scheme if enabled
  ColorScheme? getHighContrastColorScheme(ColorScheme baseScheme) {
    if (!_highContrastEnabled) return null;

    // Return high contrast version of the color scheme
    return baseScheme.copyWith(
      primary: _highContrastEnabled ? Colors.blue.shade900 : baseScheme.primary,
      onPrimary: Colors.white,
      secondary: _highContrastEnabled ? Colors.orange.shade800 : baseScheme.secondary,
      onSecondary: Colors.white,
      surface: _highContrastEnabled ? Colors.white : baseScheme.surface,
      onSurface: _highContrastEnabled ? Colors.black : baseScheme.onSurface,
      error: _highContrastEnabled ? Colors.red.shade900 : baseScheme.error,
      onError: Colors.white,
      outline: _highContrastEnabled ? Colors.black : baseScheme.outline,
    );
  }

  /// Get animation duration considering reduced motion preferences
  Duration getAnimationDuration(Duration defaultDuration) {
    return _reducedMotionEnabled ? Duration.zero : defaultDuration;
  }

  /// Dispose of accessibility service resources
  void dispose() {
    _announcementQueue.clear();
    _focusHistory.clear();
    _currentFocus = null;
  }
}

/// Extension for adding accessibility helpers to widgets
extension AccessibilityExtensions on Widget {
  /// Add semantic label with financial context
  Widget withFinancialSemantics({
    required String label,
    String? hint,
    String? value,
    bool isButton = false,
    bool isHeader = false,
    VoidCallback? onTap,
  }) {
    return Semantics(
      label: label,
      hint: hint,
      value: value,
      button: isButton,
      header: isHeader,
      onTap: onTap,
      child: this,
    );
  }

  /// Add live region semantics for dynamic content
  Widget withLiveRegionSemantics({
    bool isLive = true,
    String? liveRegionLabel,
  }) {
    return Semantics(
      liveRegion: isLive,
      label: liveRegionLabel,
      child: this,
    );
  }

  /// Ensure minimum touch target size
  Widget withMinimumTouchTarget({Size? customSize}) {
    final minSize = customSize ?? AccessibilityService.instance.getMinimumTouchTarget();
    return ConstrainedBox(
      constraints: BoxConstraints(
        minWidth: minSize.width,
        minHeight: minSize.height,
      ),
      child: this,
    );
  }
}
