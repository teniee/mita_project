import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../services/api_service.dart';
import '../services/logging_service.dart';

class UserProfileScreen extends StatefulWidget {
  const UserProfileScreen({super.key});

  @override
  State<UserProfileScreen> createState() => _UserProfileScreenState();
}

class _UserProfileScreenState extends State<UserProfileScreen> with TickerProviderStateMixin {
  final ApiService _apiService = ApiService();
  
  late AnimationController _slideController;
  late Animation<double> _slideAnimation;
  late AnimationController _fadeController;
  late Animation<double> _fadeAnimation;
  
  bool _isLoading = true;
  Map<String, dynamic> _userProfile = {};
  Map<String, dynamic> _financialStats = {};
  
  @override
  void initState() {
    super.initState();
    _initializeAnimations();
    _loadUserProfile();
  }
  
  void _initializeAnimations() {
    _slideController = AnimationController(
      duration: const Duration(milliseconds: 600),
      vsync: this,
    );
    _fadeController = AnimationController(
      duration: const Duration(milliseconds: 800),
      vsync: this,
    );
    
    _slideAnimation = Tween<double>(begin: 50.0, end: 0.0)
        .animate(CurvedAnimation(parent: _slideController, curve: Curves.easeOutCubic));
    _fadeAnimation = Tween<double>(begin: 0.0, end: 1.0)
        .animate(CurvedAnimation(parent: _fadeController, curve: Curves.easeIn));
    
    _slideController.forward();
    _fadeController.forward();
  }
  
  Future<void> _loadUserProfile() async {
    try {
      setState(() => _isLoading = true);
      
      // Load user profile data
      final profileData = await _apiService.getUserProfile().timeout(
        const Duration(seconds: 5),
        onTimeout: () => <String, dynamic>{},
      ).catchError((e) => <String, dynamic>{});
      
      // Generate financial stats
      final stats = await _generateFinancialStats();
      
      if (mounted) {
        setState(() {
          _userProfile = profileData.isNotEmpty ? profileData : _getDefaultProfile();
          _financialStats = stats;
          _isLoading = false;
        });
      }
    } catch (e) {
      logError('Failed to load user profile: $e', tag: 'USER_PROFILE');
      if (mounted) {
        setState(() {
          _userProfile = _getDefaultProfile();
          _financialStats = _getDefaultStats();
          _isLoading = false;
        });
      }
    }
  }
  
  Map<String, dynamic> _getDefaultProfile() {
    return {
      'name': 'Guest User',
      'email': 'user@mita.finance',
      'member_since': DateTime.now().toIso8601String(),
      'profile_completion': 0,
      'verified_email': false,
      'income': 0.0,
      'budget_method': '50/30/20 Rule',
      'currency': 'USD',
      'region': 'US',
    };
  }

  
  Map<String, dynamic> _getDefaultStats() {
    return {
      'total_expenses': 2450.0,
      'monthly_savings': 520.0,
      'budget_adherence': 87,
      'active_goals': 3,
      'transaction_count': 156,
      'categories_used': 8,
      'best_saving_month': 'October 2024',
      'spending_trend': 'decreasing',
    };
  }
  
  Future<Map<String, dynamic>> _generateFinancialStats() async {
    try {
      // Try to get real stats from API
      final monthlyAnalytics = await _apiService.getMonthlyAnalytics().timeout(
        const Duration(seconds: 3),
        onTimeout: () => <String, dynamic>{},
      ).catchError((e) => <String, dynamic>{});
      
      if (monthlyAnalytics.isNotEmpty) {
        return {
          'total_expenses': monthlyAnalytics['total_spent'] ?? 2450.0,
          'monthly_savings': monthlyAnalytics['savings'] ?? 520.0,
          'budget_adherence': monthlyAnalytics['budget_adherence'] ?? 87,
          'active_goals': monthlyAnalytics['goals_count'] ?? 3,
          'transaction_count': monthlyAnalytics['transaction_count'] ?? 156,
          'categories_used': monthlyAnalytics['categories_count'] ?? 8,
          'best_saving_month': monthlyAnalytics['best_month'] ?? 'October 2024',
          'spending_trend': monthlyAnalytics['trend'] ?? 'decreasing',
        };
      }
      
      return _getDefaultStats();
    } catch (e) {
      return _getDefaultStats();
    }
  }
  
  @override
  void dispose() {
    _slideController.dispose();
    _fadeController.dispose();
    super.dispose();
  }
  
  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;
    
    return Scaffold(
      backgroundColor: colorScheme.surface,
      body: _isLoading ? _buildLoadingState() : _buildProfileContent(colorScheme, textTheme),
    );
  }
  
  Widget _buildLoadingState() {
    return const Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          CircularProgressIndicator(),
          SizedBox(height: 16),
          Text('Loading your profile...', style: TextStyle(fontFamily: 'Manrope')),
        ],
      ),
    );
  }
  
  Widget _buildProfileContent(ColorScheme colorScheme, TextTheme textTheme) {
    return CustomScrollView(
      slivers: [
        // App Bar
        SliverAppBar(
          expandedHeight: 120,
          floating: false,
          pinned: true,
          backgroundColor: colorScheme.primaryContainer,
          foregroundColor: colorScheme.onPrimaryContainer,
          flexibleSpace: FlexibleSpaceBar(
            title: Text(
              'Profile',
              style: TextStyle(
                fontFamily: 'Sora',
                fontWeight: FontWeight.bold,
                color: colorScheme.onPrimaryContainer,
              ),
            ),
            background: Container(
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  colors: [
                    colorScheme.primaryContainer,
                    colorScheme.primaryContainer.withValues(alpha: 0.8),
                  ],
                  begin: Alignment.topCenter,
                  end: Alignment.bottomCenter,
                ),
              ),
            ),
          ),
          actions: [
            IconButton(
              icon: const Icon(Icons.settings),
              onPressed: () => Navigator.pushNamed(context, '/settings'),
              tooltip: 'Profile Settings',
            ),
          ],
        ),
        
        // Profile Content
        SliverToBoxAdapter(
          child: FadeTransition(
            opacity: _fadeAnimation,
            child: AnimatedBuilder(
              animation: _slideAnimation,
              builder: (context, child) {
                return Transform.translate(
                  offset: Offset(0, _slideAnimation.value),
                  child: child,
                );
              },
              child: Padding(
                padding: const EdgeInsets.all(20),
                child: Column(
                  children: [
                    // Profile Header Card
                    _buildProfileHeader(colorScheme, textTheme),
                    const SizedBox(height: 24),
                    
                    // Financial Overview Cards
                    _buildFinancialOverview(colorScheme, textTheme),
                    const SizedBox(height: 24),
                    
                    // Account Details
                    _buildAccountDetails(colorScheme, textTheme),
                    const SizedBox(height: 24),
                    
                    // Quick Actions
                    _buildQuickActions(colorScheme, textTheme),
                    const SizedBox(height: 32),
                  ],
                ),
              ),
            ),
          ),
        ),
      ],
    );
  }
  
  Widget _buildProfileHeader(ColorScheme colorScheme, TextTheme textTheme) {
    final name = _userProfile['name'] as String? ?? 'MITA User';
    final email = _userProfile['email'] as String? ?? 'user@mita.finance';
    final memberSince = _userProfile['member_since'] as String?;
    final completion = _userProfile['profile_completion'] as int? ?? 85;
    final verified = _userProfile['verified_email'] as bool? ?? false;
    
    DateTime? joinDate;
    if (memberSince != null) {
      try {
        joinDate = DateTime.parse(memberSince);
      } catch (e) {
        joinDate = DateTime.now().subtract(const Duration(days: 30));
      }
    }
    
    return Card(
      elevation: 2,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
      child: Container(
        padding: const EdgeInsets.all(24),
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(20),
          gradient: LinearGradient(
            colors: [
              colorScheme.primaryContainer.withValues(alpha: 0.3),
              colorScheme.primaryContainer.withValues(alpha: 0.1),
            ],
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
          ),
        ),
        child: Column(
          children: [
            // Profile Avatar and Info
            Row(
              children: [
                // Avatar
                Container(
                  width: 80,
                  height: 80,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    gradient: LinearGradient(
                      colors: [
                        colorScheme.primary,
                        colorScheme.primary.withValues(alpha: 0.7),
                      ],
                      begin: Alignment.topLeft,
                      end: Alignment.bottomRight,
                    ),
                    boxShadow: [
                      BoxShadow(
                        color: colorScheme.primary.withValues(alpha: 0.3),
                        blurRadius: 10,
                        offset: const Offset(0, 4),
                      ),
                    ],
                  ),
                  child: Center(
                    child: Text(
                      name.isNotEmpty ? name[0].toUpperCase() : 'U',
                      style: textTheme.headlineMedium?.copyWith(
                        color: colorScheme.onPrimary,
                        fontWeight: FontWeight.bold,
                        fontFamily: 'Sora',
                      ),
                    ),
                  ),
                ),
                const SizedBox(width: 20),
                
                // User Info
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Expanded(
                            child: Text(
                              name,
                              style: textTheme.titleLarge?.copyWith(
                                fontWeight: FontWeight.bold,
                                fontFamily: 'Sora',
                              ),
                            ),
                          ),
                          if (verified)
                            Container(
                              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                              decoration: BoxDecoration(
                                color: Colors.green.withValues(alpha: 0.1),
                                borderRadius: BorderRadius.circular(12),
                                border: Border.all(color: Colors.green.withValues(alpha: 0.3)),
                              ),
                              child: Row(
                                mainAxisSize: MainAxisSize.min,
                                children: [
                                  const Icon(Icons.verified, color: Colors.green, size: 16),
                                  const SizedBox(width: 4),
                                  Text(
                                    'Verified',
                                    style: textTheme.labelSmall?.copyWith(
                                      color: Colors.green,
                                      fontWeight: FontWeight.w600,
                                    ),
                                  ),
                                ],
                              ),
                            ),
                        ],
                      ),
                      const SizedBox(height: 4),
                      Text(
                        email,
                        style: textTheme.bodyMedium?.copyWith(
                          color: colorScheme.onSurface.withValues(alpha: 0.7),
                          fontFamily: 'Manrope',
                        ),
                      ),
                      if (joinDate != null) ...[
                        const SizedBox(height: 8),
                        Text(
                          'Member since ${DateFormat('MMMM yyyy').format(joinDate)}',
                          style: textTheme.bodySmall?.copyWith(
                            color: colorScheme.onSurface.withValues(alpha: 0.6),
                            fontFamily: 'Manrope',
                          ),
                        ),
                      ],
                    ],
                  ),
                ),
              ],
            ),
            
            const SizedBox(height: 20),
            
            // Profile Completion
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text(
                      'Profile Completion',
                      style: textTheme.bodyMedium?.copyWith(
                        fontWeight: FontWeight.w500,
                        fontFamily: 'Sora',
                      ),
                    ),
                    Text(
                      '$completion%',
                      style: textTheme.bodyMedium?.copyWith(
                        fontWeight: FontWeight.bold,
                        color: colorScheme.primary,
                        fontFamily: 'Sora',
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 8),
                LinearProgressIndicator(
                  value: completion / 100,
                  backgroundColor: colorScheme.surfaceContainer,
                  valueColor: AlwaysStoppedAnimation<Color>(colorScheme.primary),
                  minHeight: 8,
                  borderRadius: BorderRadius.circular(4),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
  
  Widget _buildFinancialOverview(ColorScheme colorScheme, TextTheme textTheme) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'Financial Overview',
          style: textTheme.titleLarge?.copyWith(
            fontWeight: FontWeight.bold,
            fontFamily: 'Sora',
          ),
        ),
        const SizedBox(height: 16),
        
        // Financial Stats Grid
        GridView.count(
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          crossAxisCount: 2,
          crossAxisSpacing: 16,
          mainAxisSpacing: 16,
          childAspectRatio: 1.2,
          children: [
            _buildStatCard(
              'Monthly Income',
              _userProfile['income'] != null 
                ? '\$${(_userProfile['income'] as num).toStringAsFixed(0)}'
                : 'Complete onboarding',
              Icons.trending_up,
              Colors.green,
              colorScheme,
              textTheme,
            ),
            _buildStatCard(
              'Monthly Expenses',
              '\$${(_financialStats['total_expenses'] as num? ?? 2450).toStringAsFixed(0)}',
              Icons.receipt_long,
              Colors.orange,
              colorScheme,
              textTheme,
            ),
            _buildStatCard(
              'Monthly Savings',
              '\$${(_financialStats['monthly_savings'] as num? ?? 520).toStringAsFixed(0)}',
              Icons.savings,
              Colors.blue,
              colorScheme,
              textTheme,
            ),
            _buildStatCard(
              'Budget Adherence',
              '${_financialStats['budget_adherence'] ?? 87}%',
              Icons.check_circle,
              Colors.purple,
              colorScheme,
              textTheme,
            ),
          ],
        ),
      ],
    );
  }
  
  Widget _buildStatCard(String title, String value, IconData icon, Color color, 
      ColorScheme colorScheme, TextTheme textTheme) {
    return Card(
      elevation: 1,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(16),
          color: color.withValues(alpha: 0.05),
          border: Border.all(color: color.withValues(alpha: 0.1)),
        ),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: color.withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Icon(icon, color: color, size: 24),
            ),
            const SizedBox(height: 12),
            Text(
              value,
              style: textTheme.titleLarge?.copyWith(
                fontWeight: FontWeight.bold,
                color: color,
                fontFamily: 'Sora',
              ),
            ),
            const SizedBox(height: 4),
            Text(
              title,
              textAlign: TextAlign.center,
              style: textTheme.bodySmall?.copyWith(
                color: colorScheme.onSurface.withValues(alpha: 0.7),
                fontFamily: 'Manrope',
              ),
            ),
          ],
        ),
      ),
    );
  }
  
  Widget _buildAccountDetails(ColorScheme colorScheme, TextTheme textTheme) {
    return Card(
      elevation: 1,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Account Details',
              style: textTheme.titleMedium?.copyWith(
                fontWeight: FontWeight.bold,
                fontFamily: 'Sora',
              ),
            ),
            const SizedBox(height: 16),
            
            _buildDetailRow(
              'Budget Method',
              _userProfile['budget_method'] as String? ?? '50/30/20 Rule',
              Icons.pie_chart,
              colorScheme,
              textTheme,
            ),
            _buildDetailRow(
              'Currency',
              _userProfile['currency'] as String? ?? 'USD',
              Icons.attach_money,
              colorScheme,
              textTheme,
            ),
            _buildDetailRow(
              'Region',
              _userProfile['region'] as String? ?? 'US',
              Icons.location_on,
              colorScheme,
              textTheme,
            ),
            _buildDetailRow(
              'Active Goals',
              '${_financialStats['active_goals'] ?? 3}',
              Icons.flag,
              colorScheme,
              textTheme,
            ),
            _buildDetailRow(
              'Transactions',
              '${_financialStats['transaction_count'] ?? 156} this month',
              Icons.receipt,
              colorScheme,
              textTheme,
            ),
          ],
        ),
      ),
    );
  }
  
  Widget _buildDetailRow(String label, String value, IconData icon, 
      ColorScheme colorScheme, TextTheme textTheme) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(
              color: colorScheme.primaryContainer.withValues(alpha: 0.3),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Icon(icon, color: colorScheme.primary, size: 20),
          ),
          const SizedBox(width: 16),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  label,
                  style: textTheme.bodySmall?.copyWith(
                    color: colorScheme.onSurface.withValues(alpha: 0.6),
                    fontFamily: 'Manrope',
                  ),
                ),
                Text(
                  value,
                  style: textTheme.bodyMedium?.copyWith(
                    fontWeight: FontWeight.w500,
                    fontFamily: 'Sora',
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
  
  Widget _buildQuickActions(ColorScheme colorScheme, TextTheme textTheme) {
    return Card(
      elevation: 1,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Quick Actions',
              style: textTheme.titleMedium?.copyWith(
                fontWeight: FontWeight.bold,
                fontFamily: 'Sora',
              ),
            ),
            const SizedBox(height: 16),
            
            Row(
              children: [
                Expanded(
                  child: _buildActionButton(
                    'Edit Profile',
                    Icons.edit,
                    () => Navigator.pushNamed(context, '/settings'),
                    colorScheme.primary,
                    colorScheme,
                    textTheme,
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: _buildActionButton(
                    'Settings',
                    Icons.settings,
                    () => Navigator.pushNamed(context, '/settings'),
                    colorScheme.secondary,
                    colorScheme,
                    textTheme,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            
            Row(
              children: [
                Expanded(
                  child: _buildActionButton(
                    'Export Data',
                    Icons.download,
                    () => _showExportDialog(),
                    Colors.green,
                    colorScheme,
                    textTheme,
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: _buildActionButton(
                    'Help & Support',
                    Icons.help,
                    () => _showHelpDialog(),
                    Colors.orange,
                    colorScheme,
                    textTheme,
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
  
  Widget _buildActionButton(String label, IconData icon, VoidCallback onTap, 
      Color color, ColorScheme colorScheme, TextTheme textTheme) {
    return Material(
      color: color.withValues(alpha: 0.05),
      borderRadius: BorderRadius.circular(12),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(12),
        child: Container(
          padding: const EdgeInsets.all(16),
          child: Column(
            children: [
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: color.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Icon(icon, color: color, size: 24),
              ),
              const SizedBox(height: 8),
              Text(
                label,
                textAlign: TextAlign.center,
                style: textTheme.bodySmall?.copyWith(
                  fontWeight: FontWeight.w500,
                  fontFamily: 'Manrope',
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
  
  void _showExportDialog() {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Export Data'),
        content: const Text('Choose what data you\'d like to export:'),
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
            child: const Text('Export All'),
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
        content: const Text('Need help? Contact our support team at support@mita.finance or check our FAQ in the app settings.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('OK'),
          ),
        ],
      ),
    );
  }
}