import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../theme/app_colors.dart';
import '../theme/app_typography.dart';
import 'package:url_launcher/url_launcher.dart';
import '../providers/settings_provider.dart';
import '../providers/user_provider.dart';
import '../services/api_service.dart';
import '../services/logging_service.dart';

class UserSettingsScreen extends StatefulWidget {
  const UserSettingsScreen({super.key});

  @override
  State<UserSettingsScreen> createState() => _UserSettingsScreenState();
}

class _UserSettingsScreenState extends State<UserSettingsScreen> {
  final ApiService _apiService = ApiService();

  bool _isLoading = true;
  // Settings managed by SettingsProvider: themeMode, locale, notificationsEnabled, biometricsEnabled, defaultCurrency

  // Settings not in provider - managed locally
  bool _autoSyncEnabled = true;
  bool _offlineModeEnabled = true;
  String _dateFormat = 'MM/dd/yyyy';
  double _budgetAlertThreshold = 80.0;

  // Behavioral notification settings
  bool _patternAlerts = true;
  bool _anomalyDetection = true;
  bool _budgetAdaptation = true;
  bool _weeklyInsights = true;

  // Behavioral preferences
  Map<String, dynamic> _behavioralPreferences = {};

  final List<String> _dateFormats = ['MM/dd/yyyy', 'dd/MM/yyyy', 'yyyy-MM-dd'];

  // Language code to display name mapping
  String _getLanguageDisplayName(String languageCode) {
    switch (languageCode) {
      case 'en':
        return 'English';
      case 'es':
        return 'Spanish';
      case 'fr':
        return 'French';
      case 'de':
        return 'German';
      case 'bg':
        return 'Bulgarian';
      case 'ru':
        return 'Russian';
      default:
        return 'English';
    }
  }

  String _getLanguageCode(String displayName) {
    switch (displayName) {
      case 'English':
        return 'en';
      case 'Spanish':
        return 'es';
      case 'French':
        return 'fr';
      case 'German':
        return 'de';
      case 'Bulgarian':
        return 'bg';
      case 'Russian':
        return 'ru';
      default:
        return 'en';
    }
  }

  final List<String> _languages = [
    'English',
    'Spanish',
    'French',
    'German',
    'Bulgarian',
    'Russian'
  ];

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      final settingsProvider = context.read<SettingsProvider>();
      if (!settingsProvider.isInitialized) {
        settingsProvider.initialize();
      }
    });
    _loadSettings();
  }

  Future<void> _loadSettings() async {
    try {
      setState(() => _isLoading = true);

      // Load behavioral settings and other non-provider settings from API
      final results = await Future.wait([
        _apiService
            .getUserProfile()
            .timeout(
              const Duration(seconds: 3),
              onTimeout: () => <String, dynamic>{},
            )
            .catchError((e) => <String, dynamic>{}),
        _apiService
            .getBehavioralNotificationSettings()
            .timeout(
              const Duration(seconds: 3),
              onTimeout: () => <String, dynamic>{},
            )
            .catchError((e) => <String, dynamic>{}),
        _apiService
            .getBehavioralPreferences()
            .timeout(
              const Duration(seconds: 3),
              onTimeout: () => <String, dynamic>{},
            )
            .catchError((e) => <String, dynamic>{}),
      ]);

      final settings = results[0] as Map<String, dynamic>;
      final behavioralNotifications = results[1] as Map<String, dynamic>;
      final behavioralPrefs = results[2] as Map<String, dynamic>;

      if (mounted) {
        setState(() {
          // Settings not managed by provider - load from API
          if (settings.isNotEmpty) {
            _autoSyncEnabled = settings['auto_sync'] ?? true;
            _offlineModeEnabled = settings['offline_mode'] ?? true;
            _dateFormat = settings['date_format'] ?? 'MM/dd/yyyy';
            _budgetAlertThreshold =
                (settings['budget_alert_threshold'] as num?)?.toDouble() ??
                    80.0;
          }

          // Behavioral notification settings
          if (behavioralNotifications.isNotEmpty) {
            _patternAlerts = behavioralNotifications['pattern_alerts'] ?? true;
            _anomalyDetection =
                behavioralNotifications['anomaly_detection'] ?? true;
            _budgetAdaptation =
                behavioralNotifications['budget_adaptation'] ?? true;
            _weeklyInsights =
                behavioralNotifications['weekly_insights'] ?? true;
          }

          // Behavioral preferences
          _behavioralPreferences = behavioralPrefs;

          _isLoading = false;
        });
      }
    } catch (e) {
      logError('Failed to load settings: $e', tag: 'USER_SETTINGS');
      if (mounted) setState(() => _isLoading = false);
    }
  }

  Future<void> _saveSettings() async {
    try {
      final settingsProvider = context.read<SettingsProvider>();

      final settings = {
        'dark_mode': settingsProvider.themeMode == ThemeMode.dark,
        'notifications': settingsProvider.notificationsEnabled,
        'biometric_auth': settingsProvider.biometricsEnabled,
        'auto_sync': _autoSyncEnabled,
        'offline_mode': _offlineModeEnabled,
        'currency': settingsProvider.defaultCurrency,
        'language': _getLanguageDisplayName(settingsProvider.languageCode),
        'date_format': _dateFormat,
        'budget_alert_threshold': _budgetAlertThreshold,
      };

      // Save general settings and behavioral settings in parallel
      await Future.wait([
        _apiService.updateUserProfile(settings).timeout(
              const Duration(seconds: 5),
              onTimeout: () => throw Exception('Settings save timeout'),
            ),
        _apiService
            .updateBehavioralNotificationSettings(
              patternAlerts: _patternAlerts,
              anomalyDetection: _anomalyDetection,
              budgetAdaptation: _budgetAdaptation,
              weeklyInsights: _weeklyInsights,
            )
            .timeout(
              const Duration(seconds: 5),
              onTimeout: () =>
                  throw Exception('Behavioral settings save timeout'),
            ),
      ]);

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Row(
              children: [
                Icon(Icons.check_circle, color: Colors.white),
                SizedBox(width: 8),
                Text('Settings saved successfully!'),
              ],
            ),
            backgroundColor: Colors.green,
            behavior: SnackBarBehavior.floating,
          ),
        );
      }
    } catch (e) {
      logError('Failed to save settings: $e', tag: 'USER_SETTINGS');
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Row(
              children: [
                Icon(Icons.error, color: Colors.white),
                SizedBox(width: 8),
                Text('Failed to save settings. Please try again.'),
              ],
            ),
            backgroundColor: Colors.red,
            behavior: SnackBarBehavior.floating,
          ),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;
    final settingsProvider = context.watch<SettingsProvider>();

    final isLoading = _isLoading || settingsProvider.isLoading;

    return Scaffold(
      backgroundColor: colorScheme.surface,
      appBar: AppBar(
        title: const Text(
          'Settings',
          style: TextStyle(
            fontFamily: AppTypography.fontHeading,
            fontWeight: FontWeight.w600,
          ),
        ),
        backgroundColor: colorScheme.surface,
        elevation: 0,
        actions: [
          TextButton(
            onPressed: _saveSettings,
            child: Text(
              'Save',
              style: TextStyle(
                fontWeight: FontWeight.w600,
                color: colorScheme.primary,
              ),
            ),
          ),
        ],
      ),
      body: isLoading
          ? _buildLoadingState()
          : _buildSettingsContent(colorScheme, textTheme, settingsProvider),
    );
  }

  Widget _buildLoadingState() {
    return const Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          CircularProgressIndicator(),
          SizedBox(height: 16),
          Text('Loading settings...',
              style: TextStyle(fontFamily: AppTypography.fontBody)),
        ],
      ),
    );
  }

  Widget _buildSettingsContent(ColorScheme colorScheme, TextTheme textTheme,
      SettingsProvider settingsProvider) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Appearance Settings
          _buildSectionCard(
            'Appearance',
            Icons.palette,
            [
              _buildSwitchTile(
                'Dark Mode',
                'Use dark theme throughout the app',
                Icons.dark_mode,
                settingsProvider.themeMode == ThemeMode.dark,
                (value) => settingsProvider
                    .setThemeMode(value ? ThemeMode.dark : ThemeMode.light),
              ),
              _buildDropdownTile(
                'Language',
                'Select your preferred language',
                Icons.language,
                _getLanguageDisplayName(settingsProvider.languageCode),
                _languages,
                (value) => settingsProvider
                    .setLocale(Locale(_getLanguageCode(value!))),
              ),
              _buildDropdownTile(
                'Date Format',
                'Choose how dates are displayed',
                Icons.calendar_today,
                _dateFormat,
                _dateFormats,
                (value) => setState(() => _dateFormat = value!),
              ),
            ],
            colorScheme,
            textTheme,
          ),

          const SizedBox(height: 24),

          // Notifications Settings
          _buildSectionCard(
            'Notifications',
            Icons.notifications,
            [
              _buildSwitchTile(
                'Push Notifications',
                'Receive spending alerts and tips',
                Icons.notifications_active,
                settingsProvider.notificationsEnabled,
                (value) => settingsProvider.setNotificationsEnabled(value),
              ),
              _buildSliderTile(
                'Budget Alert Threshold',
                'Get notified when you reach this % of budget',
                Icons.warning,
                _budgetAlertThreshold,
                (value) => setState(() => _budgetAlertThreshold = value),
              ),
            ],
            colorScheme,
            textTheme,
          ),

          const SizedBox(height: 24),

          // Behavioral Insights Settings
          _buildSectionCard(
            'Behavioral Insights',
            Icons.psychology,
            [
              _buildSwitchTile(
                'Pattern Alerts',
                'Get notified about your spending patterns',
                Icons.pattern,
                _patternAlerts,
                (value) => setState(() => _patternAlerts = value),
              ),
              _buildSwitchTile(
                'Anomaly Detection',
                'Alert me about unusual spending behavior',
                Icons.warning_amber,
                _anomalyDetection,
                (value) => setState(() => _anomalyDetection = value),
              ),
              _buildSwitchTile(
                'Budget Adaptation',
                'Receive adaptive budget recommendations',
                Icons.auto_fix_high,
                _budgetAdaptation,
                (value) => setState(() => _budgetAdaptation = value),
              ),
              _buildSwitchTile(
                'Weekly Insights',
                'Get weekly behavioral insights summary',
                Icons.insights,
                _weeklyInsights,
                (value) => setState(() => _weeklyInsights = value),
              ),
            ],
            colorScheme,
            textTheme,
          ),

          const SizedBox(height: 24),

          // Security Settings
          _buildSectionCard(
            'Security & Privacy',
            Icons.security,
            [
              _buildSwitchTile(
                'Biometric Authentication',
                'Use fingerprint or face unlock',
                Icons.fingerprint,
                settingsProvider.biometricsEnabled,
                (value) => settingsProvider.setBiometricsEnabled(value),
              ),
              _buildActionTile(
                'Change Password',
                'Update your account password',
                Icons.lock,
                () => _showChangePasswordDialog(),
              ),
              _buildActionTile(
                'Export Data',
                'Download your financial data',
                Icons.download,
                () => _showExportDialog(),
              ),
            ],
            colorScheme,
            textTheme,
          ),

          const SizedBox(height: 24),

          // Data & Sync Settings
          _buildSectionCard(
            'Data & Sync',
            Icons.sync,
            [
              _buildSwitchTile(
                'Auto Sync',
                'Automatically sync data when online',
                Icons.sync,
                _autoSyncEnabled,
                (value) => setState(() => _autoSyncEnabled = value),
              ),
              _buildSwitchTile(
                'Offline Mode',
                'Allow app to work without internet',
                Icons.offline_bolt,
                _offlineModeEnabled,
                (value) => setState(() => _offlineModeEnabled = value),
              ),
              _buildDropdownTile(
                'Default Currency',
                'Currency used for new transactions',
                Icons.attach_money,
                settingsProvider.defaultCurrency,
                settingsProvider.getAvailableCurrencies(),
                (value) => settingsProvider.setDefaultCurrency(value!),
              ),
            ],
            colorScheme,
            textTheme,
          ),

          const SizedBox(height: 24),

          // About Settings
          _buildSectionCard(
            'About',
            Icons.info,
            [
              _buildActionTile(
                'Help & Support',
                'Get help or contact support',
                Icons.help,
                () => _showHelpDialog(),
              ),
              _buildActionTile(
                'Privacy Policy',
                'Read our privacy policy',
                Icons.privacy_tip,
                () => _showPrivacyPolicy(),
              ),
              _buildActionTile(
                'Terms of Service',
                'Read our terms of service',
                Icons.description,
                () => _showTermsOfService(),
              ),
              _buildInfoTile(
                'App Version',
                '1.0.0 (Build 1)',
                Icons.info_outline,
              ),
            ],
            colorScheme,
            textTheme,
          ),

          const SizedBox(height: 32),

          // Danger Zone
          _buildDangerSection(colorScheme, textTheme),

          const SizedBox(height: 32),
        ],
      ),
    );
  }

  Widget _buildSectionCard(
    String title,
    IconData icon,
    List<Widget> children,
    ColorScheme colorScheme,
    TextTheme textTheme,
  ) {
    return Card(
      elevation: 1,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    color: colorScheme.primaryContainer.withValues(alpha: 0.3),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Icon(icon, color: colorScheme.primary, size: 20),
                ),
                const SizedBox(width: 12),
                Text(
                  title,
                  style: textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.bold,
                    fontFamily: AppTypography.fontHeading,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),
            ...children,
          ],
        ),
      ),
    );
  }

  Widget _buildSwitchTile(
    String title,
    String subtitle,
    IconData icon,
    bool value,
    Function(bool) onChanged,
  ) {
    return ListTile(
      contentPadding: EdgeInsets.zero,
      leading: Icon(icon),
      title: Text(
        title,
        style: const TextStyle(
            fontWeight: FontWeight.w500, fontFamily: AppTypography.fontHeading),
      ),
      subtitle: Text(
        subtitle,
        style: const TextStyle(fontFamily: AppTypography.fontBody),
      ),
      trailing: Switch(
        value: value,
        onChanged: onChanged,
      ),
    );
  }

  Widget _buildDropdownTile(
    String title,
    String subtitle,
    IconData icon,
    String value,
    List<String> options,
    Function(String?) onChanged,
  ) {
    return ListTile(
      contentPadding: EdgeInsets.zero,
      leading: Icon(icon),
      title: Text(
        title,
        style: const TextStyle(
            fontWeight: FontWeight.w500, fontFamily: AppTypography.fontHeading),
      ),
      subtitle: Text(
        subtitle,
        style: const TextStyle(fontFamily: AppTypography.fontBody),
      ),
      trailing: DropdownButton<String>(
        value: value,
        onChanged: onChanged,
        items: options
            .map((option) => DropdownMenuItem(
                  value: option,
                  child: Text(option),
                ))
            .toList(),
      ),
    );
  }

  Widget _buildSliderTile(
    String title,
    String subtitle,
    IconData icon,
    double value,
    Function(double) onChanged,
  ) {
    return Column(
      children: [
        ListTile(
          contentPadding: EdgeInsets.zero,
          leading: Icon(icon),
          title: Text(
            title,
            style: const TextStyle(
                fontWeight: FontWeight.w500,
                fontFamily: AppTypography.fontHeading),
          ),
          subtitle: Text(
            subtitle,
            style: const TextStyle(fontFamily: AppTypography.fontBody),
          ),
          trailing: Text(
            '${value.toInt()}%',
            style: const TextStyle(fontWeight: FontWeight.bold),
          ),
        ),
        Slider(
          value: value,
          min: 50,
          max: 100,
          divisions: 10,
          onChanged: onChanged,
        ),
      ],
    );
  }

  Widget _buildActionTile(
    String title,
    String subtitle,
    IconData icon,
    VoidCallback onTap,
  ) {
    return ListTile(
      contentPadding: EdgeInsets.zero,
      leading: Icon(icon),
      title: Text(
        title,
        style: const TextStyle(
            fontWeight: FontWeight.w500, fontFamily: AppTypography.fontHeading),
      ),
      subtitle: Text(
        subtitle,
        style: const TextStyle(fontFamily: AppTypography.fontBody),
      ),
      trailing: const Icon(Icons.arrow_forward_ios, size: 16),
      onTap: onTap,
    );
  }

  Widget _buildInfoTile(
    String title,
    String value,
    IconData icon,
  ) {
    return ListTile(
      contentPadding: EdgeInsets.zero,
      leading: Icon(icon),
      title: Text(
        title,
        style: const TextStyle(
            fontWeight: FontWeight.w500, fontFamily: AppTypography.fontHeading),
      ),
      trailing: Text(
        value,
        style: TextStyle(
          color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.6),
          fontFamily: AppTypography.fontBody,
        ),
      ),
    );
  }

  Widget _buildDangerSection(ColorScheme colorScheme, TextTheme textTheme) {
    return Card(
      elevation: 1,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      child: Container(
        padding: const EdgeInsets.all(20),
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(16),
          color: Colors.red.withValues(alpha: 0.05),
          border: Border.all(color: Colors.red.withValues(alpha: 0.2)),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    color: Colors.red.withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: const Icon(Icons.warning, color: Colors.red, size: 20),
                ),
                const SizedBox(width: 12),
                Text(
                  'Danger Zone',
                  style: textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.bold,
                    color: Colors.red,
                    fontFamily: AppTypography.fontHeading,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),
            _buildActionTile(
              'Delete Account',
              'Permanently delete your account and data',
              Icons.delete_forever,
              () => _showDeleteAccountDialog(),
            ),
            _buildActionTile(
              'Sign Out',
              'Sign out of your account',
              Icons.logout,
              () => _showSignOutDialog(),
            ),
          ],
        ),
      ),
    );
  }

  // Dialog methods
  void _showChangePasswordDialog() {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Change Password'),
        content:
            const Text('This feature will redirect you to account settings.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () {
              Navigator.pop(context);
              _changePassword();
            },
            child: const Text('Continue'),
          ),
        ],
      ),
    );
  }

  void _showExportDialog() {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Export Data'),
        content:
            const Text('Your financial data will be exported as a CSV file.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () {
              Navigator.pop(context);
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(content: Text('Data export started...')),
              );
            },
            child: const Text('Export'),
          ),
        ],
      ),
    );
  }

  void _showHelpDialog() {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Help & Support'),
        content: const Text(
            'Contact our support team at support@mita.finance or visit our help center.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('OK'),
          ),
        ],
      ),
    );
  }

  void _showPrivacyPolicy() {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Privacy Policy'),
        content:
            const Text('This will open the privacy policy in your browser.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () {
              Navigator.pop(context);
              _openPrivacyPolicy();
            },
            child: const Text('Open'),
          ),
        ],
      ),
    );
  }

  void _showTermsOfService() {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Terms of Service'),
        content:
            const Text('This will open the terms of service in your browser.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () {
              Navigator.pop(context);
              _openTermsOfService();
            },
            child: const Text('Open'),
          ),
        ],
      ),
    );
  }

  void _showDeleteAccountDialog() {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Delete Account'),
        content: const Text(
            'Are you sure you want to permanently delete your account? This action cannot be undone.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () {
              Navigator.pop(context);
              _deleteAccount();
            },
            style: TextButton.styleFrom(foregroundColor: Colors.red),
            child: const Text('Delete'),
          ),
        ],
      ),
    );
  }

  void _showSignOutDialog() {
    showDialog(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Sign Out'),
        content: const Text('Are you sure you want to sign out?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () async {
              Navigator.pop(dialogContext);
              await context.read<UserProvider>().logout();
              _navigateToLogin();
            },
            child: const Text('Sign Out'),
          ),
        ],
      ),
    );
  }

  /// Open privacy policy URL in browser
  Future<void> _openPrivacyPolicy() async {
    try {
      final Uri url = Uri.parse('https://mita-production-production.up.railway.app/privacy-policy');
      if (await canLaunchUrl(url)) {
        await launchUrl(url, mode: LaunchMode.externalApplication);
      } else {
        _showUrlErrorSnackbar('Could not open privacy policy');
      }
    } catch (e) {
      logError('Failed to open privacy policy URL: $e', tag: 'USER_SETTINGS');
      _showUrlErrorSnackbar('Error opening privacy policy');
    }
  }

  /// Open terms of service URL in browser
  Future<void> _openTermsOfService() async {
    try {
      final Uri url = Uri.parse('https://mita-production-production.up.railway.app/terms-of-service');
      if (await canLaunchUrl(url)) {
        await launchUrl(url, mode: LaunchMode.externalApplication);
      } else {
        _showUrlErrorSnackbar('Could not open terms of service');
      }
    } catch (e) {
      logError('Failed to open terms of service URL: $e', tag: 'USER_SETTINGS');
      _showUrlErrorSnackbar('Error opening terms of service');
    }
  }

  /// Show error message when URL fails to open
  void _showUrlErrorSnackbar(String message) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message),
        backgroundColor: Colors.red,
        duration: const Duration(seconds: 3),
      ),
    );
  }

  /// Implement password change functionality
  Future<void> _changePassword() async {
    try {
      setState(() => _isLoading = true);

      // Navigate to password change screen with proper form validation
      final result = await Navigator.push(
        context,
        MaterialPageRoute(
          builder: (context) => const PasswordChangeScreen(),
        ),
      );

      if (result == true) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Password changed successfully'),
            backgroundColor: Colors.green,
            duration: Duration(seconds: 3),
          ),
        );
      }
    } catch (e) {
      logError('Failed to change password: $e', tag: 'USER_SETTINGS');
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Error changing password'),
          backgroundColor: Colors.red,
          duration: Duration(seconds: 3),
        ),
      );
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  /// Implement account deletion functionality
  Future<void> _deleteAccount() async {
    try {
      setState(() => _isLoading = true);

      final response = await _apiService.deleteAccount();
      if (response.data['success'] == true) {
        logInfo('Account deleted successfully', tag: 'USER_SETTINGS');

        // Clear all local data using UserProvider
        await context.read<UserProvider>().logout();

        // Navigate to welcome screen
        if (mounted) {
          Navigator.pushNamedAndRemoveUntil(
            context,
            '/welcome',
            (route) => false,
          );
        }

        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text('Account deleted successfully'),
              backgroundColor: Colors.green,
              duration: Duration(seconds: 3),
            ),
          );
        }
      } else {
        throw Exception('Account deletion failed');
      }
    } catch (e) {
      logError('Failed to delete account: $e', tag: 'USER_SETTINGS');
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Error deleting account. Please contact support.'),
            backgroundColor: Colors.red,
            duration: Duration(seconds: 4),
          ),
        );
      }
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  /// Navigate to login screen after logout
  void _navigateToLogin() {
    try {
      if (mounted) {
        Navigator.pushNamedAndRemoveUntil(
          context,
          '/login',
          (route) => false,
        );
      }
    } catch (e) {
      logError('Failed to navigate to login screen: $e', tag: 'USER_SETTINGS');
    }
  }
}

/// Placeholder for password change screen
class PasswordChangeScreen extends StatefulWidget {
  const PasswordChangeScreen({super.key});

  @override
  State<PasswordChangeScreen> createState() => _PasswordChangeScreenState();
}

class _PasswordChangeScreenState extends State<PasswordChangeScreen> {
  final _formKey = GlobalKey<FormState>();
  final _currentPasswordController = TextEditingController();
  final _newPasswordController = TextEditingController();
  final _confirmPasswordController = TextEditingController();
  final ApiService _apiService = ApiService();

  bool _isLoading = false;
  bool _obscureCurrentPassword = true;
  bool _obscureNewPassword = true;
  bool _obscureConfirmPassword = true;

  @override
  void dispose() {
    _currentPasswordController.dispose();
    _newPasswordController.dispose();
    _confirmPasswordController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Change Password'),
        elevation: 0,
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16.0),
        child: Form(
          key: _formKey,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const SizedBox(height: 20),
              const Text(
                'Enter your current password and choose a new password',
                style: TextStyle(
                  fontSize: 16,
                  color: Colors.grey,
                ),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 30),

              // Current Password Field
              TextFormField(
                controller: _currentPasswordController,
                obscureText: _obscureCurrentPassword,
                decoration: InputDecoration(
                  labelText: 'Current Password',
                  border: const OutlineInputBorder(),
                  suffixIcon: IconButton(
                    icon: Icon(
                      _obscureCurrentPassword
                          ? Icons.visibility
                          : Icons.visibility_off,
                    ),
                    onPressed: () {
                      setState(() {
                        _obscureCurrentPassword = !_obscureCurrentPassword;
                      });
                    },
                  ),
                ),
                validator: (value) {
                  if (value == null || value.isEmpty) {
                    return 'Please enter your current password';
                  }
                  return null;
                },
              ),
              const SizedBox(height: 20),

              // New Password Field
              TextFormField(
                controller: _newPasswordController,
                obscureText: _obscureNewPassword,
                decoration: InputDecoration(
                  labelText: 'New Password',
                  border: const OutlineInputBorder(),
                  suffixIcon: IconButton(
                    icon: Icon(
                      _obscureNewPassword
                          ? Icons.visibility
                          : Icons.visibility_off,
                    ),
                    onPressed: () {
                      setState(() {
                        _obscureNewPassword = !_obscureNewPassword;
                      });
                    },
                  ),
                ),
                validator: (value) {
                  if (value == null || value.isEmpty) {
                    return 'Please enter a new password';
                  }
                  if (value.length < 8) {
                    return 'Password must be at least 8 characters';
                  }
                  return null;
                },
              ),
              const SizedBox(height: 20),

              // Confirm Password Field
              TextFormField(
                controller: _confirmPasswordController,
                obscureText: _obscureConfirmPassword,
                decoration: InputDecoration(
                  labelText: 'Confirm New Password',
                  border: const OutlineInputBorder(),
                  suffixIcon: IconButton(
                    icon: Icon(
                      _obscureConfirmPassword
                          ? Icons.visibility
                          : Icons.visibility_off,
                    ),
                    onPressed: () {
                      setState(() {
                        _obscureConfirmPassword = !_obscureConfirmPassword;
                      });
                    },
                  ),
                ),
                validator: (value) {
                  if (value == null || value.isEmpty) {
                    return 'Please confirm your new password';
                  }
                  if (value != _newPasswordController.text) {
                    return 'Passwords do not match';
                  }
                  return null;
                },
              ),
              const SizedBox(height: 30),

              // Change Password Button
              ElevatedButton(
                onPressed: _isLoading ? null : _changePassword,
                style: ElevatedButton.styleFrom(
                  padding: const EdgeInsets.symmetric(vertical: 16),
                ),
                child: _isLoading
                    ? const CircularProgressIndicator()
                    : const Text('Change Password'),
              ),
            ],
          ),
        ),
      ),
    );
  }

  /// Handle password change
  Future<void> _changePassword() async {
    if (!_formKey.currentState!.validate()) return;

    setState(() => _isLoading = true);

    try {
      final response = await _apiService.changePassword(
        currentPassword: _currentPasswordController.text,
        newPassword: _newPasswordController.text,
      );

      if (response.data['success'] == true) {
        logInfo('Password changed successfully', tag: 'PASSWORD_CHANGE');

        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Password changed successfully'),
            backgroundColor: Colors.green,
            duration: Duration(seconds: 3),
          ),
        );

        Navigator.pop(context, true);
      } else {
        throw Exception('Password change failed');
      }
    } catch (e) {
      logError('Failed to change password: $e', tag: 'PASSWORD_CHANGE');
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Failed to change password. Please try again.'),
          backgroundColor: Colors.red,
          duration: Duration(seconds: 3),
        ),
      );
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }
}
