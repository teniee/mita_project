import 'package:flutter/material.dart';
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
  bool _darkModeEnabled = false;
  bool _notificationsEnabled = true;
  bool _biometricEnabled = false;
  bool _autoSyncEnabled = true;
  bool _offlineModeEnabled = true;
  String _defaultCurrency = 'USD';
  String _language = 'English';
  String _dateFormat = 'MM/dd/yyyy';
  double _budgetAlertThreshold = 80.0;
  
  final List<String> _currencies = ['USD', 'EUR', 'GBP', 'CAD', 'AUD', 'JPY'];
  final List<String> _languages = ['English', 'Spanish', 'French', 'German'];
  final List<String> _dateFormats = ['MM/dd/yyyy', 'dd/MM/yyyy', 'yyyy-MM-dd'];
  
  @override
  void initState() {
    super.initState();
    _loadSettings();
  }
  
  Future<void> _loadSettings() async {
    try {
      setState(() => _isLoading = true);
      
      // Try to load settings from API
      final settings = await _apiService.getUserProfile().timeout(
        const Duration(seconds: 3),
        onTimeout: () => <String, dynamic>{},
      ).catchError((e) => <String, dynamic>{});
      
      if (mounted && settings.isNotEmpty) {
        setState(() {
          _darkModeEnabled = settings['dark_mode'] ?? false;
          _notificationsEnabled = settings['notifications'] ?? true;
          _biometricEnabled = settings['biometric_auth'] ?? false;
          _autoSyncEnabled = settings['auto_sync'] ?? true;
          _offlineModeEnabled = settings['offline_mode'] ?? true;
          _defaultCurrency = settings['currency'] ?? 'USD';
          _language = settings['language'] ?? 'English';
          _dateFormat = settings['date_format'] ?? 'MM/dd/yyyy';
          _budgetAlertThreshold = (settings['budget_alert_threshold'] as num?)?.toDouble() ?? 80.0;
          _isLoading = false;
        });
      } else {
        setState(() => _isLoading = false);
      }
    } catch (e) {
      logError('Failed to load settings: $e', tag: 'USER_SETTINGS');
      setState(() => _isLoading = false);
    }
  }
  
  Future<void> _saveSettings() async {
    try {
      final settings = {
        'dark_mode': _darkModeEnabled,
        'notifications': _notificationsEnabled,
        'biometric_auth': _biometricEnabled,
        'auto_sync': _autoSyncEnabled,
        'offline_mode': _offlineModeEnabled,
        'currency': _defaultCurrency,
        'language': _language,
        'date_format': _dateFormat,
        'budget_alert_threshold': _budgetAlertThreshold,
      };
      
      await _apiService.updateUserProfile(settings).timeout(
        const Duration(seconds: 5),
        onTimeout: () => throw Exception('Settings save timeout'),
      );
      
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
    
    return Scaffold(
      backgroundColor: colorScheme.surface,
      appBar: AppBar(
        title: const Text(
          'Settings',
          style: const TextStyle(
            fontFamily: 'Sora',
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
              style: const TextStyle(
                fontWeight: FontWeight.w600,
                color: colorScheme.primary,
              ),
            ),
          ),
        ],
      ),
      body: _isLoading ? _buildLoadingState() : _buildSettingsContent(colorScheme, textTheme),
    );
  }
  
  Widget _buildLoadingState() {
    return const Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          CircularProgressIndicator(),
          SizedBox(height: 16),
          Text('Loading settings...', style: const TextStyle(fontFamily: 'Manrope')),
        ],
      ),
    );
  }
  
  Widget _buildSettingsContent(ColorScheme colorScheme, TextTheme textTheme) {
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
                _darkModeEnabled,
                (value) => setState(() => _darkModeEnabled = value),
              ),
              _buildDropdownTile(
                'Language',
                'Select your preferred language',
                Icons.language,
                _language,
                _languages,
                (value) => setState(() => _language = value!),
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
                _notificationsEnabled,
                (value) => setState(() => _notificationsEnabled = value),
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
          
          // Security Settings
          _buildSectionCard(
            'Security & Privacy',
            Icons.security,
            [
              _buildSwitchTile(
                'Biometric Authentication',
                'Use fingerprint or face unlock',
                Icons.fingerprint,
                _biometricEnabled,
                (value) => setState(() => _biometricEnabled = value),
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
                _defaultCurrency,
                _currencies,
                (value) => setState(() => _defaultCurrency = value!),
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
                    fontFamily: 'Sora',
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
        style: const const TextStyle(fontWeight: FontWeight.w500, fontFamily: 'Sora'),
      ),
      subtitle: Text(
        subtitle,
        style: const const TextStyle(fontFamily: 'Manrope'),
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
        style: const const TextStyle(fontWeight: FontWeight.w500, fontFamily: 'Sora'),
      ),
      subtitle: Text(
        subtitle,
        style: const const TextStyle(fontFamily: 'Manrope'),
      ),
      trailing: DropdownButton<String>(
        value: value,
        onChanged: onChanged,
        items: options.map((option) => DropdownMenuItem(
          value: option,
          child: Text(option),
        )).toList(),
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
            style: const const TextStyle(fontWeight: FontWeight.w500, fontFamily: 'Sora'),
          ),
          subtitle: Text(
            subtitle,
            style: const const TextStyle(fontFamily: 'Manrope'),
          ),
          trailing: Text(
            '${value.toInt()}%',
            style: const const TextStyle(fontWeight: FontWeight.bold),
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
        style: const const TextStyle(fontWeight: FontWeight.w500, fontFamily: 'Sora'),
      ),
      subtitle: Text(
        subtitle,
        style: const const TextStyle(fontFamily: 'Manrope'),
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
        style: const const TextStyle(fontWeight: FontWeight.w500, fontFamily: 'Sora'),
      ),
      trailing: Text(
        value,
        style: const TextStyle(
          color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.6),
          fontFamily: 'Manrope',
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
                    fontFamily: 'Sora',
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
        content: const Text('This feature will redirect you to account settings.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () {
              Navigator.pop(context);
              // TODO: Implement password change
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
        content: const Text('Your financial data will be exported as a CSV file.'),
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
        content: const Text('Contact our support team at support@mita.finance or visit our help center.'),
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
        content: const Text('This will open the privacy policy in your browser.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () {
              Navigator.pop(context);
              // TODO: Open privacy policy URL
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
        content: const Text('This will open the terms of service in your browser.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () {
              Navigator.pop(context);
              // TODO: Open terms URL
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
        content: const Text('Are you sure you want to permanently delete your account? This action cannot be undone.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () {
              Navigator.pop(context);
              // TODO: Implement account deletion
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
      builder: (context) => AlertDialog(
        title: const Text('Sign Out'),
        content: const Text('Are you sure you want to sign out?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () async {
              Navigator.pop(context);
              await _apiService.logout();
              // TODO: Navigate to login screen
            },
            child: const Text('Sign Out'),
          ),
        ],
      ),
    );
  }
}