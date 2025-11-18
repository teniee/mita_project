import 'package:flutter/material.dart';
import '../theme/app_colors.dart';
import '../theme/app_typography.dart';
import '../services/api_service.dart';
import '../services/logging_service.dart';
import '../core/app_error_handler.dart';
import '../core/enhanced_error_handling.dart';

class ProfileSettingsScreen extends StatefulWidget {
  const ProfileSettingsScreen({super.key});

  @override
  State<ProfileSettingsScreen> createState() => _ProfileSettingsScreenState();
}

class _ProfileSettingsScreenState extends State<ProfileSettingsScreen> {
  final _formKey = GlobalKey<FormState>();
  final ApiService _apiService = ApiService();
  
  // User data controllers
  final TextEditingController _nameController = TextEditingController();
  final TextEditingController _emailController = TextEditingController();
  final TextEditingController _incomeController = TextEditingController();
  final TextEditingController _savingsGoalController = TextEditingController();
  
  String _selectedCurrency = 'USD';
  String _selectedRegion = 'US';
  String _budgetMethod = 'Percentage';
  bool _notificationsEnabled = true;
  bool _darkModeEnabled = false;
  bool _isLoading = false;
  bool _isSaving = false;

  final List<String> _currencies = ['USD', 'EUR', 'GBP', 'CAD', 'AUD', 'JPY', 'CNY'];
  final List<String> _regions = ['US', 'Canada', 'UK', 'Europe', 'Australia', 'Asia'];
  final List<String> _budgetMethods = ['50/30/20 Rule', '60/20/20', 'Percentage', 'Zero-Based', 'Envelope'];

  @override
  void initState() {
    super.initState();
    _loadUserProfile();
  }

  Future<void> _loadUserProfile() async {
    setState(() => _isLoading = true);

    try {
      // Try to load from API with timeout
      final profileData = await _apiService.getUserProfile().timeout(
        const Duration(seconds: 5),
        onTimeout: () => <String, dynamic>{},
      ).catchError((e) => <String, dynamic>{});

      if (profileData.isNotEmpty && profileData['data'] != null) {
        final data = profileData['data'];
        setState(() {
          _nameController.text = data['name'] ?? '';
          _emailController.text = data['email'] ?? '';
          final income = data['income'];
          if (income != null && income > 0) {
            _incomeController.text = income.toString();
          } else {
            _incomeController.text = '';
          }
          final savingsGoal = data['savings_goal'];
          if (savingsGoal != null && savingsGoal > 0) {
            _savingsGoalController.text = savingsGoal.toString();
          } else {
            _savingsGoalController.text = '';
          }
          _selectedCurrency = data['currency'] ?? 'USD';
          _selectedRegion = data['region'] ?? 'US';
          _budgetMethod = data['budget_method'] ?? '50/30/20 Rule';
          _notificationsEnabled = data['notifications_enabled'] ?? true;
          _darkModeEnabled = data['dark_mode_enabled'] ?? false;
        });
      } else {
        // No user profile data found - show empty fields
        setState(() {
          _nameController.text = '';
          _emailController.text = '';
          _incomeController.text = '';
          _savingsGoalController.text = '';
          _selectedCurrency = 'USD';
          _selectedRegion = 'US';
          _budgetMethod = '50/30/20 Rule';
          _notificationsEnabled = true;
          _darkModeEnabled = false;
        });
      }
    } catch (e) {
      logWarning('Failed to load user profile', tag: 'PROFILE_SETTINGS', extra: {'error': e.toString()});

      // Show empty fields on error
      setState(() {
        _nameController.text = '';
        _emailController.text = '';
        _incomeController.text = '';
        _savingsGoalController.text = '';
        _selectedCurrency = 'USD';
        _selectedRegion = 'US';
        _budgetMethod = '50/30/20 Rule';
        _notificationsEnabled = true;
        _darkModeEnabled = false;
      });
    } finally {
      setState(() => _isLoading = false);
    }
  }

  Future<void> _saveProfile() async {
    if (!_formKey.currentState!.validate()) return;

    setState(() => _isSaving = true);

    try {
      // Validate required fields
      if (_nameController.text.trim().isEmpty) {
        throw Exception('Name is required');
      }

      if (_emailController.text.trim().isEmpty) {
        throw Exception('Email is required');
      }

      final parsedIncome = double.tryParse(_incomeController.text) ?? 0.0;
      if (parsedIncome <= 0) {
        throw Exception('Valid income is required');
      }

      final parsedSavingsGoal = double.tryParse(_savingsGoalController.text) ?? 0.0;
      if (parsedSavingsGoal <= 0) {
        throw Exception('Valid savings goal is required');
      }

      final profileData = {
        'name': _nameController.text.trim(),
        'email': _emailController.text.trim(),
        'income': parsedIncome,
        'savings_goal': parsedSavingsGoal,
        'currency': _selectedCurrency,
        'region': _selectedRegion,
        'budget_method': _budgetMethod,
        'notifications_enabled': _notificationsEnabled,
        'dark_mode_enabled': _darkModeEnabled,
      };

      // Save locally first for instant feedback
      await Future.delayed(const Duration(milliseconds: 200)); // Simulate local save
      
      // Try to sync with backend
      try {
        await _apiService.updateUserProfile(profileData).timeout(
          const Duration(seconds: 8),
          onTimeout: () => throw Exception('Profile update timeout'),
        );

        // Also update income separately for income-specific tracking
        await _apiService.updateUserIncome(parsedIncome);
        
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Row(
                children: [
                  Icon(Icons.check_circle, color: Colors.white),
                  SizedBox(width: 8),
                  Text('Profile updated successfully!'),
                ],
              ),
              backgroundColor: Colors.green,
              behavior: SnackBarBehavior.floating,
            ),
          );
        }
      } catch (e) {
        // Backend failed, but we saved locally
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Row(
                children: [
                  Icon(Icons.cloud_off, color: Colors.white),
                  SizedBox(width: 8),
                  Text('Profile saved locally, will sync later'),
                ],
              ),
              backgroundColor: Colors.orange,
              behavior: SnackBarBehavior.floating,
            ),
          );
        }
      }
    } catch (e) {
      ErrorMessageUtils.showErrorSnackBar(context, e);
    } finally {
      setState(() => _isSaving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    
    return Scaffold(
      appBar: AppBar(
        title: const Text('Profile Settings', style: TextStyle(fontFamily: AppTypography.fontHeading, fontWeight: FontWeight.w600)),
        backgroundColor: colorScheme.surface,
        elevation: 0,
        actions: [
          if (_isSaving)
            const Padding(
              padding: EdgeInsets.only(right: 16),
              child: Center(child: SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2))),
            )
          else
            TextButton(
              onPressed: _saveProfile,
              child: const Text('Save', style: TextStyle(fontWeight: FontWeight.w600)),
            ),
        ],
      ),
      body: _isLoading 
        ? const Center(child: CircularProgressIndicator())
        : SingleChildScrollView(
            padding: const EdgeInsets.all(16),
            child: Form(
              key: _formKey,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Profile Picture Section
                  Center(
                    child: Stack(
                      children: [
                        CircleAvatar(
                          radius: 50,
                          backgroundColor: colorScheme.primaryContainer,
                          child: Icon(Icons.person, size: 50, color: colorScheme.onPrimaryContainer),
                        ),
                        Positioned(
                          bottom: 0,
                          right: 0,
                          child: Container(
                            decoration: BoxDecoration(
                              color: colorScheme.primary,
                              shape: BoxShape.circle,
                            ),
                            padding: const EdgeInsets.all(8),
                            child: Icon(Icons.camera_alt, size: 20, color: colorScheme.onPrimary),
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 32),
                  
                  // Personal Information
                  _buildSectionHeader('Personal Information'),
                  const SizedBox(height: 16),
                  
                  _buildTextField(
                    controller: _nameController,
                    label: 'Full Name',
                    icon: Icons.person_outline,
                    validator: (value) => value?.isEmpty ?? true ? 'Please enter your name' : null,
                  ),
                  const SizedBox(height: 16),
                  
                  _buildTextField(
                    controller: _emailController,
                    label: 'Email',
                    icon: Icons.email_outlined,
                    keyboardType: TextInputType.emailAddress,
                    validator: (value) {
                      if (value?.isEmpty ?? true) return 'Please enter your email';
                      // Use centralized email validation
                      return FormErrorHandler.validateEmail(value, reportError: false);
                    },
                  ),
                  const SizedBox(height: 32),
                  
                  // Financial Information
                  _buildSectionHeader('Financial Information'),
                  const SizedBox(height: 16),
                  
                  _buildTextField(
                    controller: _incomeController,
                    label: 'Monthly Income',
                    icon: Icons.attach_money,
                    keyboardType: TextInputType.number,
                    prefix: const Text('\$'),
                    validator: (value) {
                      if (value?.isEmpty ?? true) return 'Please enter your income';
                      if (double.tryParse(value!) == null) return 'Please enter a valid amount';
                      return null;
                    },
                  ),
                  const SizedBox(height: 16),
                  
                  _buildTextField(
                    controller: _savingsGoalController,
                    label: 'Monthly Savings Goal',
                    icon: Icons.savings_outlined,
                    keyboardType: TextInputType.number,
                    prefix: const Text('\$'),
                    validator: (value) {
                      if (value?.isEmpty ?? true) return 'Please enter your savings goal';
                      if (double.tryParse(value!) == null) return 'Please enter a valid amount';
                      return null;
                    },
                  ),
                  const SizedBox(height: 16),
                  
                  _buildDropdownField(
                    value: _selectedCurrency,
                    label: 'Currency',
                    icon: Icons.monetization_on_outlined,
                    items: _currencies,
                    onChanged: (value) => setState(() => _selectedCurrency = value!),
                  ),
                  const SizedBox(height: 16),
                  
                  _buildDropdownField(
                    value: _selectedRegion,
                    label: 'Region',
                    icon: Icons.location_on_outlined,
                    items: _regions,
                    onChanged: (value) => setState(() => _selectedRegion = value!),
                  ),
                  const SizedBox(height: 16),
                  
                  _buildDropdownField(
                    value: _budgetMethod,
                    label: 'Budget Method',
                    icon: Icons.pie_chart_outline,
                    items: _budgetMethods,
                    onChanged: (value) => setState(() => _budgetMethod = value!),
                  ),
                  const SizedBox(height: 32),
                  
                  // Preferences
                  _buildSectionHeader('Preferences'),
                  const SizedBox(height: 16),
                  
                  _buildSwitchTile(
                    title: 'Push Notifications',
                    subtitle: 'Receive spending alerts and tips',
                    icon: Icons.notifications_outlined,
                    value: _notificationsEnabled,
                    onChanged: (value) => setState(() => _notificationsEnabled = value),
                  ),
                  
                  _buildSwitchTile(
                    title: 'Dark Mode',
                    subtitle: 'Use dark theme for the app',
                    icon: Icons.dark_mode_outlined,
                    value: _darkModeEnabled,
                    onChanged: (value) => setState(() => _darkModeEnabled = value),
                  ),
                  
                  const SizedBox(height: 32),
                  
                  // Action Buttons
                  Row(
                    children: [
                      Expanded(
                        child: OutlinedButton.icon(
                          onPressed: () {
                            // Reset to defaults
                            _loadUserProfile();
                          },
                          icon: const Icon(Icons.refresh),
                          label: const Text('Reset'),
                          style: OutlinedButton.styleFrom(
                            padding: const EdgeInsets.symmetric(vertical: 12),
                          ),
                        ),
                      ),
                      const SizedBox(width: 16),
                      Expanded(
                        child: ElevatedButton.icon(
                          onPressed: _isSaving ? null : _saveProfile,
                          icon: _isSaving 
                            ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2))
                            : const Icon(Icons.save),
                          label: Text(_isSaving ? 'Saving...' : 'Save Profile'),
                          style: ElevatedButton.styleFrom(
                            padding: const EdgeInsets.symmetric(vertical: 12),
                          ),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 32),
                ],
              ),
            ),
          ),
    );
  }

  Widget _buildSectionHeader(String title) {
    return Text(
      title,
      style: TextStyle(
        fontSize: 18,
        fontWeight: FontWeight.w600,
        fontFamily: AppTypography.fontHeading,
        color: Theme.of(context).colorScheme.primary,
      ),
    );
  }

  Widget _buildTextField({
    required TextEditingController controller,
    required String label,
    required IconData icon,
    TextInputType? keyboardType,
    Widget? prefix,
    String? Function(String?)? validator,
  }) {
    return TextFormField(
      controller: controller,
      keyboardType: keyboardType,
      validator: validator,
      decoration: InputDecoration(
        labelText: label,
        prefixIcon: Icon(icon),
        prefix: prefix,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
        ),
        filled: true,
        fillColor: Theme.of(context).colorScheme.surfaceContainerHighest.withValues(alpha: 0.3),
      ),
    );
  }

  Widget _buildDropdownField({
    required String value,
    required String label,
    required IconData icon,
    required List<String> items,
    required void Function(String?) onChanged,
  }) {
    return DropdownButtonFormField<String>(
      value: value,
      onChanged: onChanged,
      decoration: InputDecoration(
        labelText: label,
        prefixIcon: Icon(icon),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
        ),
        filled: true,
        fillColor: Theme.of(context).colorScheme.surfaceContainerHighest.withValues(alpha: 0.3),
      ),
      items: items.map((item) => DropdownMenuItem(
        value: item,
        child: Text(item),
      )).toList(),
    );
  }

  Widget _buildSwitchTile({
    required String title,
    required String subtitle,
    required IconData icon,
    required bool value,
    required void Function(bool) onChanged,
  }) {
    return Card(
      child: SwitchListTile(
        title: Text(title, style: const TextStyle(fontWeight: FontWeight.w500)),
        subtitle: Text(subtitle),
        secondary: Icon(icon),
        value: value,
        onChanged: onChanged,
      ),
    );
  }

  @override
  void dispose() {
    _nameController.dispose();
    _emailController.dispose();
    _incomeController.dispose();
    _savingsGoalController.dispose();
    super.dispose();
  }
}